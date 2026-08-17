'use strict'

/**
 * `/api/v1` — API dịch thuật công khai cho developer bên thứ 3 (mini-spec
 * V31, docs/PLAN.md Phase G).
 *
 * Phạm vi CHỦ ĐÍCH hẹp: CHỈ dịch văn bản (tái dùng
 * `gateway.translateSubtitleBatch()` đã có từ V14 — prompt ĐƠN GIẢN, không
 * gắn "video context" như luồng dub) — KHÔNG mở ASR/TTS/video (đó là hạ
 * tầng hoàn toàn khác, chưa tồn tại server-side, xem "Audit Before Build"
 * chung đầu Phase G trong docs/PLAN.md).
 *
 * Auth: API key (`requireApiKey`, tách hẳn `requireDevice` của `/v1/ai/*`)
 * — desktop app KHÔNG đụng route này, 0 regression cho `/v1/ai/*`.
 * Billing: `ApiKey.quota`/`ApiUsageLedger` — TÁCH HẲN `CreditLedger` của
 * desktop app (Constraint 3).
 */
const { requireApiKey } = require('../middleware/apikey.middleware')
const { QuotaExceededError, consumeQuota } = require('../services/api-key.service')
const gateway = require('../services/ai-gateway.service')
const config = require('../services/config.service')
const ApiKey = require('../models/ApiKey')
const dubJob = require('../services/dub-job.service')
const {
  SOURCE_LANGS, TARGET_LANGS, isValidSourceLang, isValidTargetLang,
} = require('../utils/dub-langs')

