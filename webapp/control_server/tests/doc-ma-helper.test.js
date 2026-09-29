'use strict'

/**
 * C8 — bộ canh cho chính bộ canh.
 *
 * Bốn phép kiểm dưới đây tương ứng ĐÚNG bốn kiểu hỏng đã mắc trong một ngày
 * khi viết test đọc mã nguồn bằng `indexOf`. Nếu helper này hỏng thì mọi test
 * đọc-mã đứng trên nó đều xanh giả, nên nó phải có test riêng.
 */
const test = require('node:test')
const assert = require('node:assert')

const h = require('./helpers/doc-ma')

test('kiểu hỏng 1: so thứ tự khi vế trước KHÔNG tồn tại', () => {
  // `indexOf(a) < indexOf(b)` là true khi a vắng mặt (-1). `truoc()` phải nổ.
  assert.throws(() => h.truoc('chi co b()', 'a(', 'b('), /không thấy «a\(»/)
})

test('kiểu hỏng 2: khớp phải chữ trong CHÚ THÍCH', () => {
  assert.equal(h.demGoi(h.boChuThich('// nhớ gọi kiemTra()\nlamViecKhac()'),
    'kiemTra'), 0)
})

test('kiểu hỏng 2b: khớp phải chữ trong CHUỖI thông báo', () => {
  assert.equal(h.demGoi('throw new Error("quên gọi kiemTra() rồi")',
    'kiemTra'), 0)
})

test('nhưng vẫn TÌM được thứ nằm trong chuỗi khi cần cắt route', () => {
  // Bản đầu gộp hai việc (bỏ chú thích + moi ruột chuỗi) nên không tìm nổi
  // route nào — chính test này bắt được.
  assert.ok(h.ma('src/routes/ai.js').includes("'/product-scene'"))
})

test('kiểu hỏng 3: cắt thân hàm lây sang hàm phía sau', () => {
  const than = h.thanHam('tests/helpers/doc-ma.js', 'boChuThich')
  assert.ok(than.includes('boChuThich'))
  assert.ok(!than.includes('function thanHam'),
    'đọc lây sang hàm kế tiếp — đúng lỗi đã mắc')
})

test('kiểu hỏng 4: đếm nhầm dòng KHAI BÁO hàm cùng tên', () => {
  const ma = h.boChuThich('function kiemTra(x) { return x }\nkiemTra(1)\n')
  assert.equal(h.demGoi(ma, 'kiemTra'), 1, 'đếm cả dòng khai báo')
})

test('cắt được thân một route theo đường dẫn', () => {
  const than = h.thanHam('src/routes/ai.js', '/product-scene')
  assert.ok(than.includes('imageStage.quyetDinh('))
  assert.ok(!than.includes("fastify.post('/music'"),
    'thân route đọc lây sang route kế tiếp')
})
