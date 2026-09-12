'use strict'

/**
 * Dòng bằng chứng NGẮN: cảnh báo, không huỷ — đo trước khi chọn (12/09).
 *
 * Lượt chạy thật 11/09 trên `youtube.com/shorts/9iB1Io8InXg` hỏng vì mẩu OCR
 * hai chữ `hóa đơn` — đúng chủ đề video — nằm trong mô tả của một đoạn. Luật
 * "dòng ngắn thì kiểm CHỨA NGUYÊN VẸN" biến nó thành lệnh huỷ toàn bộ, trong
 * khi mô hình bị buộc mô tả một video tiếng Việt về hoá đơn, bằng tiếng Việt.
 *
 * ĐO trên các ca đang có trước khi chốt ngưỡng (kỷ luật "đo trước khi đặt
 * tolerance"). Kết quả: **không ngưỡng nào sạch** — số chữ không phân biệt
 * được khẩu hiệu bị chép với từ vựng thông thường, vì `STOP SCROLLING` và
 * `hóa đơn` đều hai chữ:
 *
 *     ngưỡng 2 (cũ): bỏ sót 0/4, chặn oan 3/3
 *     ngưỡng 3:      bỏ sót 1/4, chặn oan 1/3
 *     ngưỡng 4:      bỏ sót 2/4, chặn oan 1/3
 *     ngưỡng 5:      bỏ sót 3/4, chặn oan 0/3
 *
 * Nên tách HAI câu hỏi vốn bị gộp làm một:
 *
 *   1. Có chạm bằng chứng nguồn không?  -> giữ nguyên độ nhạy, không đổi.
 *   2. Chạm thì có đáng HUỶ CẢ KẾT QUẢ không?  -> chỉ khi đủ dài.
 *
 * Dòng ≥4 chữ (`MUA NGAY HÔM NAY`) và n-gram 6 chữ vẫn huỷ như cũ. Dòng 2–3
 * chữ chuyển thành CẢNH BÁO gắn vào kết quả: không mất ca phát hiện nào,
 * cũng không giết lượt chạy vì một từ ghép thông thường.
 */
const test = require('node:test')
const assert = require('node:assert')

const {
  parseFlowBlueprintResultChiTiet, TOI_THIEU_TU_DE_HUY,
} = require('../src/prompts/assist')

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

test('ngưỡng huỷ là 4 chữ — chốt lại con số đã chọn sau khi đo', () => {
  assert.strictEqual(TOI_THIEU_TU_DE_HUY, 4)
})

// --- KHÔNG còn huỷ vì từ ghép thông thường ---------------------------------

test('từ ghép 2 chữ đúng chủ đề video KHÔNG huỷ kết quả nữa', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat({
      narrative_function_vi: 'Nêu vấn đề: khối lượng hóa đơn thủ công.',
    })] }, ['hóa đơn'])

  assert.strictEqual(ket.ok, true,
    'đây là ca người dùng gặp thật 11/09 — huỷ ở đây là giết lượt chạy vì '
    + 'mô hình gọi đúng tên thứ mà video nói về')
})

test('nhưng VẪN cảnh báo, kèm cụm và số đoạn', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat({
      narrative_function_vi: 'Nêu vấn đề: khối lượng hóa đơn thủ công.',
    })] }, ['hóa đơn'])

  assert.strictEqual(ket.canh_bao.length, 1,
    'bỏ luôn cảnh báo là mất khả năng phát hiện — chỉ hạ mức, không bỏ')
  assert.strictEqual(ket.canh_bao[0].doan, 1)
  assert.match(ket.canh_bao[0].cum, /hóa đơn/)
})

test('khẩu hiệu 2 chữ bị chép: cảnh báo chứ không huỷ, VẪN phát hiện được', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat({
      overlay_pattern_abstract_vi: 'Chữ overlay ghi đúng dòng STOP SCROLLING trên nền đen',
    })] }, ['STOP SCROLLING'])

  assert.strictEqual(ket.ok, true)
  assert.strictEqual(ket.canh_bao.length, 1,
    'ca này trước đây huỷ; hạ xuống cảnh báo thì vẫn phải NHÌN THẤY được — '
    + 'ngưỡng 4 mà bỏ luôn cảnh báo là bỏ sót thật')
  assert.match(ket.canh_bao[0].cum, /stop scrolling/i)
})

// --- VẪN huỷ với ca chép thật ----------------------------------------------

test('caption 4 chữ bị chép nguyên văn vẫn HUỶ cả kết quả', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat({
      overlay_pattern_abstract_vi: 'chữ lớn ghi mua ngay hôm nay… giá sốc',
    })] }, ['MUA NGAY HÔM NAY'])

  assert.strictEqual(ket.ok, false)
  assert.strictEqual(ket.ly_do, 'SAO_CHEP_NGUYEN_VAN')
})

test('chép nguyên câu thoại (n-gram 6 chữ) vẫn HUỶ — luật này không đổi', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat({
      narrative_function_vi: 'Mở đầu bằng câu stop wasting money on this rồi cắt cảnh',
    })] }, ['Stop wasting money on this.'])

  assert.strictEqual(ket.ok, false)
  assert.strictEqual(ket.ly_do, 'SAO_CHEP_NGUYEN_VAN')
})

test('dấu ba chấm chèn vào vẫn không lách được (bài học 10/09)', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat({
      overlay_pattern_abstract_vi: 'overlay ghi đặt hàng ngay hôm nay… rồi mờ dần',
    })] }, ['ĐẶT HÀNG NGAY HÔM NAY'])

  assert.strictEqual(ket.ok, false)
})

test('kết quả sạch không có cảnh báo nào', () => {
  const ket = parseFlowBlueprintResultChiTiet({ beats: [beat()] }, ['xin chào'])
  assert.strictEqual(ket.ok, true)
  assert.deepStrictEqual(ket.canh_bao, [])
})

test('một chữ đơn không bao giờ chạm tới luật nào', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat({ narrative_function_vi: 'Mở đầu bằng một câu than.' })] },
    ['than'])
  assert.strictEqual(ket.ok, true)
  assert.deepStrictEqual(ket.canh_bao, [])
})