module.exports = async function apiV1Routes(fastify) {
  fastify.addHook('preHandler', requireApiKey)

  // Đóng gap Remaining Limits ghi trong docs/TEST_LOG.md mục V31 — developer
  // trước đây chỉ xem được quota/usage của MÌNH qua response của mỗi lượt
  // /translate, không có cách xem NGOÀI 1 lượt gọi thật (vd trước khi gọi
  // gì cả). KHÔNG lộ keyHash/orgName nội bộ khác — chỉ đúng thông tin của
  // chính API key đang xác thực.
  fastify.get('/me', async (request) => {
    const { apiKey } = request
    return {
      orgName: apiKey.orgName,
      status: apiKey.status,
      quota: apiKey.quota,
      usageCount: apiKey.usageCount,
      remaining: Math.max(0, apiKey.quota - apiKey.usageCount),
      // Mini-spec V34b — quota RIÊNG cho lồng tiếng đầy đủ, đơn vị PHÚT chứ
      // không phải lượt gọi (khác quota/usageCount ở trên, xem Constraint 2).
      dubMinutesQuota: apiKey.dubMinutesQuota,
      dubMinutesUsed: apiKey.dubMinutesUsed,
      // V43: phút đang giữ chỗ cho job queued/running của CHÍNH key này —
      // trừ luôn vào "còn lại" để không hiểu nhầm là dùng được ngay bây giờ.
      dubMinutesReserved: apiKey.dubMinutesReserved || 0,
      dubMinutesRemaining: Math.max(
        0, apiKey.dubMinutesQuota - apiKey.dubMinutesUsed - (apiKey.dubMinutesReserved || 0),
      ),
      lastUsedAt: apiKey.lastUsedAt,
    }
  })

  fastify.post('/translate', {
    config: { rateLimit: { max: 30, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['sourceFlores', 'targetFlores', 'items'],
        properties: {
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
    const { apiKey } = request
    const { items, sourceFlores, targetFlores, sourceName, targetName } = request.body

    const cfg = await config.getMany([
      'ai.max.segments.per.request', 'ai.max.chars.per.segment', 'ai.max.retries',
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

    // Kiểm nhanh (không atomic — chỉ để KHỎI gọi model tốn tiền khi đã rõ
    // hết quota; chặn THẬT SỰ vẫn là consumeQuota() atomic sau khi model
    // trả về, xử lý đúng race giữa nhiều request song song).
    const fresh = await ApiKey.findById(apiKey._id).lean()
    if (!fresh || fresh.usageCount >= fresh.quota) {
      return reply.code(429).send({
        code: 'QUOTA_EXCEEDED',
        message: `Đã dùng hết quota (${fresh ? fresh.usageCount : 0}/${fresh ? fresh.quota : 0}).`,
        quota: fresh ? fresh.quota : 0,
        usageCount: fresh ? fresh.usageCount : 0,
      })
    }

    let result
    try {
      result = await gateway.translateSubtitleBatch({
        items, sourceFlores, targetFlores, sourceName, targetName,
        maxRetries: cfg['ai.max.retries'],
      })
    } catch (err) {
      request.log.error({ err }, 'api-v1 translate failed')
      return reply.code(err.statusCode || 503).send({
        code: err.code || 'AI_UNAVAILABLE',
        message: 'Dịch vụ dịch tạm thời không phản hồi. Thử lại sau ít phút.',
        retryAfter: 30,
      })
    }

    // Trừ quota SAU khi model gọi thành công — lỗi model thì developer
    // không mất quota (cùng nguyên tắc "trừ credit sau" của /v1/ai/*).
    let updatedKey
    try {
      updatedKey = await consumeQuota(apiKey._id, {
        action: 'translate', ip: request.ip,
        metadata: { segments: result.segments.length },
      })
    } catch (err) {
      if (err instanceof QuotaExceededError) {
        return reply.code(429).send({
          code: 'QUOTA_EXCEEDED',
          message: err.message,
          quota: err.quota,
          usageCount: err.usageCount,
        })
      }
      throw err
    }

    return {
      segments: result.segments,
      quota: updatedKey.quota,
      usageCount: updatedKey.usageCount,
    }
  })

  // ---------------------------------------------------------------------
  // Mini-spec V34a→V34b (docs/PLAN.md, Phase G) — API lồng tiếng đầy đủ
  // (ASR+dịch+TTS+mux), mở rộng V31 (vốn CHỈ dịch văn bản). CHỈ submit +
  // poll/tải kết quả (KHÔNG đồng bộ như /translate — dub mất nhiều phút,
  // không thể chờ trong 1 request HTTP). V34b: billing THẬT theo phút,
  // tính SAU khi job xong (xem dub-job.service.js::chargeDubUsage) — quota
  // kiểm TRƯỚC lúc submit (402 nếu hết), KHÔNG đụng `ApiKey.quota`/
  // `usageCount` (đó là bộ đếm riêng của V31, đơn vị khác — Constraint 2).
  // ---------------------------------------------------------------------

  // --- Nộp job lồng tiếng (upload video, TRẢ VỀ NGAY) ----------------------
  fastify.post('/dub', {
    config: { rateLimit: { max: 5, timeWindow: '1 minute' } },
  }, async (request, reply) => {
    const { apiKey } = request
    const sourceLang = String(request.query.sourceLang || '').trim()
    const targetLang = String(request.query.targetLang || '').trim()
    const voice = String(request.query.voice || '').trim()
    const bgMode = String(request.query.bgMode || 'none').trim()
    if (!sourceLang || !targetLang) {
      return reply.code(400).send({
        code: 'MISSING_LANG',
        message: 'Cần query param sourceLang và targetLang.',
      })
    }
    if (!['none', 'demucs'].includes(bgMode)) {
      return reply.code(400).send({
        code: 'BAD_BG_MODE',
        message: 'bgMode phải là "none" hoặc "demucs".',
      })
    }
    // Chặn NGAY tại cửa vào: mã sai mà lọt qua đây thì phải chờ hết bước ASR
    // (tốn quota + vài phút CPU của worker) mới hỏng, kèm lỗi mơ hồ không chỉ
    // ra được sai ở đâu. Lưu ý 2 tham số dùng 2 định dạng khác nhau — xem
    // utils/dub-langs.js.
    if (!isValidSourceLang(sourceLang)) {
      return reply.code(400).send({
        code: 'BAD_SOURCE_LANG',
        message: `sourceLang "${sourceLang}" không hỗ trợ. Hợp lệ: ${SOURCE_LANGS.join(', ')}.`,
      })
    }
    if (!isValidTargetLang(targetLang)) {
      return reply.code(400).send({
        code: 'BAD_TARGET_LANG',
        message: `targetLang "${targetLang}" không hỗ trợ — cần khoá ngắn `
          + `(vd "vi"), không phải mã BCP-47. Hợp lệ: ${TARGET_LANGS.join(', ')}.`,
      })
    }
    // V43: tuỳ chọn — caller tự khai thời lượng ước tính (phút) để giữ chỗ
    // quota chính xác hơn mặc định cấu hình. Không hợp lệ (âm/không phải
    // số) thì bỏ qua, rơi về mặc định — không chặn submit vì lỗi tham số
    // phụ này.
    const estimatedMinutesRaw = Number(request.query.estimatedMinutes)
    const estimatedMinutes = Number.isFinite(estimatedMinutesRaw) && estimatedMinutesRaw > 0
      ? estimatedMinutesRaw : 0

    const maxMb = Number(await config.get('cloud.dub.max.upload.mb')) || 300
    const data = await request.file({ limits: { fileSize: maxMb * 1024 * 1024 } })
    if (!data) {
      return reply.code(400).send({ code: 'NO_FILE', message: 'Thiếu file video.' })
    }
    const buffer = await data.toBuffer()
    if (!buffer.length) {
      return reply.code(400).send({ code: 'EMPTY_FILE', message: 'File video rỗng.' })
    }

    try {
      const { job } = await dubJob.submitDubJob({
        apiKey, fileBuffer: buffer, sourceLang, targetLang, voice, bgMode, estimatedMinutes,
        ip: request.ip,
      })
      return {
        jobId: job._id,
        status: job.status,
        async: true,
        bgMode: job.bgMode,
        estimatedCostVoxPerMinute: job.estimatedCostVox,
        reservedMinutes: job.reservedMinutes,
      }
    } catch (err) {
      if (err instanceof dubJob.DubJobError) {
        return reply.code(err.statusCode).send({ code: err.code, message: err.message })
      }
      throw err
    }
  })

  // --- Trạng thái job --------------------------------------------------------
  fastify.get('/dub/:jobId', async (request, reply) => {
    const job = await dubJob.getJob(request.apiKey._id, request.params.jobId)
    if (!job) return reply.code(404).send({ code: 'NOT_FOUND' })
    return {
      jobId: job._id, status: job.status,
      error: job.error || undefined,
      metrics: job.status === 'done' ? job.metrics : undefined,
      costVox: job.status === 'done' ? job.costVox : undefined,
      expiresAt: job.expiresAt,
    }
  })

  // --- Tải video kết quả — xoá file NGAY sau khi trả (cùng chính sách dữ ---
  // liệu đã áp dụng cho cloud rendering V9, xem docs/TEST_LOG.md) ----------
  fastify.get('/dub/:jobId/result', async (request, reply) => {
    const job = await dubJob.getJob(request.apiKey._id, request.params.jobId)
    if (!job) return reply.code(404).send({ code: 'NOT_FOUND' })
    if (job.status !== 'done') {
      return reply.code(409).send({ code: 'NOT_READY', message: `Job đang ở trạng thái ${job.status}.` })
    }
    if (!job.outputPath) {
      return reply.code(404).send({ code: 'RESULT_NOT_FOUND' })
    }

    const fs = require('node:fs')
    if (!fs.existsSync(job.outputPath)) {
      return reply.code(410).send({
        code: 'RESULT_EXPIRED',
        message: 'Kết quả đã bị xoá (đã tải trước đó hoặc quá hạn TTL).',
      })
    }
    const stream = fs.createReadStream(job.outputPath)
    reply.header('Content-Type', 'video/mp4')
    reply.header('Content-Disposition', `attachment; filename="dubbed_${job._id}.mp4"`)
    await reply.send(stream)

    stream.on('close', () => {
      dubJob.cleanupJob(job._id).catch(() => {})
    })
  })
}
