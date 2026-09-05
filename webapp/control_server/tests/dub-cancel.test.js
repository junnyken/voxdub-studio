'use strict'

/**
 * Mini-spec V55 — khách huỷ job lồng tiếng đang chờ/đang chạy.
 *
 * Trước V55 không có đường huỷ nào: bấm Dừng trên app chỉ đóng cửa sổ của
 * mình, job vẫn chạy trên máy chủ và vẫn tính tiền khi xong. Ai lỡ nộp nhầm
 * 20 video thì không có cách nào chặn.
 *
 * Hai thứ phải đúng tuyệt đối:
 *   1. KHÔNG huỷ được job của người khác (huỷ job người ta nặng hơn xem trộm).
 *   2. Job đã huỷ KHÔNG BAO GIỜ bị tính tiền, kể cả khi worker báo "xong" muộn.
 *
 * Chạy:  node --test tests/dub-cancel.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const { Readable } = require('node:stream')
const { pipeline } = require('node:stream/promises')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const ApiKey = require('../src/models/ApiKey')
const DubApiJob = require('../src/models/DubApiJob')
const DubUsageLedger = require('../src/models/DubUsageLedger')
const storage = require('../src/services/job-storage.service')
const dubJob = require('../src/services/dub-job.service')
const { createApiKey } = require('../src/services/api-key.service')

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

async function makeKeyAndJob({ status = 'queued', reserved = 5, org = 'Khách A' } = {}) {
  const { plaintext, doc } = await createApiKey({
    orgName: org, contactEmail: '', quota: 100, dubMinutesQuota: 100,
  })
  await ApiKey.updateOne({ _id: doc._id }, { $set: { dubMinutesReserved: reserved } })

  const job = await DubApiJob.create({
    apiKeyId: doc._id,
    status,
    sourceLang: 'en-US',
    targetLang: 'vi',
    inputPath: 'placeholder',
    reservedMinutes: reserved,
    workerId: status === 'running' ? 'w1' : '',
    expiresAt: new Date(Date.now() + 3600_000),
  })
  const inKey = storage.inputKey(String(job._id))
  await pipeline(Readable.from([Buffer.from('video')]), await storage.openWrite(inKey))
  await DubApiJob.updateOne({ _id: job._id }, { $set: { inputPath: inKey } })
  return { apiKey: plaintext, keyId: doc._id, job }
}

function cancel(apiKey, jobId) {
  return app.inject({
    method: 'POST',
    url: `/api/v1/dub/${jobId}/cancel`,
    headers: { authorization: `Bearer ${apiKey}` },
  })
}

test('huỷ job đang chờ: chuyển cancelled, trả lại quota giữ chỗ, xoá file', async () => {
  const { apiKey, keyId, job } = await makeKeyAndJob({ reserved: 5 })

  const res = await cancel(apiKey, job._id)
  assert.equal(res.statusCode, 200)
  assert.equal(res.json().status, 'cancelled')
  assert.equal(res.json().releasedMinutes, 5)

  const after = await DubApiJob.findById(job._id).lean()
  assert.equal(after.status, 'cancelled')
  const key = await ApiKey.findById(keyId).lean()
  assert.equal(key.dubMinutesReserved, 0, 'quota giữ chỗ phải được trả lại ngay')
  assert.equal(await storage.exists(storage.inputKey(String(job._id))), false,
    'file input phải được dọn, không giữ rác của job đã huỷ')
})

test('huỷ job đang chạy cũng được (đó mới là lúc người ta muốn dừng)', async () => {
  const { apiKey, job } = await makeKeyAndJob({ status: 'running' })

  const res = await cancel(apiKey, job._id)
  assert.equal(res.statusCode, 200)
  assert.equal((await DubApiJob.findById(job._id).lean()).status, 'cancelled')
})

test('worker báo "xong" SAU khi khách huỷ: bị từ chối, KHÔNG tính tiền', async () => {
  const { apiKey, keyId, job } = await makeKeyAndJob({ status: 'running' })
  await cancel(apiKey, job._id)

  // Worker chạy xong muộn và cố báo kết quả như bình thường.
  const completed = await dubJob.completeJob(String(job._id), 'w1', {
    outputPath: 'x', metrics: { durationS: 600 },
  })

  assert.equal(completed, null, 'job đã huỷ thì không nhận báo cáo hoàn tất')
  const key = await ApiKey.findById(keyId).lean()
  assert.equal(key.dubMinutesUsed, 0, 'tuyệt đối không tính tiền job đã huỷ')
  assert.equal(await DubUsageLedger.countDocuments({}), 0, 'không sinh dòng sổ cái')
  assert.equal((await DubApiJob.findById(job._id).lean()).status, 'cancelled',
    'trạng thái không được bị worker ghi đè thành done')
})

test('KHÔNG huỷ được job của API key khác', async () => {
  const { job } = await makeKeyAndJob({ org: 'Khách A' })
  const { plaintext: intruder } = await createApiKey({
    orgName: 'Khách B', contactEmail: '', quota: 10, dubMinutesQuota: 10,
  })

  const res = await cancel(intruder, job._id)
  assert.equal(res.statusCode, 409)
  assert.equal((await DubApiJob.findById(job._id).lean()).status, 'queued',
    'job của người khác phải còn nguyên')
})

test('job đã xong thì không huỷ được nữa (và không hoàn quota lần hai)', async () => {
  const { apiKey, keyId, job } = await makeKeyAndJob({ status: 'queued', reserved: 3 })
  await DubApiJob.updateOne({ _id: job._id }, { $set: { status: 'done' } })

  const res = await cancel(apiKey, job._id)
  assert.equal(res.statusCode, 409)
  assert.equal(res.json().code, 'CANNOT_CANCEL')
  const key = await ApiKey.findById(keyId).lean()
  assert.equal(key.dubMinutesReserved, 3, 'không được đụng vào giữ chỗ của job đã xong')
})

test('huỷ 2 lần: lần sau trả 409, quota không bị trả lại 2 lần', async () => {
  const { apiKey, keyId, job } = await makeKeyAndJob({ reserved: 7 })

  assert.equal((await cancel(apiKey, job._id)).statusCode, 200)
  assert.equal((await cancel(apiKey, job._id)).statusCode, 409)

  const key = await ApiKey.findById(keyId).lean()
  assert.equal(key.dubMinutesReserved, 0, 'không âm, không cộng bù hai lần')
})

test('jobId sai định dạng: 409 chứ không phải 500', async () => {
  const { apiKey } = await makeKeyAndJob()

  const res = await cancel(apiKey, 'khong-phai-objectid')
  assert.equal(res.statusCode, 409)
})

test('không có API key: 401, không đụng gì tới job', async () => {
  const { job } = await makeKeyAndJob()

  const res = await app.inject({
    method: 'POST', url: `/api/v1/dub/${job._id}/cancel`,
  })
  assert.equal(res.statusCode, 401)
  assert.equal((await DubApiJob.findById(job._id).lean()).status, 'queued')
})
