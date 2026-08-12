'use strict'

/**
 * Mini-spec V31 (docs/PLAN.md, Phase G) — `/api/v1/translate` qua HTTP thật
 * (fastify.inject). Mock `gateway.translateSubtitleBatch` (không gọi AI
 * provider thật). Kiểm: xác thực API key tách biệt hoàn toàn khỏi device
 * auth, quota atomic, billing KHÔNG đụng CreditLedger/Device.
 *
 * Chạy:  node --test tests/api-v1-route.test.js
 */
const test = require('node:test')
const { mock } = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const Device = require('../src/models/Device')
const ApiKey = require('../src/models/ApiKey')
const ApiUsageLedger = require('../src/models/ApiUsageLedger')
const CreditLedger = require('../src/models/CreditLedger')
const gateway = require('../src/services/ai-gateway.service')
const { createApiKey } = require('../src/services/api-key.service')

let app

test.before(async () => {
  await startDb()
  app = await build({ mongo: false, web: false, logger: false })
  await app.ready()
})
test.after(async () => {
  await app.close()
  await stopDb()
})
test.beforeEach(async () => {
  await clearDb()
  mock.restoreAll()
})

function fakeSuccess(items) {
  return {
    segments: items.map((it) => ({ id: it.id, text: `dịch: ${it.text}` })),
    usage: { promptTokens: 10, completionTokens: 10 },
    provider: 'fake', model: 'fake-model',
  }
}

function post(key, payload) {
  return app.inject({
    method: 'POST', url: '/api/v1/translate',
    headers: key ? { authorization: `Bearer ${key}` } : {},
    payload,
  })
}

test('thiếu API key -> 401 NO_API_KEY', async () => {
  const res = await post(null, {
    sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }],
  })
  assert.equal(res.statusCode, 401)
  assert.equal(res.json().code, 'NO_API_KEY')
})

test('API key sai -> 401 BAD_API_KEY', async () => {
  const res = await post('vx_live_khong-ton-tai', {
    sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }],
  })
  assert.equal(res.statusCode, 401)
  assert.equal(res.json().code, 'BAD_API_KEY')
})

test('API key đã revoke -> 403 API_KEY_REVOKED', async () => {
  const { plaintext, doc } = await createApiKey({ orgName: 'Test Org' })
  await ApiKey.updateOne({ _id: doc._id }, { $set: { status: 'revoked' } })
  const res = await post(plaintext, {
    sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }],
  })
  assert.equal(res.statusCode, 403)
  assert.equal(res.json().code, 'API_KEY_REVOKED')
})

test('API key hợp lệ -> dịch thành công, quota trừ đúng, ghi ApiUsageLedger', async () => {
  mock.method(gateway, 'translateSubtitleBatch', async ({ items }) => fakeSuccess(items))
  const { plaintext, doc } = await createApiKey({ orgName: 'Test Org', quota: 10 })

  const items = [{ id: 1, text: 'hello' }, { id: 2, text: 'world' }]
  const res = await post(plaintext, {
    sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items,
  })

  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(body.segments.length, 2)
  assert.equal(body.segments[0].text, 'dịch: hello')
  assert.equal(body.usageCount, 1)
  assert.equal(body.quota, 10)

  const updated = await ApiKey.findById(doc._id)
  assert.equal(updated.usageCount, 1)

  const ledgerCount = await ApiUsageLedger.countDocuments({ apiKeyId: doc._id })
  assert.equal(ledgerCount, 1)
})

test('quota hết -> 429 QUOTA_EXCEEDED, KHÔNG gọi gateway (kiểm trước khi tốn tiền model)', async () => {
  const fn = mock.method(gateway, 'translateSubtitleBatch', async ({ items }) => fakeSuccess(items))
  const { plaintext, doc } = await createApiKey({ orgName: 'Test Org', quota: 1 })
  await ApiKey.updateOne({ _id: doc._id }, { $set: { usageCount: 1 } }) // đã hết quota

  const res = await post(plaintext, {
    sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }],
  })

  assert.equal(res.statusCode, 429)
  assert.equal(res.json().code, 'QUOTA_EXCEEDED')
  assert.equal(fn.mock.callCount(), 0, 'không được gọi model khi đã biết hết quota')
})

test('billing KHÔNG đụng CreditLedger/Device của desktop app', async () => {
  mock.method(gateway, 'translateSubtitleBatch', async ({ items }) => fakeSuccess(items))
  const fingerprint = 'd'.repeat(64)
  await Device.create({ fingerprint, balance: 1000, status: 'active' })

  const { plaintext } = await createApiKey({ orgName: 'Test Org' })
  await post(plaintext, {
    sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }],
  })

  const device = await Device.findOne({ fingerprint })
  assert.equal(device.balance, 1000, 'ví Vox desktop app không được đụng tới')
  const creditLedgerCount = await CreditLedger.countDocuments({})
  assert.equal(creditLedgerCount, 0, 'API key billing không được ghi vào CreditLedger')
})

test('mã FLORES-200 sai định dạng -> 400 (validate schema)', async () => {
  const { plaintext } = await createApiKey({ orgName: 'Test Org' })
  const res = await post(plaintext, {
    sourceFlores: 'not-a-code', targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }],
  })
  assert.equal(res.statusCode, 400)
})

test('device token (app desktop) KHÔNG dùng được cho /api/v1 (2 hệ auth tách biệt)', async () => {
  const fingerprint = 'e'.repeat(64)
  await Device.create({ fingerprint, balance: 1000, status: 'active' })
  const regRes = await app.inject({
    method: 'POST', url: '/v1/device/register',
    payload: { fingerprint, name: 'x', appVersion: '3.0.0' },
  })
  const deviceToken = regRes.json().token

  const res = await post(deviceToken, {
    sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }],
  })
  assert.equal(res.statusCode, 401, 'device token không phải API key hợp lệ')
})
