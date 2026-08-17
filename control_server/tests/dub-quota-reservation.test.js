'use strict'

/**
 * Mini-spec V43 (docs/PLAN.md, Phase G) — giữ chỗ (reserve) quota phút dub
 * atomic lúc submit, đóng gap race condition mà V42 phát hiện
 * (`dubMinutesUsed` chỉ `$inc` SAU khi job hoàn tất → nhiều submit đồng
 * thời từ CÙNG 1 key đều đọc thấy quota còn trống).
 *
 * Chạy:  node --test tests/dub-quota-reservation.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

process.env.DUB_UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'voxdub-dub-reserve-test-'))

const ApiKey = require('../src/models/ApiKey')
const DubApiJob = require('../src/models/DubApiJob')
const config = require('../src/services/config.service')
const dubJob = require('../src/services/dub-job.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(async () => { await clearDb(); config.invalidate() })

function makeApiKey(dubMinutesQuota = 100) {
  return ApiKey.create({
    keyHash: `h${Date.now()}${Math.random()}`, keyPrefix: 'testpfx1', orgName: 'Test', dubMinutesQuota,
  })
}

function fakeBuffer() {
  return Buffer.from('fake-mp4-bytes')
}

test('submitDubJob: giữ chỗ đúng mặc định cấu hình khi không khai estimatedMinutes', async () => {
  const apiKey = await makeApiKey(100)
  const defaultMinutes = await config.get('cloud.dub.reservation.default.minutes')
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi',
  })
  assert.equal(job.reservedMinutes, defaultMinutes)

  const fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, defaultMinutes)
})

test('submitDubJob: caller tự khai estimatedMinutes -> giữ đúng số đã khai', async () => {
  const apiKey = await makeApiKey(100)
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: 30,
  })
  assert.equal(job.reservedMinutes, 30)
  const fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, 30)
})

test('submitDubJob: estimatedMinutes vượt trần cấu hình -> bị kẹp về trần', async () => {
  const apiKey = await makeApiKey(10000)
  const maxMinutes = await config.get('cloud.dub.reservation.max.minutes')
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: 999999,
  })
  assert.equal(job.reservedMinutes, maxMinutes)
})

test('submitDubJob: estimatedMinutes âm/0/NaN -> rơi về mặc định, không throw', async () => {
  const apiKey = await makeApiKey(100)
  const defaultMinutes = await config.get('cloud.dub.reservation.default.minutes')
  for (const bad of [-5, 0, NaN]) {
    const { job } = await dubJob.submitDubJob({
      apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: bad,
    })
    assert.equal(job.reservedMinutes, defaultMinutes)
  }
})

test('reserveDubMinutes: atomic — N submit đồng thời chỉ đúng số vừa đủ quota lọt qua (đóng gap race V42)', async () => {
  // Quota=12 phút, mỗi job khai 5 phút -> tối đa 2 job lọt qua (10 <= 12),
  // job thứ 3 phải bị từ chối dù đọc "dubMinutesUsed=0" y hệt 2 job kia lúc
  // submit gần như đồng thời (đây chính là race trước V43).
  const apiKey = await makeApiKey(12)
  const attempts = await Promise.allSettled(Array.from({ length: 5 }, () => dubJob.submitDubJob({
    apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: 5,
  })))

  const fulfilled = attempts.filter((a) => a.status === 'fulfilled')
  const rejected = attempts.filter((a) => a.status === 'rejected')
  assert.equal(fulfilled.length, 2, 'chỉ đúng 2 job (5+5=10 <= 12) được lọt qua')
  assert.equal(rejected.length, 3)
  for (const r of rejected) {
    assert.equal(r.reason.code, 'DUB_QUOTA_EXCEEDED')
  }

  const fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, 10, 'không vượt quota dù 5 request bắn gần như đồng thời')
})

test('completeJob: giải phóng reservation VÀ cộng usage thật trong cùng 1 lần cập nhật', async () => {
  const apiKey = await makeApiKey(100)
  const perMinute = await config.get('credit.cost.cloud.dub.vox.per.minute')
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: 20,
  })
  let fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, 20)

  await dubJob.claimNextJob('worker-1')
  const paths = dubJob.jobPaths(job._id)
  fs.writeFileSync(paths.output, 'x')
  const completed = await dubJob.completeJob(job._id, 'worker-1', {
    outputPath: paths.output,
    metrics: { durationS: 125 },   // -> 3 phút thật, KHÁC 20 phút đã giữ chỗ
  })
  assert.equal(completed.costVox, 3 * perMinute)

  fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, 0, 'giữ chỗ phải về 0, không phải 20-3')
  assert.equal(fresh.dubMinutesUsed, 3, 'chỉ trừ đúng phút THẬT, không phải số đã giữ chỗ')
})

test('completeJob: durationS=0 (worker cũ) -> vẫn giải phóng reservation dù không tính phí', async () => {
  const apiKey = await makeApiKey(100)
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: 15,
  })
  await dubJob.claimNextJob('worker-1')
  const paths = dubJob.jobPaths(job._id)
  fs.writeFileSync(paths.output, 'x')
  await dubJob.completeJob(job._id, 'worker-1', { outputPath: paths.output, metrics: { durationS: 0 } })

  const fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, 0, 'không rò rỉ quota vĩnh viễn dù không tính phí được')
  assert.equal(fresh.dubMinutesUsed, 0)
})

test('failJob: job lỗi -> giải phóng TOÀN BỘ reservation, không trừ usage', async () => {
  const apiKey = await makeApiKey(100)
  const { job } = await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: 25,
  })
  await dubJob.claimNextJob('worker-1')
  await dubJob.failJob(job._id, 'worker-1', new Error('pipeline crashed'))

  const fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, 0)
  assert.equal(fresh.dubMinutesUsed, 0)
})

test('sweepStaleRunning: worker mất kết nối -> giải phóng reservation của job đó', async () => {
  const apiKey = await makeApiKey(100)
  await config.set('cloud.dub.heartbeat.stale.minutes', 1)
  await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'running', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/x.mp4', workerId: 'dead-worker', reservedMinutes: 8,
    heartbeatAt: new Date(Date.now() - 5 * 60 * 1000),
    expiresAt: new Date(Date.now() + 3600_000),
  })
  await ApiKey.updateOne({ _id: apiKey._id }, { $inc: { dubMinutesReserved: 8 } })

  const failed = await dubJob.sweepStaleRunning()
  assert.equal(failed, 1)
  const fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, 0)
})

test('sweepStaleQueued: không worker nào claim kịp TTL -> failed + giải phóng reservation', async () => {
  const apiKey = await makeApiKey(100)
  const staleJob = await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'queued', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/x.mp4', reservedMinutes: 12,
    expiresAt: new Date(Date.now() - 1000),
  })
  const freshQueued = await DubApiJob.create({
    apiKeyId: apiKey._id, status: 'queued', sourceLang: 'en-US', targetLang: 'vi',
    inputPath: '/tmp/y.mp4', reservedMinutes: 5,
    expiresAt: new Date(Date.now() + 3600_000),
  })
  await ApiKey.updateOne({ _id: apiKey._id }, { $inc: { dubMinutesReserved: 17 } })

  const failed = await dubJob.sweepStaleQueued()
  assert.equal(failed, 1)

  const stale = await DubApiJob.findById(staleJob._id).lean()
  assert.equal(stale.status, 'failed')
  assert.match(stale.error, /không worker/i)

  const stillQueued = await DubApiJob.findById(freshQueued._id).lean()
  assert.equal(stillQueued.status, 'queued', 'job chưa hết hạn không bị đụng')

  const fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, 5, 'chỉ giải phóng đúng 12 của job hết hạn, giữ nguyên 5 của job còn sống')
})

test('submitDubJob: tạo job hỏng SAU khi đã giữ chỗ -> rollback, không rò rỉ quota', async () => {
  const apiKey = await makeApiKey(100)
  const badBuffer = null   // fs.writeFile(dir, null) sẽ throw -> mô phỏng lỗi ghi đĩa sau khi đã reserve
  await assert.rejects(() => dubJob.submitDubJob({
    apiKey, fileBuffer: badBuffer, sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: 40,
  }))
  const fresh = await ApiKey.findById(apiKey._id).lean()
  assert.equal(fresh.dubMinutesReserved, 0, 'reservation phải được trả lại khi tạo job thất bại')
})

test('DUB_QUOTA_EXCEEDED: thông báo phản ánh đúng cả phần đang giữ chỗ bởi job khác', async () => {
  const apiKey = await makeApiKey(10)
  await dubJob.submitDubJob({
    apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: 8,
  })
  await assert.rejects(
    () => dubJob.submitDubJob({
      apiKey, fileBuffer: fakeBuffer(), sourceLang: 'en-US', targetLang: 'vi', estimatedMinutes: 5,
    }),
    (err) => {
      assert.equal(err.code, 'DUB_QUOTA_EXCEEDED')
      assert.match(err.message, /8 phút cho job khác/)
      assert.match(err.message, /hạn mức 10 phút/)
      return true
    },
  )
})
