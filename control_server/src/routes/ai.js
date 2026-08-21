'use strict'

/**
 * `/v1/ai` — cổng duy nhất app gọi để dùng mô hình.
 *
 * Trật tự bất biến của mọi route ở đây:
 *   1. Idempotency: `jobId` đã xử lý rồi → trả kết quả cũ, KHÔNG tính phí lại
 *   2. Kiểm tra trần cứng (số câu, độ dài câu) — app không đổi được
 *   3. Kiểm tra số dư
 *   4. Gọi mô hình
 *   5. Trừ credit (chỉ khi mô hình trả về thành công)
 *   6. Lưu kết quả theo jobId + ghi UsageLog
 *
 * Trừ credit SAU khi gọi mô hình: mô hình lỗi thì người dùng không mất gì.
 * Rủi ro ngược lại (gọi xong, chưa kịp trừ thì server chết) được UsageLog ghi
 * lại để đối chiếu, và nó hiếm hơn nhiều so với việc mô hình lỗi.
 *
 * `holdId` (tùy chọn, luồng wizard): thay vì trừ ví từng lượt, usage tích lũy
 * vào CreditHold — ví đã bị trừ trước bằng số ước tính lúc tạo hold, chốt
 * sổ lúc người dùng bấm Xuất video. Không có holdId thì mọi thứ như cũ.
 *
 * Response KHÔNG BAO GIỜ chứa tên provider, model, token hay chi phí.
 */
const JobResult = require('../models/JobResult')
const UsageLog = require('../models/UsageLog')
const credit = require('../services/credit.service')
const holds = require('../services/hold.service')
const config = require('../services/config.service')
const gateway = require('../services/ai-gateway.service')
const prompts = require('../prompts/translate')
const assistPrompts = require('../prompts/assist')
const scenePrompts = require('../prompts/product_scene')
const imageStage = require('../services/image-stage.service')
const { containsCjk } = require('../utils/json-repair')

/** Kết quả đã lưu của jobId này, hoặc null. */
/**
 * Số lượt trợ lý máy này đã dùng HÔM NAY (mini-spec V89).
 *
 * Server mới chỉ có giới hạn theo PHÚT (fastify rateLimit) — thứ chặn được
 * bấm dồn dập nhưng không chặn được một vòng lặp hỏng chạy cả ngày, hay một
 * máy gọi đều đặn suốt 24 tiếng. Đếm theo ngày là lớp chặn còn thiếu.
 */
async function assistUsedToday(fingerprint, task) {
  const dau_ngay = new Date()
  dau_ngay.setHours(0, 0, 0, 0)
  // Lượt "Thử ngay" của trang quản trị KHÔNG tính: nó là phép kiểm cấu hình
  // của người quản trị, không phải người dùng đang tiêu hạn mức của mình.
  const dieu_kien = {
    fingerprint,
    action: 'assist',
    runMode: { $ne: 'test_now' },
    createdAt: { $gte: dau_ngay },
  }
  if (task) dieu_kien.assistTask = task
  return UsageLog.countDocuments(dieu_kien)
}

async function replay(jobId, fingerprint) {
  if (!jobId) return null
  const doc = await JobResult.findOne({ jobId, fingerprint }).lean()
  return doc ? doc.result : null
}

async function remember(jobId, fingerprint, action, result, creditCharged) {
  if (!jobId) return
  try {
    await JobResult.create({ jobId, fingerprint, action, result, creditCharged })
  } catch (err) {
    if (err.code !== 11000) throw err   // trùng jobId = đã lưu rồi, không sao
  }
}

/**
 * Kiểm tra khả năng chi trả TRƯỚC khi gọi mô hình.
 *
 * Hold hấp thụ được lượt này (active, hoặc committed + gói đăng bài cho
 * generate_post — xem `holds.canAbsorb`): đã trả tiền trọn lượt lúc tạo hold,
 * không kiểm tra gì nữa. Không có hold: so với số dư ví (đường dự phòng,
 * xem `walletCost`).
 * Trả về null nếu đủ, ngược lại {balance, required} để route trả 402.
 */
async function precheck(fingerprint, holdId, cost, { action = '', jobId = '' } = {}) {
  if (holdId) {
    const hold = await holds.getHold(fingerprint, holdId)
    if (holds.canAbsorb(hold, action, jobId)) return null
  }
  if (cost <= 0) return null
  const balance = await credit.getBalance(fingerprint)
  if (balance >= cost) return null
  return { balance, required: cost }
}

/**
 * Kết thúc một lượt AI thành công.
 *
 * Hold hấp thụ được (active — hoặc committed + gói đăng bài cho đúng một
 * lượt generate_post): KHÔNG trừ ví. Tiền của cả lượt đã thu lúc tạo hold
 * theo số segment, nên ở đây chỉ ghi `internalVox` vào `hold.usage` để đối
 * soát biên lợi nhuận. `charged: 0` là đúng — app hiện tổng một lần ở bước
 * xuất video, không hiện từng lượt.
 *
 * Hold không hấp thụ được (đã tự chốt sau TTL, hoặc lượt vượt phạm vi):
 * rơi về trừ ví thẳng theo `walletCost` — đường dự phòng cho các lượt lẻ
 * ngoài luồng wizard.
 * Trả về { charged, balanceAfter }.
 */
