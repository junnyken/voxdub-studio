'use strict'
/**
 * mini-spec H2b — tác vụ `doc_chu_khung_hinh` (đọc chữ overlay bằng mô hình
 * nhìn ảnh, vì OCR trên máy không phát ra được dấu tiếng Việt).
 *
 * Trọng tâm của bộ test này là ÁNH XẠ ẢNH↔CHỮ. Sai một khung là mọi khung
 * sau đó gán nhầm chữ, và không có tín hiệu nào để phát hiện — nên phần lớn
 * test dưới đây kiểm đúng chuyện đó, không phải kiểm câu chữ prompt.
 */
const test = require('node:test')
const assert = require('node:assert')
const prompts = require('../src/prompts/assist')

const { parseDocChuResult, docChuOutputSchema, getTask } = prompts

test('doc_chu_khung_hinh có mặt trong danh sách tác vụ đóng', () => {
  const spec = getTask('doc_chu_khung_hinh')
  assert.ok(spec, 'tác vụ phải tồn tại')
  assert.equal(spec.nhanAnh, true)
  assert.equal(spec.soAnhToiDa, 6)
  assert.equal(spec.costKey, 'credit.cost.assist.doc_chu_khung_hinh')
  assert.equal(typeof spec.outputSchema, 'function')
  assert.equal(typeof spec.parseResult, 'function')
})

