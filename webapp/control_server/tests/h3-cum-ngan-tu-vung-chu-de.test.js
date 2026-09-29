'use strict'

/**
 * H3 — cụm NGẮN của nguồn là TỪ VỰNG CHỦ ĐỀ, không phải bằng chứng chép.
 *
 * Lượt chạy thật 14/09/2026: brand «Mắt Bão Invoice» viết kịch bản cho phần
 * mềm hoá đơn; video tham khảo cũng về phần mềm hoá đơn. Dấu vân tay chứa dòng
 * bằng chứng hai âm tiết `hóa đơn` ⇒ beat nào nói "hóa đơn" cũng `flagged`, và
 * `blocked` thắng cả kịch bản. Viết kịch bản hoá đơn mà cấm chữ "hóa đơn" là
 * việc KHÔNG LÀM ĐƯỢC.
 *
 * Cùng lớp với E2 (11/09) ở gate H2 — `STOP SCROLLING` và `hóa đơn` đều hai
 * từ, nên ngưỡng theo SỐ TỪ không tách được hai lớp. Cách xử đã chốt ở E2:
 * tách "có chạm không" (giữ ngưỡng 2) khỏi "chạm thì có đáng chặn không"
 * (ngưỡng 4). Tệp này chốt cả hai chiều.
 */
const test = require('node:test')
const assert = require('node:assert')
const dvt = require('../src/services/dau-van-tay.service')
const kiem = require('../src/services/kiem-kich-ban.service')

test('TAI HIEN 14/09: brand hoa don bi chan vi cum 2 am tiet cua nguon', () => {
  // Bằng chứng nguồn đúng như video MISA: dòng OCR hai âm tiết "hoa don".
  const vanTay = dvt.taoDauVanTay(['hóa đơn', 'nhập hóa đơn'])
  const beat = {
    voiceoverTextVi: 'Đơn hàng dồn dập, doanh thu chạm mốc trăm triệu mỗi '
      + 'tháng, nhưng nhìn đống hóa đơn thì lại thấy nản',
    captionSuggestionVi: 'Doanh thu tăng, hóa đơn dồn dập?',
    visualBriefVi: 'Cận cảnh một bàn tay đang gõ máy tính',
  }
  const r = kiem.kiemNguyenGoc(beat, vanTay, 'ok')
  assert.equal(r.originalityFlag, 'clear',
    'brand làm phần mềm hoá đơn mà cấm chữ "hóa đơn" là việc KHÔNG LÀM ĐƯỢC')
  assert.ok(r.chamCumNgan, 'vẫn phải GHI NHẬN là có chạm, không được giấu')
})

test('cum DAI chep that thi VAN chan nhu cu', () => {
  const nguon = 'Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc nấu nướng'
  const vanTay = dvt.taoDauVanTay([nguon])
  const r = kiem.kiemNguyenGoc({ voiceoverTextVi: nguon }, vanTay, 'ok')
  assert.equal(r.originalityFlag, 'flagged', 'chép nguyên văn phải bị chặn')
})

test('cum ngan 4 tu tro len VAN chan — nguong chi ha cho 2-3 tu', () => {
  const vanTay = dvt.taoDauVanTay(['mua ngay hôm nay'])
  const r = kiem.kiemNguyenGoc(
    { voiceoverTextVi: 'Bạn hãy mua ngay hôm nay để nhận ưu đãi' }, vanTay, 'ok')
  assert.equal(r.originalityFlag, 'flagged')
  assert.equal(r.flaggedExcerpt, 'mua ngay hôm nay')
})

test('cum 2 tu KHONG duoc che mat mot cum 5 tu chep that trong cung beat', () => {
  const vanTay = dvt.taoDauVanTay(['hóa đơn', 'sale bùng nổ đơn hàng'])
  const r = kiem.kiemNguyenGoc({
    voiceoverTextVi: 'Nhìn đống hóa đơn mà nản',
    captionSuggestionVi: 'sale bùng nổ đơn hàng',
  }, vanTay, 'ok')
  assert.equal(r.originalityFlag, 'flagged',
    'đi tiếp sau cụm ngắn, nếu không một cụm chép thật sẽ lọt')
})
