'use strict'
/**
 * mini-spec H2c — dấu vân tay một chiều của bằng chứng nguồn.
 *
 * Hai thứ bộ test này phải giữ bằng được:
 *   1. **Không có chữ nào đọc lại được** trong thứ đem đi lưu — đó là toàn bộ
 *      lý do chọn cách này thay vì lưu thẳng transcript.
 *   2. **"Chưa kiểm được" không bao giờ được biến thành "đã kiểm, sạch"** —
 *      trộn hai ca đó là biến một kịch bản chưa ai soi thành kịch bản được
 *      coi là an toàn để xuất sang H4.
 */
const test = require('node:test')
const assert = require('node:assert')
const dvt = require('../src/services/dau-van-tay.service')

const NGUON = [
  'Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc chuẩn bị bữa ăn không',
  'Chiếc máy này giúp rút ngắn toàn bộ quy trình xuống chỉ còn vài phút thôi',
  'MUA NGAY HÔM NAY',
  'STOP SCROLLING',
]

test('bắt được câu chép gần như nguyên văn từ nguồn', () => {
  const v = dvt.taoDauVanTay(NGUON)
  const ra = dvt.timTrungLap(
    'Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc nấu nướng không', v)
  assert.equal(ra.trung, true)
  assert.equal(ra.kiemDuoc, true)
  assert.ok(ra.cum, 'phải chỉ ra được cụm bị trùng')
  assert.equal(ra.kieu, 'cum_dai')
})

test('bắt được caption NGẮN bị bê nguyên vào kịch bản mới', () => {
  // Dòng ngắn kiểu hook/CTA không đủ 6 từ để tạo cụm dài — nhánh riêng.
  const v = dvt.taoDauVanTay(NGUON)
  const ra = dvt.timTrungLap('Đừng lướt qua nhé, MUA NGAY HÔM NAY để kịp ưu đãi', v)
  assert.equal(ra.trung, true)
  assert.equal(ra.kieu, 'dong_ngan')
  assert.match(ra.cum, /mua ngay hôm nay/i)
})

test('KHÔNG báo nhầm với câu diễn đạt lại hợp lệ, cùng ý khác chữ', () => {
  // Ba ca paraphrase thật, viết tay, cùng ý với dòng nguồn nhưng khác cấu
  // trúc và khác từ. Báo nhầm ở đây nghĩa là mọi kịch bản tử tế đều bị chặn,
  // và người dùng sẽ học cách bỏ qua cảnh báo — hỏng cả bộ chặn.
  const v = dvt.taoDauVanTay(NGUON)
  for (const cau of [
    'Buổi sáng của bạn có đang trôi đi vì những việc bếp núc lặt vặt?',
    'Chỉ vài phút là xong bữa sáng, thay vì loay hoay cả buổi',
    'Sản phẩm rút gọn công đoạn chuẩn bị, trả lại cho bạn thời gian buổi sáng',
  ]) {
    const ra = dvt.timTrungLap(cau, v)
    assert.equal(ra.trung, false, `báo nhầm câu hợp lệ: ${cau}`)
    assert.equal(ra.kiemDuoc, true)
  }
})

