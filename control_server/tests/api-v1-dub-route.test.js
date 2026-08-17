'use strict'

/**
 * Mini-spec V34a→V34b (docs/PLAN.md, Phase G) — `/api/v1/dub*` qua HTTP
 * thật (fastify.inject, kể cả multipart upload thật — tự dựng body
 * multipart tối thiểu vì repo chưa có dependency `form-data`). Worker
 * Python KHÔNG chạy thật ở đây (không cần Docker/mạng) — mô phỏng bằng
 * cách gọi thẳng `dub-job.service.js` (claim/complete), giống cách
 * `render-job.integration.test.js` mô phỏng render_worker.py.
 *
 * V34b: `dubMinutesQuota` mặc định 0 (opt-in) — `makeDubApiKey()` dưới
 * đây cấp sẵn quota để các test không phải tự lo billing, trừ test CHỦ
 * ĐÍCH kiểm quota (đặt tên rõ). Xác nhận riêng: auth tách biệt API key/
 * device/worker; billing THẬT tính sau khi job xong, KHÔNG đụng
 * `quota`/`usageCount` của V31 (Constraint 2 của V34b).
 *
 * Chạy:  node --test tests/api-v1-dub-route.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

process.env.DUB_UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'voxdub-api-v1-dub-test-'))

const { build } = require('../src/app')
const ApiKey = require('../src/models/ApiKey')
const { createApiKey } = require('../src/services/api-key.service')
const dubJobService = require('../src/services/dub-job.service')
const storage = require('../src/services/job-storage.service')
const config = require('../src/services/config.service')

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

function makeDubApiKey(opts = {}) {
  return createApiKey({ orgName: 'Test', dubMinutesQuota: 100, ...opts })
}

/** Dựng body multipart/form-data tối thiểu cho 1 file — @fastify/multipart
 * lấy part ĐẦU TIÊN có filename, không quan tâm tên field. */
function buildMultipart(filename, contentType, buffer) {
  const boundary = `----voxdubtest${Date.now()}`
  const head = Buffer.from(
    `--${boundary}\r\n`
    + `Content-Disposition: form-data; name="file"; filename="${filename}"\r\n`
    + `Content-Type: ${contentType}\r\n\r\n`,
  )
  const tail = Buffer.from(`\r\n--${boundary}--\r\n`)
  return {
    body: Buffer.concat([head, buffer, tail]),
    contentType: `multipart/form-data; boundary=${boundary}`,
  }
}

function postDub(key, { sourceLang = 'en-US', targetLang = 'vi', voice, bgMode, buffer } = {}) {
  const qs = new URLSearchParams({
    sourceLang, targetLang, ...(voice ? { voice } : {}), ...(bgMode ? { bgMode } : {}),
  }).toString()
  const mp = buildMultipart('video.mp4', 'video/mp4', buffer || Buffer.from('fake-mp4'))
  return app.inject({
    method: 'POST',
    url: `/api/v1/dub?${qs}`,
    headers: key ? { authorization: `Bearer ${key}`, 'content-type': mp.contentType } : { 'content-type': mp.contentType },
    payload: mp.body,
  })
}

test('POST /dub: thiếu API key -> 401 NO_API_KEY', async () => {
  const res = await postDub(null)
  assert.equal(res.statusCode, 401)
  assert.equal(res.json().code, 'NO_API_KEY')
})

test('POST /dub: thiếu sourceLang/targetLang -> 400 MISSING_LANG', async () => {
  const { plaintext } = await makeDubApiKey()
  const mp = buildMultipart('video.mp4', 'video/mp4', Buffer.from('fake-mp4'))
  const res = await app.inject({
    method: 'POST', url: '/api/v1/dub',
    headers: { authorization: `Bearer ${plaintext}`, 'content-type': mp.contentType },
    payload: mp.body,
  })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'MISSING_LANG')
})

test('POST /dub: bgMode không hợp lệ -> 400 BAD_BG_MODE', async () => {
  const { plaintext } = await makeDubApiKey()
  const res = await postDub(plaintext, { bgMode: 'reverb' })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'BAD_BG_MODE')
})

test('POST /dub: multipart hợp lệ nhưng không có file part -> 400 NO_FILE', async () => {
  const { plaintext } = await makeDubApiKey()
  const boundary = '----voxdubtestempty'
  const res = await app.inject({
    method: 'POST', url: '/api/v1/dub?sourceLang=en-US&targetLang=vi',
    headers: {
      authorization: `Bearer ${plaintext}`,
      'content-type': `multipart/form-data; boundary=${boundary}`,
    },
    payload: Buffer.from(`--${boundary}--\r\n`),
  })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'NO_FILE')
})

test('POST /dub: hết quota phút dub (mặc định 0) -> 402 DUB_QUOTA_EXCEEDED', async () => {
  const { plaintext } = await createApiKey({ orgName: 'No Quota' })
  const res = await postDub(plaintext)
  assert.equal(res.statusCode, 402)
  assert.equal(res.json().code, 'DUB_QUOTA_EXCEEDED')
})

