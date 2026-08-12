'use strict'

/**
 * Mini-spec V31 (docs/PLAN.md, Phase G) — `services/api-key.service.js`.
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const ApiKey = require('../src/models/ApiKey')
const {
  QuotaExceededError, hashApiKey, generateApiKey, createApiKey,
  findByPlaintext, consumeQuota,
} = require('../src/services/api-key.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(clearDb)

test('generateApiKey sinh key dạng vx_live_<hex>, không trùng lặp', () => {
  const a = generateApiKey()
  const b = generateApiKey()
  assert.match(a, /^vx_live_[0-9a-f]{48}$/)
  assert.notEqual(a, b)
})

test('hashApiKey xác định (cùng input -> cùng hash)', () => {
  assert.equal(hashApiKey('abc'), hashApiKey('abc'))
  assert.notEqual(hashApiKey('abc'), hashApiKey('abd'))
})

test('createApiKey không lưu plaintext, chỉ lưu hash + prefix', async () => {
  const { plaintext, doc } = await createApiKey({ orgName: 'Acme' })
  assert.equal(doc.keyHash, hashApiKey(plaintext))
  assert.ok(!doc.keyHash.includes(plaintext.slice(8)))
  assert.equal(doc.keyPrefix, plaintext.slice(0, 15))
  assert.equal(doc.quota, 1000) // mặc định
})

test('findByPlaintext tìm đúng key đã tạo, trả null cho key sai', async () => {
  const { plaintext } = await createApiKey({ orgName: 'Acme' })
  const found = await findByPlaintext(plaintext)
  assert.ok(found)
  assert.equal(found.orgName, 'Acme')

  const notFound = await findByPlaintext('vx_live_khong-ton-tai')
  assert.equal(notFound, null)
})

test('consumeQuota tăng usageCount đúng, ghi ledger', async () => {
  const { doc } = await createApiKey({ orgName: 'Acme', quota: 5 })
  const updated = await consumeQuota(doc._id, { action: 'translate' })
  assert.equal(updated.usageCount, 1)

  const updated2 = await consumeQuota(doc._id, { action: 'translate' })
  assert.equal(updated2.usageCount, 2)
})

test('consumeQuota raise QuotaExceededError khi hết quota', async () => {
  const { doc } = await createApiKey({ orgName: 'Acme', quota: 1 })
  await consumeQuota(doc._id, { action: 'translate' })
  await assert.rejects(
    () => consumeQuota(doc._id, { action: 'translate' }),
    QuotaExceededError,
  )
})

test('consumeQuota raise khi key đã revoked', async () => {
  const { doc } = await createApiKey({ orgName: 'Acme', quota: 100 })
  await ApiKey.updateOne({ _id: doc._id }, { $set: { status: 'revoked' } })
  await assert.rejects(
    () => consumeQuota(doc._id, { action: 'translate' }),
    QuotaExceededError,
  )
})

test('consumeQuota xử lý đúng dưới tải đồng thời (atomic, không vượt quota)', async () => {
  const { doc } = await createApiKey({ orgName: 'Acme', quota: 5 })
  const attempts = Array.from({ length: 10 }, () => consumeQuota(doc._id, { action: 'translate' }).catch(() => null))
  const results = await Promise.all(attempts)
  const succeeded = results.filter(Boolean)
  assert.equal(succeeded.length, 5, 'đúng 5 lượt thành công dù 10 request chạy song song')

  const final = await ApiKey.findById(doc._id)
  assert.equal(final.usageCount, 5, 'usageCount không được vượt quota dù race condition')
})
