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
 *
 * `dubMinutesQuota`/`dubMinutesUsed` (mini-spec V34b, docs/PLAN.md) — CẶP
 * FIELD RIÊNG cho API lồng tiếng đầy đủ, TÁCH HẲN `quota`/`usageCount` ở
 * trên (field đó đếm LƯỢT GỌI dịch văn bản của V31, đơn vị khác — "phút
 * video" không so sánh được với "lượt gọi"). `dubMinutesQuota` mặc định 0
 * — tính năng dub qua API là OPT-IN, admin phải cấp quota rõ ràng qua
 * `/v1/admin`, không tự động mở cho API key hiện có (Constraint 2 của
 * V34b: 3 hệ billing độc lập, key cũ chỉ dùng V31 không bị ảnh hưởng gì).
 *
 * `dubMinutesReserved` (mini-spec V43, docs/PLAN.md) — đóng gap race
 * condition mà V42 phát hiện: `dubMinutesUsed` chỉ `$inc` SAU khi job hoàn
 * tất, nên nhiều job submit đồng thời từ CÙNG 1 key đều đọc thấy quota còn
 * trống dù tổng thời lượng thật sẽ vượt xa. Field này giữ chỗ NGAY lúc
 * submit (atomic, cùng kỹ thuật `balance: {$gte}` của `credit.service.js`),
 * giải phóng lúc job xong/lỗi/hết hạn — xem `dub-job.service.js`.
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
  dubMinutesQuota: { type: Number, default: 0 },
  dubMinutesUsed: { type: Number, default: 0 },
  dubMinutesReserved: { type: Number, default: 0 },
  lastUsedAt: { type: Date, default: null },
  createdIp: { type: String, default: '' },
}, { timestamps: true })

module.exports = mongoose.models.ApiKey || mongoose.model('ApiKey', apiKeySchema)
