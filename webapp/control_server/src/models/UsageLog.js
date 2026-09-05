'use strict'

/**
 * Nhật ký từng lượt gọi AI (translate/analyze/review/generate_post/
 * translate_subtitle) — dùng cho đối soát chi phí + dashboard analytics.
 * Dựng lại từ routes/ai.js — xem ghi chú Device.js.
 */
const mongoose = require('mongoose')

const usageLogSchema = new mongoose.Schema({
  fingerprint: { type: String, required: true, index: true },
  jobId: { type: String, required: true },
  action: {
    type: String,
    // 'translate_subtitle' thêm ở mini-spec V14 (docs/PLAN.md) — dịch phụ
    // đề rời, tách khỏi 'translate' (pipeline dub).
    // 'sound_effect'/'music' thêm ở mini-spec V37 — nhạc nền/hiệu ứng âm
    // thanh AI qua ElevenLabs.
    // 'assist' thêm ở mini-spec V89 — cổng trợ lý đa tác vụ. Tên tác vụ cụ
    // thể nằm ở `assistTask` để thống kê tách được từng loại mà không phải
    // nới enum mỗi lần thêm việc mới.
    enum: ['translate', 'analyze', 'review', 'generate_post', 'translate_subtitle',
          'sound_effect', 'music', 'assist',
          // 'product_scene' thêm ở mini-spec C1 — dựng bối cảnh cho ảnh sản
          // phẩm. Ghi riêng để tra được ai đã sinh ảnh nào, phục vụ đúng lúc
          // người bán bị TikTok gắn cờ và cần bằng chứng.
          'product_scene'],
    required: true,
  },
  assistTask: { type: String, default: '' },
  // V89 hoàn thiện: vai trò THẬT đã dùng (chưa cấu hình vai 'assist' thì rơi
  // về 'translate' — đắt hơn nhiều lần, phải nhìn thấy được ở bảng theo dõi)
  // và phiên bản prompt, để tách chất lượng trước/sau mỗi lần sửa câu chữ.
  assistRole: { type: String, default: '' },
  assistPromptVersion: { type: Number, default: 0 },
  fromCache: { type: Boolean, default: false },
  // --- mini-spec C2 -------------------------------------------------------
  // Lượt này là hiệu chỉnh hay chạy thật. LUÔN do máy chủ đặt theo
  // `image.scene.stage`; không bao giờ đọc từ thân yêu cầu.
  runMode: { type: String, default: '' },
  // Phán quyết của bước kiểm bao bì: SAFE | CONCEPT (rỗng = tác vụ khác).
  // Không ghi thứ này thì báo cáo hiệu chỉnh không có gì để đếm — C1 ghi đủ
  // tác vụ, mô hình, token, mã lỗi, nhưng KHÔNG ghi kết quả.
  verdict: { type: String, default: '' },
  // Lý do BẰNG LỜI của mô hình. Đây là thứ người soi tay đọc để quyết đồng ý
  // hay không — thiếu nó thì bảng hiệu chỉnh chỉ còn hai con số SAFE/CONCEPT
  // và không ai soi được gì.
  reason: { type: String, default: '' },
  // --- Soi tay lượt hiệu chỉnh (mini-spec C5) ----------------------------
  // Đếm số LƯỢT không nói lên điều gì: mô hình quyết ra sao là một chuyện,
  // nó quyết ĐÚNG hay SAI là chuyện khác, và chỉ người mới trả lời được.
  // `reviewAgree` = người soi có đồng ý với phán quyết của mô hình không.
  reviewedAt: { type: Date, default: null },
  reviewAgree: { type: Boolean, default: null },
  reviewNote: { type: String, default: '' },
  inputSize: { type: Number, default: 0 },
  status: { type: String, enum: ['pending', 'success', 'error'], default: 'pending' },
  errorCode: { type: String, default: '' },
  errorMessage: { type: String, default: '' },
  creditCharged: { type: Number, default: 0 },
  aiProvider: { type: String, default: '' },
  aiModel: { type: String, default: '' },
  promptTokens: { type: Number, default: 0 },
  completionTokens: { type: Number, default: 0 },
  durationMs: { type: Number, default: 0 },
  ip: { type: String, default: '' },
  appVersion: { type: String, default: '' },
}, { timestamps: true })

usageLogSchema.index({ createdAt: -1 })

module.exports = mongoose.models.UsageLog || mongoose.model('UsageLog', usageLogSchema)
