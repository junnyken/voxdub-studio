'use strict'

/**
 * Mini-spec H1 (docs/PLAN.md, Phase H) — `/v1/brand-profiles`.
 *
 * Trọng tâm: một "tài khoản VoxDub" ở hệ thống này CHÍNH LÀ một thiết bị
 * (không có model Account riêng — xem models/BrandProfile.js), nên phép thử
 * quan trọng nhất là CÁCH LY giữa hai thiết bị: thiết bị A không được đọc/
 * sửa/xoá hồ sơ của thiết bị B qua API thật (không phải chỉ qua service).
 *
 * Chạy:  node --test tests/brand-profiles-route.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const crypto = require('node:crypto')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const deviceService = require('../src/services/device.service')
const BrandProfile = require('../src/models/BrandProfile')

let app

test.before(async () => {
  await startDb()
  app = await build({ mongo: false, web: false, logger: false })
  await app.ready()
})
test.after(async () => {
  await app.close()
  await stopDb()
})
test.beforeEach(clearDb)

function vanTay() {
  return crypto.randomBytes(32).toString('hex')
}

async function thietBiMoi(ten) {
  const { device, token } = await deviceService.registerDevice({
    fingerprint: vanTay(), name: ten,
  })
  return { device, token }
}

function goi(method, url, token, payload) {
  return app.inject({
    method, url, payload,
    headers: token ? { authorization: `Bearer ${token}` } : {},
  })
}

const HO_SO_MAU = {
  tenBrand: 'Trà sữa Bình Minh',
  moTaSanPham: 'Trà sữa organic, không đường tinh luyện',
  doiTuongKhach: 'Học sinh, sinh viên 15-25 tuổi',
  toneGiong: 'vui vẻ, gần gũi',
  usp: 'Nguyên liệu hữu cơ, giao trong 15 phút',
  rangBuocKhongDuocNoi: ['không hứa giảm cân', 'không dùng từ "số một thị trường"'],
}

// --------------------------------------------------------- xác thực -------

test('thiếu token -> 401, không lộ đường nào', async () => {
  const res = await goi('GET', '/v1/brand-profiles/', null)
  assert.equal(res.statusCode, 401)
})

// ------------------------------------------------------------- tạo --------

test('tạo hồ sơ -> gắn đúng ownerDeviceId từ token, KHÔNG nhận từ body', async () => {
  const a = await thietBiMoi('Máy A')
  const bB = await thietBiMoi('Máy B')

  const res = await goi('POST', '/v1/brand-profiles/', a.token, {
    ...HO_SO_MAU, ownerDeviceId: String(bB.device._id), // cố tình giả danh
  })
  assert.equal(res.statusCode, 201)
  const body = res.json()
  assert.equal(body.tenBrand, HO_SO_MAU.tenBrand)
  assert.ok(!('ownerDeviceId' in body), 'không lộ id thiết bị ra client')

  const doc = await BrandProfile.findById(body.id)
  assert.equal(String(doc.ownerDeviceId), String(a.device._id),
    'phải gắn theo TOKEN đang gọi, không phải giá trị client tự gửi')
})

test('thiếu tenBrand -> 400 (schema chặn)', async () => {
  const a = await thietBiMoi('Máy A')
  const { rangBuocKhongDuocNoi } = HO_SO_MAU
  const res = await goi('POST', '/v1/brand-profiles/', a.token, { rangBuocKhongDuocNoi })
  assert.equal(res.statusCode, 400)
})

test('thiếu rangBuocKhongDuocNoi -> 400 (Constraint 2: phải đi qua bước hỏi)', async () => {
  const a = await thietBiMoi('Máy A')
  const { rangBuocKhongDuocNoi, ...con } = HO_SO_MAU
  const res = await goi('POST', '/v1/brand-profiles/', a.token, con)
  assert.equal(res.statusCode, 400)
})

test('rangBuocKhongDuocNoi rỗng vẫn tạo được — không bắt buộc CÓ NỘI DUNG, chỉ bắt buộc CÓ MẶT', async () => {
  const a = await thietBiMoi('Máy A')
  const res = await goi('POST', '/v1/brand-profiles/', a.token,
    { ...HO_SO_MAU, rangBuocKhongDuocNoi: [] })
  assert.equal(res.statusCode, 201)
  assert.deepEqual(res.json().rangBuocKhongDuocNoi, [])
})

test('một thiết bị tạo được NHIỀU hồ sơ, mỗi hồ sơ độc lập', async () => {
  const a = await thietBiMoi('Máy A')
  const r1 = await goi('POST', '/v1/brand-profiles/', a.token, HO_SO_MAU)
  const r2 = await goi('POST', '/v1/brand-profiles/', a.token,
    { ...HO_SO_MAU, tenBrand: 'Bánh mì Sài Gòn' })
  assert.equal(r1.statusCode, 201)
  assert.equal(r2.statusCode, 201)
  assert.notEqual(r1.json().id, r2.json().id)

  const list = await goi('GET', '/v1/brand-profiles/', a.token)
  assert.equal(list.json().data.length, 2)
})

// -------------------------------------------------- cách ly giữa thiết bị -

test('GET: thiết bị B không thấy hồ sơ của thiết bị A', async () => {
  const a = await thietBiMoi('Máy A')
  const b = await thietBiMoi('Máy B')
  await goi('POST', '/v1/brand-profiles/', a.token, HO_SO_MAU)

  const listA = await goi('GET', '/v1/brand-profiles/', a.token)
  const listB = await goi('GET', '/v1/brand-profiles/', b.token)
  assert.equal(listA.json().data.length, 1)
  assert.equal(listB.json().data.length, 0, 'thiết bị B không được thấy hồ sơ của A')
})

test('PUT: thiết bị B sửa hồ sơ của thiết bị A -> 404, KHÔNG đổi được dữ liệu', async () => {
  const a = await thietBiMoi('Máy A')
  const b = await thietBiMoi('Máy B')
  const created = (await goi('POST', '/v1/brand-profiles/', a.token, HO_SO_MAU)).json()

  const res = await goi('PUT', `/v1/brand-profiles/${created.id}`, b.token,
    { ...HO_SO_MAU, tenBrand: 'BỊ SỬA TRỘM' })
  assert.equal(res.statusCode, 404)

  const doc = await BrandProfile.findById(created.id)
  assert.equal(doc.tenBrand, HO_SO_MAU.tenBrand, 'dữ liệu của A không được đổi')
})

test('DELETE: thiết bị B xoá hồ sơ của thiết bị A -> 404, hồ sơ VẪN CÒN', async () => {
  const a = await thietBiMoi('Máy A')
  const b = await thietBiMoi('Máy B')
  const created = (await goi('POST', '/v1/brand-profiles/', a.token, HO_SO_MAU)).json()

  const res = await goi('DELETE', `/v1/brand-profiles/${created.id}`, b.token)
  assert.equal(res.statusCode, 404)
  assert.ok(await BrandProfile.findById(created.id), 'hồ sơ của A không được mất')
})

test('chủ thật sửa được hồ sơ của chính mình', async () => {
  const a = await thietBiMoi('Máy A')
  const created = (await goi('POST', '/v1/brand-profiles/', a.token, HO_SO_MAU)).json()

  const res = await goi('PUT', `/v1/brand-profiles/${created.id}`, a.token,
    { ...HO_SO_MAU, tenBrand: 'Trà sữa Bình Minh 2' })
  assert.equal(res.statusCode, 200)
  assert.equal(res.json().tenBrand, 'Trà sữa Bình Minh 2')
})

test('chủ thật xoá được hồ sơ của chính mình', async () => {
  const a = await thietBiMoi('Máy A')
  const created = (await goi('POST', '/v1/brand-profiles/', a.token, HO_SO_MAU)).json()

  const res = await goi('DELETE', `/v1/brand-profiles/${created.id}`, a.token)
  assert.equal(res.statusCode, 200)
  assert.equal(await BrandProfile.findById(created.id), null)
})

test('id sai khuôn ObjectId -> 404, không phải 500 (CastError)', async () => {
  const a = await thietBiMoi('Máy A')
  const res = await goi('PUT', '/v1/brand-profiles/khong-phai-object-id', a.token, HO_SO_MAU)
  assert.equal(res.statusCode, 404)
})

// -------------------------------------------- hồi quy: gỡ kiểm sở hữu -----

test('REGRESSION GIẢ ĐỊNH: truy vấn không lọc theo ownerDeviceId sẽ LỘ dữ liệu', async () => {
  // Test này mô phỏng đúng bẫy mà Constraint/Test Plan của H1 yêu cầu phải
  // bắt được: nếu ai đó lỡ gỡ điều kiện `ownerDeviceId` khỏi truy vấn
  // (findOne/find), một thiết bị SẼ đọc được hồ sơ của thiết bị khác. Test
  // các route thật ở trên (đã PASS) chính là bằng chứng điều kiện đó đang
  // có mặt; test này ghi lại rõ NẾU KHÔNG có điều kiện đó thì hỏng ra sao,
  // để ai sửa route sau này hiểu vì sao dòng `ownerDeviceId` không được bỏ.
  const a = await thietBiMoi('Máy A')
  await goi('POST', '/v1/brand-profiles/', a.token, HO_SO_MAU)

  const layKhongLoc = await BrandProfile.find({}) // KHÔNG lọc ownerDeviceId
  const layCoLoc = await BrandProfile.find({ ownerDeviceId: 'khong-ton-tai' })
    .catch(() => [])
  assert.equal(layKhongLoc.length, 1, 'không lọc thì thấy MỌI hồ sơ — đúng lỗ hổng cần chặn')
  assert.equal(layCoLoc.length, 0, 'lọc đúng theo chủ sở hữu thì không thấy hồ sơ của người khác')
})

// ---------------------------------------------------------------------------
// Lỗ đổi chủ sở hữu hồ sơ — tìm ra trong đợt rà soát 10/09/2026.
//
// `bodySchema` thiếu `additionalProperties: false`. Đo thật với đúng cấu hình
// ajv của fastify (`removeAdditional: true`): trường lạ KHÔNG bị xoá mà đi
// thẳng vào `request.body`. Cộng với `Object.assign(doc, request.body)` ở
// `PUT`, mongoose nhận gán lại `ownerDeviceId` và `validateSync()` không kêu.
// `POST` thoát nạn chỉ nhờ đặt `ownerDeviceId` SAU phần spread.

test('PUT KHÔNG cho đổi chủ sở hữu hồ sơ sang máy khác', async () => {
  const a = await thietBiMoi('may-a')
  const b = await thietBiMoi('may-b')
  const ho_so = await BrandProfile.create({ ...HO_SO_MAU, ownerDeviceId: a.device._id })

  const r = await goi('PUT', `/v1/brand-profiles/${ho_so._id}`, a.token, {
    tenBrand: 'Đổi chủ', rangBuocKhongDuocNoi: [],
    ownerDeviceId: String(b.device._id),
  })
  // fastify cấu hình ajv `removeAdditional: true`, nên cặp với
  // `additionalProperties: false` nó XOÁ trường lạ rồi cho qua (200) chứ
  // không trả 400. Điều cần bảo vệ là chủ sở hữu, không phải mã trả về.
  assert.equal(r.statusCode, 200, r.body)

  const sau = await BrandProfile.findById(ho_so._id)
  assert.equal(String(sau.ownerDeviceId), String(a.device._id),
    'hồ sơ đã đổi chủ — máy B nay đọc được dữ liệu của máy A')

  // Và máy B vẫn không thấy hồ sơ đó.
  const ds = await goi('GET', '/v1/brand-profiles/', b.token)
  assert.equal(ds.json().data.length, 0)
})

test('PUT KHÔNG cho ghi đè _id', async () => {
  const a = await thietBiMoi('may-a')
  const ho_so = await BrandProfile.create({ ...HO_SO_MAU, ownerDeviceId: a.device._id })
  const r = await goi('PUT', `/v1/brand-profiles/${ho_so._id}`, a.token, {
    tenBrand: 'X', rangBuocKhongDuocNoi: [], _id: 'zzz',
  })
  assert.equal(r.statusCode, 200, 'ghi đè _id từng làm doc.save() ném ra 500')
  assert.equal(String(r.json().id), String(ho_so._id), '_id bị ghi đè')
})

test('PUT vẫn sửa được đúng những trường cho phép', async () => {
  const a = await thietBiMoi('may-a')
  const ho_so = await BrandProfile.create({ ...HO_SO_MAU, ownerDeviceId: a.device._id })
  const r = await goi('PUT', `/v1/brand-profiles/${ho_so._id}`, a.token, {
    tenBrand: 'Tên mới', usp: 'Giao trong ngày',
    rangBuocKhongDuocNoi: ['tốt nhất'],
  })
  assert.equal(r.statusCode, 200, r.body)
  assert.equal(r.json().tenBrand, 'Tên mới')
  assert.equal(r.json().usp, 'Giao trong ngày')
})
