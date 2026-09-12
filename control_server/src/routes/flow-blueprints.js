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
const { replay, remember, ghiSoDung, precheck, charge, kiemHanMucNgay } = require('../services/assist-billing.service')
const dauVanTay = require('../services/dau-van-tay.service')

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
    // H2c — CHỈ metadata của dấu vân tay, KHÔNG bao giờ kèm `muoi`/`dai`/
    // `ngan`. Đưa mảng băm ra cho client là biến nó thành máy dò đoán câu
    // nguồn; nhưng giấu cả phần metadata thì không ai kiểm được dấu vân tay
    // có được tạo hay không, và người dùng cũng không hiểu vì sao kịch bản
    // của mình bị "chưa kiểm được".
    evidenceFingerprint: doc.evidenceFingerprint
      ? thongTinVanTay(doc.evidenceFingerprint) : null,
    createdAt: doc.createdAt,
    updatedAt: doc.updatedAt,
  }
}

/**
 * Metadata dấu vân tay cho API — TUYỆT ĐỐI không kèm `muoi`/`dai`/`ngan`.
 *
 * `soBam` là `null` khi hai mảng băm không được nạp (API danh sách cố ý bỏ
 * chúng khỏi truy vấn). Trả 0 ở đó là NÓI DỐI: người đọc sẽ tưởng bản ghi
 * không có băm nào, trong khi thực ra chỉ là chưa nạp về.
 */
function thongTinVanTay(vt) {
  const coMangBam = Array.isArray(vt.dai) && Array.isArray(vt.ngan)
  return {
    v: vt.v,
    soBam: coMangBam ? vt.dai.length + vt.ngan.length : null,
    soDong: vt.soDong,
    soDongBoQua: vt.soDongBoQua,
    dayTran: vt.dayTran,
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
    // Bỏ hai mảng BĂM khỏi truy vấn danh sách (H2c): mỗi bản ghi có thể tới
    // hàng chục nghìn chuỗi, kéo về cho mọi lần mở trang là phí vô ích. Phần
    // metadata vẫn về, riêng `soBam` sẽ là `null` (xem `thongTinVanTay`) —
    // cần con số đó thì gọi `GET /:id`.
    const list = await FlowBlueprint.find({ ownerDeviceId: request.device._id })
      .select('-evidenceFingerprint.dai -evidenceFingerprint.ngan')
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

    // Lớp chặn chi phí thứ 3 (hạn mức ngày). Route này gọi thẳng
    // `gateway.assist()` nên không đi qua chỗ kiểm của `/v1/ai/assist` —
    // thiếu lớp này thì rate-limit theo phút chỉ chặn được người bấm dồn
    // dập, không chặn được một vòng lặp hỏng chạy cả ngày.
    const hetHanMuc = await kiemHanMucNgay(config, device.fingerprint, 'viral_flow_blueprint')
    if (hetHanMuc) {
      return reply.code(429).send({ code: 'DAILY_LIMIT', message: hetHanMuc.message })
    }

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
    const batDau = Date.now()
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
      // Nhánh này từng thay MỌI lỗi không phải 400 bằng một câu duy nhất
      // ("Không phân tích được lúc này. Thử lại sau."). Người dùng chạy thật
      // 11/09/2026 mất gần sáu phút và ~88 Vox cho phần đọc chữ, rồi nhận
      // đúng câu đó — không biết nên đợi mạng, đổi video, hay báo lỗi.
      //
      // Máy chủ BIẾT nguyên nhân: `AiError` mang sẵn `code` và câu riêng.
      // Ném đi rồi đoán lại là tự bịt mắt mình.
      //
      // Luôn ghi nhật ký ĐẦY ĐỦ trước, kể cả khi có trả mã riêng: nhật ký
      // chạy của máy chủ là chỗ duy nhất còn `err.stack`.
      request.log.warn({ err, jobId, code: err.code, statusCode: err.statusCode },
        'flow_blueprint analysis failed')

      // Lỗi do gateway CHỦ ĐỘNG dựng (có `code`) thì chuyển nguyên vẹn: nó
      // đã được viết cho người đọc. Chỉ lỗi trần — mạng đứt, socket rơi —
      // mới là ca "thử lại sau" thật sự.
      if (err.code && err.statusCode) {
        // 503 GIỮ NGUYÊN 503 kèm `retryAfter`. Bản đầu của đoạn này ép mọi
        // mã >= 500 về 502 và làm mất `retryAfter` — tức nói với máy khách
        // rằng lỗi nằm ở phía nó, cho đúng ca hay gặp nhất trong thực tế:
        // `callWithFallback` ném `PROVIDER_UNAVAILABLE` với statusCode 503
        // khi hết nhà cung cấp (ai-gateway.service.js:349).
        if (err.statusCode === 503) {
          return reply.code(503).send({
            code: err.code, message: err.message, retryAfter: 30,
          })
        }
        return reply.code(err.statusCode < 500 ? err.statusCode : 502).send({
          code: err.code,
          message: err.message,
        })
      }
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

    // H2c — dựng dấu vân tay MỘT CHIỀU của bằng chứng NGAY TẠI ĐÂY, chỗ duy
    // nhất còn nhìn thấy transcript/OCR thô trước khi chúng bị bỏ đi cùng
    // request. Không lưu chữ, chỉ lưu băm (xem dau-van-tay.service.js).
    const bcTranscript = dauVanTay.locBangChungDaXacNhan(transcript)
    const bcOcr = dauVanTay.locBangChungDaXacNhan(ocrEvidence)
    const vanTay = dauVanTay.taoDauVanTay([...bcTranscript.dong, ...bcOcr.dong])
    if (vanTay) vanTay.soDongBoQua = bcTranscript.soBoQua + bcOcr.soBoQua

    const doc = await FlowBlueprint.create({
      ownerDeviceId: device._id,
      sourceType,
      sourceReference,
      status: 'ready',
      languageSourceDetected,
      evidenceSummary,
      samplingPolicyUsed,
      // Tình trạng bằng chứng do MÁY CHỦ suy từ bằng chứng OCR máy khách gửi
      // lên, không phải do mô hình khai. Xem `trangThaiBangChung()`: trước
      // đây trường này không có đường nào được ghi nên mọi đoạn đều rơi về
      // `default: 'ok'`, tức bằng chứng rác cũng được chấm là sạch.
      beats: result.beats.map((b) => ({
        ...b,
        evidenceStatus: assistPrompts.trangThaiBangChung(
          b.startS, b.endS, ocrEvidence),
      })),
      evidenceFingerprint: vanTay,
    })

    const response = { ...view(doc), creditCharged: paid.charged, balanceAfter: paid.balanceAfter }
    await Promise.all([
      remember(jobId, device.fingerprint, 'flow_blueprint', response, paid.charged),
      ghiSoDung({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: 'viral_flow_blueprint',
        assistRole: result.role,
        assistPromptVersion: assistPrompts.PROMPT_VERSION,
        // Trước ghi cứng `durationMs: 0` và bỏ trống mọi số liệu khác — tức
        // là không có gì để dựa vào khi cần định giá lại hay tìm lượt chạy
        // chậm. Ghi thật từ đây.
        inputSize: (transcript || []).length + (ocrEvidence || []).length,
        aiProvider: result.provider,
        aiModel: result.model,
        promptTokens: result.usage?.promptTokens || 0,
        completionTokens: result.usage?.completionTokens || 0,
        durationMs: Date.now() - batDau,
        creditCharged: paid.charged,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }).catch(() => {}),
    ])

    return reply.code(201).send(response)
  })
}
