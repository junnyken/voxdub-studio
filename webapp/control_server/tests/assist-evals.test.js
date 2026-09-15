'use strict'

/**
 * Mini-spec V89 — bộ đo phải BẮT ĐƯỢC kết quả kém.
 *
 * Một bộ đo luôn xanh còn tệ hơn không có: nó tạo cảm giác đã kiểm. Nên ở
 * đây cho ăn kết quả GIẢ đã biết trước là tốt/xấu, rồi bắt bộ đo chấm đúng.
 */
const test = require('node:test')
const assert = require('node:assert')

const { CASES } = require('../evals/cases')

/** Chấm một kết quả giả theo đúng cách evals/run.js chấm. */
function cham(mau, ket) {
  let dat = 0
  let tong = 0
  for (const [, kiem] of mau.kiem) {
    for (let i = 0; i < ket.length; i += 1) {
      tong += 1
      if (kiem(ket[i], mau, i)) dat += 1
    }
  }
  return { dat, tong }
}

function timMau(task, chua) {
  const m = CASES.find((c) => c.task === task && c.ten.includes(chua))
  assert.ok(m, `không thấy mẫu ${task}/${chua}`)
  return m
}

test('bắt được lời giải thích lỗi đầy từ kỹ thuật', () => {
  const mau = timMau('explain_error', 'thiếu FFmpeg')
  const tot = cham(mau, [{
    value: 'Máy chưa có công cụ xử lý video. Đúp chuột tệp cài đặt trong thư mục ứng dụng rồi mở lại.',
    reason: 'Thiếu một chương trình phụ trợ',
  }])
  const xau = cham(mau, [{
    value: 'WinError 2: subprocess không tìm thấy binary, kiểm tra PATH',
    reason: 'Hãy mở issue trên GitHub kèm traceback',
  }])
  assert.strictEqual(tot.dat, tot.tong, 'kết quả tốt mà bị chấm trượt')
  assert.ok(xau.dat < xau.tong, 'kết quả đầy từ kỹ thuật mà vẫn cho đạt')
})

test('bắt được câu rút gọn không hề ngắn đi', () => {
  const mau = timMau('tighten_line', 'câu dài')
  const tot = cham(mau, [{ value: 'Phần này rất quan trọng với cả quá trình.',
    reason: 'bỏ chữ đệm' }])
  const xau = cham(mau, [{ value: mau.input.line, reason: 'giữ nguyên' }])
  assert.strictEqual(tot.dat, tot.tong)
  assert.ok(xau.dat < xau.tong, 'trả lại y nguyên câu gốc mà vẫn cho đạt')
})

test('bắt được câu rút gọn làm mất con số', () => {
  const mau = timMau('tighten_line', 'câu có số')
  const tot = cham(mau, [{ value: 'Ninh sáu tiếng với hai ký xương và gừng nướng.',
    reason: 'bỏ chữ thừa' }])
  const xau = cham(mau, [{ value: 'Ninh xương thật lâu cho nước ngọt.',
    reason: 'gọn hơn' }])
  assert.strictEqual(tot.dat, tot.tong)
  assert.ok(xau.dat < xau.tong, 'mất con số mà vẫn cho đạt')
})

test('bắt được mô tả nhạc lạc sang mô tả hình ảnh', () => {
  const mau = timMau('music_suggest', 'video game')
  const tot = cham(mau, [{ value: 'nhạc điện tử nhịp nhanh, năng lượng cao',
    reason: 'video game đối kháng' }])
  const xau = cham(mau, [{ value: 'màu sắc rực rỡ, khung hình sôi động',
    reason: 'hợp không khí' }])
  assert.strictEqual(tot.dat, tot.tong)
  assert.ok(xau.dat < xau.tong, 'mô tả hình ảnh mà vẫn cho đạt')
})

test('bắt được từ khoá tóm tắt bịa ra ngoài lời thoại', () => {
  const mau = timMau('video_summary', 'từ khoá')
  const tot = cham(mau, [{ value: 'xương ống', reason: 'hai ký xương ống' }])
  const xau = cham(mau, [{ value: 'lẩu thái', reason: 'món ăn liên quan' }])
  assert.strictEqual(tot.dat, tot.tong)
  assert.ok(xau.dat < xau.tong, 'từ khoá không có trong lời thoại mà vẫn đạt')
})

test('bắt được tên nhân vật dài lê thê', () => {
  const mau = timMau('character_name', 'tên phải ngắn')
  const tot = cham(mau, [{ value: 'Người dẫn', reason: 'đọc bản tin' }])
  const xau = cham(mau, [{
    value: 'Người dẫn chương trình bản tin thời sự buổi tối',
    reason: 'đọc bản tin' }])
  assert.strictEqual(tot.dat, tot.tong)
  assert.ok(xau.dat < xau.tong, 'tên dài quá bảng mà vẫn cho đạt')
})

test('mọi tác vụ đều có mẫu đo — thêm tác vụ mà quên mẫu là đỏ ngay', () => {
  const assist = require('../src/prompts/assist')
  const coMau = new Set(CASES.map((c) => c.task))
  const thieu = assist.TASK_NAMES.filter((t) => !coMau.has(t))
  assert.deepStrictEqual(thieu, [], `tác vụ chưa có mẫu đo: ${thieu.join(', ')}`)
})
