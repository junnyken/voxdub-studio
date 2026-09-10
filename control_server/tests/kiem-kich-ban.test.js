'use strict'
/**
 * mini-spec H3 — hai lớp kiểm + bảng tính trạng thái BrandScript.
 *
 * Đây là phần chịu trách nhiệm chính về rủi ro pháp lý của cả Phase H, nên
 * bộ test này canh hai chiều ngang nhau:
 *   - **bắt được thật** (gỡ chốt là phải đỏ), và
 *   - **không báo nhầm** — báo nhầm thì người dùng học cách bỏ qua cảnh báo,
 *     và lúc đó bộ chặn còn tệ hơn không có.
 */
const test = require('node:test')
const assert = require('node:assert')
const kiem = require('../src/services/kiem-kich-ban.service')
const dauVanTay = require('../src/services/dau-van-tay.service')

const NGUON = [
  'Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc chuẩn bị bữa ăn không',
  'Chiếc máy này giúp rút ngắn toàn bộ quy trình xuống chỉ còn vài phút thôi',
  'MUA NGAY HÔM NAY',
]
const CAM = ['tốt nhất', 'số một', 'chữa bệnh']

function beat(loi, caption = '', visual = 'Cận cảnh sản phẩm trên bàn bếp') {
  return {
    beatType: 'hook', voiceoverTextVi: loi,
    captionSuggestionVi: caption, visualBriefVi: visual,
  }
}

// ------------------------------------------------------------ tuân thủ -----

test('bắt đúng cụm bị cấm và chỉ ra câu ràng buộc đã kích hoạt', () => {
  const r = kiem.kiemTuanThu(beat('Đây là loại nồi tốt nhất bạn từng dùng'), CAM)
  assert.equal(r.complianceFlag, 'violated')
  assert.equal(r.complianceExcerpt, 'tốt nhất')
  assert.equal(r.complianceRule, 'tốt nhất',
    'phải nói rõ câu ràng buộc nào kích hoạt, không chỉ báo "có vi phạm"')
})

test('chữ hoa và dấu câu KHÔNG giúp lách bộ kiểm tuân thủ', () => {
  assert.equal(kiem.kiemTuanThu(beat('Sản phẩm TỐT NHẤT!!!'), CAM).complianceFlag, 'violated')
})

test('bắt cụm cấm nằm ở caption và visual brief, không chỉ lời đọc', () => {
  // Caption là chỗ dễ lọt nhất nếu chỉ kiểm lời đọc.
  assert.equal(kiem.kiemTuanThu(beat('Lời đọc sạch', 'SỐ MỘT THỊ TRƯỜNG'), CAM)
    .complianceFlag, 'violated')
  assert.equal(kiem.kiemTuanThu(beat('Lời đọc sạch', '', 'Cảnh quay nói về chữa bệnh'), CAM)
    .complianceFlag, 'violated')
})

test('KHÔNG báo nhầm câu hợp lệ có từ gần giống cụm cấm', () => {
  // "nhất" nằm trong "nhất định"/"thống nhất" là chuyện bình thường. So khớp
  // ở mức KÝ TỰ sẽ bắt oan hàng loạt câu vô hại.
  for (const cau of [
    'Bạn nhất định sẽ thích cảm giác này',
    'Cả nhà thống nhất chọn món này cho bữa sáng',
    'Số lượng có hạn trong tháng này',
  ]) {
    assert.equal(kiem.kiemTuanThu(beat(cau), CAM).complianceFlag, 'clear',
      `báo nhầm câu hợp lệ: ${cau}`)
  }
})

// --------------------------------------------------------- nguyên gốc -----

test('bắt beat chép gần nguyên văn từ bằng chứng nguồn', () => {
  const vt = dauVanTay.taoDauVanTay(NGUON)
  const r = kiem.kiemNguyenGoc(
    beat('Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc nấu nướng không'),
    vt, 'ok')
  assert.equal(r.originalityFlag, 'flagged')
  assert.ok(r.flaggedExcerpt, 'phải chỉ ra cụm bị chặn trong kịch bản MỚI')
})

test('KHÔNG báo nhầm với câu diễn đạt lại hợp lệ', () => {
  const vt = dauVanTay.taoDauVanTay(NGUON)
  for (const cau of [
    'Buổi sáng của bạn có đang trôi đi vì những việc bếp núc lặt vặt?',
    'Chỉ vài phút là xong bữa sáng, thay vì loay hoay cả buổi',
    'Sản phẩm rút gọn công đoạn chuẩn bị, trả lại thời gian buổi sáng cho bạn',
  ]) {
    assert.equal(kiem.kiemNguyenGoc(beat(cau), vt, 'ok').originalityFlag, 'clear',
      `báo nhầm câu hợp lệ: ${cau}`)
  }
})