async function charge(device, { holdId, jobId, action, walletCost, internalVox,
  sentences, description, ip }) {
  if (holdId) {
    const res = await holds.accrue({
      holdId,
      fingerprint: device.fingerprint,
      jobId,
      action,
      vox: internalVox,
      sentences,
    })
    if (res) {
      return { charged: 0, balanceAfter: await credit.getBalance(device.fingerprint) }
    }
    // Hold không hấp thụ được lượt này — rơi về đường cũ.
  }
  const amount = walletCost
  if (amount <= 0) {
    return { charged: 0, balanceAfter: await credit.getBalance(device.fingerprint) }
  }
  const prefix = { translate: 'translate', analyze: 'analyze', review: 'review',
    generate_post: 'post' }[action] || action
  try {
    const deducted = await credit.deduct(device.fingerprint, amount, {
      type: 'usage',
      idempotencyKey: `${prefix}-${jobId}`,
      description,
      metadata: { jobId, action, sentences, ip },
    })
    return { charged: amount, balanceAfter: deducted.balanceAfter }
  } catch (err) {
    if (!(err instanceof credit.InsufficientCreditError)) throw err
    // Precheck đã qua nhưng một request song song rút cạn ví trước khi trừ.
    // Mô hình ĐÃ chạy — phí AI phía server đã tiêu. Ném lỗi ở đây nghĩa là
    // route trả 5xx, jobId chưa được remember, app retry → server trả phí AI
    // lần thứ hai cho cùng một việc. Thay vào đó thu trần số dư còn lại và
    // trả kết quả — server không bao giờ chịu lỗ, ví không bao giờ âm.
    const clamp = Math.max(0, err.balance)
    if (clamp === 0) {
      return { charged: 0, balanceAfter: 0 }
    }
    try {
      const deducted = await credit.deduct(device.fingerprint, clamp, {
        type: 'usage',
        idempotencyKey: `${prefix}-${jobId}`,
        description: `${description} (thu được ${clamp}/${amount} Vox)`,
        metadata: { jobId, action, sentences, ip, clamped: true, intended: amount },
      })
      return { charged: clamp, balanceAfter: deducted.balanceAfter }
    } catch (err2) {
      // Ví lại bị rút tiếp giữa hai nhịp — thôi, coi như thu được 0. Kết quả
      // vẫn phải trả về: phí AI đã tiêu, giữ kết quả lại không cứu được gì.
      if (err2 instanceof credit.InsufficientCreditError) {
        return { charged: 0, balanceAfter: Math.max(0, err2.balance) }
      }
      throw err2
    }
  }
}

