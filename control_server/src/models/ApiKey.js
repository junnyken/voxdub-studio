'use strict'

/**
 * API key cho developer bên thứ 3 (mini-spec V31, docs/PLAN.md Phase G) —
 * lớp identity THỨ 2 SONG SONG với `Device` (device-fingerprint), KHÔNG
 * thay thế. Chỉ dùng cho `/api/v1/*` (namespace riêng, xem
 * `routes/api-v1.js`) — app desktop VoxDub không đụng tới model này.
 *
 * `keyHash` là SHA-256 của key thật (dạng `vx_live_<hex>`) — KHÔNG lưu
 * plaintext, đúng nguyên tắc `keyPrefix` để hiển thị UI nhận diện key nào
 * (8 ký tự đầu sau "vx_live_", không đủ để đoán ra key thật).
 *
 * `usageCount`/`quota` là bộ đếm NHANH (cùng vai trò `Device.balance`) —
 * sổ cái chi tiết từng lượt gọi nằm ở `ApiUsageLedger` (TÁCH RIÊNG khỏi
 * `CreditLedger` của desktop app — Constraint 3 của V31).
 */
const mongoose = require('mongoose')

const apiKeySchema = new mongoose.Schema({
  keyHash: { type: String, required: true, unique: true },
  keyPrefix: { type: String, required: true },
  orgName: { type: String, required: true, maxlength: 200 },
  contactEmail: { type: String, default: '' },
  status: { type: String, enum: ['active', 'revoked'], default: 'active' },
  quota: { type: Number, default: 1000 },
  usageCount: { type: Number, default: 0 },
  lastUsedAt: { type: Date, default: null },
  createdIp: { type: String, default: '' },
}, { timestamps: true })

module.exports = mongoose.models.ApiKey || mongoose.model('ApiKey', apiKeySchema)
