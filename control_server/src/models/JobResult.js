'use strict'

/**
 * Kết quả đã lưu theo jobId — cho phép app retry an toàn (idempotent replay)
 * mà không bị tính phí/gọi AI lần hai. Dựng lại từ routes/ai.js — xem ghi
 * chú Device.js.
 */
const mongoose = require('mongoose')

const jobResultSchema = new mongoose.Schema({
  jobId: { type: String, required: true },
  fingerprint: { type: String, required: true },
  action: {
    type: String,
    enum: ['translate', 'analyze', 'review', 'generate_post'],
    required: true,
  },
  result: { type: mongoose.Schema.Types.Mixed, required: true },
  creditCharged: { type: Number, default: 0 },
}, { timestamps: true })

// replay() đọc bằng {jobId, fingerprint} — cùng cặp phải là duy nhất,
// remember() dựa vào lỗi 11000 để phát hiện "đã lưu rồi".
jobResultSchema.index({ jobId: 1, fingerprint: 1 }, { unique: true })

module.exports = mongoose.models.JobResult || mongoose.model('JobResult', jobResultSchema)
