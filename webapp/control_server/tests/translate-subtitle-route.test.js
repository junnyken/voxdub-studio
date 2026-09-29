'use strict'

/**
 * Mini-spec V14 (docs/PLAN.md) — `/v1/ai/translate-subtitle` qua HTTP thật
 * (fastify.inject). Mock `gateway.translateSubtitleBatch` (không gọi AI
 * provider thật — không có key trong môi trường test) để kiểm được đúng
 * phần route tự làm: validate, precheck, BILLING (Constraint 4 — tính giá
 * autotranslate mỗi dòng, KHÔNG cộng segment.base), idempotency theo jobId.
 *
 * Chạy:  node --test tests/translate-subtitle-route.test.js
 */
const test = require('node:test')
const { mock } = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const Device = require('../src/models/Device')
const JobResult = require('../src/models/JobResult')
const gateway = require('../src/services/ai-gateway.service')
const { DEFAULTS } = require('../src/services/config.service')

let app
let deviceToken
let fingerprint

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
  fingerprint = 'c'.repeat(64)
  await Device.create({ fingerprint, balance: 1000, status: 'active' })
  const res = await app.inject({
    method: 'POST', url: '/v1/device/register',
    payload: { fingerprint, name: 'subtitle-test', appVersion: '3.0.0' },
  })
  deviceToken = res.json().token
  // register() có thể cộng thêm trial vox lên trên balance đã tạo (tuỳ
  // trạng thái device) — chốt lại về đúng 1000 để mỗi test có mốc xuất phát
  // xác định, không phụ thuộc logic trial.
  await Device.updateOne({ fingerprint }, { $set: { balance: 1000 } })
})

function post(payload) {
  return app.inject({
    method: 'POST', url: '/v1/ai/translate-subtitle',
    headers: { authorization: `Bearer ${deviceToken}` },
    payload,
  })
}

function fakeSuccess(items) {
  return {
    segments: items.map((it) => ({ id: it.id, text: `dịch: ${it.text}` })),
    usage: { promptTokens: 10, completionTokens: 10 },
    provider: 'fake', model: 'fake-model',
  }
}

test('thiếu token thiết bị -> 401', async () => {
  const res = await app.inject({
    method: 'POST', url: '/v1/ai/translate-subtitle',
    payload: { jobId: 'j'.repeat(8), sourceFlores: 'eng_Latn',
      targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }] },
  })
  assert.equal(res.statusCode, 401)
})

test('mã FLORES-200 sai định dạng -> 400 (validate schema)', async () => {
  const res = await post({
    jobId: 'j'.repeat(8), sourceFlores: 'not-a-code',
    targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }],
  })
  assert.equal(res.statusCode, 400)
})

test('billing: tính đúng số dòng x giá autotranslate, KHÔNG cộng segment.base', async () => {
  mock.method(gateway, 'translateSubtitleBatch', async ({ items }) => fakeSuccess(items))

  const items = [{ id: 1, text: 'one' }, { id: 2, text: 'two' }, { id: 3, text: 'three' }]
  const res = await post({
    jobId: 'j'.repeat(8), sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items,
  })
  assert.equal(res.statusCode, 200)
  const body = res.json()
  const expected = items.length * DEFAULTS['credit.cost.segment.autotranslate']
  assert.equal(body.creditCharged, expected,
    'phải đúng 3 dòng x giá autotranslate, không lẫn segment.base (giá dub thường)')
  assert.equal(body.balanceAfter, 1000 - expected)
  assert.equal(body.segments.length, 3)
  assert.equal(body.segments[0].text, 'dịch: one')
})

test('idempotent theo jobId: gọi lại KHÔNG trừ Vox lần hai', async () => {
  const fn = mock.method(gateway, 'translateSubtitleBatch',
    async ({ items }) => fakeSuccess(items))

  const items = [{ id: 1, text: 'one' }]
  const jobId = 'j'.repeat(8)
  const res1 = await post({ jobId, sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items })
  const res2 = await post({ jobId, sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items })

  assert.equal(res1.statusCode, 200)
  assert.deepEqual(res1.json(), res2.json())
  assert.equal(fn.mock.callCount(), 1, 'lần gọi lại phải trả kết quả cũ, KHÔNG gọi lại AI')

  const count = await JobResult.countDocuments({ jobId })
  assert.equal(count, 1)
})

test('quá trần segments.per.request -> 400 BATCH_TOO_LARGE, không gọi gateway', async () => {
  const fn = mock.method(gateway, 'translateSubtitleBatch', async ({ items }) => fakeSuccess(items))
  const items = Array.from(
    { length: DEFAULTS['ai.max.segments.per.request'] + 1 },
    (_, i) => ({ id: i, text: 'x' }),
  )
  const res = await post({
    jobId: 'j'.repeat(8), sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items,
  })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'BATCH_TOO_LARGE')
  assert.equal(fn.mock.callCount(), 0)
})

test('gateway lỗi -> 503 AI_UNAVAILABLE, KHÔNG trừ Vox', async () => {
  mock.method(gateway, 'translateSubtitleBatch', async () => {
    throw Object.assign(new Error('provider down'), { code: 'AI_UNAVAILABLE', statusCode: 503 })
  })
  const res = await post({
    jobId: 'j'.repeat(8), sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn',
    items: [{ id: 1, text: 'hi' }],
  })
  assert.equal(res.statusCode, 503)
  assert.equal(res.json().code, 'AI_UNAVAILABLE')

  const device = await Device.findOne({ fingerprint }).lean()
  assert.equal(device.balance, 1000, 'lỗi AI thì không được trừ Vox')
})

test('credit.enabled=false -> creditCharged=0 nhưng vẫn dịch được', async () => {
  mock.method(gateway, 'translateSubtitleBatch', async ({ items }) => fakeSuccess(items))
  const config = require('../src/services/config.service')
  await config.set('credit.enabled', false)

  const res = await post({
    jobId: 'j'.repeat(8), sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn',
    items: [{ id: 1, text: 'hi' }],
  })
  assert.equal(res.statusCode, 200)
  assert.equal(res.json().creditCharged, 0)

  await config.set('credit.enabled', true)
})