test('trần ảnh của tác vụ không vượt trần schema route /v1/ai/assist', () => {
  // Route khai `images.maxItems: 6`. Đặt `soAnhToiDa` lớn hơn thì yêu cầu bị
  // chặn ở tầng schema với một lỗi trống không, TRƯỚC khi tới chỗ có thông
  // báo tử tế — đúng lớp lỗi mà chú thích trong route đã cảnh báo.
  const src = require('node:fs').readFileSync(
    require('node:path').join(__dirname, '..', 'src', 'routes', 'ai.js'), 'utf8')
  const khop = src.match(/images:\s*\{[\s\S]{0,400}?maxItems:\s*(\d+)/)
  assert.ok(khop, 'không tìm thấy trần maxItems của images trong route')
  assert.ok(getTask('doc_chu_khung_hinh').soAnhToiDa <= Number(khop[1]),
    `soAnhToiDa (${getTask('doc_chu_khung_hinh').soAnhToiDa}) vượt trần route (${khop[1]})`)
})

test('schema ép có "anh" và "dong", giới hạn đúng số ảnh tối đa', () => {
  const s = docChuOutputSchema()
  assert.deepEqual(s.required, ['khung'])
  assert.equal(s.properties.khung.maxItems, 6)
  assert.deepEqual(s.properties.khung.items.required, ['anh', 'dong'])
  assert.equal(s.properties.khung.items.properties.anh.type, 'integer')
})

test('đọc bình thường: giữ nguyên dấu tiếng Việt, đúng thứ tự ảnh', () => {
  const ra = parseDocChuResult({
    khung: [
      { anh: 1, dong: ['Excuse me', 'Xin lỗi'] },
      { anh: 2, dong: ['Nhưng nó không ngon lắm'] },
    ],
  }, { soAnh: 2 })
  assert.deepEqual(ra, {
    results: [
      { anh: 1, dong: ['Excuse me', 'Xin lỗi'] },
      { anh: 2, dong: ['Nhưng nó không ngon lắm'] },
    ],
  })
})

test('khung mô hình BỎ SÓT vẫn có mặt với dong rỗng — không lệch ánh xạ', () => {
  // Đây là ca hỏng nguy hiểm nhất: mô hình bỏ qua ảnh 2 (không có chữ), nếu
  // ta trả về mảng 2 phần tử thì chữ của ảnh 3 bị gán cho ảnh 2.
  const ra = parseDocChuResult({
    khung: [{ anh: 1, dong: ['Mở đầu'] }, { anh: 3, dong: ['Kết'] }],
  }, { soAnh: 3 })
  assert.equal(ra.results.length, 3)
  assert.deepEqual(ra.results.map((r) => r.anh), [1, 2, 3])
  assert.deepEqual(ra.results[1].dong, [])
  assert.deepEqual(ra.results[2].dong, ['Kết'])
})

test('mô hình trả LỘN XỘN thứ tự vẫn xếp lại đúng theo số ảnh', () => {
  const ra = parseDocChuResult({
    khung: [{ anh: 3, dong: ['ba'] }, { anh: 1, dong: ['một'] }, { anh: 2, dong: ['hai'] }],
  }, { soAnh: 3 })
  assert.deepEqual(ra.results.map((r) => r.dong[0]), ['một', 'hai', 'ba'])
})

test('mô hình lặp lại một số ảnh: giữ mục đầu, KHÔNG nhân đôi chữ', () => {
  const ra = parseDocChuResult({
    khung: [{ anh: 1, dong: ['thật'] }, { anh: 1, dong: ['ảo giác lặp'] }],
  }, { soAnh: 1 })
  assert.deepEqual(ra.results, [{ anh: 1, dong: ['thật'] }])
})

test('số ảnh ngoài khoảng 1..soAnh bị bỏ, không làm vỡ kết quả', () => {
  const ra = parseDocChuResult({
    khung: [{ anh: 0, dong: ['x'] }, { anh: 99, dong: ['y'] }, { anh: 1, dong: ['ok'] }],
  }, { soAnh: 2 })
  assert.deepEqual(ra.results, [{ anh: 1, dong: ['ok'] }, { anh: 2, dong: [] }])
})

test('dòng rỗng/khoảng trắng bị loại, dòng thật được cắt gọn hai đầu', () => {
  const ra = parseDocChuResult({
    khung: [{ anh: 1, dong: ['  Xin lỗi  ', '', '   ', null, 'Excuse me'] }],
  }, { soAnh: 1 })
  assert.deepEqual(ra.results[0].dong, ['Xin lỗi', 'Excuse me'])
})

test('mọi khung đều không có chữ vẫn là câu trả lời HỢP LỆ, không phải lỗi', () => {
  // Video sạch chữ là chuyện thường. Trả null ở đây thì cổng trợ lý ném
  // BAD_AI_RESPONSE và người dùng thấy "trợ lý chưa trả lời được" — sai hẳn
  // nguyên nhân, đúng lớp lỗi C56 (chưa cài ≠ quét xong không thấy gì).
  const ra = parseDocChuResult({ khung: [{ anh: 1, dong: [] }] }, { soAnh: 1 })
  assert.deepEqual(ra, { results: [{ anh: 1, dong: [] }] })
})

test('output sai khuôn -> null để cổng trợ lý báo lỗi, KHÔNG trả rỗng âm thầm', () => {
  assert.equal(parseDocChuResult(null, { soAnh: 1 }), null)
  assert.equal(parseDocChuResult({}, { soAnh: 1 }), null)
  assert.equal(parseDocChuResult({ khung: 'không phải mảng' }, { soAnh: 1 }), null)
})

test('thiếu soAnh -> null: không đoán số khung thay bên gọi', () => {
  assert.equal(parseDocChuResult({ khung: [{ anh: 1, dong: ['a'] }] }, {}), null)
  assert.equal(parseDocChuResult({ khung: [{ anh: 1, dong: ['a'] }] }, { soAnh: 0 }), null)
})

test('parseResult trả đúng khuôn {results:[...]} mà route /v1/ai/assist đọc được', () => {
  // Route dùng `result.results` (mảng đục) và `result.results.length`. Đổi
  // khuôn trả về ở đây là vỡ route mà test của route không nhất thiết bắt
  // được — chốt lại tại đây.
  const ra = getTask('doc_chu_khung_hinh').parseResult(
    { khung: [{ anh: 1, dong: ['a'] }] }, { soAnh: 1 })
  assert.ok(Array.isArray(ra.results))
  assert.equal(ra.results.length, 1)
})

test('prompt nói rõ hai điều bắt buộc: giữ dấu tiếng Việt và KHÔNG dịch', () => {
  // Hai câu này là lý do tồn tại của cả tác vụ. Ai sửa prompt mà bỏ chúng đi
  // thì bug gốc ("dịch ra tiếng Việt mà không có dấu") quay lại y nguyên.
  const sys = getTask('doc_chu_khung_hinh').system
  assert.match(sys, /dấu tiếng Việt/i)
  assert.match(sys, /KHÔNG dịch/i)
})

test('buildUser nói đúng số ảnh gửi lên', () => {
  assert.match(getTask('doc_chu_khung_hinh').buildUser({ soAnh: 4 }), /4 ảnh/)
})
