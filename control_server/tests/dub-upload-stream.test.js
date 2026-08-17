'use strict'

/**
 * Mini-spec V44 (docs/PLAN.md, Phase G) — nhận video upload THEO DÒNG thay
 * vì nuốt trọn vào RAM.
 *
 * Bối cảnh thật: `cloud.dub.max.upload.mb` mặc định 300, container chạy
 * prod (`voxdub-app` trên Vibe Host) chỉ có 1 GB RAM, rate limit cho phép 5
 * request/phút/key. Bản trước V44 gọi `data.toBuffer()` → 2 upload lớn
 * đồng thời đủ để OOM cả tiến trình, kéo theo mọi job đang chạy.
 *
 * Nhóm test "đường hỏng" quan trọng ngang đường thành công: hỏng giữa
 * chừng mà không dọn thì để lại file CỤT trên đĩa (không document nào trỏ
 * tới → sweeper không bao giờ thấy) và/hoặc giữ chỗ quota vĩnh viễn.
 *
 * Chạy:  node --test tests/dub-upload-stream.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'voxdub-upload-stream-test-'))
process.env.DUB_UPLOAD_DIR = UPLOAD_DIR

const { build } = require('../src/app')
const ApiKey = require('../src/models/ApiKey')
const DubApiJob = require('../src/models/DubApiJob')
const config = require('../src/services/config.service')
const { createApiKey } = require('../src/services/api-key.service')
const storage = require('../src/services/job-storage.service')

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
test.beforeEach(async () => {
  await clearDb()
  config.invalidate()
  // Dọn đĩa giữa các test — nếu không, thư mục job của test TRƯỚC sẽ bị các
  // assert "không để lại file cụt" ở dưới tính nhầm là rác của chính nó.
  fs.rmSync(UPLOAD_DIR, { recursive: true, force: true })
  fs.mkdirSync(UPLOAD_DIR, { recursive: true })
})

async function makeKey(dubMinutesQuota = 100) {
  const { plaintext } = await createApiKey({
    orgName: 'Test V44', contactEmail: '', quota: 100, dubMinutesQuota,
  })
  return plaintext
}

/** Dựng body multipart thật (không dùng thư viện) để đi qua đúng đường
 * `@fastify/multipart` mà route dùng ở prod. */
function multipart(bytes) {
  const boundary = '----voxdubV44test'
  const head = Buffer.from(
    `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="v.mp4"\r\n`
    + 'Content-Type: video/mp4\r\n\r\n',
  )
  const tail = Buffer.from(`\r\n--${boundary}--\r\n`)
  return {
    payload: Buffer.concat([head, bytes, tail]),
    headers: { 'content-type': `multipart/form-data; boundary=${boundary}` },
  }
}

function submit(apiKey, bytes, query = 'sourceLang=en-US&targetLang=vi') {
  const { payload, headers } = multipart(bytes)
  return app.inject({
    method: 'POST',
    url: `/api/v1/dub?${query}`,
    headers: { ...headers, authorization: `Bearer ${apiKey}` },
    payload,
  })
}

