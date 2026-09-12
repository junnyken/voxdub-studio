'use strict'

/**
 * Cấu hình provider AI (key/model/priority) — lớp DUY NHẤT biết provider/key
 * thật. Dựng lại từ ai-gateway.service.js/admin.js — xem ghi chú Device.js.
 */
const mongoose = require('mongoose')

const aiProviderSchema = new mongoose.Schema({
  name: { type: String, required: true, unique: true, maxlength: 60 },
  label: { type: String, default: '' },
  // 'assist' thêm ở mini-spec V89 — cổng trợ lý đa tác vụ. THIẾU giá trị này
  // thì không ai tạo nổi nhà cung cấp cho vai đó: Mongoose chặn ngay lúc lưu,
  // mà `ai-gateway.service.js` lại đang hỏi `providersFor('assist')` —
  // hệ thống âm thầm dùng chung vai 'translate', đắt hơn hàng chục lần (V94).
  role: {
    type: String,
    enum: ['translate', 'content', 'assist', 'image'],
    default: 'translate',
  },
  // 'openai_compat' = /chat/completions (chữ). Ba giá trị còn lại là các API
  // SINH ẢNH, mỗi nhà một kiểu — xem `services/image-transport.service.js`.
  type: {
    type: String,
    enum: ['openai_compat', 'google', 'openrouter_images', 'openai_images',
      'custom_images'],
    default: 'openai_compat',
  },
  // --- Giao thức tự khai (mini-spec C4) ---------------------------------
  // Để cắm được nền tảng chưa ai lường tới mà không phải chờ bản phát hành
  // mới. Chỉ dùng khi `type === 'custom_images'`.
  imagePath: { type: String, default: '' },          // vd /images/edits
  imageBodyTemplate: { type: String, default: '' },  // JSON có {{cho_dien}}
  imageResponsePath: { type: String, default: '' },  // vd data.0.b64_json
  imageMimePath: { type: String, default: '' },      // vd data.0.media_type
  authHeaderName: { type: String, default: '' },     // mặc định Authorization
  authHeaderValue: { type: String, default: '' },    // mặc định Bearer {{api_key}}
  // --- Phép thử nhìn ảnh (mini-spec C4) ---------------------------------
  // Lần gần nhất mô hình này đọc được nội dung một tấm ảnh do máy chủ vẽ.
  // Rỗng = chưa chứng minh được; bước kiểm bao bì sẽ từ chối dùng.
  visionOkAt: { type: Date, default: null },
  visionNote: { type: String, default: '' },
  baseUrl: { type: String, default: '' },
  apiKeyEnc: { type: String, default: '' },
  model: { type: String, required: true },
  temperature: { type: Number, default: 0.3 },
  maxTokens: { type: Number, default: 16384 },
  priority: { type: Number, default: 100 },
  enabled: { type: Boolean, default: true },
  timeoutMs: { type: Number, default: 180000 },
  disableReasoning: { type: Boolean, default: false },
  lastOkAt: { type: Date, default: null },
  lastErrorAt: { type: Date, default: null },
  lastError: { type: String, default: '' },
}, { timestamps: true })

aiProviderSchema.index({ role: 1, priority: 1 })

module.exports = mongoose.models.AiProvider
  || mongoose.model('AiProvider', aiProviderSchema)
