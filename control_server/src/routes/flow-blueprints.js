'use strict'

/**
 * `/v1/flow-blueprints` — mini-spec H2 (docs/PLAN.md, Phase H mới "Viral
 * Flow Clone & Brand Rewrite").
 *
 * Kiến trúc: video download + ASR (`autodub.transcribe_tool`) + OCR
 * (`autodub.media.text_regions.read_text_regions`, mini-spec H2a) chạy TRÊN
 * MÁY NGƯỜI DÙNG — không có engine AI nặng nào ở control_server (đúng kiến
 * trúc dự án, xem docs/ARCH.md). App gửi BẰNG CHỨNG đã trích (transcript +
 * quan sát OCR, không phải video) lên đây; route này gọi mô hình phân tích
 * cấu trúc (task `viral_flow_blueprint`, đăng ký ở `prompts/assist.js`) rồi
 * LƯU kết quả — một lượt tổng hợp, không phải job nền bất đồng bộ (không có
 * gì xử lý nặng ở phía server để cần hàng đợi).
 *
 * `ownerDeviceId` lấy TỪ token (`request.device._id`), KHÔNG BAO GIỜ nhận
 * từ client — cùng quy ước H1 (`routes/brand-profiles.js`).
 *
 * KHÔNG lưu transcript/OCR thô — chỉ dùng TẠM để gọi mô hình rồi bỏ, đúng
 * Constraint 2/Scope B của H2 ("không thêm raw transcript/caption source
 * thành field output-facing").
 */
const FlowBlueprint = require('../models/FlowBlueprint')
const assistPrompts = require('../prompts/assist')
const gateway = require('../services/ai-gateway.service')
const config = require('../services/config.service')
const { replay, remember, precheck, charge } = require('../services/assist-billing.service')

function view(doc) {
  return {
    id: String(doc._id),
    sourceType: doc.sourceType,
    sourceReference: doc.sourceReference,
    status: doc.status,
    languageSourceDetected: doc.languageSourceDetected,
    analysisLanguage: doc.analysisLanguage,
    evidenceSummary: doc.evidenceSummary,
    samplingPolicyUsed: doc.samplingPolicyUsed,
    beats: (doc.beats || []).map((b) => ({
      startS: b.startS,
      endS: b.endS,
      beatType: b.beatType,
      narrativeFunctionVi: b.narrativeFunctionVi,
      pacingNoteVi: b.pacingNoteVi,
      overlayPatternAbstractVi: b.overlayPatternAbstractVi,
      spokenPatternAbstractVi: b.spokenPatternAbstractVi,
      evidenceStatus: b.evidenceStatus,
    })),
    userReviewNote: doc.userReviewNote,
    createdAt: doc.createdAt,
    updatedAt: doc.updatedAt,
  }
}

const evidenceItemSchema = {
  type: 'object',
  required: ['start_s', 'end_s', 'text'],
  properties: {
    start_s: { type: 'number' },
    end_s: { type: 'number' },
    text: { type: 'string', maxLength: 2000 },
    status: { type: 'string', maxLength: 20 },
  },
}

const createBodySchema = {
  type: 'object',
  required: ['jobId', 'sourceType', 'sourceReference'],
  properties: {
    jobId: { type: 'string', minLength: 8, maxLength: 100 },
    sourceType: { type: 'string', enum: ['url', 'file'] },
    sourceReference: { type: 'string', minLength: 1, maxLength: 2000 },
    languageSourceDetected: { type: 'string', maxLength: 20, default: '' },
    samplingPolicyUsed: { type: 'string', maxLength: 200, default: '' },
    evidenceSummary: { type: 'string', maxLength: 1000, default: '' },
    transcript: { type: 'array', maxItems: 400, items: evidenceItemSchema, default: [] },
    ocrEvidence: { type: 'array', maxItems: 400, items: evidenceItemSchema, default: [] },
    holdId: { type: 'string', minLength: 8, maxLength: 100 },
  },
}

/** `:id` sai khuôn ObjectId (CastError) coi như không thấy, không phải 500
 * — cùng cách xử lý đã có ở BrandProfile (mini-spec H1). */
