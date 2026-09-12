'use strict'

/**
 * Huỷ kết quả khi beat bị bằng chứng nguồn PHỦ nhiều, không phải khi cụm đủ dài.
 *
 * Lượt chạy thật 12/09 của chủ dự án hỏng lần thứ hai: đoạn 5 bị huỷ vì cụm
 * `tự động gửi dữ liệu` — chức năng của phần mềm trong video. Mô tả "vai trò
 * kể chuyện" của đoạn đó mà không được gọi tên việc phần mềm tự động gửi dữ
 * liệu thì không mô tả được gì.
 *
 * ĐO ra nguyên nhân sâu hơn ngưỡng: `tự động gửi dữ liệu lên` là **ba từ**
 * tiếng Việt nhưng **sáu âm tiết**, nên nó rơi vào luật n-gram. Ngưỡng
 * `NGUONG_TU_LIEN_TIEP = 6` hiệu chỉnh trên ví dụ tiếng Anh ("Stop wasting
 * money on this" = 5 từ = 5 tiếng). Tiếng Việt tách theo âm tiết, nên 6 tiếng
 * chỉ là một cụm tầm thường — luật chặt hơn tiếng Anh gấp đôi mà không ai
 * chọn điều đó.
 *
 * Nên đổi ĐẠI LƯỢNG chứ không đổi con số: "chép" nghĩa là beat TÁI TẠO nguồn,
 * đo bằng phần trăm beat bị cụm khớp phủ — giống cách đo đạo văn thật, không
 * phải bằng độ dài tuyệt đối của một cụm.
 *
 * Số đo trên 15 ca (7 phải huỷ, 8 không được huỷ):
 *
 *     luật cũ (cụm >= 4 tiếng): sai 5/15
 *     phủ >= 30% | 35% | 40%:   sai 1/15
 *     phủ >= 45%:               sai 0/15   <- điểm DUY NHẤT sạch
 *     phủ >= 50%:               sai 1/15
 *
 * Một điểm duy nhất đúng, nằm giữa 40% (ca phải qua) và 45% (ca phải huỷ),
 * nghĩa là phép đo VẪN chưa tách được hai lớp — không phải đã tìm ra ngưỡng.
 * Nên chuyển sang mẫu H3: huỷ chỉ ở mức không còn tranh cãi (70%), còn lại
 * gắn cờ cảnh báo. Xem chú thích `TY_LE_PHU_DE_HUY` trong `src/prompts/assist.js`.
 */
const test = require('node:test')
const assert = require('node:assert')

const {
  parseFlowBlueprintResultChiTiet, TY_LE_PHU_DE_HUY,
} = require('../src/prompts/assist')

function beat(vanBan, ghiDe = {}) {
  return {
    start_s: 0, end_s: 3, beat_type: 'proof',
    narrative_function_vi: vanBan,
    pacing_note_vi: 'Cắt nhanh.',
    overlay_pattern_abstract_vi: 'Chữ lớn giữa khung.',
    spoken_pattern_abstract_vi: 'Giọng gấp.',
    ...ghiDe,
  }
}

const XIN = (vanBan, nguon) =>
  parseFlowBlueprintResultChiTiet({ beats: [beat(vanBan)] }, nguon)

test('ngưỡng huỷ là 70% — mức KHÔNG còn tranh cãi', () => {
  // 45% là giá trị duy nhất sạch trên 15 ca, nhưng nằm ĐÚNG trên ranh: ca
  // phải qua của chủ dự án phủ 40%, ca phải huỷ phủ 45%. Không biên nào cả,
  // nên video thứ ba lệch một chút là lại mất 88 Vox và năm phút.
  //
  // Chủ dự án chọn (12/09) đi theo đúng mẫu H3 — lớp gác thứ SẼ ĐĂNG: H3
  // không huỷ gì cả, nó gắn `originalityFlag='flagged'` cho đúng đoạn rồi
  // mời viết lại đoạn đó. H2 chỉ sinh bản phân tích nội bộ mà lại chặt hơn
  // hẳn lớp gác quan trọng hơn nó — đó mới là chỗ sai.
  //
  // 70% = beat bị nguồn phủ hơn hai phần ba, không ai gọi đó là phân tích.
  // Cách ca phải-qua cao nhất đo được (40%) tới 30 điểm.
  assert.strictEqual(TY_LE_PHU_DE_HUY, 0.7)
})

// --- KHÔNG được huỷ: mô tả dùng từ vựng của chủ đề ------------------------

test('ĐO THẬT 12/09 — đoạn tả chức năng phần mềm KHÔNG bị huỷ', () => {
  const ket = XIN(
    'Bằng chứng: phần mềm tự động gửi dữ liệu lên cơ quan thuế mỗi ngày, '
    + 'kèm nhắc nhở thông minh.',
    ['tự động gửi dữ liệu',
     'Và tự động gửi dữ liệu lên cơ quan phối mỗi ngày'])

  assert.strictEqual(ket.ok, true,
    'đây là ca người dùng gặp thật lần thứ hai — huỷ ở đây là bắt mô hình '
    + 'mô tả một video mà không được gọi tên thứ video đó nói về')
  assert.strictEqual(ket.canh_bao.length, 1, 'vẫn phải thấy được')
})

