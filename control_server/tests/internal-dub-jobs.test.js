'use strict'

/**
 * Integration test cho `/internal/dub-jobs/*` (mini-spec V34a, xem
 * docs/PLAN.md) — cùng khuôn `internal-jobs.test.js` (V12): xác nhận cổng
 * WORKER_INTERNAL_TOKEN chặn đúng, và toàn bộ luồng
 * claim→heartbeat→complete/fail hoạt động đúng qua HTTP thật.
 *
 * Chạy:  node --test tests/internal-dub-jobs.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

process.env.DUB_UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'voxdub-internal-dub-jobs-test-'))

const { build } = require('../src/app')
const ApiKey = require('../src/models/ApiKey')
const DubApiJob = require('../src/models/DubApiJob')

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
test.beforeEach(clearDb)

const TOKEN = process.env.WORKER_INTERNAL_TOKEN

async function makeQueuedJob() {
  const apiKey = await ApiKey.create({
    keyHash: 'h'.repeat(64), keyPrefix: 'testpfx1', orgName: 'Test Org',
  })
  return DubApiJob.create({
    apiKeyId: apiKey._id, status: 'queued',
    sourceLang: 'en-US', targetLang: 'vi', inputPath: '/tmp/in.mp4',
    expiresAt: new Date(Date.now() + 3600_000),
  })
}

test('claim: thiếu X-Worker-Token → 401', async () => {
  const res = await app.inject({ method: 'POST', url: '/internal/dub-jobs/claim', payload: { workerId: 'w1' } })
  assert.equal(res.statusCode, 401)
  assert.equal(res.json().code, 'BAD_WORKER_TOKEN')
})

test('claim: sai token → 401', async () => {
  const res = await app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { 'x-worker-token': 'wrong' }, payload: { workerId: 'w1' },
  })
  assert.equal(res.statusCode, 401)
})

test('claim: đúng token, có job queued → trả về job + tham số dịch', async () => {
  const job = await makeQueuedJob()
  const res = await app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(String(body.job.jobId), String(job._id))
  assert.equal(body.job.sourceLang, 'en-US')
  assert.equal(body.job.targetLang, 'vi')
  assert.ok(body.job.inputPath)
  assert.ok(body.job.outputPath)

  const updated = await DubApiJob.findById(job._id).lean()
  assert.equal(updated.status, 'running')
  assert.equal(updated.workerId, 'w1')
})

test('claim: không có job queued → job: null (không lỗi)', async () => {
  const res = await app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  assert.equal(res.statusCode, 200)
  assert.equal(res.json().job, null)
})

test('heartbeat → complete: luồng đầy đủ qua HTTP thật, kèm metrics thật', async () => {
  await makeQueuedJob()
  const claimRes = await app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  const { jobId } = claimRes.json().job

  const hbRes = await app.inject({
    method: 'POST', url: `/internal/dub-jobs/${jobId}/heartbeat`,
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  assert.equal(hbRes.statusCode, 200)
  assert.equal(hbRes.json().ok, true)

  const completeRes = await app.inject({
    method: 'POST', url: `/internal/dub-jobs/${jobId}/complete`,
    headers: { 'x-worker-token': TOKEN },
    payload: {
      workerId: 'w1', outputPath: '/tmp/out.mp4',
      metrics: { inputBytes: 1024, outputBytes: 2048, processingMs: 5000 },
    },
  })
  assert.equal(completeRes.statusCode, 200)

  const job = await DubApiJob.findById(jobId).lean()
  assert.equal(job.status, 'done')
  assert.equal(job.outputPath, '/tmp/out.mp4')
  assert.equal(job.metrics.processingMs, 5000)
})

test('complete: thiếu outputPath → 400', async () => {
  await makeQueuedJob()
  const claimRes = await app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  const { jobId } = claimRes.json().job

  const res = await app.inject({
    method: 'POST', url: `/internal/dub-jobs/${jobId}/complete`,
    headers: { 'x-worker-token': TOKEN },
    payload: { workerId: 'w1' },
  })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'BAD_RESULT')
})

test('complete: worker khác với worker đã claim → 409, job không đổi', async () => {
  await makeQueuedJob()
  const claimRes = await app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  const { jobId } = claimRes.json().job

  const res = await app.inject({
    method: 'POST', url: `/internal/dub-jobs/${jobId}/complete`,
    headers: { 'x-worker-token': TOKEN },
    payload: { workerId: 'w2', outputPath: '/tmp/out.mp4' },
  })
  assert.equal(res.statusCode, 409)

  const job = await DubApiJob.findById(jobId).lean()
  assert.equal(job.status, 'running', 'worker sai không được đổi trạng thái job của worker khác')
})

test('fail: chuyển job sang failed kèm lý do', async () => {
  await makeQueuedJob()
  const claimRes = await app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  const { jobId } = claimRes.json().job

  const res = await app.inject({
    method: 'POST', url: `/internal/dub-jobs/${jobId}/fail`,
    headers: { 'x-worker-token': TOKEN },
    payload: { workerId: 'w1', error: 'voxdub dub exit 1: ASR lỗi' },
  })
  assert.equal(res.statusCode, 200)

  const job = await DubApiJob.findById(jobId).lean()
  assert.equal(job.status, 'failed')
  assert.equal(job.error, 'voxdub dub exit 1: ASR lỗi')
})

test('token thiết bị/API key KHÔNG lọt qua được cổng worker — hệ auth tách biệt', async () => {
  const res = await app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { authorization: 'Bearer some-api-key' }, payload: { workerId: 'w1' },
  })
  assert.equal(res.statusCode, 401)
})
