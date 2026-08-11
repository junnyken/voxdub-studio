'use strict'

/**
 * Cấu hình provider AI (key/model/priority) — lớp DUY NHẤT biết provider/key
 * thật. Dựng lại từ ai-gateway.service.js/admin.js — xem ghi chú Device.js.
 */
const mongoose = require('mongoose')

const aiProviderSchema = new mongoose.Schema({
  name: { type: String, required: true, unique: true, maxlength: 60 },
  label: { type: String, default: '' },
  role: { type: String, enum: ['translate', 'content'], default: 'translate' },
  type: { type: String, enum: ['openai_compat', 'google'], default: 'openai_compat' },
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
