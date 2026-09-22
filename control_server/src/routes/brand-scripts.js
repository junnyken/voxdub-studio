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
const { replay, remember, ghiSoDung, precheck, charge, kiemHanMucNgay } = require('../services/assist-billing.service')
const dauVanTay = require('../services/dau-van-tay.service')
const kiem = require('../services/kiem-kich-ban.service')
const chiDao = require('../services/visual-direction.service')

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
      chamCumNgan: b.chamCumNgan || '',
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
function trangThaiHienTai(doc, nguon) {
  if (doc.status !== 'ready') return doc.status
  if (doc.originalityCheckVersion !== dauVanTay.PHIEN_BAN) return 'unconfirmed'
  if (!nguon) return doc.status

  // RS-2 — xoá dây chuyền. Trước đây việc này CHỈ được phát hiện ở
  // `regenerate-beat`; ai chỉ mở danh sách rồi bấm «Dùng kịch bản này» thì
  // thấy `ready` như thường, dù bằng chứng để kiểm lại đã không còn. Cùng
  // một Constraint 14, chỉ là trước nay thiếu một nửa số cửa.
  if (nguon.thieuNguon) return 'unconfirmed'

  // RS-1 — ràng buộc brand đã đổi kể từ lần kiểm. Chuỗi rỗng nghĩa là bản
  // ghi tạo trước RS-1: không biết lần đó kiểm bằng luật gì, mà hạ cấp dựa
  // trên "không biết" là đoán. Để nguyên, và mọi bản ghi mới đều có dấu.
  if (doc.brandRulesFingerprint
      && nguon.vanTayRangBuoc
      && doc.brandRulesFingerprint !== nguon.vanTayRangBuoc) {
    return 'unconfirmed'
  }
  return doc.status
}

/** Gom nguồn cho một lô kịch bản trong 2 truy vấn, không phải 2 truy vấn MỖI
 * kịch bản — danh sách 50 bản ghi mà hỏi từng cái là 100 lượt đi DB. */
async function gomNguon(docs, ownerDeviceId) {
  const idBrand = [...new Set(docs.map((d) => String(d.brandProfileId)))]
  const idBp = [...new Set(docs.map((d) => String(d.flowBlueprintId)))]
  const [brands, bps] = await Promise.all([
    BrandProfile.find({ _id: { $in: idBrand }, ownerDeviceId }).lean(),
    FlowBlueprint.find({ _id: { $in: idBp }, ownerDeviceId })
      .select('_id').lean(),
  ])
  const theoBrand = new Map(brands.map((b) => [String(b._id), b]))
  const coBp = new Set(bps.map((b) => String(b._id)))
  return (doc) => {
    const brand = theoBrand.get(String(doc.brandProfileId))
    return {
      thieuNguon: !brand || !coBp.has(String(doc.flowBlueprintId)),
      vanTayRangBuoc: brand
        ? kiem.vanTayRangBuoc(brand.rangBuocKhongDuocNoi || [])
        : '',
    }
  }
}

