'use strict'

/**
 * Mini-spec V50 — nhìn được dung lượng kho file job.
 *
 * Từ V45 video nằm TRONG database (GridFS). Bền vững qua redeploy, nhưng đổi
 * lại DB phình theo lượng job — và không có chỗ nào nhìn thì chỉ phát hiện
 * đúng lúc hết dung lượng. Con số đáng theo dõi nhất KHÔNG phải tổng dung
 * lượng mà là `orphanFiles`: file không còn job nào trỏ tới = sweeper sót
 * việc.
 *
 * Chạy:  node --test tests/storage-stats.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const { Readable } = require('node:stream')
const { pipeline } = require('node:stream/promises')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const DubApiJob = require('../src/models/DubApiJob')
const ApiKey = require('../src/models/ApiKey')
const config = require('../src/services/config.service')
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
})
test.beforeEach(async () => { await clearDb(); config.invalidate() })

async function put(key, bytes) {
  await pipeline(Readable.from([Buffer.alloc(bytes, 1)]), await storage.openWrite(key))
}

/** 1 job thật + file output của nó (tức file CÓ CHỦ). */
async function jobWithFile(bytes) {
  const key = await ApiKey.create({
    keyHash: `h${Math.random()}`, keyPrefix: 'p', orgName: 'T', dubMinutesQuota: 10,
  })
  const job = await DubApiJob.create({
    apiKeyId: key._id,
    status: 'done',
    sourceLang: 'en-US',
    targetLang: 'vi',
    inputPath: 'x',
    expiresAt: new Date(Date.now() + 3600_000),
  })
  await put(storage.outputKey(String(job._id)), bytes)
  return job
}

function getStorage() {
  return app.inject({
    method: 'GET', url: '/v1/admin/storage', headers: { 'x-admin-token': 'test-admin-token' },
  })
}

test('kho rỗng: mọi con số là 0, không nổ', async () => {
  const res = await getStorage()
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(body.files, 0)
  assert.equal(body.totalBytes, 0)
  assert.equal(body.orphanFiles, 0)
  assert.equal(body.orphanChunks, 0)
  assert.equal(body.overWarnThreshold, false)
})

test('đếm đúng số file và tổng byte', async () => {
  await jobWithFile(1024)
  await jobWithFile(2048)

  const body = (await getStorage()).json()
  assert.equal(body.files, 2)
  assert.equal(body.totalBytes, 3072)
  assert.ok(body.oldestUploadedAt, 'phải biết file cũ nhất từ bao giờ')
})

test('file KHÔNG còn job nào trỏ tới bị đếm là mồ côi', async () => {
  const job = await jobWithFile(1024)
  await put('dub/6a83000000000000deadbeef/output.mp4', 4096)   // job không tồn tại

  let body = (await getStorage()).json()
  assert.equal(body.files, 2)
  assert.equal(body.orphanFiles, 1, 'chỉ file không có chủ mới là mồ côi')
  assert.equal(body.orphanBytes, 4096)

  // Xoá job đi thì file của nó cũng thành mồ côi — đây chính là dấu hiệu
  // sweeper dọn job mà quên dọn file.
  await DubApiJob.deleteOne({ _id: job._id })
  body = (await getStorage()).json()
  assert.equal(body.orphanFiles, 2)
})

test('chunk không thuộc file nào được đếm riêng (rác vô hình với mọi cách dọn theo tên)', async () => {
  const mongoose = require('mongoose')
  await jobWithFile(1024)

  // Mô phỏng đúng thứ rò rỉ thật khi upload đứt: chunk còn, bản ghi file thì
  // không bao giờ được tạo.
  await mongoose.connection.db.collection('dubfiles.chunks').insertOne({
    files_id: new mongoose.Types.ObjectId(), n: 0, data: Buffer.alloc(16),
  })

  const body = (await getStorage()).json()
  assert.equal(body.orphanChunks, 1, 'phải thấy chunk mồ côi')
  assert.equal(body.orphanFiles, 0, 'chunk mồ côi KHÁC file mồ côi — không được lẫn')
})

test('ngưỡng cảnh báo đọc từ cấu hình', async () => {
  await jobWithFile(3 * 1024 * 1024)   // 3 MB

  await config.set('storage.warn.mb', 10)
  config.invalidate()
  assert.equal((await getStorage()).json().overWarnThreshold, false)

  await config.set('storage.warn.mb', 1)
  config.invalidate()
  const body = (await getStorage()).json()
  assert.equal(body.overWarnThreshold, true, '3 MB vượt ngưỡng 1 MB')
  assert.equal(body.warnMb, 1)
})

test('không có admin token -> 401', async () => {
  const res = await app.inject({ method: 'GET', url: '/v1/admin/storage' })
  assert.equal(res.statusCode, 401)
})
