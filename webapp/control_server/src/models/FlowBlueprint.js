'use strict'

/**
 * Hồ sơ phân tích cấu trúc video tham khảo — mini-spec H2 (docs/PLAN.md,
 * Phase H mới "Viral Flow Clone & Brand Rewrite").
 *
 * `ownerDeviceId` — cùng quy ước H1 (`models/BrandProfile.js`): hệ thống
 * này không có khái niệm "tài khoản" tách khỏi thiết bị.
 *
 * `beats` là kết quả PHÂN TÍCH CẤU TRÚC (trừu tượng), KHÔNG bao giờ chứa
 * transcript/caption gốc nguyên văn — Constraint 2 của H2. Trường
 * `evidence_summary` mô tả TÌNH TRẠNG bằng chứng (đã có/thiếu/không chắc),
 * không phải bằng chứng thô — bằng chứng thô (nếu cần giữ để trace/debug)
 * không có field nào ở entity này, cố ý (Scope B của H2: "Không thêm raw
 * transcript/caption source thành field output-facing hoặc API response").
 */
const mongoose = require('mongoose')

const BEAT_TYPES = [
  'hook', 'problem_context', 'tension', 'proof', 'demonstration',
  'payoff', 'twist', 'objection', 'cta', 'transition', 'unknown',
]

const EVIDENCE_STATUSES = ['no_text', 'unconfirmed', 'unavailable', 'failed', 'ok']

const beatSchema = new mongoose.Schema({
  startS: { type: Number, required: true },
  endS: { type: Number, required: true },
  beatType: { type: String, enum: BEAT_TYPES, required: true },
  narrativeFunctionVi: { type: String, default: '', maxlength: 500 },
  pacingNoteVi: { type: String, default: '', maxlength: 300 },
  overlayPatternAbstractVi: { type: String, default: '', maxlength: 300 },
  spokenPatternAbstractVi: { type: String, default: '', maxlength: 300 },
  evidenceStatus: { type: String, enum: EVIDENCE_STATUSES, default: 'ok' },
}, { _id: false })

/** Dấu vân tay bằng chứng (mini-spec H2c). `dayTran` = số băm chạm trần nên
 * vùng phủ KHÔNG đầy đủ; H3 phải coi đó là "chưa kiểm đủ", không phải "sạch".
 * `soDongBoQua` = số dòng bằng chứng chưa xác nhận đã bị loại trước khi băm. */
const fingerprintSchema = new mongoose.Schema({
  v: { type: Number, required: true },
  muoi: { type: String, required: true },
  dai: { type: [String], default: [] },
  ngan: { type: [String], default: [] },
  nganSoTu: { type: [Number], default: [] },
  soDong: { type: Number, default: 0 },
  soDongBoQua: { type: Number, default: 0 },
  dayTran: { type: Boolean, default: false },
}, { _id: false })

const flowBlueprintSchema = new mongoose.Schema({
  ownerDeviceId: {
    type: mongoose.Schema.Types.ObjectId, ref: 'Device', required: true, index: true,
  },
  sourceType: { type: String, enum: ['url', 'file'], required: true },
  // Chỉ THAM CHIẾU (url hoặc tên file người dùng đặt) — KHÔNG lưu video lên
  // máy chủ (Constraint/chính sách dữ liệu đã áp dụng cho ảnh sản phẩm C1).
  sourceReference: { type: String, required: true, maxlength: 2000 },
  status: {
    type: String,
    enum: ['queued', 'extracting_evidence', 'analyzing', 'ready', 'blocked', 'failed'],
    default: 'queued',
  },
  languageSourceDetected: { type: String, default: '', maxlength: 20 },
  analysisLanguage: { type: String, default: 'vi', maxlength: 10 },
  evidenceSummary: { type: String, default: '', maxlength: 1000 },
  samplingPolicyUsed: { type: String, default: '', maxlength: 200 },
  beats: { type: [beatSchema], default: [] },
  userReviewNote: { type: String, default: '', maxlength: 2000 },
  // Dấu vân tay MỘT CHIỀU của bằng chứng nguồn — mini-spec H2c, dọn đường
  // cho H3 (kiểm kịch bản brand mới có trùng câu chữ video gốc không).
  //
  // KHÔNG phải là ngoại lệ của Constraint 2/Scope B: ở đây chỉ có BĂM, không
  // có chữ, nên máy chủ vẫn không trở thành kho câu chữ nguyên văn dùng lại
  // được. Đánh đổi kèm theo: không trưng ra được cụm gốc bên nguồn — xem
  // `services/dau-van-tay.service.js`.
  //
  // KHÔNG lộ ra API: `view()` ở `routes/flow-blueprints.js` là danh sách
  // trắng, trường này cố ý không có mặt trong đó. Đưa băm ra cho client là
  // biến nó thành máy dò đoán câu nguồn.
  evidenceFingerprint: { type: fingerprintSchema, default: null },
}, { timestamps: true })

module.exports = mongoose.models.FlowBlueprint
  || mongoose.model('FlowBlueprint', flowBlueprintSchema)
module.exports.BEAT_TYPES = BEAT_TYPES
module.exports.EVIDENCE_STATUSES = EVIDENCE_STATUSES
