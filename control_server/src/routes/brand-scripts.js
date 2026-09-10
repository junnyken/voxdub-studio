'use strict'

/**
 * `/v1/brand-scripts` — mini-spec H3 (docs/MINI-SPEC_H3_Brand_Script_Rewrite.md).
 *
 * Sinh kịch bản mới cho một brand từ nhịp kể chuyện của một Flow Blueprint,
 * rồi chạy HAI lớp kiểm trước khi cho phép dùng tiếp sang H4:
 *   - tuân thủ  — kịch bản có chứa cụm brand tự cấm không;
 *   - nguyên gốc — kịch bản có vô tình trùng câu chữ video tham khảo không.
 *
 * **`status` chỉ do engine tính**, không có endpoint nào cho client đặt
 * thẳng. Không có đường nào bỏ qua bước kiểm — đó là toàn bộ lý do tồn tại
 * của mini-spec này.
 *
 * Cả `flowBlueprintId` lẫn `brandProfileId` đều phải thuộc ĐÚNG thiết bị đang
 * gọi. Kiểm chéo cả hai, không chỉ kiểm bản ghi mới: tham chiếu tới dữ liệu
 * của thiết bị khác là một đường rò rỉ, dù bản ghi tạo ra có gắn đúng chủ.
 */
const BrandScript = require('../models/BrandScript')
const BrandProfile = require('../models/BrandProfile')
const FlowBlueprint = require('../models/FlowBlueprint')
const assistPrompts = require('../prompts/assist')
const gateway = require('../services/ai-gateway.service')
const config = require('../services/config.service')
const { replay, remember, precheck, charge } = require('../services/assist-billing.service')
const dauVanTay = require('../services/dau-van-tay.service')
const kiem = require('../services/kiem-kich-ban.service')

/**
 * Trường hồ sơ brand BẮT BUỘC phải có nội dung trước khi sinh kịch bản.
 *
 * Constraint 7 của H3: thiếu thì BÁO NGƯỜI DÙNG BỔ SUNG, tuyệt đối không để
 * mô hình tự bịa. Một USP bịa ra nghe rất hợp lý và sẽ đi thẳng vào quảng cáo
 * thật của người ta.
 */
const TRUONG_BRAND_BAT_BUOC = [
  ['moTaSanPham', 'mô tả sản phẩm'],
  ['doiTuongKhach', 'đối tượng khách'],
  ['toneGiong', 'giọng điệu'],
  ['usp', 'điểm mạnh (USP)'],
]

function view(doc) {
  return {
    id: String(doc._id),
    flowBlueprintId: String(doc.flowBlueprintId),
    brandProfileId: String(doc.brandProfileId),
    status: doc.status,
    originalityCheckVersion: doc.originalityCheckVersion,
    beats: (doc.beats || []).map((b) => ({
      beatType: b.beatType,
      voiceoverTextVi: b.voiceoverTextVi,
      captionSuggestionVi: b.captionSuggestionVi,
      visualBriefVi: b.visualBriefVi,
      originalityFlag: b.originalityFlag,
      flaggedExcerpt: b.flaggedExcerpt,
      lyDoChuaKiem: b.lyDoChuaKiem,
      complianceFlag: b.complianceFlag,
      complianceExcerpt: b.complianceExcerpt,
      complianceRule: b.complianceRule,
    })),
    createdAt: doc.createdAt,
    updatedAt: doc.updatedAt,
  }
}

/** `:id` sai khuôn ObjectId coi như không thấy, không phải 500 — cùng cách
 * xử lý đã có ở H1/H2. */
async function timCuaThietBi(Model, id, ownerDeviceId) {
  try {
    return await Model.findOne({ _id: id, ownerDeviceId })
  } catch (err) {
    if (err.name === 'CastError') return null
    throw err
  }
}

/**
 * Đọc lại trạng thái đã lưu, hạ cấp nếu bộ kiểm đã đổi phiên bản.
 *
 * Constraint 13 của H3: một kịch bản được duyệt `ready` bằng luật CŨ mà vẫn
 * hiện `ready` mãi mãi là nói dối người dùng — luật đã đổi thì lần duyệt cũ
 * không còn giá trị. Chỉ hạ lúc ĐỌC, không ghi đè DB: bản ghi vẫn giữ nguyên
 * lịch sử nó từng được duyệt bằng phiên bản nào.
 */