test('cụm 6 ÂM TIẾT (3 từ) không còn tự động huỷ như luật n-gram cũ', () => {
  const ket = XIN(
    'Bằng chứng: công cụ tự động gửi dữ liệu lên cơ quan thuế mỗi ngày mà '
    + 'người bán không phải thao tác gì thêm, kèm cảnh báo khi thiếu.',
    ['tự động gửi dữ liệu lên'])
  assert.strictEqual(ket.ok, true)
})

test('tên sản phẩm trong mô tả dài — qua', () => {
  const ket = XIN(
    'Giới thiệu giải pháp: phần mềm misa einvoice được nêu tên ở giữa video, '
    + 'chữ lớn.', ['misa einvoice'])
  assert.strictEqual(ket.ok, true)
})

test('nhắc khẩu hiệu bên trong mô tả dài — qua, nhưng có cảnh báo', () => {
  const ket = XIN(
    'Chữ overlay lớn giữa khung ghi đúng dòng STOP SCROLLING trên nền đen, '
    + 'xuất hiện đột ngột', ['STOP SCROLLING'])
  assert.strictEqual(ket.ok, true)
  assert.strictEqual(ket.canh_bao.length, 1)
})

// --- VẪN phải huỷ: beat tái tạo nguồn -------------------------------------

test('beat CHÍNH LÀ caption — huỷ', () => {
  const ket = XIN('mua ngay hôm nay', ['MUA NGAY HÔM NAY'])
  assert.strictEqual(ket.ok, false)
  assert.strictEqual(ket.ly_do, 'SAO_CHEP_NGUYEN_VAN')
})

test('beat nhại nguyên CTA, thêm một chữ — huỷ (phủ 75%)', () => {
  assert.strictEqual(XIN('đặt hàng ngay thôi', ['ĐẶT HÀNG NGAY']).ok, false)
})

test('beat một nửa là caption — CẢNH BÁO, không huỷ', () => {
  // Phủ 50%: nửa mô tả vẫn là chữ của người viết. Theo mẫu H3 thì đây là ca
  // gắn cờ cho người đọc tự xét, không phải ca giết cả lượt chạy.
  const ket = XIN('Chốt bằng sale sốc hôm nay cuối cùng', ['SALE SỐC HÔM NAY'])
  assert.strictEqual(ket.ok, true)
  assert.strictEqual(ket.canh_bao.length, 1)
  assert.match(ket.canh_bao[0].cum, /sale sốc hôm nay/)
})

test('chép nguyên câu thoại tiếng Anh — CẢNH BÁO (phủ 45%)', () => {
  const ket = XIN('Mở đầu bằng câu stop wasting money on this rồi cắt',
                  ['Stop wasting money on this.'])
  assert.strictEqual(ket.ok, true)
  assert.strictEqual(ket.canh_bao.length, 1,
    'hạ mức thì vẫn PHẢI nhìn thấy được — bỏ luôn là mất khả năng phát hiện')
})

test('chép NGUYÊN VẸN một câu thoại — vẫn huỷ (phủ 100%)', () => {
  assert.strictEqual(
    XIN('lai xong ngồi gom đơn đến 2 giờ sáng nhập hóa đơn',
        ['Lai xong ngồi gom đơn đến 2 giờ sáng nhập hóa đơn']).ok, false)
})

test('CA THẬT trong repo — chép nguyên câu 10 tiếng, phủ 59% -> cảnh báo', () => {
  // `flow-blueprint-schema.test.js` chốt ca này là HUỶ từ trước. Đổi có chủ
  // ý theo quyết định 12/09; test kia cập nhật kèm lý do tại chỗ.
  const ket = XIN(
    'Mô tả: "Stop wasting money on skincare that does nothing for you" '
    + 'chính là câu mở đầu',
    ['Stop wasting money on skincare that does nothing for you.'])
  assert.strictEqual(ket.ok, true)
  assert.strictEqual(ket.canh_bao.length, 1)
})

test('dấu ba chấm chèn vào vẫn không lách được (bài học 10/09)', () => {
  // Phủ 4/6 = 67% -> dưới 70%, thành cảnh báo. Điều PHẢI giữ là dấu ba chấm
  // không làm mất PHÁT HIỆN — đó mới là lỗ hổng của bài học 10/09.
  const ket = XIN('mua ngay hôm nay… giá sốc', ['MUA NGAY HÔM NAY'])
  assert.strictEqual(ket.canh_bao.length, 1,
    'dấu câu chèn vào không được làm mất dấu vết')
  assert.match(ket.canh_bao[0].cum, /mua ngay hôm nay/)
})

// --- Lấy khớp DÀI NHẤT, không phải khớp đầu tiên ---------------------------

test('nhiều nguồn khớp thì tính theo cụm DÀI NHẤT', () => {
  // Khớp ngắn gặp trước không được che mất khớp dài đứng sau, nếu không thì
  // thứ tự dòng bằng chứng quyết định kết quả — cùng video, cùng beat, đảo
  // thứ tự OCR là ra kết quả khác.
  const ket = XIN('sale sốc hôm nay nhé', ['sốc', 'SALE SỐC HÔM NAY'])
  assert.strictEqual(ket.ok, false,
    'khớp 4 tiếng phủ 4/5 = 80% phải thắng khớp 1 tiếng gặp trước')
})

test('kết quả sạch không có cảnh báo nào', () => {
  const ket = XIN('Mở đầu bằng tình huống quá tải, tạo đồng cảm.', ['xin chào'])
  assert.strictEqual(ket.ok, true)
  assert.deepStrictEqual(ket.canh_bao, [])
})
