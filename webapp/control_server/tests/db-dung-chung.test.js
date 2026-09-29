'use strict'

/**
 * Bộ canh cho chính cách bộ test lấy cơ sở dữ liệu (21-08).
 *
 * Lỗi được sửa: mỗi tệp test dựng một `mongod` riêng, `node --test` chạy 12
 * tệp song song nên trên máy bận thì đỏ hàng loạt (đo thật: 2 lượt song song
 * = 55 và 81 đỏ, cùng mã nguồn mà chạy đơn độc 0 đỏ). Sửa xong rồi thì phải
 * có thứ giữ, vì lần tới chỉ cần ai đó đổi `npm test` về `node --test` trần
 * là quay lại y như cũ mà **không có dấu hiệu nào** — bộ test vẫn xanh trên
 * máy rảnh.
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const { MongoClient } = require('mongodb')
const mongoose = require('mongoose')
const { MongoMemoryServer } = require('mongodb-memory-server')

const { startDb, stopDb, tenDbTest } = require('./helpers/db')
const { ma, demGoi } = require('./helpers/doc-ma')

const GOC = path.join(__dirname, '..')

/**
 * Địa chỉ máy chủ chung: dùng lại của `tests/chay.js` nếu đang chạy dưới nó,
 * còn chạy lẻ thì tự dựng ĐÚNG MỘT cái.
 *
 * Phải nhớ lại (`hua`) chứ không gọi lại: bản đầu của chính tệp này gọi hàm
 * hai lần, lần hai dựng thêm một `mongod` và **ghi đè biến giữ cái thứ nhất**
 * — cái thứ nhất thành mồ côi, tiến trình không bao giờ thoát và bộ test treo
 * cứng. Đúng lớp rò rỉ mà cả mini-spec này sinh ra để dọn.
 */
let rieng = null
let hua = null
function uriChung() {
  if (process.env.TEST_MONGO_URI) return Promise.resolve(process.env.TEST_MONGO_URI)
  if (!hua) {
    hua = MongoMemoryServer.create().then((may) => {
      rieng = may
      return may.getUri()
    })
  }
  return hua
}

test.after(async () => {
  if (rieng) await rieng.stop()
})

test('npm test đi qua tests/chay.js, không phải `node --test` trần', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(GOC, 'package.json'), 'utf8'))
  assert.match(pkg.scripts.test, /tests\/chay\.js/)
  assert.ok(
    !pkg.scripts.test.includes('--test'),
    'gọi thẳng `node --test` là mỗi tệp lại tự dựng một mongod',
  )
})

test('chay.js dựng đúng MỘT mongod cho cả suite', () => {
  assert.strictEqual(demGoi(ma('tests/chay.js'), 'MongoMemoryServer.create'), 1)
})

test('startDb dùng máy chủ chung khi có TEST_MONGO_URI', async () => {
  const uri = await uriChung()
  const cu = process.env.TEST_MONGO_URI
  process.env.TEST_MONGO_URI = uri
  try {
    await startDb()
    const cong = Number(new URL(uri).port)
    assert.strictEqual(mongoose.connection.port, cong, 'phải nối vào máy chủ chung')
    assert.match(mongoose.connection.name, /^voxdub_test_/, 'mỗi tiến trình một database riêng')
    await stopDb()
  } finally {
    if (cu === undefined) delete process.env.TEST_MONGO_URI
    else process.env.TEST_MONGO_URI = cu
  }
})

test('stopDb KHÔNG tắt máy chủ chung — tệp khác còn đang chạy', async () => {
  const uri = await uriChung()
  const cu = process.env.TEST_MONGO_URI
  process.env.TEST_MONGO_URI = uri
  try {
    await startDb()
    await stopDb()
    // Bằng chứng thật: nối lại được và ping được sau khi một tệp đã stopDb.
    const khach = new MongoClient(uri, { serverSelectionTimeoutMS: 5000 })
    await khach.connect()
    const ra = await khach.db('admin').command({ ping: 1 })
    await khach.close()
    assert.strictEqual(ra.ok, 1)
  } finally {
    if (cu === undefined) delete process.env.TEST_MONGO_URI
    else process.env.TEST_MONGO_URI = cu
  }
})

test('chạy lẻ một tệp (không có TEST_MONGO_URI) vẫn tự dựng được mongod', async () => {
  const cu = process.env.TEST_MONGO_URI
  delete process.env.TEST_MONGO_URI
  try {
    await startDb()
    assert.strictEqual(mongoose.connection.readyState, 1, 'phải nối được dù không có máy chủ chung')
    await stopDb()
  } finally {
    if (cu !== undefined) process.env.TEST_MONGO_URI = cu
  }
})

test('mỗi tiến trình một tên database riêng, pid cấp lại cũng không đụng', () => {
  assert.notStrictEqual(tenDbTest(), tenDbTest())
})