function trangThaiHienTai(doc) {
  if (doc.status === 'ready' && doc.originalityCheckVersion !== dauVanTay.PHIEN_BAN) {
    return 'unconfirmed'
  }
  return doc.status
}

function viewCapNhat(doc) {
  return { ...view(doc), status: trangThaiHienTai(doc) }
}

const createBodySchema = {
  type: 'object',
  required: ['jobId', 'flowBlueprintId', 'brandProfileId'],
  properties: {
    jobId: { type: 'string', minLength: 8, maxLength: 100 },
    flowBlueprintId: { type: 'string', minLength: 1, maxLength: 100 },
    brandProfileId: { type: 'string', minLength: 1, maxLength: 100 },
    holdId: { type: 'string', minLength: 8, maxLength: 100 },
  },
}

const regenBodySchema = {
  type: 'object',
  required: ['jobId', 'beatIndex'],
  properties: {
    jobId: { type: 'string', minLength: 8, maxLength: 100 },
    beatIndex: { type: 'integer', minimum: 0 },
    holdId: { type: 'string', minLength: 8, maxLength: 100 },
  },
}

module.exports = async function brandScriptRoutes(fastify) {
  const { requireDevice } = require('../middleware/auth.middleware')
  fastify.addHook('preHandler', requireDevice)

  fastify.get('/', async (request) => {
    const list = await BrandScript.find({ ownerDeviceId: request.device._id })
      .sort({ createdAt: -1 }).lean()
    return { data: list.map(viewCapNhat) }
  })

  fastify.get('/:id', async (request, reply) => {
    const doc = await timCuaThietBi(BrandScript, request.params.id, request.device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_KICH_BAN', message: 'Không thấy kịch bản này.' })
    }
    return viewCapNhat(doc)
  })

  fastify.delete('/:id', async (request, reply) => {
    const doc = await timCuaThietBi(BrandScript, request.params.id, request.device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_KICH_BAN', message: 'Không thấy kịch bản này.' })
    }
    await doc.deleteOne()
    return { ok: true }
  })

  fastify.post('/', {
    config: { rateLimit: { max: 10, timeWindow: '1 minute' } },
    schema: { body: createBodySchema },
  }, async (request, reply) => {
    const { device } = request
    if (await config.get('maintenance.mode')) {
      return reply.code(503).send({
        code: 'MAINTENANCE', message: 'Máy chủ đang bảo trì, thử lại sau.' })
    }

    const { jobId, flowBlueprintId, brandProfileId, holdId } = request.body

    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    // Kiểm chéo ownership CẢ HAI tham chiếu. Dùng chung mã 404 cho "không tồn
    // tại" và "của thiết bị khác" — đúng style H1/H2, cố ý không tiết lộ dữ
    // liệu của thiết bị khác có tồn tại hay không.
    const blueprint = await timCuaThietBi(FlowBlueprint, flowBlueprintId, device._id)
    if (!blueprint) {
      return reply.code(404).send({
        code: 'KHONG_THAY_BLUEPRINT', message: 'Không thấy Flow Blueprint này.' })
    }
    const brand = await timCuaThietBi(BrandProfile, brandProfileId, device._id)
    if (!brand) {
      return reply.code(404).send({
        code: 'KHONG_THAY_HO_SO', message: 'Không thấy hồ sơ brand này.' })
    }

    const thieu = TRUONG_BRAND_BAT_BUOC
      .filter(([khoa]) => !String(brand[khoa] || '').trim())
      .map(([, ten]) => ten)
    if (thieu.length) {
      return reply.code(400).send({
        code: 'HO_SO_BRAND_THIEU',
        message: `Hồ sơ brand còn thiếu: ${thieu.join(', ')}. `
          + 'Bổ sung rồi tạo lại — những mục này không thể để máy tự nghĩ hộ.',
        thieu,
      })
    }

    if (!(blueprint.beats || []).length) {
      return reply.code(400).send({
        code: 'BLUEPRINT_RONG',
        message: 'Flow Blueprint này chưa có đoạn nào để dựng kịch bản.' })
    }

    const spec = assistPrompts.getTask('brand_script_rewrite')
    const cfg = await config.getMany(['credit.enabled', spec.costKey])
    const cost = cfg['credit.enabled'] ? (cfg[spec.costKey] || 0) : 0

    const lacking = await precheck(device.fingerprint, holdId, cost,
      { action: 'brand_script', jobId })
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
        task: 'brand_script_rewrite',
        input: dungInput(blueprint, brand),
        images: [],
      })
    } catch (err) {
      if (err.statusCode === 400) {
        return reply.code(400).send({ code: err.code || 'BAD_REQUEST', message: err.message })
      }
      request.log.warn({ err, jobId }, 'brand_script_rewrite failed')
      return reply.code(503).send({
        code: 'AI_UNAVAILABLE',
        message: 'Chưa viết được kịch bản lúc này. Thử lại sau.',
        retryAfter: 30,
      })
    }

    const paid = await charge(device, {
      holdId, jobId, action: 'brand_script', walletCost: cost, internalVox: 0,
      description: 'Viết lại kịch bản cho brand', ip: request.ip,
    })

    const daKiem = kiem.kiemToanBo(result.beats, {
      rangBuocKhongDuocNoi: brand.rangBuocKhongDuocNoi || [],
      vanTay: blueprint.evidenceFingerprint,
      beatsNguon: blueprint.beats,
    })

    const doc = await BrandScript.create({
      ownerDeviceId: device._id,
      flowBlueprintId: blueprint._id,
      brandProfileId: brand._id,
      status: daKiem.status,
      originalityCheckVersion: dauVanTay.PHIEN_BAN,
      beats: daKiem.beats,
    })

    const response = { ...view(doc), creditCharged: paid.charged, balanceAfter: paid.balanceAfter }
    await Promise.all([
      remember(jobId, device.fingerprint, 'brand_script', response, paid.charged),
      require('../models/UsageLog').create({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: 'brand_script_rewrite',
        assistRole: result.role,
        assistPromptVersion: assistPrompts.PROMPT_VERSION,
        // Ghi lại phán quyết để đếm được tỉ lệ bị chặn — nếu không, không ai
        // biết bộ kiểm đang gắt hay đang dễ dãi khi đi hiệu chỉnh ngưỡng.
        verdict: daKiem.status,
        creditCharged: paid.charged,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }).catch(() => {}),
    ])

    return reply.code(201).send(response)
  })

  /**
   * Tạo lại MỘT đoạn, nhưng kiểm lại TOÀN BỘ script (Constraint 11).
   *
   * Đoạn mới có thể vô tình trùng với bằng chứng mà một đoạn khác — đã từng
   * sạch — không hề đụng tới. Chỉ kiểm đoạn vừa sửa sẽ tạo ra một trạng thái
   * "nửa vá": trông sạch nhưng chưa bao giờ được xác nhận lại toàn bộ.
   */
  fastify.post('/:id/regenerate-beat', {
    config: { rateLimit: { max: 20, timeWindow: '1 minute' } },
    schema: { body: regenBodySchema },
  }, async (request, reply) => {
    const { device } = request
    if (await config.get('maintenance.mode')) {
      return reply.code(503).send({
        code: 'MAINTENANCE', message: 'Máy chủ đang bảo trì, thử lại sau.' })
    }

    const { jobId, beatIndex, holdId } = request.body
    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    const doc = await timCuaThietBi(BrandScript, request.params.id, device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_KICH_BAN', message: 'Không thấy kịch bản này.' })
    }
    if (beatIndex >= (doc.beats || []).length) {
      return reply.code(400).send({
        code: 'DOAN_KHONG_TON_TAI', message: 'Không có đoạn số đó trong kịch bản.' })
    }

    const blueprint = await timCuaThietBi(FlowBlueprint, doc.flowBlueprintId, device._id)
    const brand = await timCuaThietBi(BrandProfile, doc.brandProfileId, device._id)
    if (!blueprint || !brand) {
      // Xoá dây chuyền (Constraint 14): nguồn đã mất thì không kiểm lại được,
      // nên KHÔNG được giữ `ready` — hạ về `unconfirmed` và nói rõ lý do.
      doc.status = 'unconfirmed'
      doc.beats = (doc.beats || []).map((b) => ({
        ...(b.toObject ? b.toObject() : b),
        originalityFlag: 'unconfirmed',
        flaggedExcerpt: '',
        lyDoChuaKiem: 'bang_chung_khong_du',
      }))
      await doc.save()
      return reply.code(409).send({
        code: 'NGUON_DA_MAT',
        message: 'Flow Blueprint hoặc hồ sơ brand gốc đã bị xoá — không kiểm '
          + 'lại được kịch bản này.',
      })
    }

    const spec = assistPrompts.getTask('brand_script_rewrite')
    const cfg = await config.getMany(['credit.enabled', spec.costKey])
    const cost = cfg['credit.enabled'] ? (cfg[spec.costKey] || 0) : 0

    const lacking = await precheck(device.fingerprint, holdId, cost,
      { action: 'brand_script', jobId })
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
        task: 'brand_script_rewrite',
        input: dungInput(blueprint, brand, {
          vietLaiDoan: beatIndex + 1,
          doanDangCo: (doc.beats || []).map((b) => b.voiceoverTextVi),
          lyDoVietLai: lyDoVietLai(doc.beats?.[beatIndex]),
        }),
        images: [],
      })
    } catch (err) {
      request.log.warn({ err, jobId, beatIndex }, 'regenerate-beat failed')
      return reply.code(503).send({
        code: 'AI_UNAVAILABLE',
        message: 'Chưa viết lại được đoạn này. Thử lại sau.',
        retryAfter: 30,
      })
    }

    const paid = await charge(device, {
      holdId, jobId, action: 'brand_script', walletCost: cost, internalVox: 0,
      description: `Viết lại đoạn ${beatIndex + 1}`, ip: request.ip,
    })

    // CHỈ thay đúng đoạn người dùng yêu cầu, giữ nguyên các đoạn khác...
    const beatsMoi = (doc.beats || []).map((b, i) => (
      i === beatIndex ? result.beats[i] : (b.toObject ? b.toObject() : b)))
    // ...nhưng chạy lại cả hai bộ kiểm cho TOÀN BỘ.
    const daKiem = kiem.kiemToanBo(beatsMoi, {
      rangBuocKhongDuocNoi: brand.rangBuocKhongDuocNoi || [],
      vanTay: blueprint.evidenceFingerprint,
      beatsNguon: blueprint.beats,
    })

    doc.beats = daKiem.beats
    doc.status = daKiem.status
    doc.originalityCheckVersion = dauVanTay.PHIEN_BAN
    await doc.save()

    const response = { ...view(doc), creditCharged: paid.charged, balanceAfter: paid.balanceAfter }
    await remember(jobId, device.fingerprint, 'brand_script', response, paid.charged)
    return response
  })
}

