'use strict'

/**
 * Hồ sơ brand — mini-spec H1 (docs/PLAN.md, Phase H: Viral Flow Clone &
 * Brand Rewrite), nền tảng multi-tenant cho H3 (viết lại kịch bản) và H4
 * (dựng video) đọc sau này.
 *
 * `ownerDeviceId` LÀ khoá cách ly dữ liệu của mini-spec ("owner_account_id"
 * trong đặc tả) — hệ thống này không có khái niệm "tài khoản" tách rời khỏi
 * thiết bị (xem `models/Device.js`: "định danh bằng machine fingerprint
 * SHA-256, không có tài khoản người dùng"), nên "một tài khoản VoxDub" ở đây
 * chính là một thiết bị đã đăng ký. Tái dùng nguyên cơ chế xác thực device
 * hiện có (Vox, cổng trợ lý AI đều đã dùng), không dựng khái niệm tài khoản
 * mới cho H1.
 */
const mongoose = require('mongoose')

const brandProfileSchema = new mongoose.Schema({
  ownerDeviceId: {
    type: mongoose.Schema.Types.ObjectId, ref: 'Device', required: true, index: true,
  },
  tenBrand: { type: String, required: true, trim: true, maxlength: 120 },
  moTaSanPham: { type: String, default: '', maxlength: 2000 },
  doiTuongKhach: { type: String, default: '', maxlength: 1000 },
  // Design Choice của H1: văn bản tự do, không phải danh sách đóng — chưa đủ
  // dữ liệu thật để biết các tone phổ biến nhất, và văn bản tự do linh hoạt
  // hơn cho H3 đọc bằng AI.
  toneGiong: { type: String, default: '', maxlength: 200 },
  usp: { type: String, default: '', maxlength: 1000 },
  // Constraint 4 của H1: H3 đọc trường này để CHẶN khi viết lại kịch bản
  // (ví dụ cấm hứa công dụng y tế, cấm từ tuyệt đối "tốt nhất/số một" — cùng
  // luật đã có ở scene_script C3b).
  rangBuocKhongDuocNoi: { type: [String], default: [] },
  // I7 §B2-b — SÂN KHẤU quen thuộc của thương hiệu.
  //
  // Đặt ở hồ sơ brand chứ không chỉ ở từng kịch bản: đồng nhất trong MỘT
  // video là chuyện dễ, đồng nhất giữa NHIỀU video của cùng thương hiệu mới
  // là thứ người xem nhận ra. Để trống thì mô hình tự chốt cho kịch bản đó —
  // giống nếp chỉ đạo của I6, đây là CHỖ RƠI chứ không phải lệnh.
  sanKhau: {
    boiCanh: { type: String, default: '', maxlength: 300 },
    daoCuAnhSang: { type: String, default: '', maxlength: 300 },
    quyUocKhungNguoi: { type: String, default: '', maxlength: 300 },
  },
  // I6 — nếp chỉ đạo hình ảnh của thương hiệu này.
  //
  // Là GỢI Ý, không phải ràng buộc: `scene_director` vẫn được chọn khác khi
  // một đoạn cần thế. Ép cứng thì preset vô hiệu hoá luôn việc chỉ đạo, mà
  // chỉ đạo mới là thứ người dùng trả tiền.
  //
  // `catalogVersion` để biết preset còn khớp từ điển hiện tại hay đã cũ —
  // cùng lý do với bản chỉ đạo.
  visualPreset: {
    catalogVersion: { type: Number, default: 0 },
    chon: {
      type: [{
        nhom: { type: String, required: true, maxlength: 40 },
        ma: { type: String, required: true, maxlength: 60 },
      }],
      default: [],
      _id: false,
    },
  },
}, { timestamps: true })

module.exports = mongoose.models.BrandProfile
  || mongoose.model('BrandProfile', brandProfileSchema)
