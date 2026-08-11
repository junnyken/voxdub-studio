'use strict'

/**
 * Giữ chỗ Vox (hold) — luồng wizard: hold sau ASR, commit lúc xuất video.
 * Dựng lại từ hold.service.js — xem ghi chú trong Device.js. Field/index ở
 * đây được RÀNG BUỘC bởi test có sẵn `tests/hold.test.js` (status enum,
 * index {status,expiresAt}, holdId unique) — không đổi các ràng buộc đó.
 */
const mongoose = require('mongoose')

const usageEntrySchema = new mongoose.Schema({
  action: { type: String, required: true },
  jobId: { type: String, required: true },
  vox: { type: Number, required: true },
  sentences: { type: Number, default: 0 },
  at: { type: Date, default: Date.now },
}, { _id: false })

const creditHoldSchema = new mongoose.Schema({
  holdId: {
    type: String, required: true, unique: true,
  },
  fingerprint: { type: String, required: true, index: true },
  deviceId: { type: mongoose.Schema.Types.ObjectId, ref: 'Device', required: true },
  estimatedVox: { type: Number, required: true },
  usedVox: { type: Number, default: 0 },
  usage: { type: [usageEntrySchema], default: [] },
  encKeyHex: { type: String, required: true },
  status: { type: String, enum: ['active', 'committed', 'released'], default: 'active' },
  expiresAt: { type: Date, required: true },
  committedAt: { type: Date, default: null },
  autoCommitted: { type: Boolean, default: false },
  meta: { type: mongoose.Schema.Types.Mixed, default: {} },
}, { timestamps: true })

// Sweeper (`expireSweep`) quét { status, expiresAt } — không được thiếu.
creditHoldSchema.index({ status: 1, expiresAt: 1 })

module.exports = mongoose.models.CreditHold
  || mongoose.model('CreditHold', creditHoldSchema)
