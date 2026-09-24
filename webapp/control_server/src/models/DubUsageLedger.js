'use strict'

/**
 * Sổ cái phí API lồng tiếng đầy đủ (mini-spec V34b, docs/PLAN.md Phase G)
 * — mỗi job tính phí thành công 1 dòng, bất biến. TÁCH HẲN `CreditLedger`
 * (Vox desktop) VÀ `ApiUsageLedger` (V31 dịch văn bản, đếm LƯỢT GỌI chứ
 * không phải PHÚT VIDEO) — đúng Constraint 2 của V34b, cùng nguyên tắc
 * "lỗi 1 hệ không ảnh hưởng ví người dùng khác" đã áp dụng cho
 * `ApiUsageLedger.js` (V31).
 *
 * SỐNG ĐỘC LẬP với vòng đời `DubApiJob` — job bị TTL sweeper xoá sau
 * `cloud.dub.ttl.hours` (dọn file trên đĩa), nhưng lịch sử billing ở đây
 * KHÔNG bao giờ bị xoá tự động (khác `RenderJob`/`DubApiJob`, vốn thiết kế
 * để xoá vì lý do lưu trữ, không phải lý do kế toán).
 */
const mongoose = require('mongoose')

const dubUsageLedgerSchema = new mongoose.Schema({
  apiKeyId: { type: mongoose.Schema.Types.ObjectId, ref: 'ApiKey', required: true, index: true },
  jobId: { type: mongoose.Schema.Types.ObjectId, ref: 'DubApiJob', required: true },
  bgMode: { type: String, enum: ['none', 'demucs'], required: true },
  durationS: { type: Number, required: true },
  minutesCharged: { type: Number, required: true },
  costVox: { type: Number, required: true },
  dubMinutesUsedAfter: { type: Number, required: true },
}, { timestamps: true })

dubUsageLedgerSchema.index({ apiKeyId: 1, createdAt: -1 })

module.exports = mongoose.models.DubUsageLedger
  || mongoose.model('DubUsageLedger', dubUsageLedgerSchema)
