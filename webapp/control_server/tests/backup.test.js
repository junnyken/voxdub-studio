'use strict'

/**
 * Mini-spec V48 — sao lưu/khôi phục MongoDB không phụ thuộc nền tảng.
 *
 * Điều đáng test KHÔNG phải "endpoint có trả về gì đó không" mà là **khôi
 * phục xong có ra đúng dữ liệu cũ không**: một bản sao lưu không restore
 * được thì tệ hơn không có, vì nó tạo cảm giác an toàn giả. Vòng test chính
 * ở đây là xuất → xoá sạch → nhập lại → đối chiếu từng field, bao gồm kiểu
 * `ObjectId`/`Date` (JSON thường sẽ làm hỏng đúng 2 kiểu này).
 *
 * Chạy:  node --test tests/backup.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const zlib = require('node:zlib')
const readline = require('node:readline')
const { Readable } = require('node:stream')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const mongoose = require('mongoose')
const { build } = require('../src/app')
const Device = require('../src/models/Device')
const ApiKey = require('../src/models/ApiKey')
const backup = require('../src/services/backup.service')

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

async function seed() {
  const device = await Device.create({
    fingerprint: 'f'.repeat(64), name: 'máy thật', balance: 1234, status: 'active',
  })
  const key = await ApiKey.create({
    keyHash: 'h'.repeat(64), keyPrefix: 'vx_live_', orgName: 'Khách A',
    quota: 500, dubMinutesQuota: 60,
  })
  return { device, key }
}

function fetchBackup() {
  return app.inject({
    method: 'GET', url: '/v1/admin/backup', headers: { 'x-admin-token': 'test-admin-token' },
  })
}

/** Giải nén + tách dòng bản dump trả về từ endpoint. */
function parseDump(rawBody) {
  const text = zlib.gunzipSync(rawBody).toString('utf8')
  return text.split('\n').filter(Boolean)
}

/** Dump lấy THẲNG từ service, không qua HTTP.
 *
 * Route `/v1/admin/backup` bị rate limit 3 lượt/phút CÓ CHỦ ĐÍCH (endpoint
 * đọc toàn bộ dữ liệu). Các test vòng tròn dưới đây quan tâm tới đúng cái
 * generator mà route stream ra, nên gọi thẳng service thay vì đốt hạn mức —
 * lần đầu viết test đã dính đúng bẫy này: lượt gọi thứ 4 trả JSON 429 và
 * gunzip báo "incorrect header check", trông như lỗi nén. */
async function dumpFromService() {
  const chunks = []
  for await (const line of backup.exportLines()) chunks.push(line)
  return Buffer.from(chunks.join(''))
}

test('không có admin token -> 401, không lộ một byte dữ liệu nào', async () => {
  await seed()
  const res = await app.inject({ method: 'GET', url: '/v1/admin/backup' })
  assert.equal(res.statusCode, 401)
  assert.ok(!res.body.includes('Khách A'), 'response lỗi không được chứa dữ liệu')
})

test('xuất: có dòng siêu dữ liệu + đủ bản ghi của mọi collection', async () => {
  await seed()
  const res = await fetchBackup()
  assert.equal(res.statusCode, 200)
  assert.equal(res.headers['content-type'], 'application/gzip')
  assert.match(res.headers['content-disposition'], /voxdub-backup-.*\.ndjson\.gz/)

  const lines = parseDump(res.rawPayload)
  const meta = JSON.parse(lines[0]).__meta
  assert.equal(meta.version, 1)
  assert.ok(meta.collections.includes('devices'), 'phải liệt kê collection devices')
  assert.ok(meta.collections.includes('apikeys'), 'phải liệt kê collection apikeys')

  const bodies = lines.slice(1).map((l) => JSON.parse(l))
  assert.equal(bodies.filter((b) => b.__collection === 'devices').length, 1)
  assert.equal(bodies.filter((b) => b.__collection === 'apikeys').length, 1)
})

test('vòng tròn xuất -> XOÁ SẠCH -> nhập lại: dữ liệu khớp từng field, giữ đúng kiểu', async () => {
  const { device } = await seed()
  const dump = await dumpFromService()

  // Xoá sạch như thể vừa mất database (đúng thứ đã xảy ra thật 2026-08-17).
  await clearDb()
  assert.equal(await Device.countDocuments({}), 0)
  assert.equal(await ApiKey.countDocuments({}), 0)

  const lines = readline.createInterface({ input: Readable.from(dump), crlfDelay: Infinity })
  const stats = await backup.importLines(lines, { mode: 'wipe' })

  assert.equal(stats.counts.devices, 1)
  assert.equal(stats.counts.apikeys, 1)
  assert.ok(stats.total >= 2, `phải nhập lại ít nhất 2 bản ghi, nhận ${stats.total}`)

  const restored = await Device.findOne({ fingerprint: 'f'.repeat(64) }).lean()
  assert.ok(restored, 'thiết bị phải sống lại')
  assert.equal(restored.balance, 1234, 'số dư ví phải nguyên vẹn — đây là tiền thật của khách')
  assert.equal(restored.name, 'máy thật', 'chuỗi tiếng Việt có dấu không được hỏng')

  // 2 kiểu mà JSON thường sẽ phá: ObjectId biến thành chuỗi, Date thành chuỗi.
  assert.ok(restored._id instanceof mongoose.Types.ObjectId, '_id phải còn là ObjectId')
  assert.equal(String(restored._id), String(device._id), '_id phải khớp bản gốc')
  assert.ok(restored.firstSeenAt instanceof Date, 'trường thời gian phải còn là Date')
})

test('nhập chế độ mặc định (upsert): ghi đè bản ghi trùng _id, KHÔNG xoá bản ghi lạ', async () => {
  const { device } = await seed()
  const dump = await dumpFromService()

  // Sau khi sao lưu: ví bị sửa sai, và có thêm 1 thiết bị mới hoàn toàn.
  await Device.updateOne({ _id: device._id }, { $set: { balance: 0 } })
  await Device.create({ fingerprint: 'c'.repeat(64), name: 'máy mới', balance: 77, status: 'active' })

  const lines = readline.createInterface({ input: Readable.from(dump), crlfDelay: Infinity })
  await backup.importLines(lines)

  const restored = await Device.findById(device._id).lean()
  assert.equal(restored.balance, 1234, 'bản ghi trùng _id phải được khôi phục về giá trị đã sao lưu')
  const survivor = await Device.findOne({ fingerprint: 'c'.repeat(64) }).lean()
  assert.ok(survivor, 'chế độ upsert KHÔNG được xoá bản ghi tạo sau bản sao lưu')
  assert.equal(survivor.balance, 77)
})

test('nhập lại 2 lần liên tiếp: kết quả không nhân đôi (idempotent theo _id)', async () => {
  await seed()
  const dump = await dumpFromService()

  for (let i = 0; i < 2; i += 1) {
    const lines = readline.createInterface({ input: Readable.from(dump), crlfDelay: Infinity })
    // eslint-disable-next-line no-await-in-loop
    await backup.importLines(lines)
  }

  assert.equal(await Device.countDocuments({}), 1)
  assert.equal(await ApiKey.countDocuments({}), 1)
})