module.exports = async function aiRoutes(fastify) {
  const { requireDevice } = require('../middleware/auth.middleware')

  fastify.addHook('preHandler', requireDevice)

  // Chặn mọi request AI khi đang bảo trì — chạy dở nửa chừng lúc bảo trì tệ
  // hơn là báo rõ ngay từ đầu.
  fastify.addHook('preHandler', async (request, reply) => {
    if (await config.get('maintenance.mode')) {
      return reply.code(503).send({
        code: 'MAINTENANCE',
        message: (await config.get('maintenance.message'))
          || 'Hệ thống đang bảo trì. Vui lòng thử lại sau ít phút.',
      })
    }
  })

  // ------------------------------------------------------------ dịch lô ---
  fastify.post('/translate', {
    config: { rateLimit: { max: 40, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['jobId', 'segments'],
        properties: {
          jobId: { type: 'string', minLength: 8, maxLength: 100 },
          holdId: { type: 'string', minLength: 8, maxLength: 100 },
          sourceLang: { type: 'string', maxLength: 16, default: 'zh-CN' },
          // Mini-spec V15 (docs/PLAN.md) — bug thật đã sửa: trước đây
          // KHÔNG có field này, server luôn dịch sang tiếng Việt bất kể
          // client đang lồng tiếng ngôn ngữ nào (xem docs/TEST_LOG.md).
          // Mặc định "vi" — 0 regression cho client cũ không gửi field này.
          targetLang: { type: 'string', pattern: '^[a-z]{2,3}$', default: 'vi' },
          cpsBudget: { type: 'number', minimum: 4, maximum: 40, default: 12.5 },
          // Mini-spec V28 (docs/PLAN.md, Phase G) — bật thì LLM gắn thêm
          // `tone` mỗi câu (dùng chọn style VieNeu per-segment). Mặc định
          // false — 0 regression cho client cũ không gửi field này.
          emotionTone: { type: 'boolean', default: false },
          segments: {
            type: 'array',
            minItems: 1,
            items: {
              type: 'object',
              required: ['id', 'text'],
              properties: {
                id: { type: 'integer' },
                text: { type: 'string' },
                duration: { type: 'number' },
                max_chars: { type: 'integer' },
              },
            },
          },
          prevContext: {
            type: 'array',
            maxItems: 5,
            items: { type: 'object', additionalProperties: true },
          },
          context: {
            type: 'object',
            properties: {
              videoTitle: { type: 'string' },
              domain: { type: 'string' },
              context: { type: 'string' },
              pronouns: { type: 'string' },
              glossary: { type: 'string' },
              styleNotes: { type: 'string' },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    const { jobId, holdId, segments, sourceLang = 'zh-CN', targetLang = 'vi',
      cpsBudget = 12.5, emotionTone = false } = request.body

    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    const cfg = await config.getMany([
      'ai.max.segments.per.request', 'ai.max.chars.per.segment',
      'ai.max.retries', 'credit.enabled',
      'credit.cost.segment.base', 'credit.cost.segment.autotranslate',
      'internal.cost.translate.per_sentence',
    ])
    if (segments.length > cfg['ai.max.segments.per.request']) {
      return reply.code(400).send({
        code: 'BATCH_TOO_LARGE',
        message: `Tối đa ${cfg['ai.max.segments.per.request']} câu mỗi lượt.`,
        maxSegments: cfg['ai.max.segments.per.request'],
      })
    }
    const maxChars = cfg['ai.max.chars.per.segment']
    const tooLong = segments.find((s) => String(s.text || '').length > maxChars)
    if (tooLong) {
      return reply.code(400).send({
        code: 'SEGMENT_TOO_LONG',
        message: `Câu ${tooLong.id} dài quá ${maxChars} ký tự.`,
      })
    }

    // Không có hold thì thu thẳng đơn giá segment của lượt dịch tự động —
    // gọi được /translate nghĩa là đang dùng server để dịch, giá phải bằng
    // đúng giá trong hold, không có đường tắt nào rẻ hơn.
    const perSegment = cfg['credit.cost.segment.base']
      + cfg['credit.cost.segment.autotranslate']
    const cost = cfg['credit.enabled'] ? segments.length * perSegment : 0
    if (cfg['credit.enabled']) {
      const short = await precheck(device.fingerprint, holdId, cost,
        { action: 'translate', jobId })
      if (short) {
        return reply.code(402).send({
          code: 'INSUFFICIENT_CREDIT',
          message: `Không đủ Vox. Cần ${short.required}, bạn có ${short.balance}.`,
          balance: short.balance,
          required: short.required,
        })
      }
    }

    const log = await UsageLog.create({
      fingerprint: device.fingerprint,
      jobId,
      action: 'translate',
      inputSize: segments.length,
      ip: request.ip,
      appVersion: device.appVersion,
    })
    const started = Date.now()

    let result
    try {
      const context = prompts.sanitizeContext(request.body.context || {})
      result = await gateway.translateBatch({
        segments,
        sourceLang,
        targetKey: targetLang,
        context,
        cpsBudget,
        prevContext: request.body.prevContext || [],
        maxRetries: cfg['ai.max.retries'],
        emotionTone,
      })
      // Lưới cuối: câu nào còn chữ Hán thì dịch lại ngay, app không phải
      // biết chuyện này tồn tại.
      const fix = await gateway.fixCjkLeftovers({
        merged: result.segments, sourceLang, targetKey: targetLang,
        context, cpsBudget,
      })
      result.segments = fix.segments
      result.usage.promptTokens += fix.usage.promptTokens
      result.usage.completionTokens += fix.usage.completionTokens
    } catch (err) {
      await UsageLog.updateOne({ _id: log._id }, {
        $set: {
          status: 'error',
          errorCode: err.code || 'AI_ERROR',
          errorMessage: String(err.message).slice(0, 500),
          durationMs: Date.now() - started,
        },
      })
      request.log.error({ err, jobId }, 'translate failed')
      return reply.code(err.statusCode || 503).send({
        code: err.code || 'AI_UNAVAILABLE',
        message: 'Dịch vụ dịch tạm thời không phản hồi. Thử lại sau ít phút.',
        retryAfter: 30,
      })
    }

    // Chỉ tính phí những câu thực sự dịch được.
    const done = result.segments.length
    const paid = await charge(device, {
      holdId,
      jobId,
      action: 'translate',
      walletCost: cfg['credit.enabled'] ? done * perSegment : 0,
      internalVox: done * cfg['internal.cost.translate.per_sentence'],
      sentences: done,
      description: `Dịch ${done} segment`,
      ip: request.ip,
    })

    const response = {
      jobId,
      segments: result.segments,
      creditCharged: paid.charged,
      balanceAfter: paid.balanceAfter,
    }
    await Promise.all([
      remember(jobId, device.fingerprint, 'translate', response, paid.charged),
      UsageLog.updateOne({ _id: log._id }, {
        $set: {
          status: 'success',
          creditCharged: paid.charged,
          aiProvider: result.provider,
          aiModel: result.model,
          promptTokens: result.usage.promptTokens,
          completionTokens: result.usage.completionTokens,
          durationMs: Date.now() - started,
        },
      }),
    ])
    return response
  })

  // ----------------------------------------------- phân tích ngữ cảnh ----
  fastify.post('/analyze', {
    config: { rateLimit: { max: 20, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['jobId', 'lines'],
        properties: {
          jobId: { type: 'string', minLength: 8, maxLength: 100 },
          holdId: { type: 'string', minLength: 8, maxLength: 100 },
          sourceLang: { type: 'string', maxLength: 16, default: 'zh-CN' },
          targetLang: { type: 'string', pattern: '^[a-z]{2,3}$', default: 'vi' },
          videoTitle: { type: 'string', maxLength: 300 },
          // App đã lấy mẫu đầu–giữa–cuối trước khi gửi; đây là trần cứng.
          lines: { type: 'array', maxItems: 400, items: { type: 'string', maxLength: 800 } },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    const { jobId, lines, sourceLang = 'zh-CN', targetLang = 'vi',
      videoTitle = '', holdId } = request.body

    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    const cfg = await config.getMany(['credit.enabled', 'internal.cost.analyze'])
    const cost = cfg['credit.enabled'] ? cfg['internal.cost.analyze'] : 0
    const lacking = await precheck(device.fingerprint, holdId, cost,
      { action: 'analyze', jobId })
    if (lacking) {
      return reply.code(402).send({
        code: 'INSUFFICIENT_CREDIT',
        message: `Không đủ Vox. Cần ${lacking.required}, bạn có ${lacking.balance}.`,
        balance: lacking.balance,
        required: lacking.required,
      })
    }

    const started = Date.now()
    let result
    try {
      result = await gateway.analyze({
        lines: lines.join('\n'),
        sourceLang,
        targetKey: targetLang,
        videoTitle: String(videoTitle).slice(0, 300),
      })
    } catch (err) {
      // Phân tích là bước phụ trợ — hỏng thì app dịch như thường, không tính
      // phí, không dựng cờ đỏ trước mặt người dùng.
      request.log.warn({ err, jobId }, 'analyze failed')
      return { jobId, analysis: null, creditCharged: 0, balanceAfter: await credit.getBalance(device.fingerprint) }
    }
    if (!result.analysis) {
      return { jobId, analysis: null, creditCharged: 0, balanceAfter: await credit.getBalance(device.fingerprint) }
    }

    const paid = await charge(device, {
      holdId,
      jobId,
      action: 'analyze',
      walletCost: cost,
      internalVox: cfg['internal.cost.analyze'],
      description: 'Phân tích ngữ cảnh video',
      ip: request.ip,
    })

    const response = {
      jobId,
      analysis: result.analysis,
      creditCharged: paid.charged,
      balanceAfter: paid.balanceAfter,
    }
    await Promise.all([
      remember(jobId, device.fingerprint, 'analyze', response, paid.charged),
      UsageLog.create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'analyze',
        inputSize: lines.length,
        creditCharged: paid.charged,
        aiProvider: result.provider,
        aiModel: result.model,
        promptTokens: result.usage.promptTokens,
        completionTokens: result.usage.completionTokens,
        durationMs: Date.now() - started,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }),
    ])
    return response
  })

  // ------------------------------------------------------------ rà soát ---
  fastify.post('/review', {
    config: { rateLimit: { max: 20, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['jobId', 'items'],
        properties: {
          jobId: { type: 'string', minLength: 8, maxLength: 100 },
          holdId: { type: 'string', minLength: 8, maxLength: 100 },
          sourceLang: { type: 'string', maxLength: 16, default: 'zh-CN' },
          targetLang: { type: 'string', pattern: '^[a-z]{2,3}$', default: 'vi' },
          cpsBudget: { type: 'number', minimum: 4, maximum: 40, default: 12.5 },
          context: { type: 'object', additionalProperties: true },
          items: {
            type: 'array',
            minItems: 1,
            maxItems: 60,
            items: {
              type: 'object',
              required: ['id', 'reason', 'text', 'current'],
              properties: {
                id: { type: 'integer' },
                reason: { type: 'string', enum: ['cjk', 'over_budget', 'too_short'] },
                text: { type: 'string', maxLength: 800 },
                current: { type: 'string', maxLength: 1200 },
                duration: { type: 'number' },
                max_chars: { type: 'integer' },
                neighbors: { type: 'string', maxLength: 1200 },
              },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    const { jobId, items, sourceLang = 'zh-CN', targetLang = 'vi',
      cpsBudget = 12.5, holdId } = request.body
    const { field: targetField } = prompts.resolveTargetLang(targetLang)

    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    const cfg = await config.getMany(['credit.enabled', 'internal.cost.review.per_sentence'])
    const unitCost = cfg['credit.enabled'] ? cfg['internal.cost.review.per_sentence'] : 0
    const lacking = await precheck(device.fingerprint, holdId, items.length * unitCost,
      { action: 'review', jobId })
    if (lacking) {
      return reply.code(402).send({
        code: 'INSUFFICIENT_CREDIT',
        message: `Không đủ Vox. Cần ${lacking.required}, bạn có ${lacking.balance}.`,
        balance: lacking.balance,
        required: lacking.required,
      })
    }

    const context = prompts.sanitizeContext(request.body.context || {})
    const started = Date.now()
    let promptTokens = 0
    let completionTokens = 0

    // V66 — gom theo lô thay vì mỗi câu một lượt gọi.
    //
    // Bản cũ `Promise.all(items.map(...))` gọi riêng từng câu, mỗi lượt gánh
    // trọn system prompt của bước DỊCH: 2.562 token cho đúng một câu, trong
    // khi dịch chính câu đó chỉ tốn 84. Với system prompt riêng cho review
    // (139 token) và lô 20 câu, đo được giảm 33 lần token vào.
    //
    // Lô hỏng thì rơi về gọi từng câu CHỈ cho lô đó — giữ nguyên chất lượng
    // của bản cũ, và chỉ trả giá token cũ ở đúng đường hỏng hiếm gặp.
    const CHUNK = 20
    const chunks = []
    for (let i = 0; i < items.length; i += CHUNK) chunks.push(items.slice(i, i + CHUNK))

    const perItem = async (item) => {
      try {
        const { text, usage } = await gateway.reviewOne({
          segment: {
            id: item.id, text: item.text, duration: item.duration,
            max_chars: item.max_chars, [targetField]: item.current,
          },
          reason: item.reason,
          neighbors: item.neighbors || '',
          sourceLang,
          targetKey: targetLang,
          context,
          cpsBudget,
        })
        promptTokens += usage.promptTokens
        completionTokens += usage.completionTokens
        if (!accept(item, text)) return null
        return { id: item.id, [targetField]: text }
      } catch {
        // Một câu rà soát hỏng không được phép làm hỏng cả lượt — giữ bản cũ.
        return null
      }
    }

    const nested = await Promise.all(chunks.map(async (chunk) => {
      try {
        const { fixes, usage } = await gateway.reviewBatch({
          items: chunk.map((it) => ({ ...it, [targetField]: it.current })),
          targetKey: targetLang,
          context,
          cpsBudget,
        })
        promptTokens += usage.promptTokens
        completionTokens += usage.completionTokens
        return chunk.map((item) => {
          const text = fixes.get(item.id)
          // Mô hình bỏ sót câu nào thì giữ bản cũ — KHÔNG gọi lại lẻ cho nó.
          // Bỏ sót lác đác là chuyện thường; gọi lại lẻ sẽ lặng lẽ kéo chi phí
          // về đúng mức cũ mà không ai thấy.
          if (!text || !accept(item, text)) return null
          return { id: item.id, [targetField]: text }
        })
      } catch {
        return Promise.all(chunk.map(perItem))
      }
    }))
    const results = nested.flat()

    const fixed = results.filter(Boolean)
    const paid = await charge(device, {
      holdId,
      jobId,
      action: 'review',
      walletCost: unitCost > 0 ? fixed.length * unitCost : 0,
      internalVox: fixed.length * cfg['internal.cost.review.per_sentence'],
      sentences: fixed.length,
      description: `Rà soát ${fixed.length} câu`,
      ip: request.ip,
    })

    const response = {
      jobId,
      segments: fixed,
      creditCharged: paid.charged,
      balanceAfter: paid.balanceAfter,
    }
    await Promise.all([
      remember(jobId, device.fingerprint, 'review', response, paid.charged),
      UsageLog.create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'review',
        inputSize: items.length,
        creditCharged: paid.charged,
        promptTokens,
        completionTokens,
        durationMs: Date.now() - started,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }),
    ])
    return response
  })

  // ------------------------------------------- dịch phụ đề rời (V14) ----
  //
  // Tách khỏi `/translate` (dùng cho pipeline dub, payload gắn `duration`/
  // `max_chars`/`cpsBudget` — ràng buộc tốc độ đọc cho TTS, không áp dụng
  // cho phụ đề thuần không có TTS nào đọc theo). Ngôn ngữ là mã FLORES-200
  // (vd "vie_Latn"), không phải khoá ngắn "vi"/"en" như /translate — xem
  // Constraint 1/3 mini-spec V14, docs/PLAN.md.
  //
  // Billing: mỗi dòng phụ đề tính giá autotranslate (KHÔNG cộng
  // `credit.cost.segment.base`, phần đó gắn xử lý ASR/dub segment không áp
  // dụng ở đây — Constraint 4 của V14).
  fastify.post('/translate-subtitle', {
    config: { rateLimit: { max: 20, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['jobId', 'sourceFlores', 'targetFlores', 'items'],
        properties: {
          jobId: { type: 'string', minLength: 8, maxLength: 100 },
          holdId: { type: 'string', minLength: 8, maxLength: 100 },
          sourceFlores: { type: 'string', pattern: '^[a-z]{3}_[A-Z][a-z]{3}$' },
          targetFlores: { type: 'string', pattern: '^[a-z]{3}_[A-Z][a-z]{3}$' },
          sourceName: { type: 'string', maxLength: 80 },
          targetName: { type: 'string', maxLength: 80 },
          items: {
            type: 'array',
            minItems: 1,
            items: {
              type: 'object',
              required: ['id', 'text'],
              properties: {
                id: { type: 'integer' },
                text: { type: 'string' },
              },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    const { jobId, holdId, items, sourceFlores, targetFlores,
      sourceName, targetName } = request.body

    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    const cfg = await config.getMany([
      'ai.max.segments.per.request', 'ai.max.chars.per.segment',
      'ai.max.retries', 'credit.enabled',
      'credit.cost.segment.autotranslate',
      'internal.cost.translate.per_sentence',
    ])
    if (items.length > cfg['ai.max.segments.per.request']) {
      return reply.code(400).send({
        code: 'BATCH_TOO_LARGE',
        message: `Tối đa ${cfg['ai.max.segments.per.request']} dòng mỗi lượt.`,
        maxSegments: cfg['ai.max.segments.per.request'],
      })
    }
    const maxChars = cfg['ai.max.chars.per.segment']
    const tooLong = items.find((s) => String(s.text || '').length > maxChars)
    if (tooLong) {
      return reply.code(400).send({
        code: 'SEGMENT_TOO_LONG',
        message: `Dòng ${tooLong.id} dài quá ${maxChars} ký tự.`,
      })
    }

    const perLine = cfg['credit.cost.segment.autotranslate']
    const cost = cfg['credit.enabled'] ? items.length * perLine : 0
    if (cfg['credit.enabled']) {
      const short = await precheck(device.fingerprint, holdId, cost,
        { action: 'translate_subtitle', jobId })
      if (short) {
        return reply.code(402).send({
          code: 'INSUFFICIENT_CREDIT',
          message: `Không đủ Vox. Cần ${short.required}, bạn có ${short.balance}.`,
          balance: short.balance,
          required: short.required,
        })
      }
    }

    const log = await UsageLog.create({
      fingerprint: device.fingerprint,
      jobId,
      action: 'translate_subtitle',
      inputSize: items.length,
      ip: request.ip,
      appVersion: device.appVersion,
    })
    const started = Date.now()

    let result
    try {
      result = await gateway.translateSubtitleBatch({
        items, sourceFlores, targetFlores, sourceName, targetName,
        maxRetries: cfg['ai.max.retries'],
      })
    } catch (err) {
      await UsageLog.updateOne({ _id: log._id }, {
        $set: {
          status: 'error',
          errorCode: err.code || 'AI_ERROR',
          errorMessage: String(err.message).slice(0, 500),
          durationMs: Date.now() - started,
        },
      })
      request.log.error({ err, jobId }, 'translate-subtitle failed')
      return reply.code(err.statusCode || 503).send({
        code: err.code || 'AI_UNAVAILABLE',
        message: 'Dịch vụ dịch tạm thời không phản hồi. Thử lại sau ít phút.',
        retryAfter: 30,
      })
    }

    const done = result.segments.length
    const paid = await charge(device, {
      holdId,
      jobId,
      action: 'translate_subtitle',
      walletCost: cfg['credit.enabled'] ? done * perLine : 0,
      internalVox: done * cfg['internal.cost.translate.per_sentence'],
      sentences: done,
      description: `Dịch phụ đề ${done} dòng`,
      ip: request.ip,
    })

    const response = {
      jobId,
      segments: result.segments,
      creditCharged: paid.charged,
      balanceAfter: paid.balanceAfter,
    }
    await Promise.all([
      remember(jobId, device.fingerprint, 'translate_subtitle', response, paid.charged),
      UsageLog.updateOne({ _id: log._id }, {
        $set: {
          status: 'success',
          creditCharged: paid.charged,
          promptTokens: result.usage.promptTokens,
          completionTokens: result.usage.completionTokens,
          durationMs: Date.now() - started,
        },
      }),
    ])
    return response
  })

  // ------------------------------------------------- nội dung đăng bài ----
  fastify.post('/generate-post', {
    config: { rateLimit: { max: 10, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['jobId', 'scriptOriginal', 'scriptVi'],
        properties: {
          jobId: { type: 'string', minLength: 8, maxLength: 100 },
          holdId: { type: 'string', minLength: 8, maxLength: 100 },
          scriptOriginal: { type: 'string', maxLength: 20000 },
          scriptVi: { type: 'string', maxLength: 20000 },
          videoTitle: { type: 'string', maxLength: 300 },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    const { jobId, scriptOriginal, scriptVi, videoTitle = '', holdId } = request.body

    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    // Không kèm hold thì thu đúng giá công khai của gói tiêu đề + mô tả.
    const cfg = await config.getMany([
      'credit.enabled', 'credit.cost.metadata', 'internal.cost.generate_post',
    ])
    const cost = cfg['credit.enabled'] ? cfg['credit.cost.metadata'] : 0
    // Luồng wizard gọi bước này SAU khi hold đã chốt (bấm Xuất video) —
    // canAbsorb vẫn nhận vì gói tiêu đề + mô tả đã nằm trong giá hold.
    const lacking = await precheck(device.fingerprint, holdId, cost,
      { action: 'generate_post', jobId })
    if (lacking) {
      return reply.code(402).send({
        code: 'INSUFFICIENT_CREDIT',
        message: `Không đủ Vox. Cần ${lacking.required}, bạn có ${lacking.balance}.`,
        balance: lacking.balance,
        required: lacking.required,
      })
    }

    const started = Date.now()
    let result
    try {
      result = await gateway.generatePost({ scriptOriginal, scriptVi, videoTitle })
    } catch (err) {
      request.log.warn({ err, jobId }, 'generate-post failed')
      return reply.code(503).send({
        code: 'AI_UNAVAILABLE',
        message: 'Chưa viết được nội dung đăng bài. Video của bạn không bị ảnh hưởng.',
        retryAfter: 30,
      })
    }

    const paid = await charge(device, {
      holdId,
      jobId,
      action: 'generate_post',
      walletCost: cost,
      internalVox: cfg['internal.cost.generate_post'],
      description: 'Tạo tiêu đề + mô tả',
      ip: request.ip,
    })

    const response = {
      jobId,
      metadata: result.metadata,
      creditCharged: paid.charged,
      balanceAfter: paid.balanceAfter,
    }
    await Promise.all([
      remember(jobId, device.fingerprint, 'generate_post', response, paid.charged),
      UsageLog.create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'generate_post',
        inputSize: 1,
        creditCharged: paid.charged,
        aiProvider: result.provider,
        aiModel: result.model,
        promptTokens: result.usage.promptTokens,
        completionTokens: result.usage.completionTokens,
        durationMs: Date.now() - started,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }),
    ])
    return response
  })

  // ------------------------------------ cổng trợ lý (mini-spec V89) --
  //
  // MỘT cửa cho mọi việc cần mô hình ngôn ngữ, nhận TÊN tác vụ chứ không
  // nhận prompt. Bốn lớp chặn chi phí, không lớp nào thay được lớp nào:
  //   1. danh sách tác vụ đóng (`assistPrompts.TASK_NAMES` trong schema)
  //   2. trần ký tự đầu vào — cắt TRƯỚC khi gọi mô hình
  //   3. hạn mức theo ngày mỗi máy (`assistUsedToday`)
  //   4. giá Vox theo từng tác vụ, đổi được lúc chạy
  fastify.post('/assist', {
    config: { rateLimit: { max: 20, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['jobId', 'task'],
        properties: {
          jobId: { type: 'string', minLength: 8, maxLength: 100 },
          task: { type: 'string', enum: assistPrompts.TASK_NAMES },
          holdId: { type: 'string', minLength: 8, maxLength: 100 },
          input: { type: 'object', additionalProperties: true },
          // Ảnh gửi kèm (mini-spec C1). Trần đặt ở ĐÂY, trước khi chạm tới
          // mô hình: một ảnh 10 MB base64 vừa tốn tiền vừa làm nghẽn hàng
          // đợi, mà chặn sau khi đã gọi thì tiền đã mất.
          images: {
            type: 'array',
            // Trần CHUNG ở tầng schema = trần lớn nhất trong các tác vụ; trần
            // riêng từng tác vụ (`soAnhToiDa`) do cổng trợ lý ép. Để 2 ở đây
            // thì thêm tác vụ nhận nhiều ảnh là bị chặn oan ngay tầng schema,
            // trước khi tới chỗ có thông báo tử tế.
            maxItems: 6,
            items: {
              type: 'object',
              required: ['mimeType', 'data'],
              properties: {
                mimeType: { type: 'string', enum: ['image/png', 'image/jpeg', 'image/webp'] },
                data: { type: 'string', maxLength: 2_800_000 },
              },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    // Nấc hiện tại chỉ dùng để GHI SỔ ở đây, không dùng để chặn: chặn bước
    // kiểm an toàn là làm ngược — cửa sinh ảnh đã đóng thì không có ảnh nào
    // để kiểm, còn ai đã có ảnh thì càng nên cho họ kiểm.
    //
    // Chỉ hỏi khi thật sự cần: sáu tác vụ chữ còn lại không dính gì tới nấc
    // ảnh, bắt chúng đọc thêm cấu hình mỗi lượt là phí công vô ích.
    const runModeCuaLuot = request.body.task !== 'packaging_check' ? '' :
      (imageStage.quyetDinh({
        stage: await config.get('image.scene.stage'),
        devices: await config.get('image.scene.calibration.devices'),
        fingerprint: device.fingerprint,
      }).runMode || '')
    const { jobId, task, input = {}, holdId, images = [] } = request.body
    const spec = assistPrompts.getTask(task)

    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    // Nhớ đệm theo NỘI DUNG: `jobId` chỉ chống gọi trùng do mạng chập chờn,
    // còn người dùng bấm lại nút thì jobId mới → trả tiền lần nữa cho câu hỏi
    // y hệt. Khoá băm gồm cả phiên bản prompt nên sửa prompt là tự hết hiệu lực.
    const khoaNoiDung = assistPrompts.cacheKey(task, input, images)
    const cuNoiDung = await replay(khoaNoiDung, device.fingerprint)
    if (cuNoiDung) {
      UsageLog.create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: task,
        // C2 — ghi PHÁN QUYẾT của bước kiểm bao bì. C1 ghi đủ tác vụ, mô
        // hình, token, mã lỗi, nhưng không ghi kết quả, nên không có gì để
        // đếm khi cần biết mô hình đang gắt hay đang dễ dãi.
        verdict: task === 'packaging_check'
          ? String(result.results[0]?.value || '') : '',
        reason: task === 'packaging_check'
          ? String(result.results[0]?.reason || '').slice(0, 500) : '',
        runMode: runModeCuaLuot,
        assistPromptVersion: assistPrompts.PROMPT_VERSION,
        fromCache: true,
        creditCharged: 0,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }).catch(() => {})
      return { ...cuNoiDung, jobId, creditCharged: 0, fromCache: true }
    }

    const cfg = await config.getMany([
      'credit.enabled', spec.costKey,
      'assist.daily.limit', `assist.daily.limit.${task}`,
    ])
    const cost = cfg['credit.enabled'] ? (cfg[spec.costKey] || 0) : 0

    // Hạn mức riêng của tác vụ (nếu có) đi trước hạn mức chung: tác vụ miễn
    // phí như explain_error cần trần riêng vì nó không bị giá Vox chặn.
    const tranRieng = cfg[`assist.daily.limit.${task}`]
    if (tranRieng > 0) {
      const daDung = await assistUsedToday(device.fingerprint, task)
      if (daDung >= tranRieng) {
        return reply.code(429).send({
          code: 'DAILY_LIMIT',
          message: `Hôm nay đã dùng hết ${tranRieng} lượt cho việc này. Thử lại vào ngày mai.`,
        })
      }
    }
    const tranChung = cfg['assist.daily.limit']
    if (tranChung > 0) {
      const daDung = await assistUsedToday(device.fingerprint, '')
      if (daDung >= tranChung) {
        return reply.code(429).send({
          code: 'DAILY_LIMIT',
          message: `Hôm nay đã dùng hết ${tranChung} lượt trợ lý. Thử lại vào ngày mai.`,
        })
      }
    }

    const lacking = await precheck(device.fingerprint, holdId, cost,
      { action: 'assist', jobId })
    if (lacking) {
      return reply.code(402).send({
        code: 'INSUFFICIENT_CREDIT',
        message: `Không đủ Vox. Cần ${lacking.required}, bạn có ${lacking.balance}.`,
        balance: lacking.balance,
        required: lacking.required,
      })
    }

    const started = Date.now()
    let result
    try {
      result = await gateway.assist({ task, input, images })
    } catch (err) {
      // Lỗi do NGƯỜI GỌI sai (gửi ảnh cho tác vụ không nhận ảnh, quá số ảnh)
      // phải trả đúng 400 kèm lý do — gộp hết vào 503 "trợ lý chưa trả lời
      // được" thì phía app không phân biệt nổi lỗi của mình với lỗi máy chủ.
      if (err.statusCode === 400) {
        return reply.code(400).send({
          code: err.code || 'BAD_REQUEST',
          message: err.message,
        })
      }
      request.log.warn({ err, jobId, task }, 'assist failed')
      UsageLog.create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: task,
        status: 'error',
        errorCode: err.code || 'AI_UNAVAILABLE',
        errorMessage: String(err.message).slice(0, 300),
        durationMs: Date.now() - started,
        ip: request.ip,
        appVersion: device.appVersion,
      }).catch(() => {})
      // App LUÔN có đường lui cho các tác vụ này (tầng luật chạy trên máy),
      // nên hỏng ở đây không phải chuyện lớn — nhưng phải nói ra để phía app
      // biết mà rơi về đường lui, thay vì tưởng là không có gợi ý nào.
      return reply.code(503).send({
        code: 'AI_UNAVAILABLE',
        message: 'Trợ lý chưa trả lời được. Bạn vẫn dùng bình thường được.',
        retryAfter: 30,
      })
    }

    const paid = await charge(device, {
      holdId,
      jobId,
      action: 'assist',
      walletCost: cost,
      internalVox: 0,
      description: `Trợ lý: ${task}`,
      ip: request.ip,
    })

    const response = {
      jobId,
      task,
      results: result.results,
      creditCharged: paid.charged,
      balanceAfter: paid.balanceAfter,
    }
    await Promise.all([
      remember(jobId, device.fingerprint, 'assist', response, paid.charged),
      // Lưu thêm dưới khoá nội dung để lần bấm sau không tính tiền lại.
      remember(khoaNoiDung, device.fingerprint, 'assist', response, paid.charged),
      UsageLog.create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: task,
        assistRole: result.role,
        assistPromptVersion: assistPrompts.PROMPT_VERSION,
        inputSize: result.results.length,
        creditCharged: paid.charged,
        aiProvider: result.provider,
        aiModel: result.model,
        promptTokens: result.usage.promptTokens,
        completionTokens: result.usage.completionTokens,
        durationMs: Date.now() - started,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }),
    ])
    return response
  })

  // -------------------------- dựng bối cảnh ảnh sản phẩm (mini-spec C1) --
  //
  // Người bán đưa MỘT ảnh sản phẩm thật, chọn bối cảnh, nhận về ảnh mới.
  //
  // Bối cảnh đổi, SẢN PHẨM THÌ KHÔNG — câu lệnh gửi mô hình cấm sửa bao bì
  // (xem `prompts/product_scene.js`). Đây là ranh giới giữa "chụp ảnh sản
  // phẩm bình thường" và thứ khiến người bán bị TikTok Shop cưỡng chế theo
  // chính sách "quảng bá sản phẩm không nhất quán".
  //
  // Chế độ CONCEPT (cho phép dựng lại bao bì) có hạn mức NGÀY RIÊNG, thấp hẳn
  // so với SAFE: rủi ro thật không nằm ở một tấm ảnh, mà ở việc đăng hàng loạt
  // rồi bị máy quét gắn cờ đồng loạt.
  fastify.post('/product-scene', {
    config: { rateLimit: { max: 10, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['jobId', 'scene', 'image'],
        properties: {
          jobId: { type: 'string', minLength: 8, maxLength: 100 },
          scene: { type: 'string', enum: scenePrompts.TEN_BOI_CANH },
          mode: { type: 'string', enum: ['SAFE', 'CONCEPT'], default: 'SAFE' },
          note: { type: 'string', maxLength: 300 },
          holdId: { type: 'string', minLength: 8, maxLength: 100 },
          image: {
            type: 'object',
            required: ['mimeType', 'data'],
            properties: {
              mimeType: { type: 'string', enum: ['image/png', 'image/jpeg', 'image/webp'] },
              data: { type: 'string', maxLength: 2_800_000 },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    const { jobId, scene, image, mode = 'SAFE', note = '', holdId } = request.body

    // Chốt chuyển pha (C2) đứng TRƯỚC cả `replay`: cửa đã đóng thì không
    // được phục vụ nốt kết quả cũ — đóng cửa mà vẫn trả hàng qua khe thì
    // không gọi là đóng.
    const nac = imageStage.quyetDinh({
      stage: await config.get('image.scene.stage'),
      devices: await config.get('image.scene.calibration.devices'),
      fingerprint: device.fingerprint,
    })
    if (!nac.choPhep) {
      return reply.code(409).send({ code: nac.code, message: nac.message })
    }

    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    const cfg = await config.getMany([
      'credit.enabled', 'credit.cost.image.scene',
      'image.daily.limit', 'image.daily.limit.concept',
    ])
    const cost = cfg['credit.enabled'] ? (cfg['credit.cost.image.scene'] || 0) : 0

    // Hạn mức riêng của CONCEPT đi TRƯỚC hạn mức chung: hết trần concept thì
    // vẫn còn dùng SAFE được, đó mới là điều người bán cần trong ngày.
    if (mode === 'CONCEPT' && cfg['image.daily.limit.concept'] > 0) {
      const daDung = await UsageLog.countDocuments({
        fingerprint: device.fingerprint,
        action: 'product_scene',
        assistTask: 'CONCEPT',
        runMode: { $ne: 'test_now' },
        createdAt: { $gte: new Date(new Date().setHours(0, 0, 0, 0)) },
      })
      if (daDung >= cfg['image.daily.limit.concept']) {
        return reply.code(429).send({
          code: 'DAILY_LIMIT_CONCEPT',
          message: `Hôm nay đã dựng ${cfg['image.daily.limit.concept']} ảnh đổi `
            + 'bao bì. Chế độ giữ nguyên bao bì vẫn dùng bình thường.',
        })
      }
    }
    if (cfg['image.daily.limit'] > 0) {
      const daDung = await UsageLog.countDocuments({
        fingerprint: device.fingerprint,
        action: 'product_scene',
        runMode: { $ne: 'test_now' },
        createdAt: { $gte: new Date(new Date().setHours(0, 0, 0, 0)) },
      })
      if (daDung >= cfg['image.daily.limit']) {
        return reply.code(429).send({
          code: 'DAILY_LIMIT',
          message: `Hôm nay đã dựng hết ${cfg['image.daily.limit']} ảnh. `
            + 'Thử lại vào ngày mai.',
        })
      }
    }

    const lacking = await precheck(device.fingerprint, holdId, cost,
      { action: 'product_scene', jobId })
    if (lacking) {
      return reply.code(402).send({
        code: 'INSUFFICIENT_CREDIT',
        message: `Không đủ Vox. Cần ${lacking.required}, bạn có ${lacking.balance}.`,
        balance: lacking.balance,
        required: lacking.required,
      })
    }

    const started = Date.now()
    let result
    try {
      result = await gateway.generateScene({ image, scene, mode, note })
    } catch (err) {
      request.log.warn({ err, jobId, scene, mode }, 'product-scene failed')
      UsageLog.create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'product_scene',
        assistTask: mode,
        runMode: nac.runMode,
        status: 'error',
        errorCode: err.code || 'AI_UNAVAILABLE',
        errorMessage: String(err.message).slice(0, 300),
        durationMs: Date.now() - started,
        ip: request.ip,
        appVersion: device.appVersion,
      }).catch(() => {})
      return reply.code(err.statusCode || 503).send({
        code: err.code || 'AI_UNAVAILABLE',
        message: err.message || 'Chưa dựng được ảnh. Thử lại sau ít phút.',
        retryAfter: 30,
      })
    }

    const paid = await charge(device, {
      holdId,
      jobId,
      action: 'product_scene',
      walletCost: cost,
      internalVox: 0,
      description: `Dựng bối cảnh ảnh (${mode})`,
      ip: request.ip,
    })

    const response = {
      jobId,
      scene,
      mode,
      image: result.image,
      creditCharged: paid.charged,
      balanceAfter: paid.balanceAfter,
    }
    await Promise.all([
      remember(jobId, device.fingerprint, 'product_scene', response, paid.charged),
      UsageLog.create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'product_scene',
        // Ghi CHẾ ĐỘ vào đây để đếm hạn mức concept và để tra lại sau này.
        assistTask: mode,
        runMode: nac.runMode,
        inputSize: 1,
        creditCharged: paid.charged,
        aiProvider: result.provider,
        aiModel: result.model,
        durationMs: Date.now() - started,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }),
    ])
    return response
  })

  // ------------------------------------- nhạc nền/SFX AI (mini-spec V37) --
  //
  // KHÔNG dùng `replay`/`JobResult` (Constraint PoC hẹp — xem docs/PLAN.md
  // Remaining Limits mục V37): audio nhị phân không hợp để lưu JSON,
  // lượt gọi lại thật (network retry) hiếm và giá trị nhỏ, chấp nhận rủi
  // ro tính phí trùng hiếm gặp thay vì xây hệ cache file riêng cho PoC.
  // Trả về NHỊ PHÂN trực tiếp (khác mọi route JSON khác ở file này) — cùng
  // cách `routes/jobs.js` stream kết quả Demucs.
  const crypto = require('node:crypto')
  const elevenlabs = require('../services/elevenlabs-audio.service')

  fastify.post('/sound-effect', {
    config: { rateLimit: { max: 10, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['text'],
        properties: {
          text: { type: 'string', minLength: 1, maxLength: 500 },
          durationSeconds: { type: 'number', minimum: 0.5, maximum: 30 },
          jobId: { type: 'string', maxLength: 100 },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    const { text, durationSeconds } = request.body
    const jobId = request.body.jobId || crypto.randomUUID()

    if (!(await config.get('cloud.music_match.enabled'))) {
      return reply.code(409).send({ code: 'MUSIC_MATCH_DISABLED', message: 'Tính năng nhạc nền/SFX đang tắt.' })
    }
    const cost = Number(await config.get('credit.cost.cloud.sound_effect')) || 0
    const lacking = await precheck(device.fingerprint, null, cost, { action: 'sound_effect', jobId })
    if (lacking) {
      return reply.code(402).send({
        code: 'INSUFFICIENT_CREDIT',
        message: `Không đủ Vox. Cần ${lacking.required}, bạn có ${lacking.balance}.`,
        balance: lacking.balance, required: lacking.required,
      })
    }

    let audio
    try {
      audio = await elevenlabs.generateSoundEffect({ text, durationSeconds })
    } catch (err) {
      if (err instanceof elevenlabs.ElevenLabsError) {
        return reply.code(err.statusCode).send({ code: err.code, message: err.message })
      }
      throw err
    }

    const paid = await charge(device, {
      jobId, action: 'sound_effect', walletCost: cost, internalVox: cost,
      description: 'Hiệu ứng âm thanh AI', ip: request.ip,
    })
    await UsageLog.create({
      fingerprint: device.fingerprint, jobId, action: 'sound_effect',
      inputSize: text.length, creditCharged: paid.charged,
      aiProvider: 'elevenlabs', aiModel: 'eleven_text_to_sound_v2',
      promptTokens: 0, completionTokens: 0, durationMs: 0,
      status: 'success', ip: request.ip, appVersion: device.appVersion,
    })

    reply.header('Content-Type', 'audio/mpeg')
    reply.header('X-Credit-Charged', String(paid.charged))
    reply.header('X-Balance-After', String(paid.balanceAfter))
    return reply.send(audio)
  })

  fastify.post('/music', {
    config: { rateLimit: { max: 5, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['prompt'],
        properties: {
          prompt: { type: 'string', minLength: 1, maxLength: 2000 },
          musicLengthMs: { type: 'integer', minimum: 3000, maximum: 600000 },
          jobId: { type: 'string', maxLength: 100 },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    const { prompt, musicLengthMs } = request.body
    const jobId = request.body.jobId || crypto.randomUUID()

    if (!(await config.get('cloud.music_match.enabled'))) {
      return reply.code(409).send({ code: 'MUSIC_MATCH_DISABLED', message: 'Tính năng nhạc nền/SFX đang tắt.' })
    }
    const cost = Number(await config.get('credit.cost.cloud.music')) || 0
    const lacking = await precheck(device.fingerprint, null, cost, { action: 'music', jobId })
    if (lacking) {
      return reply.code(402).send({
        code: 'INSUFFICIENT_CREDIT',
        message: `Không đủ Vox. Cần ${lacking.required}, bạn có ${lacking.balance}.`,
        balance: lacking.balance, required: lacking.required,
      })
    }

    let audio
    try {
      audio = await elevenlabs.generateMusic({ prompt, musicLengthMs })
    } catch (err) {
      if (err instanceof elevenlabs.ElevenLabsError) {
        return reply.code(err.statusCode).send({ code: err.code, message: err.message })
      }
      throw err
    }

    const paid = await charge(device, {
      jobId, action: 'music', walletCost: cost, internalVox: cost,
      description: 'Nhạc nền AI', ip: request.ip,
    })
    await UsageLog.create({
      fingerprint: device.fingerprint, jobId, action: 'music',
      inputSize: prompt.length, creditCharged: paid.charged,
      aiProvider: 'elevenlabs', aiModel: 'music_v2',
      promptTokens: 0, completionTokens: 0, durationMs: 0,
      status: 'success', ip: request.ip, appVersion: device.appVersion,
    })

    reply.header('Content-Type', 'audio/mpeg')
    reply.header('X-Credit-Charged', String(paid.charged))
    reply.header('X-Balance-After', String(paid.balanceAfter))
    return reply.send(audio)
  })
}

/** Bản dịch lại chỉ được nhận khi thật sự sửa được lý do bị cờ. */
function accept(item, text) {
  const next = String(text || '').trim()
  if (!next) return false
  if (containsCjk(next)) return false
  if (item.reason === 'over_budget') {
    if (item.max_chars && next.length > item.max_chars * 1.25) return false
    return next.length < String(item.current || '').length
  }
  return true
}
