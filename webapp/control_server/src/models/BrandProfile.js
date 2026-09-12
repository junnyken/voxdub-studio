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
}, { timestamps: true })

module.exports = mongoose.models.BrandProfile
  || mongoose.model('BrandProfile', brandProfileSchema)
