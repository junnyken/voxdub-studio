'use strict'

/**
 * Mini-spec V34a (docs/PLAN.md, Phase G) — `/api/v1/dub*` qua HTTP thật
 * (fastify.inject, kể cả multipart upload thật — tự dựng body multipart
 * tối thiểu vì repo chưa có dependency `form-data`). Worker Python KHÔNG
 * chạy thật ở đây (không cần Docker/mạng) — mô phỏng bằng cách gọi thẳng
 * `dub-job.service.js` (claim/complete), giống cách
 * `render-job.integration.test.js` mô phỏng render_worker.py.
 *
 * Xác nhận riêng cho V34a: auth tách biệt API key/device/worker, KHÔNG
 * billing thật (Constraint 1 — usageCount/quota không đổi qua toàn luồng).
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

function postDub(key, { sourceLang = 'en-US', targetLang = 'vi', voice, buffer } = {}) {
  const qs = new URLSearchParams({ sourceLang, targetLang, ...(voice ? { voice } : {}) }).toString()
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
  const { plaintext } = await createApiKey({ orgName: 'Test' })
  const mp = buildMultipart('video.mp4', 'video/mp4', Buffer.from('fake-mp4'))
  const res = await app.inject({
    method: 'POST', url: '/api/v1/dub',
    headers: { authorization: `Bearer ${plaintext}`, 'content-type': mp.contentType },
    payload: mp.body,
  })
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'MISSING_LANG')
})

test('POST /dub: multipart hợp lệ nhưng không có file part -> 400 NO_FILE', async () => {
  const { plaintext } = await createApiKey({ orgName: 'Test' })
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

test('POST /dub: hợp lệ -> 200, queued, async:true, KHÔNG đụng usageCount/quota', async () => {
  const { plaintext, doc } = await createApiKey({ orgName: 'Test', quota: 100 })
  const res = await postDub(plaintext, { voice: 'Minh Trang' })
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(body.status, 'queued')
  assert.equal(body.async, true)
  assert.ok(body.jobId)
  assert.ok(typeof body.estimatedCostVox === 'number')

  const fresh = await ApiKey.findById(doc._id).lean()
  assert.equal(fresh.usageCount, 0, 'V34a Constraint 1: không billing thật')
  assert.equal(fresh.quota, 100)
})

test('GET /dub/:jobId: job của API key khác -> 404 (không lộ job giữa các org)', async () => {
  const { plaintext: keyA } = await createApiKey({ orgName: 'Org A' })
  const { plaintext: keyB } = await createApiKey({ orgName: 'Org B' })
  const submitRes = await postDub(keyA)
  const { jobId } = submitRes.json()

  const res = await app.inject({
    method: 'GET', url: `/api/v1/dub/${jobId}`,
    headers: { authorization: `Bearer ${keyB}` },
  })
  assert.equal(res.statusCode, 404)
})

test('luồng đầy đủ: submit -> worker giả claim/complete -> poll done -> tải video -> xoá file', async () => {
  const { plaintext } = await createApiKey({ orgName: 'Test' })
  const submitRes = await postDub(plaintext)
  const { jobId } = submitRes.json()

  // Worker giả lập (thay cho dub_worker.py thật — xem module docstring).
  const claimed = await dubJobService.claimNextJob('test-worker')
  assert.equal(String(claimed._id), String(jobId))
  const paths = dubJobService.jobPaths(jobId)
  fs.writeFileSync(paths.output, 'fake-dubbed-video-bytes')
  await dubJobService.completeJob(jobId, 'test-worker', {
    outputPath: paths.output,
    metrics: { inputBytes: 8, outputBytes: 24, processingMs: 999 },
  })

  const pollRes = await app.inject({
    method: 'GET', url: `/api/v1/dub/${jobId}`,
    headers: { authorization: `Bearer ${plaintext}` },
  })
  assert.equal(pollRes.statusCode, 200)
  const pollBody = pollRes.json()
  assert.equal(pollBody.status, 'done')
  assert.equal(pollBody.metrics.processingMs, 999)

  const downloadRes = await app.inject({
    method: 'GET', url: `/api/v1/dub/${jobId}/result`,
    headers: { authorization: `Bearer ${plaintext}` },
  })
  assert.equal(downloadRes.statusCode, 200)
  assert.equal(downloadRes.body, 'fake-dubbed-video-bytes')
  assert.equal(downloadRes.headers['content-type'], 'video/mp4')

  await new Promise((r) => setTimeout(r, 50))   // stream 'close' handler xoá file bất đồng bộ
  assert.ok(!fs.existsSync(paths.output), 'file phải bị xoá ngay sau khi tải (chính sách dữ liệu V9)')
})

test('GET /dub/:jobId/result: chưa xong -> 409 NOT_READY', async () => {
  const { plaintext } = await createApiKey({ orgName: 'Test' })
  const submitRes = await postDub(plaintext)
  const { jobId } = submitRes.json()

  const res = await app.inject({
    method: 'GET', url: `/api/v1/dub/${jobId}/result`,
    headers: { authorization: `Bearer ${plaintext}` },
  })
  assert.equal(res.statusCode, 409)
  assert.equal(res.json().code, 'NOT_READY')
})
