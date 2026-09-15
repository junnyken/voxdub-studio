'use strict'

/**
 * Ảnh minh hoạ cho một đoạn kịch bản — mini-spec H4d.
 *
 * Khác hẳn `product_scene.js`, và khác ở đúng chỗ nguy hiểm nhất: ở đó có ảnh
 * sản phẩm THẬT làm neo, luật là "đừng đổi gì cả". Ở đây không có neo nào —
 * mô hình vẽ từ chữ — nên luật phải là điều ngược lại: **đừng vẽ sản phẩm nào
 * hết**.
 *
 * Vì sao gắt như vậy cho một tấm ảnh nền: ảnh này nằm trong CÙNG một video
 * bán hàng, cạnh sản phẩm thật. Mô hình vẽ ra một hộp, một chai hay một gói
 * có nhãn — dù nhãn hoàn toàn bịa — thì người xem lẫn máy quét thị giác của
 * TikTok đều thấy "sản phẩm" trong video quảng bá. Đó đúng là điều khoản
 * *quảng bá sản phẩm không nhất quán* đã đẻ ra C1, chỉ tới từ cửa khác.
 *
 * Câu lệnh một mình không đủ để tin (bài học "Đo trước khi tin prompt": chỉ
 * khoảng một phần ba luật viết trong prompt thật sự có tác dụng). Nên phía
 * sau còn một bước kiểm ảnh riêng — `kiem_anh_minh_hoa` trong `assist.js`.
 */

/** Trần độ dài gợi ý hình ảnh nhận từ kịch bản. */
const DAI_TOI_DA = 400

/**
 * Phần cấm, dùng chung cho mọi ảnh minh hoạ.
 *
 * Cấm cả CHỮ đọc được, không chỉ cấm nhãn: mô hình sinh ảnh viết chữ sai
 * chính tả rất thường xuyên, và một dòng chữ méo mó trên khung hình của video
 * bán hàng vừa lộ là ảnh máy vẽ, vừa có thể trùng tên một thương hiệu thật.
 */
const KHONG_VE_SAN_PHAM = [
  'TUYỆT ĐỐI không vẽ bất kỳ sản phẩm đóng gói nào: không hộp, không chai,',
  'không lọ, không túi, không gói có nhãn.',
  'KHÔNG vẽ logo, thương hiệu, tem nhãn hay bao bì của bất kỳ hãng nào.',
  'KHÔNG vẽ chữ, số hay ký tự đọc được ở bất kỳ đâu trong khung hình.',
  'Đây là ảnh MINH HOẠ bối cảnh, không phải ảnh sản phẩm.',
].join(' ')

/**
 * Câu lệnh gửi cho mô hình sinh ảnh.
 *
 * `brief` là `visualBriefVi` của một đoạn kịch bản — đã bị prompt H3 cấm mô tả
 * nhận dạng người (khuôn mặt, tuổi, tóc, trang phục), nên tới đây nó chỉ còn
 * vai trò và hành động.
 */
function buildPrompt({ brief }) {
  const goi_y = String(brief || '').trim().slice(0, DAI_TOI_DA)
  if (!goi_y) throw new Error('Thiếu gợi ý hình ảnh cho ảnh minh hoạ')

  return [
    `Vẽ một khung hình minh hoạ: ${goi_y}.`,
    'Khung dọc 9:16, trông như ảnh chụp thật, ánh sáng tự nhiên, hậu cảnh mờ nhẹ.',
    KHONG_VE_SAN_PHAM,
  ].join(' ')
}

module.exports = { buildPrompt, KHONG_VE_SAN_PHAM, DAI_TOI_DA }
