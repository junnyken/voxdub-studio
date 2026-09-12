'use strict'

/**
 * Bộ chặn sao chép phải CHỈ RA cụm nào, ở đoạn nào.
 *
 * `parseFlowBlueprintResult` trả `null` khi phát hiện chép nguyên văn —
 * `null` đi lên thành `BAD_AI_RESPONSE` ("Kết quả trả về không dùng được"),
 * gộp chung với ca mô hình trả rác. Hai ca này khác hẳn nhau:
 *
 *   - trả rác      -> lỗi phần mềm/mô hình, người dùng không làm gì được
 *   - chép nguyên văn -> có thật một cụm chữ cụ thể, nói ra thì hiểu ngay
 *
 * Tệp này chỉ đo CÁCH NÓI RA lý do, không đo ngưỡng. Ngưỡng huỷ nằm ở
 * `tests/sao-chep-dong-ngan-canh-bao.test.js` kèm số đo — đừng sửa ngưỡng ở
 * đây rồi tưởng đã đo.
 */
const test = require('node:test')
const assert = require('node:assert')

const {
  parseFlowBlueprintResultChiTiet,
} = require('../src/prompts/assist')

// Dòng >= 4 chữ mới HUỶ (xem `sao-chep-dong-ngan-canh-bao.test.js` cho lý do
// và số đo). Dùng đúng loại dòng đó ở đây, vì tệp này đo cách NÓI RA lý do,
// không đo ngưỡng.
const NGUON = [
  'Super sale đơn nổ mà sao mặt mày thế',
  'MUA NGAY HÔM NAY',
]

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

test('chép nguyên văn thì nói RA cụm nào và ở đoạn thứ mấy', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat(), beat({
      start_s: 3, end_s: 6, beat_type: 'problem_context',
      narrative_function_vi: 'Chữ lớn ghi mua ngay hôm nay… rồi mờ dần.',
    })] }, NGUON)

  assert.strictEqual(ket.ok, false)
  assert.strictEqual(ket.ly_do, 'SAO_CHEP_NGUYEN_VAN')
  assert.strictEqual(ket.doan, 2, 'phải nói đoạn thứ mấy, đếm từ 1')
  assert.strictEqual(ket.truong, 'narrative_function_vi')
  assert.match(ket.cum, /mua ngay hôm nay/,
    'phải nói cụm bị coi là chép — không nói thì không sửa được gì')
})

test('chép nguyên câu thoại (n-gram 6 chữ) vẫn huỷ và vẫn nói ra cụm', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat({
      overlay_pattern_abstract_vi: 'Nhắc lại super sale đơn nổ mà sao mặt mày thế',
    })] }, NGUON)

  assert.strictEqual(ket.ok, false)
  assert.strictEqual(ket.ly_do, 'SAO_CHEP_NGUYEN_VAN')
  assert.strictEqual(ket.truong, 'overlay_pattern_abstract_vi')
  assert.match(ket.cum, /super sale đơn nổ/i)
})

test('khuôn sai thì nói là khuôn sai, KHÁC với chép', () => {
  const ket = parseFlowBlueprintResultChiTiet({ beats: [] }, NGUON)
  assert.strictEqual(ket.ok, false)
  assert.strictEqual(ket.ly_do, 'KHUON_SAI')
})

test('mọi beat đều bị loại vì mốc thời gian hỏng cũng là KHUÔN SAI', () => {
  const ket = parseFlowBlueprintResultChiTiet(
    { beats: [beat({ start_s: 5, end_s: 1 })] }, NGUON)
  assert.strictEqual(ket.ok, false)
  assert.strictEqual(ket.ly_do, 'KHUON_SAI')
})

test('kết quả sạch thì trả beats như cũ', () => {
  const ket = parseFlowBlueprintResultChiTiet({ beats: [beat()] }, NGUON)
  assert.strictEqual(ket.ok, true)
  assert.strictEqual(ket.beats.length, 1)
  assert.strictEqual(ket.beats[0].beatType, 'hook')
})

test('hàm cũ `parseFlowBlueprintResult` giữ NGUYÊN chữ ký (null khi hỏng)', () => {
  const { parseFlowBlueprintResult } = require('../src/prompts/assist')
  assert.strictEqual(
    parseFlowBlueprintResult({ beats: [] }, NGUON), null,
    'còn nơi khác gọi hàm này — đổi chữ ký là gãy âm thầm')
  const ok = parseFlowBlueprintResult({ beats: [beat()] }, NGUON)
  assert.ok(ok && ok.beats.length === 1)
})
