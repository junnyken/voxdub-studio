'use strict'

/**
 * Độ NHẠY PHÁT HIỆN không được giảm khi hạ mức hậu quả.
 *
 * `sao-chep-do-bang-ty-le-phu.test.js` chốt NGƯỠNG HUỶ (70%) kèm số đo. Tệp
 * này chốt thứ khác và quan trọng không kém: mọi ca từng bị bắt trước đây
 * vẫn phải **hiện ra**, chỉ khác ở chỗ nay là cờ cảnh báo thay vì giết cả
 * lượt chạy.
 *
 * Vì sao tách hai tệp: hạ ngưỡng mà bỏ luôn phát hiện là "chữa" bằng cách
 * gỡ guardrail — trông y hệt nhau trên bảng kết quả test nếu chỉ chốt ngưỡng.
 */
const test = require('node:test')
const assert = require('node:assert')

const { parseFlowBlueprintResultChiTiet } = require('../src/prompts/assist')

function beat(ghiDe = {}) {
  return {
    start_s: 0, end_s: 3, beat_type: 'hook',
    narrative_function_vi: 'Mở đầu bằng tình huống quá tải, tạo đồng cảm.',
    pacing_note_vi: 'Cắt nhanh, hai nhịp trong ba giây.',
    overlay_pattern_abstract_vi: 'Chữ lớn giữa khung, xuất hiện đột ngột.',
    spoken_pattern_abstract_vi: 'Giọng than, nhịp gấp.',
    ...ghiDe,
  }
}

const XIN = (ghiDe, nguon) =>
  parseFlowBlueprintResultChiTiet({ beats: [beat(ghiDe)] }, nguon)

// --- Vẫn PHÁT HIỆN, kèm đủ thông tin để người đọc tự xét -------------------

test('cảnh báo mang đủ: số đoạn, trường nào, cụm nào', () => {
  const ket = XIN(
    { narrative_function_vi: 'Nêu vấn đề: khối lượng hóa đơn thủ công.' },
    ['hóa đơn'])

  assert.strictEqual(ket.ok, true)
  assert.strictEqual(ket.canh_bao.length, 1,
    'bỏ luôn cảnh báo là mất khả năng phát hiện — chỉ hạ mức, không bỏ')
  assert.strictEqual(ket.canh_bao[0].doan, 1, 'phải nói đoạn thứ mấy')
  assert.strictEqual(ket.canh_bao[0].truong, 'narrative_function_vi')
  assert.match(ket.canh_bao[0].cum, /hóa đơn/)
})

test('khẩu hiệu 2 tiếng bị nhắc lại — vẫn phát hiện', () => {
  const ket = XIN(
    { overlay_pattern_abstract_vi:
        'Chữ overlay ghi đúng dòng STOP SCROLLING trên nền đen' },
    ['STOP SCROLLING'])
  assert.strictEqual(ket.canh_bao.length, 1)
  assert.match(ket.canh_bao[0].cum, /stop scrolling/i)
})

test('caption 4 tiếng bị chép — vẫn phát hiện', () => {
  const ket = XIN(
    { overlay_pattern_abstract_vi: 'chữ lớn ghi mua ngay hôm nay… giá sốc' },
    ['MUA NGAY HÔM NAY'])
  assert.strictEqual(ket.canh_bao.length, 1)
  assert.match(ket.canh_bao[0].cum, /mua ngay hôm nay/)
})

test('chép nguyên câu thoại — vẫn phát hiện', () => {
  const ket = XIN(
    { narrative_function_vi:
        'Mở đầu bằng câu stop wasting money on this rồi cắt cảnh' },
    ['Stop wasting money on this.'])
  assert.strictEqual(ket.canh_bao.length, 1)
  assert.match(ket.canh_bao[0].cum, /stop wasting money/i)
})

test('dấu ba chấm chèn vào KHÔNG làm mất dấu vết (bài học 10/09)', () => {
  // Lỗ hổng 10/09 là dấu câu làm cụm không khớp băm nữa — tức mất PHÁT HIỆN.
  // Đó mới là thứ phải giữ; mức hậu quả là chuyện khác.
  const ket = XIN(
    { overlay_pattern_abstract_vi:
        'overlay ghi đặt hàng ngay hôm nay… rồi mờ dần' },
    ['ĐẶT HÀNG NGAY HÔM NAY'])
  assert.strictEqual(ket.canh_bao.length, 1)
  assert.match(ket.canh_bao[0].cum, /đặt hàng ngay hôm nay/)
})

// --- Không báo bừa ---------------------------------------------------------

test('kết quả sạch không có cảnh báo nào', () => {
  const ket = parseFlowBlueprintResultChiTiet({ beats: [beat()] }, ['xin chào'])
  assert.strictEqual(ket.ok, true)
  assert.deepStrictEqual(ket.canh_bao, [])
})

test('một tiếng đơn không bao giờ chạm tới luật nào', () => {
  const ket = XIN(
    { narrative_function_vi: 'Mở đầu bằng một câu than.' }, ['than'])
  assert.strictEqual(ket.ok, true)
  assert.deepStrictEqual(ket.canh_bao, [])
})

test('nhiều đoạn chạm thì cảnh báo đủ từng đoạn, không dừng ở đoạn đầu', () => {
  const ket = parseFlowBlueprintResultChiTiet({
    beats: [
      beat({ narrative_function_vi: 'Nêu vấn đề: khối lượng hóa đơn thủ công.' }),
      beat({ start_s: 3, end_s: 6, beat_type: 'proof',
             narrative_function_vi: 'Bằng chứng: có cảnh báo khi thiếu số.' }),
    ],
  }, ['hóa đơn', 'cảnh báo'])

  assert.strictEqual(ket.ok, true)
  assert.strictEqual(ket.canh_bao.length, 2,
    'dừng ở đoạn đầu thì đoạn sau không ai biết')
  assert.deepStrictEqual(ket.canh_bao.map((c) => c.doan), [1, 2])
})
