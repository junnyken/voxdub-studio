'use strict'

/**
 * C5 — nút "Thử ngay", và bấm nấc chạy thật phải dựa trên lượt ĐÃ SOI TAY.
 *
 * Hai lớp lỗi cần chặn:
 *
 * 1. Lỗi cấu hình chỉ lộ ra giữa một mẻ hiệu chỉnh đang tốn tiền. Nút thử
 *    ngay kéo chi phí phát hiện xuống gần 0 — nhưng chỉ khi nó không tự tính
 *    vào hạn mức và không lẫn vào sổ hiệu chỉnh.
 * 2. Bấm nấc `production` dựa trên SỐ LƯỢT ĐÃ CHẠY. Chạy 100 ảnh mà không ai
 *    nhìn thì con số 100 chỉ nói đã tiêu bao nhiêu tiền.
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const stats = require('../src/services/assist-stats.service')

const h = require('./helpers/doc-ma')

/** Mã đã bỏ chú thích; `thanHam` cắt đúng một hàm, tới hàm kế tiếp.
 *
 *  Cắt tới `module.exports` như bản đầu là đọc lây sang các hàm phía sau —
 *  test đỏ oan vì thấy mã của hàm khác. Nay dùng chung lớp `helpers/doc-ma`
 *  (mini-spec C8), có test riêng cho cả bốn kiểu hỏng. */
const doc = (p) => h.ma(p)
const thanHam = (ten) => h.thanHam('src/services/ai-gateway.service.js', ten)

// -- Thử ngay không được đụng vào tiền của ai --------------------------------

test('lượt thử ngay KHÔNG tính vào hạn mức ngày', () => {
  const src = doc('src/routes/ai.js')
  // Ba chỗ đếm hạn mức: trợ lý theo ngày, ảnh theo ngày, ảnh CONCEPT theo ngày.
  const soLanLoc = (src.match(/runMode: \{ \$ne: 'test_now' \}/g) || []).length
  assert.equal(soLanLoc, 3,
    `mới ${soLanLoc}/3 chỗ đếm hạn mức loại lượt thử ngay ra`)
})

test('thử ngay dùng ảnh do máy chủ tự vẽ, không phải ảnh khách', () => {
  assert.match(thanHam('thuNgay'), /visionProbe\.taoBaiThu\(\)/)
})

test('thử ngay chỉ gọi ĐÚNG nơi đang thử, không rơi sang nơi khác', () => {
  // Không ghim thì nơi thứ nhất hỏng sẽ được nơi thứ hai đỡ, và người bấm
  // tưởng cấu hình vừa sửa đã chạy — trong khi nó vẫn hỏng.
  const than = thanHam('thuNgay')
  assert.match(than, /chiDinh: \[provider\]/, 'nhánh sinh ảnh không ghim nơi gọi')
  assert.match(than, /thuNhinMotNoi\(provider\)/, 'nhánh vai chữ không ghim nơi gọi')
})

test('thử ngay luôn chấm lại phép nhìn, không xài kết quả cũ', () => {
  // Người bấm vừa đổi cấu hình; dấu của bản cũ không nói lên điều gì.
  assert.doesNotMatch(thanHam('thuNgay'),
    /visionOkAt \? new Date\(provider\.visionOkAt\)/,
    'thử ngay đang dùng lại kết quả nhìn đã lưu')
})

test('gọi hỏng ở nhánh vai chữ KHÔNG đóng dấu mô hình mù', () => {
  const than = thanHam('thuNgay')
  const bat = than.slice(than.lastIndexOf('} catch (err) {'))
  assert.doesNotMatch(bat, /visionNote:/,
    'lỗi mạng mà vẫn ghi dấu mù = kết tội oan, dấu ở lại 7 ngày')
})

// -- Bấm nấc chạy thật -------------------------------------------------------

test('đếm lượt ĐÃ SOI TAY, không phải lượt đã chạy', () => {
  const nhieuLuotKhongSoi = stats.sanSangXetDuyet(
    [{ runMode: 'calibration', luot: 500, daSoi: 3, dongY: 3 }])
  assert.equal(nhieuLuotKhongSoi.du, false,
    '500 lượt chạy mà mới soi 3 vẫn không được coi là đủ')

  const itLuotSoiDu = stats.sanSangXetDuyet(
    [{ runMode: 'calibration', luot: 20, daSoi: 20, dongY: 15 }])
  assert.equal(itLuotSoiDu.du, true)
})

test('báo cáo tỷ lệ người soi ĐỒNG Ý với mô hình', () => {
  // Đây mới là số quyết định có mở cho người bán thật hay không.
  const r = stats.sanSangXetDuyet(
    [{ runMode: 'calibration', luot: 40, daSoi: 25, dongY: 20 }])
  assert.equal(r.tyLeDongY, 80)
})

test('chưa soi lượt nào thì không chia cho 0', () => {
  const r = stats.sanSangXetDuyet([{ runMode: 'calibration', luot: 9, daSoi: 0 }])
  assert.equal(r.tyLeDongY, 0)
  assert.equal(r.du, false)
})

test('bảng phán quyết có đếm số lượt đã soi và số lượt đồng ý', () => {
  const group = stats.theoPhanQuyet(7).find((c) => c.$group).$group
  assert.ok(group.daSoi, 'thiếu nhóm đếm đã soi')
  assert.ok(group.dongY, 'thiếu nhóm đếm đồng ý')
})

test('MÁY CHỦ chặn bật nấc chạy thật khi chưa soi đủ', () => {
  // Hỏi lại trên giao diện không phải là chặn: giao diện nào cũng đi vòng
  // được bằng một lượt gọi API.
  const than = h.thanHam('src/routes/admin.js', '/config/:key')
  assert.match(than, /image\.scene\.stage/)
  assert.match(than, /CHUA_DU_LUOT_SOI_TAY/)
  // Mốc so thứ tự phải là MÃ, không phải chữ: `truoc()` moi ruột chuỗi (để
  // "gọi hàm X" không bị tính khi X nằm trong câu thông báo), nên mã lỗi
  // `'CHUA_DU_LUOT_SOI_TAY'` biến mất khỏi bản đem so. Dùng `xet.du` —
  // chính phép kiểm — làm mốc.
  h.truoc(than, 'xet.du', 'await config.set(',
    'phải chặn TRƯỚC khi ghi giá trị mới')
})

test('sổ hiệu chỉnh lưu LÝ DO bằng lời, không chỉ nhãn', () => {
  // Thiếu lý do thì bảng soi tay chỉ còn hai chữ SAFE/CONCEPT và không ai
  // soi được gì.
  assert.match(doc('src/models/UsageLog.js'), /reason: \{ type: String/)
  assert.match(doc('src/routes/ai.js'), /reason: task === 'packaging_check'/)
})

test('cửa soi tay chỉ nhận lượt hiệu chỉnh của đúng tác vụ kiểm bao bì', () => {
  const than = h.thanHam('src/routes/admin.js', '/calibration/runs/:id/review')
  assert.match(than, /runMode: 'calibration'/)
  assert.match(than, /assistTask: 'packaging_check'/)
})
