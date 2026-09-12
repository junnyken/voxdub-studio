'use strict'

/**
 * Mini-spec V13 (docs/PLAN.md) — `/v1/telemetry/pipeline-event` qua HTTP
 * thật (fastify.inject). Bài quan trọng nhất: PRIVACY TEST bắt buộc theo
 * Scope E của mini-spec — cố ý gửi field cấm (nội dung/đường dẫn) và xác
 * nhận bị CHẶN THẬT (400), không phải chỉ tin lời hứa ở tầng client.
 *
 * Chạy:  node --test tests/telemetry-route.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const Device = require('../src/models/Device')
const PipelineEvent = require('../src/models/PipelineEvent')

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
  fingerprint = 'b'.repeat(64)
  await Device.create({ fingerprint, balance: 1000, status: 'active' })
  const res = await app.inject({
    method: 'POST', url: '/v1/device/register',
    payload: { fingerprint, name: 'telemetry-test', appVersion: '3.0.0' },
  })
  deviceToken = res.json().token
})

function post(payload) {
  return app.inject({
    method: 'POST', url: '/v1/telemetry/pipeline-event',
    headers: { authorization: `Bearer ${deviceToken}` },
    payload,
  })
}

test('thiếu token thiết bị -> 401, không ghi gì vào DB', async () => {
  const res = await app.inject({
    method: 'POST', url: '/v1/telemetry/pipeline-event',
    payload: { runId: 'r1', status: 'started', stage: 'acquire' },
  })
  assert.equal(res.statusCode, 401)
  assert.equal(await PipelineEvent.countDocuments({}), 0)
})

test('event hợp lệ -> 200, ghi đúng vào DB với fingerprint từ TOKEN (không phải client tự khai)', async () => {
  const res = await post({ runId: 'r1', status: 'started', stage: 'acquire' })
  assert.equal(res.statusCode, 200)
  const doc = await PipelineEvent.findOne({ runId: 'r1' }).lean()
  assert.equal(doc.fingerprint, fingerprint)
  assert.equal(doc.stage, 'acquire')
})

test('status lạ -> 400 BAD_STATUS', async () => {
  const res = await post({ runId: 'r1', status: 'abandoned', stage: 'acquire' })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'BAD_STATUS')
})

test('stage lạ -> 400 BAD_STAGE', async () => {
  const res = await post({ runId: 'r1', status: 'started', stage: 'not_a_real_stage' })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'BAD_STAGE')
})

test('thiếu runId -> 400 BAD_RUN_ID', async () => {
  const res = await post({ status: 'started', stage: 'acquire' })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'BAD_RUN_ID')
})

// ---------------------------------------------------- PRIVACY TEST (Scope E) --
// "cố ý thử gửi field cấm phải bị chặn" — đây chính là bài đó, không phải
// suy diễn từ code, mà thật sự POST field cấm qua HTTP và xác nhận 400.

test('PRIVACY: field lạ "transcript" bị CHẶN (400), KHÔNG được ghi vào DB', async () => {
  const res = await post({
    runId: 'leak1', status: 'started', stage: 'acquire',
    transcript: 'nội dung video nhạy cảm không được phép gửi',
  })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'FORBIDDEN_FIELD')
  assert.equal(await PipelineEvent.countDocuments({ runId: 'leak1' }), 0,
    'field cấm phải chặn TRƯỚC KHI ghi, không phải ghi rồi lọc sau')
})

test('PRIVACY: field lạ "filePath" (đường dẫn máy người dùng) bị chặn', async () => {
  const res = await post({
    runId: 'leak2', status: 'started', stage: 'acquire',
    filePath: 'C:\\Users\\thật\\Videos\\bí mật.mp4',
  })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'FORBIDDEN_FIELD')
})

test('PRIVACY: field lạ "audioUrl" bị chặn', async () => {
  const res = await post({
    runId: 'leak3', status: 'started', stage: 'acquire', audioUrl: 'https://example.com/leak.wav',
  })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'FORBIDDEN_FIELD')
})

test('PRIVACY: đúng 4 field cho phép (runId/status/stage/errorStage) vẫn qua bình thường', async () => {
  const res = await post({ runId: 'ok1', status: 'failed', stage: 'asr', errorStage: 'asr' })
  assert.equal(res.statusCode, 200)
})

test('luồng đầy đủ qua HTTP thật: started nhiều lần -> completed, đúng 1 document', async () => {
  await post({ runId: 'full1', status: 'started', stage: 'acquire' })
  await post({ runId: 'full1', status: 'started', stage: 'asr' })
  await post({ runId: 'full1', status: 'started', stage: 'tts' })
  await post({ runId: 'full1', status: 'completed', stage: 'done' })

  const docs = await PipelineEvent.find({ runId: 'full1' }).lean()
  assert.equal(docs.length, 1)
  assert.equal(docs[0].status, 'completed')
  assert.equal(docs[0].stage, 'done')
})
