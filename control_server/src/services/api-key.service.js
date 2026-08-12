'use strict'

/**
 * Sinh/xác thực/tiêu thụ quota API key bên thứ 3 (mini-spec V31,
 * docs/PLAN.md Phase G).
 *
 * `consumeQuota()` dùng đúng kỹ thuật atomic `findOneAndUpdate` đã có ở
 * `credit.service.js::charge()` (Constraint 5 — KHÔNG thêm MongoDB
 * transaction/replica-set) — nhưng tách hoàn toàn khỏi `Device`/
 * `CreditLedger` (Constraint 3).
 */
const crypto = require('node:crypto')
const ApiKey = require('../models/ApiKey')
const ApiUsageLedger = require('../models/ApiUsageLedger')

class QuotaExceededError extends Error {
  constructor(quota, usageCount) {
    super(`Đã dùng hết quota (${usageCount}/${quota}).`)
    this.name = 'QuotaExceededError'
    this.quota = quota
    this.usageCount = usageCount
  }
}

function hashApiKey(key) {
  return crypto.createHash('sha256').update(String(key)).digest('hex')
}

/** Sinh 1 API key mới dạng `vx_live_<48 hex>` — KHÔNG lưu ở đâu, caller tự lưu keyHash. */
function generateApiKey() {
  return `vx_live_${crypto.randomBytes(24).toString('hex')}`
}

/** Tạo 1 ApiKey mới trong DB, trả về { plaintext, doc } — plaintext CHỈ xuất
 * hiện 1 LẦN DUY NHẤT lúc tạo (giống mọi hệ API key thật), không đọc lại được. */
async function createApiKey({ orgName, contactEmail = '', quota = 1000, createdIp = '' }) {
  const plaintext = generateApiKey()
  const doc = await ApiKey.create({
    keyHash: hashApiKey(plaintext),
    keyPrefix: plaintext.slice(0, 15), // "vx_live_" + 7 ký tự đầu của phần hex
    orgName,
    contactEmail,
    quota,
    createdIp,
  })
  return { plaintext, doc }
}

/** Tìm ApiKey theo key thật (hash rồi tra DB — lookup theo index, không
 * phải so sánh timing-unsafe trên nhiều key). */
async function findByPlaintext(plaintext) {
  return ApiKey.findOne({ keyHash: hashApiKey(plaintext) })
}

/**
 * Tiêu 1 đơn vị quota — atomic, chỉ thành công nếu còn quota VÀ key vẫn
 * `active` (điều kiện trong chính lệnh update, không phải kiểm tra rồi
 * update riêng — tránh race giữa 2 request song song). Raise
 * `QuotaExceededError` nếu hết quota/key không còn active.
 */
async function consumeQuota(apiKeyId, { action, ip = '', metadata = {} } = {}) {
  const updated = await ApiKey.findOneAndUpdate(
    { _id: apiKeyId, status: 'active', $expr: { $lt: ['$usageCount', '$quota'] } },
    { $inc: { usageCount: 1 }, $set: { lastUsedAt: new Date() } },
    { new: true },
  )
  if (!updated) {
    const current = await ApiKey.findById(apiKeyId).lean()
    throw new QuotaExceededError(current ? current.quota : 0, current ? current.usageCount : 0)
  }
  await ApiUsageLedger.create({
    apiKeyId, action, usageAfter: updated.usageCount, ip, metadata,
  })
  return updated
}

module.exports = {
  QuotaExceededError, hashApiKey, generateApiKey, createApiKey, findByPlaintext, consumeQuota,
}
