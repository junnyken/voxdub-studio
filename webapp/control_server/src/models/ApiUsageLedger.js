'use strict'

/**
 * Sổ cái lượt gọi API key (mini-spec V31, docs/PLAN.md Phase G) — mỗi
 * request thành công 1 dòng, bất biến. TÁCH HẲN khỏi `CreditLedger` của
 * desktop app (Constraint 3) — 1 lỗi logic ở billing API bên thứ 3 không
 * được có khả năng ảnh hưởng ví Vox của người dùng desktop cá nhân, đúng
 * tinh thần `CreditLedger.js` (mỗi giao dịch một dòng, bất biến) áp cho
 * đối tượng khác.
 */
const mongoose = require('mongoose')

const apiUsageLedgerSchema = new mongoose.Schema({
  apiKeyId: { type: mongoose.Schema.Types.ObjectId, ref: 'ApiKey', required: true, index: true },
  action: { type: String, required: true },
  usageAfter: { type: Number, required: true },
  ip: { type: String, default: '' },
  metadata: { type: mongoose.Schema.Types.Mixed, default: {} },
}, { timestamps: true })

apiUsageLedgerSchema.index({ apiKeyId: 1, createdAt: -1 })

module.exports = mongoose.models.ApiUsageLedger
  || mongoose.model('ApiUsageLedger', apiUsageLedgerSchema)
