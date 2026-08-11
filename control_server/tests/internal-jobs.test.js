'use strict'

/**
 * Integration test cho `/internal/jobs/*` (mini-spec V12, xem docs/PLAN.md)
 * — API nội bộ worker Python gọi qua HTTP thật (fastify.inject), chạm
 * MongoDB thật (in-memory). Xác nhận: cổng WORKER_INTERNAL_TOKEN chặn đúng
 * (không phải token thiết bị/admin nào lọt qua được), và toàn bộ luồng
 * claim→heartbeat→complete/fail hoạt động đúng qua HTTP thật (không chỉ
 * qua lời gọi hàm trực tiếp như render-job.integration.test.js).
 *
 * Chạy:  node --test tests/internal-jobs.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

process.env.RENDER_UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'voxdub-internal-jobs-test-'))

const { build } = require('../src/app')
const Device = require('../src/models/Device')
const RenderJob = require('../src/models/RenderJob')

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
  const device = await Device.create({ fingerprint: 'z'.repeat(64), balance: 1000, status: 'active' })
  return RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'queued', inputPath: '/tmp/in.wav', expiresAt: new Date(Date.now() + 3600_000),
  })
}

test('claim: thiếu X-Worker-Token → 401', async () => {
  const res = await app.inject({ method: 'POST', url: '/internal/jobs/claim', payload: { workerId: 'w1' } })
  assert.equal(res.statusCode, 401)
  assert.equal(res.json().code, 'BAD_WORKER_TOKEN')
})

test('claim: sai token → 401', async () => {
  const res = await app.inject({
    method: 'POST', url: '/internal/jobs/claim',
    headers: { 'x-worker-token': 'wrong' }, payload: { workerId: 'w1' },
  })
  assert.equal(res.statusCode, 401)
})

test('claim: đúng token, có job queued → trả về job + đường dẫn kết quả', async () => {
  const job = await makeQueuedJob()
  const res = await app.inject({
    method: 'POST', url: '/internal/jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(String(body.job.jobId), String(job._id))
  assert.equal(body.job.stage, 'demucs')
  assert.ok(body.job.vocalsPath)
  assert.ok(body.job.noVocalsPath)

  const updated = await RenderJob.findById(job._id).lean()
  assert.equal(updated.status, 'running')
  assert.equal(updated.workerId, 'w1')
})

test('claim: không có job queued → job: null (không lỗi)', async () => {
  const res = await app.inject({
    method: 'POST', url: '/internal/jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  assert.equal(res.statusCode, 200)
  assert.equal(res.json().job, null)
})

test('heartbeat → complete: luồng đầy đủ qua HTTP thật', async () => {
  await makeQueuedJob()
  const claimRes = await app.inject({
    method: 'POST', url: '/internal/jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  const { jobId } = claimRes.json().job

  const hbRes = await app.inject({
    method: 'POST', url: `/internal/jobs/${jobId}/heartbeat`,
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  assert.equal(hbRes.statusCode, 200)
  assert.equal(hbRes.json().ok, true)

  const completeRes = await app.inject({
    method: 'POST', url: `/internal/jobs/${jobId}/complete`,
    headers: { 'x-worker-token': TOKEN },
    payload: { workerId: 'w1', resultPaths: { vocals: '/tmp/v.wav', no_vocals: '/tmp/nv.wav' } },
  })
  assert.equal(completeRes.statusCode, 200)

  const job = await RenderJob.findById(jobId).lean()
  assert.equal(job.status, 'done')
  assert.equal(job.resultPaths.vocals, '/tmp/v.wav')
})

test('complete: worker khác với worker đã claim → 409, job không đổi', async () => {
  await makeQueuedJob()
  const claimRes = await app.inject({
    method: 'POST', url: '/internal/jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  const { jobId } = claimRes.json().job

  const res = await app.inject({
    method: 'POST', url: `/internal/jobs/${jobId}/complete`,
    headers: { 'x-worker-token': TOKEN },
    payload: { workerId: 'w2', resultPaths: { vocals: '/tmp/v.wav', no_vocals: '/tmp/nv.wav' } },
  })
  assert.equal(res.statusCode, 409)

  const job = await RenderJob.findById(jobId).lean()
  assert.equal(job.status, 'running', 'worker sai không được đổi trạng thái job của worker khác')
})

test('fail: chuyển job sang failed kèm lý do', async () => {
  await makeQueuedJob()
  const claimRes = await app.inject({
    method: 'POST', url: '/internal/jobs/claim',
    headers: { 'x-worker-token': TOKEN }, payload: { workerId: 'w1' },
  })
  const { jobId } = claimRes.json().job

  const res = await app.inject({
    method: 'POST', url: `/internal/jobs/${jobId}/fail`,
    headers: { 'x-worker-token': TOKEN },
    payload: { workerId: 'w1', error: 'ffmpeg decode error' },
  })
  assert.equal(res.statusCode, 200)

  const job = await RenderJob.findById(jobId).lean()
  assert.equal(job.status, 'failed')
  assert.equal(job.error, 'ffmpeg decode error')
})

test('token thiết bị (Bearer) KHÔNG lọt qua được cổng worker — 2 hệ thống auth tách biệt', async () => {
  const res = await app.inject({
    method: 'POST', url: '/internal/jobs/claim',
    headers: { authorization: 'Bearer some-device-token' }, payload: { workerId: 'w1' },
  })
  assert.equal(res.statusCode, 401)
})
