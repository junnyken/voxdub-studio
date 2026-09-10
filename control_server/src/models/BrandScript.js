'use strict'

/**
 * Kịch bản viết lại cho brand — mini-spec H3 (docs/MINI-SPEC_H3_Brand_Script
 * _Rewrite.md, Phase H "Viral Flow Clone & Brand Rewrite").
 *
 * Sinh từ một `FlowBlueprint` (nhịp kể chuyện) + một `BrandProfile` (giọng
 * điệu, USP, ràng buộc) — cả hai phải thuộc CÙNG thiết bị đang gọi.
 *
 * `ownerDeviceId` — đúng quy ước H1/H2, hệ thống không có khái niệm "tài
 * khoản" tách khỏi thiết bị.
 *
 * **`status` chỉ do engine tính**, không có đường nào cho client đặt thẳng
 * (Constraint 1/D của H3). Bảng ưu tiên: có beat nào `blocked` ⇒ `blocked`;
 * không blocked nhưng có beat chưa kiểm được ⇒ `unconfirmed`; tất cả sạch cả
 * hai cờ ⇒ `ready`.
 *
 * **`flaggedExcerpt` chỉ chứa cụm trong kịch bản MỚI.** Không có trường cho
 * cụm gốc bên video tham khảo: bằng chứng nguồn được lưu dạng băm một chiều
 * (mini-spec H2c), không đọc ngược ra chữ được. Đây là đánh đổi có chủ đích
 * để máy chủ không tích trữ nguyên văn nội dung của người khác.
 */
const mongoose = require('mongoose')

const { BEAT_TYPES } = require('./FlowBlueprint')

const TRANG_THAI = ['draft', 'checking', 'blocked', 'unconfirmed', 'ready', 'failed']
const CO_NGUYEN_GOC = ['clear', 'flagged', 'unconfirmed']
const CO_TUAN_THU = ['clear', 'violated']

/** Vì sao một beat KHÔNG kiểm được — bốn nguyên nhân tách bạch, không gộp
 * thành một câu "chưa kiểm được" (Constraint 6 của H3). Giao diện phải nói
 * đúng nguyên nhân thì người dùng mới biết có làm gì được không. */
const LY_DO_CHUA_KIEM = [
  'khong_co_dau_van_tay',   // Blueprint tạo trước H2c — không vá ngược được
  'khac_phien_ban',         // dấu vân tay dựng bằng thuật toán đời khác
  'day_tran',               // số băm chạm trần ⇒ vùng phủ không đầy đủ
  'bang_chung_khong_du',    // beat nguồn không có bằng chứng xác nhận
]

const beatSchema = new mongoose.Schema({
  beatType: { type: String, enum: BEAT_TYPES, required: true },
  voiceoverTextVi: { type: String, default: '', maxlength: 1500 },
  captionSuggestionVi: { type: String, default: '', maxlength: 300 },
  visualBriefVi: { type: String, default: '', maxlength: 600 },

  originalityFlag: { type: String, enum: CO_NGUYEN_GOC, default: 'unconfirmed' },
  flaggedExcerpt: { type: String, default: '', maxlength: 500 },
  lyDoChuaKiem: { type: String, enum: [...LY_DO_CHUA_KIEM, ''], default: '' },

  complianceFlag: { type: String, enum: CO_TUAN_THU, default: 'clear' },
  complianceExcerpt: { type: String, default: '', maxlength: 500 },
  // Câu trong `rangBuocKhongDuocNoi` đã kích hoạt cờ vi phạm. Trường này CÓ
  // đủ chữ (khác `flaggedExcerpt`) vì ràng buộc do chính người dùng nhập.
  complianceRule: { type: String, default: '', maxlength: 500 },
}, { _id: false })

const brandScriptSchema = new mongoose.Schema({
  ownerDeviceId: {
    type: mongoose.Schema.Types.ObjectId, ref: 'Device', required: true, index: true,
  },
  flowBlueprintId: {
    type: mongoose.Schema.Types.ObjectId, ref: 'FlowBlueprint', required: true, index: true,
  },
  brandProfileId: {
    type: mongoose.Schema.Types.ObjectId, ref: 'BrandProfile', required: true, index: true,
  },
  status: { type: String, enum: TRANG_THAI, default: 'draft' },
  // Phiên bản bộ kiểm nguyên gốc đã dùng (`dau-van-tay.service.PHIEN_BAN`).
  // Script `ready` bằng phiên bản CŨ hơn hiện tại phải bị hạ về
  // `unconfirmed` khi đọc lại — nếu không, một script duyệt bằng luật cũ sẽ
  // `ready` vĩnh viễn dù luật đã đổi (Constraint 13 của H3).
  originalityCheckVersion: { type: Number, default: 0 },
  beats: { type: [beatSchema], default: [] },
}, { timestamps: true })

module.exports = mongoose.models.BrandScript
  || mongoose.model('BrandScript', brandScriptSchema)
module.exports.TRANG_THAI = TRANG_THAI
module.exports.CO_NGUYEN_GOC = CO_NGUYEN_GOC
module.exports.CO_TUAN_THU = CO_TUAN_THU
module.exports.LY_DO_CHUA_KIEM = LY_DO_CHUA_KIEM
