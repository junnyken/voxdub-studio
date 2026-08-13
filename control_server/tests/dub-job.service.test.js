'use strict'

/**
 * Integration test cho state machine job lồng tiếng đầy đủ (mini-spec
 * V34a, xem docs/PLAN.md). Cùng khuôn `render-job.integration.test.js`
 * (V9→V12) — chạm MongoDB thật (in-memory), KHÔNG spawn worker Python thật
 * (đó là việc của `control_server/worker-dub/dub_worker.py`, live-verify
 * riêng ghi ở docs/TEST_LOG.md, không cần Docker/mạng ở đây).
 *
 * Xác nhận riêng cho V34a (khác V9/V12): submitDubJob KHÔNG đụng
 * ApiKey.usageCount/quota (Constraint 1 — không billing thật ở PoC này).
 *
 * Chạy:  node --test tests/dub-job.service.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

process.env.DUB_UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'voxdub-dub-job-test-'))

const ApiKey = require('../src/models/ApiKey')
const DubApiJob = require('../src/models/DubApiJob')
const config = require('../src/services/config.service')
const dubJob = require('../src/services/dub-job.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(async () => { await clearDb(); config.invalidate() })

async function makeApiKey(orgName = 'Test Org') {
  return ApiKey.create({ keyHash: `h${Date.now()}${Math.random()}`, keyPrefix: 'testpfx1', orgName })
}

function fakeMp4Buffer() {
  return Buffer.from('fake-mp4-bytes-for-test')
}

test('submitDubJob: tắt cloud.dub.enabled thì từ chối rõ ràng, không tạo job', async () => {
  const apiKey = await makeApiKey()
  await config.set('cloud.dub.enabled', false)
  await assert.rejects(
    () => dubJob.submitDubJob({
      apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
    }),
    (err) => err.code === 'CLOUD_DUB_DISABLED',
  )
  const count = await DubApiJob.countDocuments({ apiKeyId: apiKey._id })
  assert.equal(count, 0)
})

test('submitDubJob: trả về NGAY status=queued, KHÔNG đụng ApiKey.usageCount/quota (Constraint 1)', async () => {
  const apiKey = await makeApiKey()
  const estimate = await config.get('cloud.dub.estimate.vox.per.request')

  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi', voice: 'Minh Trang',
  })

  assert.equal(job.status, 'queued')
  assert.equal(job.sourceLang, 'en-US')
  assert.equal(job.targetLang, 'vi')
  assert.equal(job.voice, 'Minh Trang')
  assert.equal(job.estimatedCostVox, estimate, 'chỉ LOG ước tính, không phải số đã trừ')
  assert.equal(job.workerId, '')
  assert.equal(job.heartbeatAt, null)
  assert.ok(fs.existsSync(job.inputPath), 'file input phải được ghi ra đĩa')

  const freshKey = await ApiKey.findById(apiKey._id).lean()
  assert.equal(freshKey.usageCount, 0, 'PoC V34a không billing thật — usageCount không đổi')
  assert.equal(freshKey.quota, apiKey.quota, 'quota không đổi')
})

test('claimNextJob → completeJob: state machine đầy đủ, metrics ghi đúng', async () => {
  const apiKey = await makeApiKey()
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
  })

  const claimed = await dubJob.claimNextJob('worker-1')
  assert.equal(String(claimed._id), String(job._id))
  assert.equal(claimed.status, 'running')

  const hbOk = await dubJob.heartbeat(job._id, 'worker-1')
  assert.equal(hbOk, true)

  const paths = dubJob.jobPaths(job._id)
  fs.writeFileSync(paths.output, 'fake-output-video-bytes')
  const completed = await dubJob.completeJob(job._id, 'worker-1', {
    outputPath: paths.output,
    metrics: { inputBytes: 24, outputBytes: 24, processingMs: 1234 },
  })
  assert.equal(completed.status, 'done')
  assert.equal(completed.outputPath, paths.output)
  assert.equal(completed.metrics.processingMs, 1234)
})

test('claimNextJob: 2 job queued → FIFO (job cũ nhất trước)', async () => {
  const apiKey = await makeApiKey()
  const { job: first } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
  })
  await new Promise((r) => setTimeout(r, 10))
  await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
  })

  const claimed = await dubJob.claimNextJob('worker-1')
  assert.equal(String(claimed._id), String(first._id))
})

test('cleanupJob: xoá sạch thư mục job, gọi lại lần 2 không lỗi (idempotent)', async () => {
  const jobId = 'fake-dub-job-id-for-cleanup-test'
  const paths = dubJob.jobPaths(jobId)
  fs.mkdirSync(paths.dir, { recursive: true })
  fs.writeFileSync(paths.input, 'x')
  assert.ok(fs.existsSync(paths.dir))

  await dubJob.cleanupJob(jobId)
  assert.ok(!fs.existsSync(paths.dir))
  await dubJob.cleanupJob(jobId)
})

test('sweepExpired: dọn đúng job hết hạn, không đụng job còn hạn', async () => {
  const apiKey = await makeApiKey()
  const expired = await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'done', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/x.mp4', expiresAt: new Date(Date.now() - 1000),
  })
  const fresh = await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'done', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/y.mp4', expiresAt: new Date(Date.now() + 3600_000),
  })

  const swept = await dubJob.sweepExpired()
  assert.equal(swept, 1)
  assert.equal(await DubApiJob.countDocuments({ _id: expired._id }), 0)
  assert.equal(await DubApiJob.countDocuments({ _id: fresh._id }), 1)
})

test('sweepStaleRunning: worker mất heartbeat quá ngưỡng → chuyển failed', async () => {
  const apiKey = await makeApiKey()
  await config.set('cloud.dub.heartbeat.stale.minutes', 1)
  const staleJob = await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'running', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/x.mp4', workerId: 'dead-worker',
    heartbeatAt: new Date(Date.now() - 5 * 60 * 1000),
    expiresAt: new Date(Date.now() + 3600_000),
  })
  const freshRunning = await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'running', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/y.mp4', workerId: 'alive-worker',
    heartbeatAt: new Date(),
    expiresAt: new Date(Date.now() + 3600_000),
  })

  const failed = await dubJob.sweepStaleRunning()
  assert.equal(failed, 1)

  const stale = await DubApiJob.findById(staleJob._id).lean()
  assert.equal(stale.status, 'failed')
  assert.match(stale.error, /mất kết nối/)

  const alive = await DubApiJob.findById(freshRunning._id).lean()
  assert.equal(alive.status, 'running')
})

test('heartbeat: job đã bị sweeper fail (worker chết) → worker cũ báo nhịp bị từ chối', async () => {
  const apiKey = await makeApiKey()
  const job = await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'failed', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/x.mp4', workerId: 'dead-worker',
    expiresAt: new Date(Date.now() + 3600_000),
  })
  const ok = await dubJob.heartbeat(job._id, 'dead-worker')
  assert.equal(ok, false)
})