/** Vì sao đoạn này phải viết lại — nói cho mô hình biết để nó tránh đúng chỗ
 * đã sai, thay vì viết lại ngẫu nhiên rồi vẫn dính lần nữa. KHÔNG gửi cụm bị
 * chặn của video nguồn (ta cũng không có), chỉ gửi cụm trong kịch bản mình. */
function lyDoVietLai(beat) {
  if (!beat) return ''
  if (beat.complianceFlag === 'violated') {
    return `đoạn cũ chứa cụm bị cấm "${beat.complianceExcerpt || ''}"`
  }
  if (beat.originalityFlag === 'flagged') {
    return `đoạn cũ trùng câu chữ video nguồn ở cụm "${beat.flaggedExcerpt || ''}"`
  }
  return 'người dùng muốn một phương án khác'
}

/** Dữ liệu gửi cho mô hình: CHỈ phần trừu tượng của Blueprint + hồ sơ brand.
 * Không gửi `sourceReference` hay bất cứ thứ gì dẫn về video gốc.
 *
 * `vietLai` (tuỳ chọn) cho lượt "viết lại đoạn N": thiếu nó thì đầu vào y hệt
 * lượt trước và mô hình trả về gần như y hệt — nút viết lại trông như hỏng
 * trong khi vẫn tính tiền mỗi lần bấm. */
function dungInput(blueprint, brand, vietLai) {
  return {
    ...(vietLai || {}),
    beats: (blueprint.beats || []).map((b) => ({
      beatType: b.beatType,
      narrativeFunctionVi: b.narrativeFunctionVi,
      pacingNoteVi: b.pacingNoteVi,
    })),
    brand: {
      tenBrand: brand.tenBrand,
      moTaSanPham: brand.moTaSanPham,
      doiTuongKhach: brand.doiTuongKhach,
      toneGiong: brand.toneGiong,
      usp: brand.usp,
      rangBuocKhongDuocNoi: brand.rangBuocKhongDuocNoi || [],
    },
  }
}