test('bốn nguyên nhân CHƯA KIỂM ĐƯỢC đều ra unconfirmed, và nói rõ lý do', () => {
  const vt = dauVanTay.taoDauVanTay(NGUON)
  const sach = beat('Một câu hoàn toàn mới không liên quan gì tới nguồn cả')

  // 1. Blueprint cũ, chưa có dấu vân tay
  assert.deepEqual(
    kiem.kiemNguyenGoc(sach, null, 'ok'),
    { originalityFlag: 'unconfirmed', flaggedExcerpt: '', lyDoChuaKiem: 'khong_co_dau_van_tay' })

  // 2. Dấu vân tay dựng bằng thuật toán đời khác
  assert.equal(kiem.kiemNguyenGoc(sach, { ...vt, v: vt.v + 1 }, 'ok').lyDoChuaKiem,
    'khac_phien_ban')

  // 3. Số băm chạm trần ⇒ vùng phủ thủng
  assert.equal(kiem.kiemNguyenGoc(sach, { ...vt, dayTran: true }, 'ok').lyDoChuaKiem,
    'day_tran')

  // 4. Beat nguồn không có bằng chứng xác nhận
  for (const tt of ['unavailable', 'failed', 'no_text']) {
    assert.equal(kiem.kiemNguyenGoc(sach, vt, tt).lyDoChuaKiem, 'bang_chung_khong_du',
      `trạng thái nguồn "${tt}" phải là chưa kiểm được`)
  }
})

test('HỒI QUY: coi "chưa kiểm được" như "sạch" là phải đỏ', () => {
  // Đây là ca hỏng nguy hiểm nhất của cả H3: một kịch bản chưa ai soi được
  // gắn nhãn sạch rồi đi thẳng sang H4.
  const r = kiem.kiemNguyenGoc(beat('Câu gì cũng được'), null, 'ok')
  assert.notEqual(r.originalityFlag, 'clear')
  assert.equal(kiem.tinhTrangThai([{ ...beat('x'), ...r, complianceFlag: 'clear' }]),
    'unconfirmed')
})

// ------------------------------------------------------- bảng trạng thái ---

test('bảng ưu tiên: blocked > unconfirmed > ready', () => {
  const ok = { originalityFlag: 'clear', complianceFlag: 'clear' }
  const chuaKiem = { originalityFlag: 'unconfirmed', complianceFlag: 'clear' }
  const trung = { originalityFlag: 'flagged', complianceFlag: 'clear' }
  const viPham = { originalityFlag: 'clear', complianceFlag: 'violated' }

  assert.equal(kiem.tinhTrangThai([ok, ok]), 'ready')
  assert.equal(kiem.tinhTrangThai([ok, chuaKiem]), 'unconfirmed')
  assert.equal(kiem.tinhTrangThai([ok, trung]), 'blocked')
  assert.equal(kiem.tinhTrangThai([ok, viPham]), 'blocked')
  // blocked thắng cả unconfirmed — chuyện nghiêm trọng hơn phải hiện ra trước
  assert.equal(kiem.tinhTrangThai([chuaKiem, trung]), 'blocked')
  assert.equal(kiem.tinhTrangThai([]), 'failed')
})

test('MỘT beat bẩn là chặn CẢ script, không lặng lẽ bỏ riêng beat đó', () => {
  const vt = dauVanTay.taoDauVanTay(NGUON)
  const ra = kiem.kiemToanBo([
    beat('Buổi sáng của bạn trôi đi vì việc bếp núc lặt vặt phải không'),
    beat('Chiếc máy này giúp rút ngắn toàn bộ quy trình xuống chỉ còn vài phút'),
  ], { rangBuocKhongDuocNoi: CAM, vanTay: vt, beatsNguon: [{ evidenceStatus: 'ok' }, { evidenceStatus: 'ok' }] })

  assert.equal(ra.status, 'blocked')
  assert.equal(ra.beats[0].originalityFlag, 'clear')
  assert.equal(ra.beats[1].originalityFlag, 'flagged')
  assert.equal(ra.beats.length, 2, 'KHÔNG được lọc bỏ beat bẩn ra khỏi kết quả')
})

test('kiemToanBo dùng đúng evidenceStatus của beat nguồn TƯƠNG ỨNG', () => {
  // Lệch chỉ số ở đây nghĩa là beat sạch bị gán trạng thái của beat khác.
  const vt = dauVanTay.taoDauVanTay(NGUON)
  const ra = kiem.kiemToanBo([beat('Câu mới hoàn toàn số một'), beat('Câu mới khác nữa')], {
    rangBuocKhongDuocNoi: [], vanTay: vt,
    beatsNguon: [{ evidenceStatus: 'ok' }, { evidenceStatus: 'unavailable' }],
  })
  assert.equal(ra.beats[0].originalityFlag, 'clear')
  assert.equal(ra.beats[1].lyDoChuaKiem, 'bang_chung_khong_du')
})

test('kiểm là THUẦN VĂN BẢN — không gọi mô hình', () => {
  // Constraint 12: nếu bước kiểm gọi AI thì "tạo lại một beat phải kiểm lại
  // toàn bộ" sẽ thành hoá đơn nhân theo mỗi lần sửa.
  const src = require('node:fs').readFileSync(
    require('node:path').join(__dirname, '..', 'src', 'services', 'kiem-kich-ban.service.js'),
    'utf8')
  assert.ok(!/ai-gateway|require\(.*gateway/.test(src),
    'bộ kiểm không được phụ thuộc cổng gọi mô hình')
})