test('dấu vân tay KHÔNG chứa chữ nào của nguồn — đọc ngược không ra', () => {
  // Đây là lời hứa cốt lõi của H2c. Nếu test này đỏ thì máy chủ đã trở lại
  // thành kho câu chữ nguyên văn, tức mất đúng thứ Scope B của H2 bảo vệ.
  const v = dvt.taoDauVanTay(NGUON)
  const chuoi = JSON.stringify(v)
  for (const tu of ['thời gian', 'buổi sáng', 'MUA NGAY', 'SCROLLING',
    'chiếc máy', 'quy trình']) {
    assert.ok(!chuoi.toLowerCase().includes(tu.toLowerCase()),
      `lộ chữ "${tu}" trong dấu vân tay`)
  }
  assert.match(chuoi, /^\{"v":1,"muoi":"[0-9a-f]{32}"/)
})

test('mỗi bản ghi một muối riêng — không đối chiếu chéo được giữa các video', () => {
  const a = dvt.taoDauVanTay(NGUON)
  const b = dvt.taoDauVanTay(NGUON)
  assert.notEqual(a.muoi, b.muoi)
  assert.notDeepEqual(a.dai, b.dai,
    'cùng nguồn mà băm giống nhau thì dò được bằng kho câu có sẵn')
  // ...nhưng vẫn phải bắt được trùng trong phạm vi CHÍNH bản ghi đó
  const cau = 'Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc gì đó'
  assert.equal(dvt.timTrungLap(cau, a).trung, true)
  assert.equal(dvt.timTrungLap(cau, b).trung, true)
})

test('không có dấu vân tay -> "CHƯA KIỂM ĐƯỢC", tuyệt đối không phải "sạch"', () => {
  for (const xau of [null, undefined, {}, { v: 1 }, { v: 1, dai: [], ngan: [] }]) {
    const ra = dvt.timTrungLap('câu bất kỳ nào đó cũng được', xau)
    assert.equal(ra.kiemDuoc, false, `coi là kiểm được với đầu vào: ${JSON.stringify(xau)}`)
    assert.equal(ra.trung, false)
  }
})

test('dấu vân tay phiên bản KHÁC cũng là "chưa kiểm được"', () => {
  // Đổi thuật toán mà vẫn tin bản ghi cũ là đang so bằng luật đã thay đổi.
  const v = dvt.taoDauVanTay(NGUON)
  v.v = dvt.PHIEN_BAN + 1
  assert.equal(dvt.timTrungLap(NGUON[0], v).kiemDuoc, false)
})

test('không có bằng chứng dùng được -> null, KHÔNG phải dấu vân tay rỗng', () => {
  // Dấu vân tay rỗng sẽ làm mọi kịch bản trông như đã kiểm và sạch.
  assert.equal(dvt.taoDauVanTay([]), null)
  assert.equal(dvt.taoDauVanTay(['', '   ', null]), null)
  assert.equal(dvt.taoDauVanTay(['một']), null, 'dòng 1 từ không đủ để làm bằng chứng')
})

test('dòng một từ bị bỏ có chủ đích, không tạo cớ chặn oan', () => {
  const v = dvt.taoDauVanTay(['Sale', 'MUA NGAY HÔM NAY'])
  assert.equal(dvt.timTrungLap('Sale lớn nhất năm nay đang diễn ra', v).trung, false)
})

test('lọc bằng chứng: bỏ dòng OCR chưa xác nhận, giữ transcript không có status', () => {
  const ra = dvt.locBangChungDaXacNhan([
    { text: 'câu ASR không có status' },
    { text: 'câu OCR đọc chắc', status: 'ok' },
    { text: 'câu OCR đọc không chắc', status: 'unconfirmed' },
    { text: '   ' },
  ])
  assert.deepEqual(ra.dong, ['câu ASR không có status', 'câu OCR đọc chắc'])
  assert.equal(ra.soBoQua, 1)
})

test('chạm trần thì ĐÁNH DẤU, không cắt âm thầm', () => {
  // Cắt bớt mà không nói ra = vùng phủ thủng, và một câu chép nguyên văn rơi
  // đúng phần bị cắt sẽ lọt qua trong im lặng.
  const crypto = require('node:crypto')
  const dong = []
  for (let i = 0; i < 900; i += 1) {
    const t = []
    for (let j = 0; j < 80; j += 1) t.push('tu' + crypto.randomInt(100000))
    dong.push(t.join(' '))
  }
  const v = dvt.taoDauVanTay(dong)
  assert.equal(v.dayTran, true)
  assert.ok(v.dai.length + v.ngan.length <= dvt.SO_BAM_TOI_DA)
})

test('chuẩn hoá dùng CHUNG với gate chống sao chép của H2', () => {
  // Hai bộ chặn lệch chuẩn hoá thì sẽ có ca H2 bắt mà H3 tha.
  const assist = require('../src/prompts/assist')
  assert.equal(typeof dvt.chuanHoaSoKhop, 'function')
  // gate H2 phải bắt đúng ca mà H2c cũng bắt
  const cau = 'Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc nấu nướng không'
  assert.equal(assist.coSaoChepNguyenVan(cau, NGUON), true)
  assert.equal(dvt.timTrungLap(cau, dvt.taoDauVanTay(NGUON)).trung, true)
})

test('dấu câu và chữ hoa không giúp lách bộ chặn', () => {
  const v = dvt.taoDauVanTay(NGUON)
  const ra = dvt.timTrungLap(
    'BẠN CÓ ĐANG MẤT QUÁ NHIỀU THỜI GIAN, mỗi sáng... cho việc gì?', v)
  assert.equal(ra.trung, true)
})
