'use strict'

/**
 * Mini-spec V50 — job tách nhạc trên cloud không ai nhận thì phải hoàn Vox.
 *
 * Lỗ hổng thật, tìm ra khi audit 2026-08-17: Vox bị trừ NGAY lúc nộp, nhưng
 * `sweepExpired` chỉ dọn `done`/`failed` và `sweepStaleRunning` chỉ lo
 * `running` — **không ai đụng tới `queued`**. Cộng thêm việc hiện KHÔNG có
 * worker render nào được triển khai trên nền tảng mới, một lượt bấm "xử lý
 * trên cloud" = mất 50 Vox, không kết quả, không cả dấu vết lỗi để hỏi.
 *
 * Ranh giới quan trọng: chỉ hoàn khi **chưa có gì chạy**. Job đã được worker
 * nhận rồi mới hỏng vẫn giữ chính sách cũ "đã tốn tài nguyên máy chủ, không
 * hoàn" (docs/API.md) — nên nhóm test "KHÔNG hoàn" dưới đây quan trọng ngang
 * nhóm "có hoàn".
 *
 * Chạy:  node --test tests/render-stale-queued-refund.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const Device = require('../src/models/Device')
const RenderJob = require('../src/models/RenderJob')
const CreditLedger = require('../src/models/CreditLedger')
const config = require('../src/services/config.service')
const renderJob = require('../src/services/render-job.service')

const FP = 'a'.repeat(64)
const COST = 50

test.before(startDb)
test.after(stopDb)
test.beforeEach(async () => { await clearDb(); config.invalidate() })

/** Job đã trừ tiền, `createdAt` lùi về quá khứ `ageMinutes` phút. */
async function makeJob({ status = 'queued', ageMinutes = 60, charged = COST } = {}) {
  await Device.create({ fingerprint: FP, balance: 1000 - charged, status: 'active' })
  const job = await RenderJob.create({
    fingerprint: FP,
    deviceId: (await Device.findOne({ fingerprint: FP }))._id,
    stage: 'demucs',
    status,
    inputPath: '/tmp/in.wav',
    creditCharged: charged,
    workerId: status === 'running' ? 'w1' : '',
    heartbeatAt: status === 'running' ? new Date() : null,
    expiresAt: new Date(Date.now() + 3600_000),
  })
  // `createdAt` do timestamps sinh — ép lùi để mô phỏng job nằm chờ đã lâu.
  // Phải đi thẳng qua driver: Mongoose đánh dấu `createdAt` là immutable nên
  // `Model.updateOne` bỏ qua $set này KHÔNG BÁO LỖI (mất 1 lượt chạy test mới
  // nhận ra — sweeper báo "0 job" trong khi tưởng đã có job cũ).
  await RenderJob.collection.updateOne(
    { _id: job._id },
    { $set: { createdAt: new Date(Date.now() - ageMinutes * 60_000) } },
  )
  return job
}

async function balance() {
  return (await Device.findOne({ fingerprint: FP }).lean()).balance
}

test('job queued quá lâu: chuyển failed VÀ hoàn đúng số Vox đã trừ', async () => {
  await makeJob({ ageMinutes: 60 })
  assert.equal(await balance(), 950)

  const failed = await renderJob.sweepStaleQueued()
  assert.equal(failed, 1)

  const job = await RenderJob.findOne({ fingerprint: FP }).lean()
  assert.equal(job.status, 'failed')
  assert.match(job.error, /không có máy xử lý|Không máy xử lý/i)
  assert.equal(await balance(), 1000, 'phải hoàn đủ 50 Vox — không có gì chạy cả')
})

test('hoàn phí ghi vào sổ cái, không sửa lịch sử cũ', async () => {
  await makeJob({ ageMinutes: 60 })
  await renderJob.sweepStaleQueued()

  const entries = await CreditLedger.find({ fingerprint: FP }).lean()
  const refunds = entries.filter((e) => e.delta > 0)
  assert.equal(refunds.length, 1, 'đúng 1 dòng hoàn')
  assert.equal(refunds[0].delta, COST)
})

test('quét 2 lần liên tiếp chỉ hoàn ĐÚNG MỘT lần', async () => {
  await makeJob({ ageMinutes: 60 })

  assert.equal(await renderJob.sweepStaleQueued(), 1)
  assert.equal(await renderJob.sweepStaleQueued(), 0, 'lượt 2 không được thấy job nào nữa')
  assert.equal(await balance(), 1000, 'số dư không được cộng 2 lần')
})

test('KHÔNG đụng job mới nộp (chưa quá ngưỡng chờ)', async () => {
  await makeJob({ ageMinutes: 1 })

  assert.equal(await renderJob.sweepStaleQueued(), 0)
  const job = await RenderJob.findOne({ fingerprint: FP }).lean()
  assert.equal(job.status, 'queued', 'job vừa nộp phải được yên để worker nhận')
  assert.equal(await balance(), 950)
})

test('KHÔNG hoàn cho job đã được worker nhận (đã tốn tài nguyên thật)', async () => {
  await makeJob({ status: 'running', ageMinutes: 60 })

  assert.equal(await renderJob.sweepStaleQueued(), 0)
  assert.equal(await balance(), 950, 'chính sách cũ giữ nguyên: job đã chạy thì không hoàn')
})

test('KHÔNG hoàn cho job đã xong', async () => {
  await makeJob({ status: 'done', ageMinutes: 60 })

  assert.equal(await renderJob.sweepStaleQueued(), 0)
  assert.equal(await balance(), 950)
})

test('job miễn phí (creditCharged=0): vẫn fail nhưng không tạo dòng hoàn rỗng', async () => {
  await makeJob({ ageMinutes: 60, charged: 0 })

  assert.equal(await renderJob.sweepStaleQueued(), 1)
  const job = await RenderJob.findOne({ fingerprint: FP }).lean()
  assert.equal(job.status, 'failed')
  assert.equal(await CreditLedger.countDocuments({ fingerprint: FP }), 0)
})

test('ngưỡng chờ đọc từ cấu hình, không hardcode', async () => {
  await makeJob({ ageMinutes: 20 })

  await config.set('cloud.render.queue.stale.minutes', 60)
  config.invalidate()
  assert.equal(await renderJob.sweepStaleQueued(), 0, 'ngưỡng 60 phút thì job 20 phút phải được tha')

  await config.set('cloud.render.queue.stale.minutes', 10)
  config.invalidate()
  assert.equal(await renderJob.sweepStaleQueued(), 1, 'ngưỡng 10 phút thì job 20 phút phải bị quét')
})
