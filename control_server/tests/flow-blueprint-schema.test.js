'use strict'

/**
 * Mini-spec H2 (docs/PLAN.md, Phase H) — khuôn output + bộ chặn sao chép
 * nguyên văn của tác vụ `viral_flow_blueprint`. Test THUẦN (không DB, không
 * gọi AI thật) cho `assistPrompts.coSaoChepNguyenVan`/`parseFlowBlueprintResult`
 * — hai hàm này là lớp AN TOÀN cuối cùng trước khi một Flow Blueprint được
 * lưu, nên phải chứng minh chúng THẬT SỰ chặn được ca sao chép, không chỉ
 * "trông có vẻ đúng".
 */
const test = require('node:test')
const assert = require('node:assert')

const assistPrompts = require('../src/prompts/assist')

const BEAT_HOP_LE = {
  start_s: 0, end_s: 3, beat_type: 'hook',
  narrative_function_vi: 'Mở đầu bằng cách phủ định một thói quen quen thuộc',
  pacing_note_vi: 'Nhịp nhanh, câu ngắn liên tiếp',
  overlay_pattern_abstract_vi: 'Chữ lớn xuất hiện đột ngột giữa khung hình',
  spoken_pattern_abstract_vi: 'Giọng gấp gáp, nhấn mạnh từ phủ định',
}

const NGUON = [
  'Stop wasting money on skincare that does nothing for you.',
  'STOP SCROLLING',
]

test('coSaoChepNguyenVan: câu khác hẳn nguồn -> false', () => {
  assert.equal(
    assistPrompts.coSaoChepNguyenVan(
      'phân tích trừu tượng không liên quan gì tới câu nguồn', NGUON),
    false)
})

test('coSaoChepNguyenVan: 6+ từ liên tiếp trùng nguồn (kể cả khác ngôn ngữ) -> true', () => {
  assert.equal(
    assistPrompts.coSaoChepNguyenVan(
      'video nói rằng stop wasting money on skincare that does nothing for you đó', NGUON),
    true)
})

test('coSaoChepNguyenVan: cụm ngắn trùng ngẫu nhiên (dưới ngưỡng) -> false', () => {
  // "on" và "for" đều xuất hiện trong nguồn nhưng rời rạc, không đủ 6 từ
  // LIÊN TIẾP — không được bắt oan.
  assert.equal(
    assistPrompts.coSaoChepNguyenVan('nhấn mạnh lợi ích cho người xem', NGUON),
    false)
})

test('flowBlueprintOutputSchema: enum beat_type khớp models/FlowBlueprint.js', () => {
  const { BEAT_TYPES } = require('../src/models/FlowBlueprint')
  const schema = assistPrompts.flowBlueprintOutputSchema()
  assert.deepEqual(
    schema.properties.beats.items.properties.beat_type.enum, BEAT_TYPES)
})

test('parseFlowBlueprintResult: beat hợp lệ -> giữ, đổi sang camelCase', () => {
  const parsed = assistPrompts.parseFlowBlueprintResult({ beats: [BEAT_HOP_LE] }, NGUON)
  assert.ok(parsed)
  assert.equal(parsed.beats.length, 1)
  assert.equal(parsed.beats[0].beatType, 'hook')
  assert.equal(parsed.beats[0].startS, 0)
})

test('parseFlowBlueprintResult: beat_type ngoài vocabulary đóng -> bỏ beat đó', () => {
  const beatLa = { ...BEAT_HOP_LE, beat_type: 'khong_co_trong_danh_sach' }
  const parsed = assistPrompts.parseFlowBlueprintResult({ beats: [beatLa, BEAT_HOP_LE] }, NGUON)
  assert.ok(parsed)
  assert.equal(parsed.beats.length, 1, 'chỉ giữ beat hợp lệ, bỏ beat_type lạ')
})

test('parseFlowBlueprintResult: start_s >= end_s -> bỏ beat đó', () => {
  const beatSai = { ...BEAT_HOP_LE, start_s: 5, end_s: 2 }
  const parsed = assistPrompts.parseFlowBlueprintResult({ beats: [beatSai] }, NGUON)
  assert.equal(parsed, null, 'không còn beat nào hợp lệ thì cả kết quả null')
})

test('parseFlowBlueprintResult: rỗng -> null (không được coi là "ready" với 0 beat)', () => {
  assert.equal(assistPrompts.parseFlowBlueprintResult({ beats: [] }, NGUON), null)
  assert.equal(assistPrompts.parseFlowBlueprintResult({}, NGUON), null)
})

// --------------------------------- REGRESSION: chặn sao chép nguyên văn ---