test('POST /dub: hợp lệ -> 200, queued, async:true, bgMode mặc định "none", KHÔNG đụng quota/usageCount V31', async () => {
  const { plaintext, doc } = await createApiKey({ orgName: 'Test', quota: 100, dubMinutesQuota: 100 })
  const res = await postDub(plaintext, { voice: 'Minh Trang' })
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(body.status, 'queued')
  assert.equal(body.async, true)
  assert.equal(body.bgMode, 'none')
  assert.ok(body.jobId)
  assert.ok(typeof body.estimatedCostVoxPerMinute === 'number')

  const fresh = await ApiKey.findById(doc._id).lean()
  assert.equal(fresh.usageCount, 0, 'quota/usageCount của V31 không liên quan tới dub')
  assert.equal(fresh.quota, 100)
  assert.equal(fresh.dubMinutesUsed, 0, 'chưa xong job thì chưa trừ phút')
})

test('POST /dub: bgMode=demucs được ghi nhận đúng', async () => {
  const { plaintext } = await makeDubApiKey()
  const res = await postDub(plaintext, { bgMode: 'demucs' })
  assert.equal(res.statusCode, 200)
  assert.equal(res.json().bgMode, 'demucs')
})

test('GET /dub/:jobId: job của API key khác -> 404 (không lộ job giữa các org)', async () => {
  const { plaintext: keyA } = await makeDubApiKey()
  const { plaintext: keyB } = await makeDubApiKey()
  const submitRes = await postDub(keyA)
  const { jobId } = submitRes.json()

  const res = await app.inject({
    method: 'GET', url: `/api/v1/dub/${jobId}`,
    headers: { authorization: `Bearer ${keyB}` },
  })
  assert.equal(res.statusCode, 404)
})

test('GET /me: hiện đúng dubMinutesQuota/dubMinutesUsed/dubMinutesRemaining', async () => {
  const { plaintext } = await makeDubApiKey({ dubMinutesQuota: 50 })
  const res = await app.inject({
    method: 'GET', url: '/api/v1/me',
    headers: { authorization: `Bearer ${plaintext}` },
  })
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(body.dubMinutesQuota, 50)
  assert.equal(body.dubMinutesUsed, 0)
  assert.equal(body.dubMinutesRemaining, 50)
})

test('luồng đầy đủ: submit -> worker giả claim/complete (kèm durationS thật) -> poll done -> tải video -> xoá file -> trừ đúng phút', async () => {
  const { plaintext, doc } = await makeDubApiKey()
  const submitRes = await postDub(plaintext)
  const { jobId } = submitRes.json()

  // Worker giả lập (thay cho dub_worker.py thật — xem module docstring).
  const claimed = await dubJobService.claimNextJob('test-worker')
  assert.equal(String(claimed._id), String(jobId))
  await putOutput(jobId, 'fake-dubbed-video-bytes')
  await dubJobService.completeJob(jobId, 'test-worker', {
    outputPath: storage.outputKey(String(jobId)),
    metrics: { inputBytes: 8, outputBytes: 24, processingMs: 999, durationS: 90 },
  })

  const pollRes = await app.inject({
    method: 'GET', url: `/api/v1/dub/${jobId}`,
    headers: { authorization: `Bearer ${plaintext}` },
  })
  assert.equal(pollRes.statusCode, 200)
  const pollBody = pollRes.json()
  assert.equal(pollBody.status, 'done')
  assert.equal(pollBody.metrics.processingMs, 999)
  const perMinute = await config.get('credit.cost.cloud.dub.vox.per.minute')
  assert.equal(pollBody.costVox, 2 * perMinute, '90s -> làm tròn lên 2 phút')

  const downloadRes = await app.inject({
    method: 'GET', url: `/api/v1/dub/${jobId}/result`,
    headers: { authorization: `Bearer ${plaintext}` },
  })
  assert.equal(downloadRes.statusCode, 200)
  assert.equal(downloadRes.body, 'fake-dubbed-video-bytes')
  assert.equal(downloadRes.headers['content-type'], 'video/mp4')

  // Dọn file chạy bất đồng bộ sau khi stream đóng — chờ tới lúc dọn xong
  // thay vì ngủ một khoảng cố định (GridFS cần vài lượt round-trip DB nên
  // 50ms cứng là nguồn flake).
  const key = storage.outputKey(String(jobId))
  for (let i = 0; i < 100; i += 1) {
    if (!(await storage.exists(key))) break
    await new Promise((r) => setTimeout(r, 20))
  }
  assert.equal(await storage.exists(key), false,
    'file phải bị xoá ngay sau khi tải (chính sách dữ liệu V9)')

  const fresh = await ApiKey.findById(doc._id).lean()
  assert.equal(fresh.dubMinutesUsed, 2)
})

test('GET /dub/:jobId/result: chưa xong -> 409 NOT_READY', async () => {
  const { plaintext } = await makeDubApiKey()
  const submitRes = await postDub(plaintext)
  const { jobId } = submitRes.json()

  const res = await app.inject({
    method: 'GET', url: `/api/v1/dub/${jobId}/result`,
    headers: { authorization: `Bearer ${plaintext}` },
  })
  assert.equal(res.statusCode, 409)
  assert.equal(res.json().code, 'NOT_READY')
})
