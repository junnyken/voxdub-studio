'use strict'

/**
 * Integration test cho state machine job lồng tiếng đầy đủ (mini-spec
 * V34a→V34b, xem docs/PLAN.md). Cùng khuôn `render-job.integration.test.js`
 * (V9→V12) — chạm MongoDB thật (in-memory), KHÔNG spawn worker Python thật
 * (đó là việc của `control_server/worker-dub/dub_worker.py`, live-verify
 * riêng ghi ở docs/TEST_LOG.md, không cần Docker/mạng ở đây).
 *
 * V34b: `dubMinutesQuota` mặc định 0 (opt-in) — `makeApiKey()` dưới đây
 * cấp sẵn quota để các test khác không phải tự lo billing, trừ các test
 * CHỦ ĐÍCH kiểm tra billing/quota (đặt tên rõ).
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
const DubUsageLedger = require('../src/models/DubUsageLedger')
const config = require('../src/services/config.service')
const dubJob = require('../src/services/dub-job.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(async () => { await clearDb(); config.invalidate() })

async function makeApiKey(orgName = 'Test Org', dubMinutesQuota = 100) {
  return ApiKey.create({
    keyHash: `h${Date.now()}${Math.random()}`, keyPrefix: 'testpfx1', orgName, dubMinutesQuota,
  })
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

test('submitDubJob: hết quota phút dub (mặc định 0, opt-in) → 402, không tạo job', async () => {
  const apiKey = await makeApiKey('No Quota Org', 0)
  await assert.rejects(
    () => dubJob.submitDubJob({
      apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
    }),
    (err) => err.code === 'DUB_QUOTA_EXCEEDED' && err.statusCode === 402,
  )
  const count = await DubApiJob.countDocuments({ apiKeyId: apiKey._id })
  assert.equal(count, 0)
})

test('submitDubJob: trả về NGAY status=queued, gắn đúng bgMode, KHÔNG đụng ApiKey.usageCount/quota V31', async () => {
  const apiKey = await makeApiKey()
  const estimate = await config.get('credit.cost.cloud.dub.vox.per.minute')

  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
    voice: 'Minh Trang', bgMode: 'none',
  })

  assert.equal(job.status, 'queued')
  assert.equal(job.sourceLang, 'en-US')
  assert.equal(job.targetLang, 'vi')
  assert.equal(job.voice, 'Minh Trang')
  assert.equal(job.bgMode, 'none')
  assert.equal(job.estimatedCostVox, estimate, 'chỉ tham khảo lúc submit, không phải số đã trừ')
  assert.equal(job.costVox, 0, 'chưa xong thì chưa tính phí thật')
  assert.equal(job.workerId, '')
  assert.equal(job.heartbeatAt, null)
  assert.ok(fs.existsSync(job.inputPath), 'file input phải được ghi ra đĩa')

  const freshKey = await ApiKey.findById(apiKey._id).lean()
  assert.equal(freshKey.usageCount, 0, 'quota/usageCount của V31 không liên quan, không đổi')
  assert.equal(freshKey.quota, apiKey.quota)
  assert.equal(freshKey.dubMinutesUsed, 0, 'chưa xong thì chưa trừ phút dub')
})

test('submitDubJob: bgMode mặc định "none" nếu không truyền', async () => {
  const apiKey = await makeApiKey()
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
  })
  assert.equal(job.bgMode, 'none')
})

test('claimNextJob → completeJob: state machine đầy đủ, metrics ghi đúng, TÍNH PHÍ THẬT theo durationS', async () => {
  const apiKey = await makeApiKey()
  const perMinute = await config.get('credit.cost.cloud.dub.vox.per.minute')
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
  // 125s = 2.08 phút -> làm tròn LÊN 3 phút.
  const completed = await dubJob.completeJob(job._id, 'worker-1', {
    outputPath: paths.output,
    metrics: { inputBytes: 24, outputBytes: 24, processingMs: 1234, durationS: 125 },
  })
  assert.equal(completed.status, 'done')
  assert.equal(completed.outputPath, paths.output)
  assert.equal(completed.metrics.processingMs, 1234)
  assert.equal(completed.metrics.durationS, 125)
  assert.equal(completed.costVox, 3 * perMinute, 'làm tròn lên phút: 125s -> 3 phút')

  const freshKey = await ApiKey.findById(apiKey._id).lean()
  assert.equal(freshKey.dubMinutesUsed, 3)

  const ledger = await DubUsageLedger.findOne({ jobId: job._id }).lean()
  assert.ok(ledger, 'phải có 1 dòng ledger')
  assert.equal(ledger.minutesCharged, 3)
  assert.equal(ledger.costVox, 3 * perMinute)
  assert.equal(ledger.bgMode, 'none')
  assert.equal(ledger.dubMinutesUsedAfter, 3)
})

test('completeJob: durationS rất ngắn vẫn tính tối thiểu 1 phút (không miễn phí)', async () => {
  const apiKey = await makeApiKey()
  const perMinute = await config.get('credit.cost.cloud.dub.vox.per.minute')
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
  })
  await dubJob.claimNextJob('worker-1')
  const paths = dubJob.jobPaths(job._id)
  fs.writeFileSync(paths.output, 'x')
  const completed = await dubJob.completeJob(job._id, 'worker-1', {
    outputPath: paths.output,
    metrics: { durationS: 3 },
  })
  assert.equal(completed.costVox, perMinute)

  const freshKey = await ApiKey.findById(apiKey._id).lean()
  assert.equal(freshKey.dubMinutesUsed, 1)
})

test('completeJob: bgMode=demucs tính theo đơn giá demucs (khác none)', async () => {
  const apiKey = await makeApiKey()
  const perMinuteDemucs = await config.get('credit.cost.cloud.dub.vox.per.minute.demucs')
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi', bgMode: 'demucs',
  })
  await dubJob.claimNextJob('worker-1')
  const paths = dubJob.jobPaths(job._id)
  fs.writeFileSync(paths.output, 'x')
  const completed = await dubJob.completeJob(job._id, 'worker-1', {
    outputPath: paths.output,
    metrics: { durationS: 60 },
  })
  assert.equal(completed.costVox, perMinuteDemucs)
})

test('completeJob: durationS=0 (worker cũ/lỗi) → KHÔNG tính phí, không tạo ledger', async () => {
  const apiKey = await makeApiKey()
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
  })
  await dubJob.claimNextJob('worker-1')
  const paths = dubJob.jobPaths(job._id)
  fs.writeFileSync(paths.output, 'x')
  const completed = await dubJob.completeJob(job._id, 'worker-1', {
    outputPath: paths.output,
    metrics: { durationS: 0 },
  })
  assert.equal(completed.costVox, 0)

  const freshKey = await ApiKey.findById(apiKey._id).lean()
  assert.equal(freshKey.dubMinutesUsed, 0)
  assert.equal(await DubUsageLedger.countDocuments({ jobId: job._id }), 0)
})

test('chargeDubUsage: atomic — 5 job "hoàn tất" đồng thời cộng dồn đúng, không mất cập nhật', async () => {
  const apiKey = await makeApiKey('Concurrent Org', 1000)
  const jobs = await Promise.all(Array.from({ length: 5 }, () => dubJob.submitDubJob({
    apiKey, fileBuffer: fakeMp4Buffer(), sourceLang: 'en-US', targetLang: 'vi',
  })))

  await Promise.all(jobs.map((j) => dubJob.chargeDubUsage(apiKey._id, j.job._id, 'none', 60)))

  const freshKey = await ApiKey.findById(apiKey._id).lean()
  assert.equal(freshKey.dubMinutesUsed, 5, 'mỗi job 60s = 1 phút, 5 job = 5 phút, không lệch do race')
  assert.equal(await DubUsageLedger.countDocuments({ apiKeyId: apiKey._id }), 5)
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

test('sweepExpired: dọn đúng job hết hạn, KHÔNG đụng DubUsageLedger (sổ cái sống độc lập)', async () => {
  const apiKey = await makeApiKey()
  const expired = await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'done', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/x.mp4', costVox: 150, expiresAt: new Date(Date.now() - 1000),
  })
  const fresh = await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'done', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/y.mp4', expiresAt: new Date(Date.now() + 3600_000),
  })
  await DubUsageLedger.create({
    apiKeyId: apiKey._id, jobId: expired._id, bgMode: 'none',
    durationS: 60, minutesCharged: 1, costVox: 150, dubMinutesUsedAfter: 1,
  })

  const swept = await dubJob.sweepExpired()
  assert.equal(swept, 1)
  assert.equal(await DubApiJob.countDocuments({ _id: expired._id }), 0)
  assert.equal(await DubApiJob.countDocuments({ _id: fresh._id }), 1)
  assert.equal(await DubUsageLedger.countDocuments({ jobId: expired._id }), 1,
    'job bị xoá do TTL nhưng lịch sử billing phải còn nguyên')
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
