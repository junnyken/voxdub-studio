'use strict'

/**
 * Hoàn phí khi kết quả dub biến mất TRƯỚC hạn (xem `refundLostResult`).
 *
 * Bối cảnh thật: nền tảng đang chạy (Vibe Host) KHÔNG có ổ đĩa bền vững —
 * đo thật 2026-08-17: cùng một job, tải trước redeploy ra 200, tải lại sau
 * redeploy ra 410 trong khi ví đã bị trừ. Test này khoá lại hành vi đúng.
 *
 * Phần khó KHÔNG phải "có hoàn tiền không" mà là "KHÔNG hoàn nhầm": file
 * biến mất còn có 2 lý do chính đáng (khách đã tải xong rồi hệ thống dọn,
 * và hết hạn giữ hàng). Ba test "không hoàn" bên dưới quan trọng ngang test
 * "có hoàn".
 *
 * Chạy:  node --test tests/dub-refund-lost-result.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

process.env.DUB_UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'voxdub-refund-test-'))

const { build } = require('../src/app')
const ApiKey = require('../src/models/ApiKey')
const DubApiJob = require('../src/models/DubApiJob')
const DubUsageLedger = require('../src/models/DubUsageLedger')
const { createApiKey } = require('../src/services/api-key.service')
const dubJobService = require('../src/services/dub-job.service')
const storage = require('../src/services/job-storage.service')

// V45: kết quả job sống trong GridFS — test dựng file qua đúng kho đó.
async function putOutput(jobId, text) {
  const { Readable } = require('node:stream')
  const { pipeline } = require('node:stream/promises')
  const key = storage.outputKey(String(jobId))
  await pipeline(Readable.from([Buffer.from(text)]), await storage.openWrite(key))
  return key
}

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

function buildMultipart(buffer) {
  const boundary = `----voxdubrefund${Date.now()}`
  const head = Buffer.from(
    `--${boundary}\r\n`
    + 'Content-Disposition: form-data; name="file"; filename="video.mp4"\r\n'
    + 'Content-Type: video/mp4\r\n\r\n',
  )
  const tail = Buffer.from(`\r\n--${boundary}--\r\n`)
  return {
    body: Buffer.concat([head, buffer, tail]),
    contentType: `multipart/form-data; boundary=${boundary}`,
  }
}

/** Submit + worker giả chạy xong → job `done`, quota đã bị trừ thật. */
async function makeDoneJob() {
  const { plaintext, doc } = await createApiKey({ orgName: 'Refund', dubMinutesQuota: 100 })
  const mp = buildMultipart(Buffer.from('fake-mp4'))
  const submitRes = await app.inject({
    method: 'POST',
    url: '/api/v1/dub?sourceLang=en-US&targetLang=vi',
    headers: { authorization: `Bearer ${plaintext}`, 'content-type': mp.contentType },
    payload: mp.body,
  })
  assert.equal(submitRes.statusCode, 200, submitRes.body)
  const { jobId } = submitRes.json()

  await dubJobService.claimNextJob('test-worker')
  await putOutput(jobId, 'fake-dubbed-video-bytes')
  await dubJobService.completeJob(jobId, 'test-worker', {
    outputPath: storage.outputKey(String(jobId)),
    metrics: { inputBytes: 8, outputBytes: 24, processingMs: 100, durationS: 90 },
  })

  const key = await ApiKey.findById(doc._id).lean()
  assert.equal(key.dubMinutesUsed, 2, '90s -> làm tròn lên 2 phút, đã trừ')
  return { plaintext, apiKeyId: doc._id, jobId }
}

function getResult(plaintext, jobId) {
  return app.inject({
    method: 'GET',
    url: `/api/v1/dub/${jobId}/result`,
    headers: { authorization: `Bearer ${plaintext}` },
  })
}

test('mất file trước hạn -> 410 RESULT_LOST_REFUNDED và hoàn đúng số phút đã trừ', async () => {
  const { plaintext, apiKeyId, jobId } = await makeDoneJob()

  // Mô phỏng đúng cái đã xảy ra thật: file bay mất, DB không hề biết.
  await storage.removeJob(String(jobId))

  const res = await getResult(plaintext, jobId)
  assert.equal(res.statusCode, 410)
  assert.equal(res.json().code, 'RESULT_LOST_REFUNDED')
  assert.equal(res.json().minutesRefunded, 2)

  const key = await ApiKey.findById(apiKeyId).lean()
  assert.equal(key.dubMinutesUsed, 0, 'phải hoàn về đúng mức trước khi trừ')

  const job = await DubApiJob.findById(jobId).lean()
  assert.ok(job.refundedAt, 'phải ghi mốc hoàn phí')
  assert.equal(job.status, 'failed', 'trạng thái phải nói thật là không giao được hàng')

  // Sổ cái bất biến: giữ cả dòng trừ lẫn dòng đảo, không sửa/xoá dòng cũ.
  const rows = await DubUsageLedger.find({ jobId }).sort({ createdAt: 1 }).lean()
  assert.equal(rows.length, 2)
  assert.equal(rows[0].minutesCharged, 2)
  assert.equal(rows[1].minutesCharged, -2, 'dòng đảo phải là số âm')
})

