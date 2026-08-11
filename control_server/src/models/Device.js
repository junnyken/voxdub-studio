'use strict'

/**
 * Thiết bị (định danh bằng machine fingerprint SHA-256, không có tài khoản
 * người dùng). File này bị THIẾU trong bản source tải về — dựng lại từ cách
 * device.service.js / auth.middleware.js / admin.js dùng field (xem
 * docs/TEST_LOG.md mục "V0 — model reconstruction" để biết nguồn suy ra từng
 * field trước khi tin tưởng schema này với dữ liệu thật).
 */
const mongoose = require('mongoose')

const deviceSchema = new mongoose.Schema({
  fingerprint: {
    type: String, required: true, unique: true, lowercase: true, trim: true,
  },
  name: { type: String, default: '', maxlength: 120 },
  contactEmail: { type: String, default: '' },
  appVersion: { type: String, default: '' },
  balance: { type: Number, default: 0 },
  status: { type: String, enum: ['active', 'blocked'], default: 'active' },
  blockedReason: { type: String, default: '' },
  tokenVersion: { type: Number, default: 0 },
  trialGranted: { type: Boolean, default: false },
  trialDeferredVox: { type: Number, default: 0 },
  firstSeenAt: { type: Date, default: Date.now },
  lastSeenAt: { type: Date, default: Date.now },
  createdIp: { type: String, default: '' },
  lastSeenIp: { type: String, default: '' },
}, { timestamps: true })

module.exports = mongoose.models.Device || mongoose.model('Device', deviceSchema)
