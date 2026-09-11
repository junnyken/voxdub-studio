'use strict'

/**
 * `/v1/brand-profiles` — mini-spec H1 (docs/PLAN.md, Phase H).
 *
 * MỘT thiết bị (không có khái niệm "tài khoản" tách rời — xem
 * `models/BrandProfile.js`) có thể tạo NHIỀU hồ sơ brand, mỗi hồ sơ độc lập.
 * Cách ly theo `ownerDeviceId` lấy TỪ token xác thực (`request.device._id`),
 * KHÔNG BAO GIỜ nhận từ client — tái dùng nguyên `requireDevice`
 * (auth.middleware.js) trên cả bốn cửa, không dựng cơ chế xác thực mới.
 *
 * Nơi gọi: `autodub_gui` (trang Hồ sơ Brand, chưa làm ở H1 — Scope D) qua
 * `autodub/saas_client.py`, cùng đường device-token với cổng trợ lý AI.
 */
const BrandProfile = require('../models/BrandProfile')

function view(doc) {
  return {
    id: String(doc._id),
    tenBrand: doc.tenBrand,
    moTaSanPham: doc.moTaSanPham,
    doiTuongKhach: doc.doiTuongKhach,
    toneGiong: doc.toneGiong,
    usp: doc.usp,
    rangBuocKhongDuocNoi: doc.rangBuocKhongDuocNoi,
    createdAt: doc.createdAt,
    updatedAt: doc.updatedAt,
  }
}

/** Đúng những trường người dùng được phép đặt. `ownerDeviceId` KHÔNG nằm ở
 * đây và không bao giờ được nằm ở đây — nó lấy từ token, xem `POST` bên dưới. */
const TRUONG_CHO_PHEP = ['tenBrand', 'moTaSanPham', 'doiTuongKhach',
  'toneGiong', 'usp', 'rangBuocKhongDuocNoi']

const bodySchema = {
  type: 'object',
  required: ['tenBrand', 'rangBuocKhongDuocNoi'],
  // `additionalProperties: false` là thứ CHẶN THẬT, không phải cho đẹp.
  //
  // Đo thật 10/09/2026 với đúng cấu hình ajv của fastify (`removeAdditional:
  // true`): thiếu dòng này thì trường lạ KHÔNG bị xoá, nó đi thẳng vào
  // `request.body`. Cộng với `Object.assign(doc, request.body)` ở `PUT`,
  // mongoose nhận gán lại `ownerDeviceId` mà `validateSync()` không kêu —
  // nghĩa là máy A gửi kèm `ownerDeviceId` của máy B thì hồ sơ **chuyển sang
  // máy B**. `POST` thoát nạn chỉ vì nó đặt `ownerDeviceId` SAU phần spread.
  additionalProperties: false,
  properties: {
    tenBrand: { type: 'string', minLength: 1, maxLength: 120 },
    moTaSanPham: { type: 'string', maxLength: 2000, default: '' },
    doiTuongKhach: { type: 'string', maxLength: 1000, default: '' },
    toneGiong: { type: 'string', maxLength: 200, default: '' },
    usp: { type: 'string', maxLength: 1000, default: '' },
    // Constraint 2 của H1: bắt buộc CÓ MẶT (mảng, có thể rỗng) — người dùng
    // phải đi qua bước hỏi ràng buộc, không được lặng lẽ vắng mặt trường
    // này. Đánh dấu `required` ở dưới (không đặt `default` — mặc định chỉ
    // áp dụng khi trường VẮNG MẶT, mà "required" đã chặn đúng ca đó trước
    // cả khi default có cơ hội chạy, nên đặt cả hai chỉ gây hiểu lầm).
    rangBuocKhongDuocNoi: {
      type: 'array', items: { type: 'string', maxLength: 300 },
    },
  },
}

/** `:id` sai khuôn ObjectId (CastError) coi như không thấy, không phải 500
 * — cùng cách xử lý đã có ở `dub-job.service.js` cho cùng bẫy này. */
async function timHoSoCuaThietBi(id, ownerDeviceId) {
  try {
    return await BrandProfile.findOne({ _id: id, ownerDeviceId })
  } catch (err) {
    if (err.name === 'CastError') return null
    throw err
  }
}

module.exports = async function brandProfileRoutes(fastify) {
  const { requireDevice } = require('../middleware/auth.middleware')
  fastify.addHook('preHandler', requireDevice)

  fastify.get('/', async (request) => {
    const list = await BrandProfile.find({ ownerDeviceId: request.device._id })
      .sort({ createdAt: -1 }).lean()
    return { data: list.map(view) }
  })

  fastify.post('/', { schema: { body: bodySchema } }, async (request, reply) => {
    const doc = await BrandProfile.create({
      ...request.body, ownerDeviceId: request.device._id,
    })
    return reply.code(201).send(view(doc))
  })

  fastify.put('/:id', { schema: { body: bodySchema } }, async (request, reply) => {
    const doc = await timHoSoCuaThietBi(request.params.id, request.device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_HO_SO', message: 'Không thấy hồ sơ brand này.' })
    }
    // Chép theo DANH SÁCH TRẮNG, không `Object.assign(doc, request.body)`:
    // hai lớp chặn cho cùng một lỗ, vì lớp schema ở trên chỉ cần một lần ai
    // đó thêm trường mới mà quên là hở lại.
    for (const truong of TRUONG_CHO_PHEP) {
      if (Object.prototype.hasOwnProperty.call(request.body, truong)) {
        doc[truong] = request.body[truong]
      }
    }
    await doc.save()
    return view(doc)
  })

  fastify.delete('/:id', async (request, reply) => {
    const doc = await timHoSoCuaThietBi(request.params.id, request.device._id)
    if (!doc) {
      return reply.code(404).send({
        code: 'KHONG_THAY_HO_SO', message: 'Không thấy hồ sơ brand này.' })
    }
    await doc.deleteOne()
    return { ok: true }
  })
}