test('REGRESSION: beat chép nguyên văn nguồn vẫn PHẢI bị phát hiện', () => {
  // Guardrail 2/6/7 của H2 — nếu ai đó lỡ gỡ bước kiểm sao chép trong
  // `parseFlowBlueprintResult`, test này phải đỏ (đã xác nhận bằng cách gỡ
  // tạm code, chạy thấy đỏ đúng chỗ, rồi khôi phục — xem docs/TEST_LOG.md).
  //
  // ĐỔI CÓ CHỦ Ý 12/09 — trước đây ca này HUỶ cả kết quả; nay là CẢNH BÁO.
  // Beat chép 10 tiếng nằm trong mô tả 17 tiếng = phủ 59%, dưới ngưỡng huỷ
  // 70%. Quyết định của chủ dự án: H2 đi theo đúng mẫu **H3** — lớp gác thứ
  // SẼ ĐĂNG. H3 không huỷ gì cả, nó gắn `originalityFlag='flagged'` cho đúng
  // đoạn rồi mời viết lại đoạn đó. H2 chỉ sinh bản phân tích NỘI BỘ mà lại
  // chặt hơn hẳn lớp gác quan trọng hơn nó.
  //
  // Lý do đổi (đo, không đoán): hai lượt chạy thật đều hỏng vì từ vựng của
  // chính chủ đề video (`hóa đơn` 11/09, `tự động gửi dữ liệu` 12/09), và
  // trên 15 ca thì CHỈ 45% là sạch — nằm đúng giữa 40% (phải qua) và 45%
  // (phải huỷ), tức không còn biên. Xem `tests/sao-chep-do-bang-ty-le-phu.test.js`.
  //
  // Thứ KHÔNG được mất là khả năng PHÁT HIỆN — nên ca này vẫn phải hiện ra.
  const beatChepNguyenVan = {
    ...BEAT_HOP_LE,
    narrative_function_vi: 'Mô tả: "Stop wasting money on skincare that does '
      + 'nothing for you" chính là câu mở đầu',
  }
  const ket = assistPrompts.parseFlowBlueprintResultChiTiet(
    { beats: [beatChepNguyenVan, BEAT_HOP_LE] }, NGUON)
  assert.equal(ket.ok, true, 'phủ 59% thì không còn huỷ cả kết quả')
  assert.equal(ket.canh_bao.length, 1, 'nhưng PHẢI còn nhìn thấy được')
  assert.match(ket.canh_bao[0].cum, /stop wasting money/i)
})

test('REGRESSION: beat TÁI TẠO nguyên nguồn thì vẫn HUỶ TOÀN BỘ', () => {
  // Nhánh huỷ chưa chết: beat gần như chỉ là chữ của nguồn (phủ >= 70%) vẫn
  // giết cả kết quả, không lọc riêng beat đó — giữ lại beat "sạch" bên cạnh
  // rủi ro làm người review chủ quan bỏ qua beat bẩn.
  const beatTaiTao = {
    ...BEAT_HOP_LE,
    narrative_function_vi: 'stop wasting money on skincare that does nothing for you',
  }
  const parsed = assistPrompts.parseFlowBlueprintResult(
    { beats: [beatTaiTao, BEAT_HOP_LE] }, NGUON)
  assert.equal(parsed, null)
})

test('REGRESSION: chép nguyên văn caption OCR (không phải transcript) vẫn bị PHÁT HIỆN', () => {
  // ĐỔI CÓ CHỦ Ý 12/09 — trước đây ca này HUỶ cả kết quả; nay là CẢNH BÁO.
  //
  // Vì sao đổi: luật cũ "dòng bằng chứng ngắn (>=2 chữ) thì kiểm CHỨA NGUYÊN
  // VẸN" không phân biệt được khẩu hiệu bị chép với từ vựng thông thường của
  // chính ngôn ngữ đầu ra — `STOP SCROLLING` và `hóa đơn` đều hai chữ. Lượt
  // chạy thật 11/09 của chủ dự án hỏng vì mẩu OCR `hóa đơn`, đúng chủ đề
  // video, sau gần sáu phút và ~88 Vox.
  //
  // Đo trên các ca đang có trước khi chọn: không ngưỡng nào sạch (2 -> chặn
  // oan 3/3; 4 -> bỏ sót 2/4). Nên tách hai câu hỏi: "có chạm không" giữ
  // nguyên độ nhạy, "chạm thì có đáng huỷ không" mới dùng ngưỡng 4 chữ.
  //
  // Điều KHÔNG được mất là khả năng phát hiện — nên ca này vẫn phải hiện ra,
  // chỉ ở mức cảnh báo. Xem `tests/sao-chep-dong-ngan-canh-bao.test.js`.
  const beatChepOcr = {
    ...BEAT_HOP_LE,
    overlay_pattern_abstract_vi: 'Chữ overlay ghi đúng dòng STOP SCROLLING trên nền đen',
  }
  const ket = assistPrompts.parseFlowBlueprintResultChiTiet(
    { beats: [beatChepOcr] }, NGUON)
  assert.equal(ket.ok, true, 'dòng hai chữ không còn huỷ cả kết quả')
  assert.equal(ket.canh_bao.length, 1, 'nhưng PHẢI còn nhìn thấy được')
  assert.match(ket.canh_bao[0].cum, /stop scrolling/i)
})