test('gọi lại nhiều lần chỉ hoàn ĐÚNG MỘT lần', async () => {
  const { plaintext, apiKeyId, jobId } = await makeDoneJob()
  await storage.removeJob(String(jobId))

  const [r1, r2, r3] = await Promise.all([
    getResult(plaintext, jobId), getResult(plaintext, jobId), getResult(plaintext, jobId),
  ])
  for (const r of [r1, r2, r3]) {
    assert.equal(r.statusCode, 410)
    assert.equal(r.json().code, 'RESULT_LOST_REFUNDED', 'lần sau vẫn phải nói rõ đã hoàn')
  }

  const key = await ApiKey.findById(apiKeyId).lean()
  assert.equal(key.dubMinutesUsed, 0, 'KHÔNG được hoàn chồng thành số âm')
  const rows = await DubUsageLedger.find({ jobId, minutesCharged: { $lt: 0 } }).lean()
  assert.equal(rows.length, 1, 'chỉ đúng 1 dòng đảo')
})

test('KHÔNG hoàn khi khách đã tải xong (file mất là do hệ thống dọn)', async () => {
  const { plaintext, apiKeyId, jobId } = await makeDoneJob()

  const dl = await getResult(plaintext, jobId)
  assert.equal(dl.statusCode, 200, 'tải lần đầu phải thành công')

  // Route dọn file bất đồng bộ sau khi stream đóng — chờ tới lúc đã dọn xong.
  // Ngưỡng chờ rộng tay (V45): ghi mốc + xoá file giờ là vài lượt round-trip
  // GridFS, không phải 1 lệnh unlink; vòng chờ 1 giây từng gây fail chập chờn.
  for (let i = 0; i < 250; i += 1) {
    const j = await DubApiJob.findById(jobId).lean()
    if (j.deliveredAt) break
    await new Promise((r) => setTimeout(r, 20))
  }
  const delivered = await DubApiJob.findById(jobId).lean()
  assert.ok(delivered.deliveredAt, 'phải ghi mốc đã giao hàng')

  const again = await getResult(plaintext, jobId)
  assert.equal(again.statusCode, 410)
  assert.equal(again.json().code, 'RESULT_EXPIRED', 'đã nhận hàng thì KHÔNG phải diện hoàn phí')

  const key = await ApiKey.findById(apiKeyId).lean()
  assert.equal(key.dubMinutesUsed, 2, 'phí phải giữ nguyên')
  const refunds = await DubUsageLedger.find({ jobId, minutesCharged: { $lt: 0 } }).lean()
  assert.equal(refunds.length, 0)
})

test('KHÔNG hoàn khi đã quá hạn giữ hàng (khách không tải trong TTL)', async () => {
  const { plaintext, apiKeyId, jobId } = await makeDoneJob()
  await storage.removeJob(String(jobId))
  await DubApiJob.updateOne({ _id: jobId }, { $set: { expiresAt: new Date(Date.now() - 1000) } })

  const res = await getResult(plaintext, jobId)
  assert.equal(res.statusCode, 410)
  assert.equal(res.json().code, 'RESULT_EXPIRED', 'hết hạn là điều khoản có sẵn, không hoàn')

  const key = await ApiKey.findById(apiKeyId).lean()
  assert.equal(key.dubMinutesUsed, 2, 'phí phải giữ nguyên')
})

test('KHÔNG hoàn cho job của API key khác (không rò rỉ qua đường hoàn phí)', async () => {
  const { apiKeyId, jobId } = await makeDoneJob()
  await storage.removeJob(String(jobId))

  const other = await createApiKey({ orgName: 'Kẻ lạ', dubMinutesQuota: 100 })
  const res = await getResult(other.plaintext, jobId)
  assert.equal(res.statusCode, 404, 'key khác không được thấy job này')

  const key = await ApiKey.findById(apiKeyId).lean()
  assert.equal(key.dubMinutesUsed, 2, 'phí của chủ job phải giữ nguyên')
  const job = await DubApiJob.findById(jobId).lean()
  assert.equal(job.refundedAt, null)
})
