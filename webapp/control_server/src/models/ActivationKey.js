'use strict'

/**
 * Mã kích hoạt (VOX-XXXX-XXXX-XXXX) — một key dùng đúng một lần trên đúng một
 * thiết bị. Dựng lại từ usage trong activation.service.js/billing.service.js/
 * admin.js — xem ghi chú trong Device.js.
 */
const mongoose = require('mongoose')

const activationKeySchema = new mongoose.Schema({
  code: {
    type: String, required: true, unique: true, uppercase: true, trim: true,
  },
  vox: { type: Number, required: true },
  status: { type: String, enum: ['issued', 'used', 'revoked'], default: 'issued' },
  source: { type: String, enum: ['order', 'admin'], default: 'order' },
  orderId: { type: mongoose.Schema.Types.ObjectId, ref: 'Order', default: null },
  packageId: { type: String, default: '' },
  amountVnd: { type: Number, default: 0 },
  note: { type: String, default: '' },
  usedByFingerprint: { type: String, default: null },
  usedByDeviceId: { type: mongoose.Schema.Types.ObjectId, ref: 'Device', default: null },
  usedAt: { type: Date, default: null },
  usedIp: { type: String, default: '' },
  revokedAt: { type: Date, default: null },
}, { timestamps: true })

module.exports = mongoose.models.ActivationKey
  || mongoose.model('ActivationKey', activationKeySchema)
