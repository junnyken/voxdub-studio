'use strict'

/**
 * Dựng bối cảnh mới cho ảnh sản phẩm — mini-spec C1.
 *
 * Bối cảnh thay đổi, SẢN PHẨM THÌ KHÔNG. Đó là toàn bộ ý nghĩa của tính năng
 * này, và là ranh giới giữa "chụp ảnh sản phẩm bình thường" với thứ khiến
 * người bán bị TikTok Shop cưỡng chế.
 *
 * Chính sách "quảng bá sản phẩm không nhất quán" của TikTok Shop yêu cầu sản
 * phẩm trong video khớp sản phẩm đang bán về màu, kích thước, chất liệu, thiết
 * kế. Máy của họ quét bằng thị giác máy tính rồi so với ảnh listing — nó không
 * đọc nhãn "AI-generated" của ta trước khi so. Nên câu lệnh gửi cho mô hình
 * phải CẤM đổi bao bì ngay từ đầu, chứ không chỉ kiểm sau khi đã sinh ra.
 *
 * Hai chế độ:
 *   SAFE    — giữ nguyên sản phẩm, chỉ đổi bối cảnh. Dùng cho video bán hàng.
 *   CONCEPT — cho phép dựng lại bao bì. CHỈ để tham khảo ý tưởng; phía app
 *             không cho gắn link sản phẩm và luôn đóng nhãn AI-generated.
 */

/** Câu cấm dùng chung cho mọi bối cảnh ở chế độ SAFE. */
const GIU_NGUYEN_SAN_PHAM = [
  'TUYỆT ĐỐI giữ nguyên sản phẩm trong ảnh gốc: đúng bao bì đó, đúng nhãn đó,',
  'đúng mọi chữ và hình in trên nhãn, đúng màu, đúng kiểu dáng, đúng chất liệu,',
  'đúng loại đóng gói và đúng khối lượng ghi trên bao bì.',
  'KHÔNG vẽ lại nhãn, KHÔNG dịch hay sửa chữ trên bao bì, KHÔNG thêm huy hiệu,',
  'tem, giải thưởng hay dòng chữ quảng cáo nào không có trong ảnh gốc.',
  'KHÔNG đổi số lượng sản phẩm trong khung hình.',
  'Chỉ thay đổi: bối cảnh xung quanh, mặt bàn/nền, ánh sáng, bóng đổ và góc máy.',
].join(' ')

/** Bối cảnh dựng sẵn — mô tả bằng lời, không ghim thương hiệu nào. */
const BOI_CANH = {
  ban_go: {
    ten: 'Bàn gỗ mộc',
    ta: 'đặt trên mặt bàn gỗ mộc, ánh sáng ban ngày dịu từ cửa sổ bên trái, '
      + 'vài chi tiết bếp mờ ở hậu cảnh',
  },
  bep_gia_dinh: {
    ten: 'Bếp gia đình',
    ta: 'trong gian bếp gia đình ấm cúng, hậu cảnh mờ, ánh sáng vàng nhẹ',
  },
  nen_studio: {
    ten: 'Nền studio',
    ta: 'trên nền studio trơn màu kem, ánh sáng đều hai bên, bóng đổ mềm',
  },
  gio_qua: {
    ten: 'Giỏ quà',
    ta: 'đặt cạnh một giỏ quà mây tre và vài nhánh lá khô, ánh sáng ấm',
  },
  ngoai_troi: {
    ten: 'Ngoài trời',
    ta: 'trên bàn gỗ ngoài sân, nắng nhẹ buổi sáng, cây xanh mờ phía sau',
  },
  tay_cam: {
    ten: 'Trên tay',
    ta: 'một bàn tay cầm sản phẩm đưa về phía máy quay, hậu cảnh cửa hàng mờ',
  },
}

const TEN_BOI_CANH = Object.keys(BOI_CANH)

function getBoiCanh(key) {
  return Object.prototype.hasOwnProperty.call(BOI_CANH, key) ? BOI_CANH[key] : null
}

/**
 * Câu lệnh gửi cho mô hình sinh ảnh.
 *
 * `mode` là 'SAFE' hoặc 'CONCEPT'. Mặc định SAFE — chế độ rủi ro phải là thứ
 * người dùng CHỌN, không phải thứ họ rơi vào vì quên đặt tham số.
 */
function buildPrompt({ scene, mode = 'SAFE', note = '' }) {
  const bc = getBoiCanh(scene)
  if (!bc) throw new Error(`Không có bối cảnh "${scene}"`)
  const ghi_chu = String(note || '').trim().slice(0, 300)

  const chung = [
    'Ảnh đính kèm là sản phẩm thật của người bán.',
    `Hãy dựng lại ảnh sản phẩm này ${bc.ta}.`,
    'Ảnh ra phải trông như ảnh chụp thật, sắc nét, dùng được để đăng bán.',
  ]

  if (mode === 'CONCEPT') {
    chung.push(
      'Được phép thiết kế lại bao bì và nhãn theo hướng đẹp hơn.',
      'Đây là ảnh Ý TƯỞNG, không dùng để đăng kèm sản phẩm đang bán.')
  } else {
    chung.push(GIU_NGUYEN_SAN_PHAM)
  }
  if (ghi_chu) chung.push(`Ghi chú của người bán: ${ghi_chu}`)
  return chung.join(' ')
}

module.exports = { BOI_CANH, TEN_BOI_CANH, getBoiCanh, buildPrompt, GIU_NGUYEN_SAN_PHAM }