function viewCapNhat(doc, nguon) {
  return { ...view(doc), status: trangThaiHienTai(doc, nguon) }
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
    if (!list.length) return { data: [] }
    const nguonCua = await gomNguon(list, request.device._id)
    return { data: list.map((d) => viewCapNhat(d, nguonCua(d))) }
  })

  fastify.get('/:id', async (request, reply) => {
    const doc = await timCuaThietBi(BrandScript, request.params.id, request.device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_KICH_BAN', message: 'Không thấy kịch bản này.' })
    }
    const nguonCua = await gomNguon([doc], request.device._id)
    return viewCapNhat(doc, nguonCua(doc))
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

    // RS-3 — CHẶN TRƯỚC KHI TRỪ TIỀN.
    //
    // `kiemNguyenGoc` có đúng ba ca khiến MỌI beat ra `unconfirmed`, tức
    // kịch bản KHÔNG ĐỜI NÀO đạt `ready`, tức cổng sang H4 không bao giờ mở.
    // Cả ba đều biết được từ bây giờ, trước khi gọi mô hình. Thu 12 Vox cho
    // một lượt đã biết chắc kết quả không dùng được là bán một thứ không tồn
    // tại — cùng loại với hai cổng `HO_SO_BRAND_THIEU`/`BLUEPRINT_RONG` ngay
    // trên, chỉ là trước nay thiếu ca này.
    const vt = blueprint.evidenceFingerprint
    const canChan = !vt ? 'khong_co_dau_van_tay'
      : vt.v !== dauVanTay.PHIEN_BAN ? 'khac_phien_ban'
        : vt.dayTran ? 'day_tran' : ''
    if (canChan) {
      const vi = {
        khong_co_dau_van_tay: 'lượt phân tích này chạy trước khi máy chủ biết '
          + 'lưu dấu vân tay bằng chứng',
        khac_phien_ban: 'dấu vân tay của lượt phân tích này dựng bằng thuật '
          + 'toán đời khác',
        day_tran: 'lượt phân tích này có quá nhiều bằng chứng nên dấu vân tay '
          + 'không phủ hết',
      }[canChan]
      return reply.code(400).send({
        code: 'BLUEPRINT_KHONG_KIEM_DUOC',
        lyDo: canChan,
        message: `Không đối chiếu được kịch bản với video nguồn vì ${vi}. `
          + 'Kịch bản viết ra sẽ không bao giờ được duyệt, nên chưa trừ Vox. '
          + 'Hãy phân tích lại video tham khảo rồi dùng lượt phân tích mới.',
      })
    }

    const spec = assistPrompts.getTask('brand_script_rewrite')
    const cfg = await config.getMany(['credit.enabled', spec.costKey])
    const cost = cfg['credit.enabled'] ? (cfg[spec.costKey] || 0) : 0

    // Lớp chặn chi phí thứ 3 (hạn mức ngày). Route này gọi thẳng
    // `gateway.assist()` nên không đi qua chỗ kiểm của `/v1/ai/assist` —
    // thiếu lớp này thì rate-limit theo phút chỉ chặn được người bấm dồn
    // dập, không chặn được một vòng lặp hỏng chạy cả ngày.
    const hetHanMuc = await kiemHanMucNgay(config, device.fingerprint, 'brand_script_rewrite')
    if (hetHanMuc) {
      return reply.code(429).send({ code: 'DAILY_LIMIT', message: hetHanMuc.message })
    }

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
    const batDau = Date.now()
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
      // I1 bước 3 — ca "chưa cắm nhà cung cấp vai trợ lý" nói câu riêng:
      // "Thử lại sau" là lời khuyên sai cho một lỗi cấu hình.
      if (gateway.laLoiChuaCoNoiGoiTroLy(err)) {
        return reply.code(503).send({ code: err.code, message: err.message })
      }
      if (err.code === 'BAD_AI_RESPONSE') {
        return reply.code(502).send({
          code: 'KICH_BAN_THIEU_DOAN',
          message: 'Mô hình viết thiếu đoạn nên kịch bản bị huỷ — bạn KHÔNG bị trừ Vox. '
          + 'Kịch bản càng nhiều đoạn càng hay gặp lỗi này. Thử lại một lượt; '
          + 'nếu vẫn vậy thì báo quản trị viên đổi mô hình cho vai «trợ lý».',
        })
      }
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
      // RS-1 — ghi luật ĐÃ DÙNG, để lần đọc sau biết luật có đổi không.
      brandRulesFingerprint: kiem.vanTayRangBuoc(brand.rangBuocKhongDuocNoi || []),
      beats: daKiem.beats,
    })

    const response = { ...view(doc), creditCharged: paid.charged, balanceAfter: paid.balanceAfter }
    await Promise.all([
      remember(jobId, device.fingerprint, 'brand_script', response, paid.charged),
      ghiSoDung({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: 'brand_script_rewrite',
        assistRole: result.role,
        assistPromptVersion: assistPrompts.PROMPT_VERSION,
        // Ghi lại phán quyết để đếm được tỉ lệ bị chặn — nếu không, không ai
        // biết bộ kiểm đang gắt hay đang dễ dãi khi đi hiệu chỉnh ngưỡng.
        verdict: daKiem.status,
        // Số liệu để về sau chốt lại GIÁ: hiện thu 12 Vox phẳng, trong khi
        // kịch bản 40 đoạn tốn hơn hẳn 5 đoạn. Không ghi từ bây giờ thì tới
        // lúc cần định giá lại sẽ không có gì để dựa vào ngoài phỏng đoán.
        inputSize: (blueprint.beats || []).length,
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
      //
      // RS-6 — nhưng chỉ lớp NGUYÊN GỐC mất chỗ dựa. Lớp TUÂN THỦ so kịch
      // bản với ràng buộc do chính người dùng nhập: cả hai vế vẫn còn, phán
      // quyết `violated` vẫn đúng nguyên. Đè phẳng `blocked` xuống
      // `unconfirmed` là hạ một phán quyết CÒN GIÁ TRỊ xuống thành "chưa
      // kiểm được" — nói sai về thứ đã kiểm rồi, và nhẹ đi một bậc.
      const beatsMoi = (doc.beats || []).map((b) => ({
        ...(b.toObject ? b.toObject() : b),
        originalityFlag: 'unconfirmed',
        flaggedExcerpt: '',
        lyDoChuaKiem: 'bang_chung_khong_du',
      }))
      doc.beats = beatsMoi
      // Tính lại bằng ĐÚNG bảng ưu tiên của engine, không đặt tay: có beat
      // nào `violated` ⇒ vẫn `blocked`; còn lại ⇒ `unconfirmed`.
      // Tính trên `beatsMoi` chứ không đọc lại `doc.beats`: sau khi gán,
      // `doc.beats` là DocumentArray của Mongoose — thêm một tầng chuyển đổi
      // giữa thứ mình vừa tính và thứ mình đang đo.
      doc.status = kiem.tinhTrangThai(beatsMoi)
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

    // Lớp chặn chi phí thứ 3 (hạn mức ngày). Route này gọi thẳng
    // `gateway.assist()` nên không đi qua chỗ kiểm của `/v1/ai/assist` —
    // thiếu lớp này thì rate-limit theo phút chỉ chặn được người bấm dồn
    // dập, không chặn được một vòng lặp hỏng chạy cả ngày.
    const hetHanMuc = await kiemHanMucNgay(config, device.fingerprint, 'brand_script_rewrite')
    if (hetHanMuc) {
      return reply.code(429).send({ code: 'DAILY_LIMIT', message: hetHanMuc.message })
    }

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
    let batDauLai = Date.now()
    try {
      batDauLai = Date.now()
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
      if (gateway.laLoiChuaCoNoiGoiTroLy(err)) {
        return reply.code(503).send({ code: err.code, message: err.message })
      }
      if (err.code === 'BAD_AI_RESPONSE') {
        return reply.code(502).send({
          code: 'KICH_BAN_THIEU_DOAN',
          message: 'Mô hình viết thiếu đoạn nên kịch bản bị huỷ — bạn KHÔNG bị trừ Vox. '
          + 'Kịch bản càng nhiều đoạn càng hay gặp lỗi này. Thử lại một lượt; '
          + 'nếu vẫn vậy thì báo quản trị viên đổi mô hình cho vai «trợ lý».',
        })
      }
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
    // RS-1 — viết lại một đoạn là kiểm lại TOÀN BỘ bằng luật HIỆN TẠI
    // (Constraint 11), nên dấu vân tay luật cũng phải theo bản hiện tại.
    doc.brandRulesFingerprint = kiem.vanTayRangBuoc(brand.rangBuocKhongDuocNoi || [])
    await doc.save()

    const response = { ...view(doc), creditCharged: paid.charged, balanceAfter: paid.balanceAfter }
    await Promise.all([
      remember(jobId, device.fingerprint, 'brand_script', response, paid.charged),
      // Lượt viết lại TRƯỚC ĐÂY không ghi sổ gì cả — nghĩa là "số lần
      // regenerate" (một trong những số liệu cần để định giá lại) không đếm
      // được, và hạn mức ngày cũng không thấy các lượt này.
      ghiSoDung({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: 'brand_script_rewrite',
        assistRole: result.role,
        assistPromptVersion: assistPrompts.PROMPT_VERSION,
        verdict: daKiem.status,
        inputSize: (blueprint.beats || []).length,
        aiProvider: result.provider,
        aiModel: result.model,
        promptTokens: result.usage?.promptTokens || 0,
        completionTokens: result.usage?.completionTokens || 0,
        durationMs: Date.now() - batDauLai,
        creditCharged: paid.charged,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }).catch(() => {}),
    ])
    return response
  })

  // ------------------------------------ bản chỉ đạo hình ảnh (I3) --
  //
  // Vì sao nằm dưới `/v1/brand-scripts/:id/` chứ không phải một nhánh API
  // mới: bản chỉ đạo là 1-1 với kịch bản, và quyền sở hữu + cách tìm theo
  // thiết bị đã có sẵn ở đây. Một nhánh riêng là một đường nữa phải tự kiểm
  // quyền — và đường tự kiểm quyền thứ hai là chỗ rò rỉ IDOR quen thuộc.

  /** Bản chỉ đạo đã lưu, kèm trạng thái còn khớp hay đã cũ. */
  fastify.get('/:id/visual-direction', async (request, reply) => {
    const doc = await timCuaThietBi(BrandScript, request.params.id, request.device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_KICH_BAN', message: 'Không thấy kịch bản này.' })
    }
    if (!doc.visualDirection) {
      return reply.code(404).send({
        code: 'CHUA_CO_CHI_DAO',
        message: 'Kịch bản này chưa có bản chỉ đạo hình ảnh.' })
    }
    return xemChiDao(doc)
  })

  /**
   * Tạo bản chỉ đạo hình ảnh cho CẢ kịch bản bằng MỘT lượt gọi mô hình.
   *
   * Thứ tự ở đây là thứ tự của tiền, và nó cố ý:
   *   1. đọc đệm theo `jobId` (gọi trùng do mạng thì không tính tiền lại);
   *   2. chặn kịch bản chưa `ready` — TRƯỚC khi gọi mô hình;
   *   3. hạn mức ngày, rồi precheck ví;
   *   4. gọi mô hình;
   *   5. **soi đầu ra với từ điển** — hỏng thì trả lỗi và KHÔNG gọi
   *      `charge()`, nên không có đồng nào bị trừ và không cần đường hoàn;
   *   6. lưu, rồi mới trừ tiền và ghi sổ.
   */
  fastify.post('/:id/visual-direction', {
    config: { rateLimit: { max: 20, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['jobId'],
        properties: {
          jobId: { type: 'string', minLength: 8, maxLength: 100 },
          holdId: { type: 'string', minLength: 8, maxLength: 100 },
        },
      },
    },
  }, async (request, reply) => {
    const { device } = request
    if (await config.get('maintenance.mode')) {
      return reply.code(503).send({
        code: 'MAINTENANCE', message: 'Máy chủ đang bảo trì, thử lại sau.' })
    }

    const { jobId, holdId } = request.body
    const cached = await replay(jobId, device.fingerprint)
    if (cached) return cached

    const doc = await timCuaThietBi(BrandScript, request.params.id, device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_KICH_BAN', message: 'Không thấy kịch bản này.' })
    }

    // Chặn TRƯỚC khi gọi mô hình (cùng mẫu RS-3): chỉ đạo hình ảnh cho một
    // kịch bản chưa duyệt là chỉ đạo cho thứ sắp bị viết lại — tiêu tiền cho
    // một bản sắp bỏ đi.
    // `trangThaiHienTai` nhận bản TÓM TẮT NGUỒN (`{thieuNguon, vanTayRangBuoc}`)
    // do `gomNguon` dựng, KHÔNG nhận thẳng tài liệu brand — đưa nhầm tài liệu
    // vào thì hai phép hạ cấp RS-1/RS-2 im lặng không chạy, và một kịch bản
    // đáng lẽ `unconfirmed` sẽ qua cổng này như thể còn `ready`.
    const nguonCua = await gomNguon([doc], device._id)
    const brand = await timCuaThietBi(BrandProfile, doc.brandProfileId, device._id)
    const trangThai = trangThaiHienTai(doc, nguonCua(doc))
    if (trangThai !== 'ready') {
      return reply.code(409).send({
        code: 'KICH_BAN_CHUA_SAN_SANG',
        message: 'Kịch bản chưa ở trạng thái «dùng được». Xử lý các cảnh báo '
          + 'của kịch bản trước, rồi mới lấy chỉ đạo hình ảnh.',
      })
    }
    if (!(doc.beats || []).length) {
      return reply.code(409).send({
        code: 'KICH_BAN_RONG', message: 'Kịch bản không có đoạn nào.' })
    }
    if (!brand) {
      // Tới đây `trangThaiHienTai` đã chặn ca thiếu nguồn, nhưng giữ lớp này
      // để `chiDao.dungInput(doc, brand)` không bao giờ nhận `null`.
      return reply.code(409).send({
        code: 'NGUON_DA_MAT',
        message: 'Hồ sơ brand gốc đã bị xoá — không lấy chỉ đạo hình ảnh được.' })
    }

    const spec = assistPrompts.getTask('scene_director')
    const cfg = await config.getMany(['credit.enabled', spec.costKey])
    const cost = cfg['credit.enabled'] ? (cfg[spec.costKey] || 0) : 0

    const hetHanMuc = await kiemHanMucNgay(config, device.fingerprint, 'scene_director')
    if (hetHanMuc) {
      return reply.code(429).send({ code: 'DAILY_LIMIT', message: hetHanMuc.message })
    }

    const lacking = await precheck(device.fingerprint, holdId, cost,
      { action: 'visual_direction', jobId })
    if (lacking) {
      return reply.code(402).send({
        code: 'INSUFFICIENT_CREDIT',
        message: `Không đủ Vox. Cần ${lacking.required}, bạn có ${lacking.balance}.`,
        balance: lacking.balance,
        required: lacking.required,
      })
    }

    const batDau = Date.now()
    let result
    try {
      result = await gateway.assist({
        task: 'scene_director',
        input: chiDao.dungInput(doc, brand),
        images: [],
      })
    } catch (err) {
      request.log.warn({ err, jobId }, 'scene_director failed')
      if (gateway.laLoiChuaCoNoiGoiTroLy(err)) {
        return reply.code(503).send({ code: err.code, message: err.message })
      }
      if (err.statusCode === 400) {
        return reply.code(400).send({ code: err.code || 'BAD_REQUEST', message: err.message })
      }
      return reply.code(503).send({
        code: 'AI_UNAVAILABLE',
        message: 'Chưa lấy được chỉ đạo hình ảnh lúc này. Thử lại sau.',
        retryAfter: 30,
      })
    }

    // Soi lại TOÀN BỘ đầu ra với từ điển. Mã lạ ⇒ huỷ CẢ lượt, không sửa cho
    // gần đúng: sửa gần đúng là đoán hộ mô hình, mà đoán sai thì không ai
    // biết. Chưa `charge()` nên người dùng không mất đồng nào.
    const soi = chiDao.kiemBanChiDao(result, {
      soDoan: doc.beats.length,
      scriptHash: chiDao.bamKichBan(doc.beats),
    })
    if (!soi.ok) {
      request.log.warn({ jobId, loi: soi.loi }, 'scene_director sai từ điển')
      ghiSoDung({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: 'scene_director',
        assistRole: result.role,
        status: 'error',
        errorCode: chiDao.MA_LOI_SAI_TU_DIEN,
        errorMessage: soi.loi.join('; ').slice(0, 300),
        aiProvider: result.provider,
        aiModel: result.model,
        promptTokens: result.usage?.promptTokens || 0,
        completionTokens: result.usage?.completionTokens || 0,
        durationMs: Date.now() - batDau,
        creditCharged: 0,
        ip: request.ip,
        appVersion: device.appVersion,
      }, request.log)
      return reply.code(502).send({
        code: chiDao.MA_LOI_SAI_TU_DIEN,
        message: 'Kết quả không khớp từ điển chỉ đạo hình ảnh nên đã bị huỷ — '
          + 'bạn KHÔNG bị trừ Vox. Thử lại một lượt nữa.',
        chiTiet: soi.loi.slice(0, 5),
      })
    }

    doc.visualDirection = soi.ban
    await doc.save()

    const paid = await charge(device, {
      holdId, jobId, action: 'visual_direction', walletCost: cost, internalVox: 0,
      description: 'Chỉ đạo hình ảnh cho kịch bản', ip: request.ip,
    })

    const response = {
      ...xemChiDao(doc),
      jobId,
      creditCharged: paid.charged,
      balanceAfter: paid.balanceAfter,
    }
    await Promise.all([
      remember(jobId, device.fingerprint, 'visual_direction', response, paid.charged,
        request.log),
      ghiSoDung({
        fingerprint: device.fingerprint,
        jobId,
        action: 'assist',
        assistTask: 'scene_director',
        assistRole: result.role,
        assistPromptVersion: assistPrompts.PROMPT_VERSION,
        inputSize: doc.beats.length,
        creditCharged: paid.charged,
        aiProvider: result.provider,
        aiModel: result.model,
        promptTokens: result.usage?.promptTokens || 0,
        completionTokens: result.usage?.completionTokens || 0,
        durationMs: Date.now() - batDau,
        status: 'success',
        ip: request.ip,
        appVersion: device.appVersion,
      }, request.log),
    ])

    return reply.code(201).send(response)
  })
}

/**
 * Bản chỉ đạo đem trả ra API.
 *
 * Hai thứ KHÔNG đọc từ dữ liệu đã lưu mà tính lại mỗi lần đọc:
 *   - `laCu` — so với catalog đang chạy và với kịch bản hiện tại;
 *   - `canhBao` — câu nói thẳng tỉ lệ gợi ý / máy dựng được.
 * Lưu sẵn thì một bản lưu từ hôm qua sẽ tự khai mình còn mới.
 */
function xemChiDao(doc) {
  const ban = doc.visualDirection
  const tt = chiDao.trangThaiBan(ban, doc.beats)
  return {
    id: String(doc._id),
    catalogVersion: ban.catalogVersion,
    taoLuc: ban.taoLuc,
    soGoiY: ban.soGoiY,
    soMayDungDuoc: ban.soMayDungDuoc,
    ...tt,
    doan: (ban.doan || []).map((d) => ({
      thuTu: d.thuTu,
      lyDo: d.lyDo,
      chon: (d.chon || []).map((c) => ({
        nhom: c.nhom, ma: c.ma, nhan: c.nhan, laGoiY: c.laGoiY,
      })),
    })),
  }
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
      // H6 — THỜI LƯỢNG của đoạn nguồn. Trước 14/09 hàm này lọc bỏ
      // `startS`/`endS`, nên mô hình KHÔNG BAO GIỜ biết video tham khảo dài
      // bao nhiêu và viết theo độ dài mặc định của văn quảng cáo. Lượt chạy
      // thật của chủ dự án: nguồn 34 giây, kịch bản đọc hết 170 giây — gấp
      // 5 lần, tức đúng cái NHỊP mà cả H2 tốn 64 Vox để học đã bị vứt đi.
      giay: Math.max(0, Number(b.endS || 0) - Number(b.startS || 0)),
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