/** Thư mục job còn sót lại trên đĩa (kể cả rỗng) — dùng để bắt file cụt. */
function leftoverDirs() {
  return fs.readdirSync(UPLOAD_DIR, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
}

test('upload bình thường: file xuống đĩa ĐỦ byte, job vào hàng đợi', async () => {
  const apiKey = await makeKey(100)
  // 3 MB — đủ lớn để chắc chắn đi qua nhiều chunk stream, không phải 1 lần ghi.
  const bytes = Buffer.alloc(3 * 1024 * 1024, 7)

  const res = await submit(apiKey, bytes)
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(body.status, 'queued')

  const job = await DubApiJob.findById(body.jobId).lean()
  assert.ok(job, 'job phải tồn tại trong DB')
  // V45: file nằm trong GridFS, không phải đĩa container.
  assert.equal(await storage.size(job.inputPath), bytes.length,
    'số byte trong kho phải khớp CHÍNH XÁC file gửi lên')
  const chunks = []
  for await (const c of await storage.openRead(job.inputPath)) chunks.push(c)
  assert.ok(Buffer.concat(chunks).equals(bytes), 'nội dung phải nguyên vẹn')
})

test('vượt hạn mức: 413 UPLOAD_TOO_LARGE, không để lại file cụt, không tạo job', async () => {
  const apiKey = await makeKey(100)
  await config.set('cloud.dub.max.upload.mb', 1)
  config.invalidate()

  const res = await submit(apiKey, Buffer.alloc(3 * 1024 * 1024, 7))
  assert.equal(res.statusCode, 413)
  assert.equal(res.json().code, 'UPLOAD_TOO_LARGE')

  assert.equal(await DubApiJob.countDocuments({}), 0, 'không được tạo job cho upload hỏng')
  // V45: chỗ có thể sót bản cụt giờ là GridFS, không phải đĩa — kiểm cả hai.
  const orphans = await storage.listAll()
  assert.deepEqual(orphans, [], `còn file cụt trong kho: ${orphans.join(',')}`)
  for (const dir of leftoverDirs()) {
    const files = fs.readdirSync(path.join(UPLOAD_DIR, dir))
    assert.deepEqual(files, [], `còn file cụt sót lại trên đĩa trong ${dir}: ${files.join(',')}`)
  }
})

test('vượt hạn mức: quota giữ chỗ được TRẢ LẠI, không kẹt vĩnh viễn', async () => {
  const apiKey = await makeKey(100)
  await config.set('cloud.dub.max.upload.mb', 1)
  config.invalidate()

  const res = await submit(apiKey, Buffer.alloc(3 * 1024 * 1024, 7))
  assert.equal(res.statusCode, 413)

  const key = await ApiKey.findOne({ orgName: 'Test V44' }).lean()
  assert.equal(key.dubMinutesReserved, 0, 'giữ chỗ phải được giải phóng khi upload hỏng')
  assert.equal(key.dubMinutesUsed, 0, 'upload hỏng KHÔNG được tính tiền')
})

test('file rỗng: 400 EMPTY_FILE, trả lại quota, không tạo job', async () => {
  const apiKey = await makeKey(100)

  const res = await submit(apiKey, Buffer.alloc(0))
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'EMPTY_FILE')

  assert.equal(await DubApiJob.countDocuments({}), 0)
  const key = await ApiKey.findOne({ orgName: 'Test V44' }).lean()
  assert.equal(key.dubMinutesReserved, 0)
})

// --- `POST /v1/jobs/demucs` — CÙNG bug, đường của app desktop ------------
// Route này giới hạn 200 MB và cũng `toBuffer()` trước V44. Khác `/api/v1/dub`
// ở chỗ nó TRỪ CREDIT: bản cũ trừ tiền TRƯỚC khi ghi file, an toàn chỉ nhờ
// việc route đã chặn file quá cỡ từ trước; ghi theo dòng thì thứ tự đó thành
// bẫy mất tiền, nên V44 đảo lại (ghi file xong mới trừ).

async function makeDevice(balance = 1000) {
  const Device = require('../src/models/Device')
  const fingerprint = 'e'.repeat(64)
  await Device.create({ fingerprint, balance, status: 'active' })
  const res = await app.inject({
    method: 'POST', url: '/v1/device/register',
    payload: { fingerprint, name: 'v44-test', appVersion: '3.1.0' },
  })
  await Device.updateOne({ fingerprint }, { $set: { balance } })
  return { token: res.json().token, fingerprint }
}

test('demucs: upload vượt 200 MB -> 413, KHÔNG trừ credit, không tạo job', async (t) => {
  const RenderJob = require('../src/models/RenderJob')
  const Device = require('../src/models/Device')
  const { token, fingerprint } = await makeDevice(1000)

  // 201 MB toàn số 0 — nén không giúp gì vì đi thẳng qua HTTP dạng thô.
  const { payload, headers } = multipart(Buffer.alloc(201 * 1024 * 1024))
  const res = await app.inject({
    method: 'POST',
    url: '/v1/jobs/demucs',
    headers: { ...headers, authorization: `Bearer ${token}` },
    payload,
  })

  assert.equal(res.statusCode, 413)
  assert.equal(res.json().code, 'UPLOAD_TOO_LARGE')
  assert.equal(await RenderJob.countDocuments({}), 0)
  const device = await Device.findOne({ fingerprint }).lean()
  assert.equal(device.balance, 1000, 'upload hỏng KHÔNG được trừ Vox của khách')
  t.diagnostic(`balance giữ nguyên ${device.balance}`)
})

test('regression: mã ngôn ngữ sai vẫn bị chặn TRƯỚC khi đọc file (V44 không phá V43/93c6878)', async () => {
  const apiKey = await makeKey(100)

  const res = await submit(apiKey, Buffer.alloc(1024, 1), 'sourceLang=en-US&targetLang=vi-VN')
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'BAD_TARGET_LANG')

  const key = await ApiKey.findOne({ orgName: 'Test V44' }).lean()
  assert.equal(key.dubMinutesReserved, 0, 'chặn sớm thì không được giữ chỗ quota nào')
  assert.deepEqual(leftoverDirs(), [], 'chặn sớm thì không được tạo thư mục job nào')
})