async function timBlueprintCuaThietBi(id, ownerDeviceId) {
  try {
    return await FlowBlueprint.findOne({ _id: id, ownerDeviceId })
  } catch (err) {
    if (err.name === 'CastError') return null
    throw err
  }
}

module.exports = async function flowBlueprintRoutes(fastify) {
  const { requireDevice } = require('../middleware/auth.middleware')
  fastify.addHook('preHandler', requireDevice)

  fastify.get('/', async (request) => {
    const list = await FlowBlueprint.find({ ownerDeviceId: request.device._id })
      .sort({ createdAt: -1 }).lean()
    return { data: list.map(view) }
  })

  fastify.get('/:id', async (request, reply) => {
    const doc = await timBlueprintCuaThietBi(request.params.id, request.device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_BLUEPRINT', message: 'Không thấy Flow Blueprint này.' })
    }
    return view(doc)
  })

  fastify.delete('/:id', async (request, reply) => {
    const doc = await timBlueprintCuaThietBi(request.params.id, request.device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_BLUEPRINT', message: 'Không thấy Flow Blueprint này.' })
    }
    await doc.deleteOne()
    return { ok: true }
  })

  fastify.post('/', {
    config: { rateLimit: { max: 20, timeWindow: '1 minute' } },
    schema: { body: createBodySchema },
  }, async (request, reply) => {
    const { device } = request
    if (await config.get('maintenance.mode')) {
      return reply.code(503).send({
        code: 'MAINTENANCE', message: 'Máy chủ đang bảo trì, thử lại sau.' })
    }

    const {
      jobId, sourceType, sourceReference, languageSourceDetected = '',
      samplingPolicyUsed = '', evidenceSummary = '', transcript = [],
      ocrEvidence = [], holdId,
    } = request.body

    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    const spec = assistPrompts.getTask('viral_flow_blueprint')
    const cfg = await config.getMany(['credit.enabled', spec.costKey])
    const cost = cfg['credit.enabled'] ? (cfg[spec.costKey] || 0) : 0

    const lacking = await precheck(device.fingerprint, holdId, cost,
      { action: 'flow_blueprint', jobId })
    if (lacking) {
      return reply.code(402).send({
        code: 'INSUFFICIENT_CREDIT',
        message: `Không đủ Vox. Cần ${lacking.required}, bạn có ${lacking.balance}.`,
        balance: lacking.balance,
        required: lacking.required,
      })
    }

    let result
    try {
      result = await gateway.assist({
        task: 'viral_flow_blueprint',
        input: {
          transcript, ocrEvidence, languageSourceDetected, samplingPolicyUsed,
          // sourceReference vào khoá nhớ đệm (qua `input`) — video khác thì
          // không được lấy lại blueprint cũ, dù transcript trùng hợp giống
          // nhau (mini-spec H2, Test Plan: "cache key phải bao gồm nguồn").
          sourceReference,
        },
        images: [],
      })
    } catch (err) {
      if (err.statusCode === 400) {
        return reply.code(400).send({ code: err.code || 'BAD_REQUEST', message: err.message })
      }
      request.log.warn({ err, jobId }, 'flow_blueprint analysis failed')
      return reply.code(503).send({
        code: 'AI_UNAVAILABLE',
        message: 'Không phân tích được lúc này. Thử lại sau.',
        retryAfter: 30,
      })
    }

    const paid = await charge(device, {
      holdId, jobId, action: 'flow_blueprint', walletCost: cost, internalVox: 0,
      description: 'Phân tích cấu trúc video tham khảo', ip: request.ip,
    })

    const doc = await FlowBlueprint.create({
      ownerDeviceId: device._id,
      sourceType,
      sourceReference,
      status: 'ready',
      languageSourceDetected,
      evidenceSummary,
      samplingPolicyUsed,
      beats: result.beats,
    })

    const response = { ...view(doc), creditCharged: paid.charged, balanceAfter: paid.balanceAfter }
    await Promise.all([
      remember(jobId, device.fingerprint, 'flow_blueprint', response, paid.charged),
      require('../models/UsageLog').create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: 'viral_flow_blueprint',
        assistRole: result.role,
        assistPromptVersion: assistPrompts.PROMPT_VERSION,
        durationMs: 0,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }).catch(() => {}),
    ])

    return reply.code(201).send(response)
  })
}
