'use strict'

/**
 * Mini-spec V45 — kết quả job phải SỐNG SÓT qua redeploy.
 *
 * Đây là test lý do tồn tại của cả mini-spec. Kịch bản đúng bằng sự cố thật
 * đo được ngày 2026-08-17 trên prod: job `done`, tải được; redeploy; tải lại
 * đúng job đó → file biến mất trong khi ví ĐÃ bị trừ. Trước V45 hệ thống chỉ
 * biết hoàn tiền (V44) — khách vẫn không có hàng.
 *
 * "Redeploy" ở đây mô phỏng bằng: đóng app, XOÁ SẠCH thư mục đĩa cục bộ
 * (đúng thứ container mất khi dựng lại), rồi dựng app mới trên CÙNG database
 * (đúng như MongoDB managed sống qua redeploy). Nếu kết quả vẫn tải được thì
 * mới thật sự bền vững.
 *
 * Chạy:  node --test tests/dub-result-durability.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const { Readable } = require('node:stream')
const { pipeline } = require('node:stream/promises')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'voxdub-durability-test-'))
process.env.DUB_UPLOAD_DIR = UPLOAD_DIR

const { build } = require('../src/app')
const DubApiJob = require('../src/models/DubApiJob')
const storage = require('../src/services/job-storage.service')
const { createApiKey } = require('../src/services/api-key.service')

const RESULT_BYTES = Buffer.from('dubbed-video-bytes-của-khách-đã-trả-tiền')

let app

test.before(async () => {
  await startDb()
  app = await build({ mongo: false, web: false, logger: false })
  await app.ready()
})
test.after(async () => {
  await app.close()
  await stopDb()
  fs.rmSync(UPLOAD_DIR, { recursive: true, force: true })
})
test.beforeEach(clearDb)

/** Dựng lại tiến trình app y như một lượt redeploy: đóng app, xoá sạch đĩa
 * cục bộ, mở app mới trên cùng database. */
async function simulateRedeploy() {
  await app.close()
  fs.rmSync(UPLOAD_DIR, { recursive: true, force: true })
  fs.mkdirSync(UPLOAD_DIR, { recursive: true })
  app = await build({ mongo: false, web: false, logger: false })
  await app.ready()
}

async function makeDoneJob() {
  const { plaintext, doc } = await createApiKey({
    orgName: 'Khách V45', contactEmail: '', quota: 100, dubMinutesQuota: 100,
  })
  const job = await DubApiJob.create({
    apiKeyId: doc._id,
    status: 'done',
    sourceLang: 'en-US',
    targetLang: 'vi',
    inputPath: 'dub/placeholder/input.mp4',
    expiresAt: new Date(Date.now() + 3600_000),
    costVox: 150,
    metrics: { durationS: 60 },
  })
  const key = storage.outputKey(String(job._id))
  await pipeline(Readable.from([RESULT_BYTES]), await storage.openWrite(key))
  await DubApiJob.updateOne({ _id: job._id }, { $set: { outputPath: key } })
  return { apiKey: plaintext, jobId: String(job._id) }
}

function download(apiKey, jobId) {
  return app.inject({
    method: 'GET',
    url: `/api/v1/dub/${jobId}/result`,
    headers: { authorization: `Bearer ${apiKey}` },
  })
}

test('kết quả vẫn tải được NGUYÊN VẸN sau khi container dựng lại', async () => {
  const { apiKey, jobId } = await makeDoneJob()

  await simulateRedeploy()

  const res = await download(apiKey, jobId)
  assert.equal(res.statusCode, 200,
    'đây chính là ca hỏng trước V45: khách đã bị trừ tiền mà nhận 410')
  assert.ok(res.rawPayload.equals(RESULT_BYTES), 'nội dung video phải nguyên vẹn từng byte')
  assert.equal(res.headers['content-type'], 'video/mp4')
})

test('sau redeploy, tải xong vẫn dọn file và đánh dấu đã giao (không hoàn tiền nhầm)', async () => {
  const { apiKey, jobId } = await makeDoneJob()
  await simulateRedeploy()

  assert.equal((await download(apiKey, jobId)).statusCode, 200)

  const key = storage.outputKey(jobId)
  for (let i = 0; i < 250; i += 1) {
    if (!(await storage.exists(key))) break
    await new Promise((r) => setTimeout(r, 20))
  }
  assert.equal(await storage.exists(key), false, 'file phải bị dọn sau khi giao (chính sách V9)')

  const after = await DubApiJob.findById(jobId).lean()
  assert.ok(after.deliveredAt, 'phải ghi mốc đã giao hàng')

  // Lượt gọi thứ hai: đã nhận hàng rồi thì KHÔNG được hoàn tiền.
  const second = await download(apiKey, jobId)
  assert.equal(second.statusCode, 410)
  assert.equal(second.json().code, 'RESULT_EXPIRED')
  const finalJob = await DubApiJob.findById(jobId).lean()
  assert.equal(finalJob.refundedAt, null, 'khách đã nhận đủ hàng thì không được hoàn phí')
})

test('lưới an toàn V44 vẫn còn: file BỊ MẤT THẬT thì hoàn tiền, không im lặng', async () => {
  const { apiKey, jobId } = await makeDoneJob()
  // Mất file trong chính kho bền vững (vd bị xoá tay/sự cố) — khác hẳn ca
  // "đĩa container bay theo redeploy" mà V45 vừa đóng.
  await storage.remove(storage.outputKey(jobId))

  const res = await download(apiKey, jobId)
  assert.equal(res.statusCode, 410)
  assert.equal(res.json().code, 'RESULT_LOST_REFUNDED')
})
