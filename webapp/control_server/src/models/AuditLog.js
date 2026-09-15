'use strict'

/**
 * Nhật ký hành động thay đổi tiền/quyền — best-effort (không bao giờ làm
 * hỏng request chính, xem audit.service.js). Dựng lại từ audit.service.js/
 * admin.js/activation.service.js/billing.service.js — xem ghi chú Device.js.
 */
const mongoose = require('mongoose')

const auditLogSchema = new mongoose.Schema({
  action: { type: String, required: true },
  actor: { type: String, default: 'system' },
  target: { type: String, default: '' },
  before: { type: mongoose.Schema.Types.Mixed, default: undefined },
  after: { type: mongoose.Schema.Types.Mixed, default: undefined },
  note: { type: String, default: '' },
  ip: { type: String, default: '' },
}, { timestamps: true })

auditLogSchema.index({ createdAt: -1 })

module.exports = mongoose.models.AuditLog || mongoose.model('AuditLog', auditLogSchema)
