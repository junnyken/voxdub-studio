'use strict'

/**
 * Nhật ký từng lượt gọi AI (translate/analyze/review/generate_post) — dùng
 * cho đối soát chi phí + dashboard analytics. Dựng lại từ routes/ai.js —
 * xem ghi chú Device.js.
 */
const mongoose = require('mongoose')

const usageLogSchema = new mongoose.Schema({
  fingerprint: { type: String, required: true, index: true },
  jobId: { type: String, required: true },
  action: {
    type: String,
    enum: ['translate', 'analyze', 'review', 'generate_post'],
    required: true,
  },
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
