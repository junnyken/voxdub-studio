'use strict'

/**
 * Sổ cái Vox — mỗi giao dịch (trừ/cộng) một dòng, bất biến. Dựng lại từ
 * credit.service.js/hold.service.js/admin.js — xem ghi chú trong Device.js.
 *
 * `type` gồm cả các giá trị hold.service.js không còn ghi nữa (`hold_release`)
 * vì đó là lịch sử — bản ghi cũ trong DB thật (nếu có) vẫn phải đọc được.
 */
const mongoose = require('mongoose')

const creditLedgerSchema = new mongoose.Schema({
  fingerprint: { type: String, required: true, index: true },
  deviceId: { type: mongoose.Schema.Types.ObjectId, ref: 'Device', required: true },
  delta: { type: Number, required: true },
  balanceAfter: { type: Number, required: true },
  type: {
    type: String,
    enum: [
      'usage', 'activation', 'trial', 'refund', 'hold', 'hold_release',
      'admin_grant', 'admin_deduct', 'transfer_out', 'transfer_in',
    ],
    required: true,
  },
  idempotencyKey: {
    type: String, required: true, unique: true,
  },
  description: { type: String, default: '' },
  metadata: { type: mongoose.Schema.Types.Mixed, default: {} },
}, { timestamps: true })

creditLedgerSchema.index({ fingerprint: 1, createdAt: -1 })

module.exports = mongoose.models.CreditLedger
  || mongoose.model('CreditLedger', creditLedgerSchema)
