'use strict'

/**
 * Mongo trong bộ nhớ cho integration test.
 *
 * **Vì sao có `TEST_MONGO_URI` (21-08).** Bản đầu dựng MỘT `MongoMemoryServer`
 * cho MỖI tệp test. `node --test` chạy song song theo số CPU (ở đây 12), mà
 * mỗi `mongod` chiếm vài trăm MB — nên trên máy đang bận, bộ test đỏ hàng
 * loạt ở đúng những tệp đụng cơ sở dữ liệu. Đo thật: chạy một lượt trên máy
 * rảnh = 0 đỏ; chạy hai lượt song song = **55 đỏ và 81 đỏ**, và số test tự
 * phình từ 472 lên 479/482 (hook teardown chết đẻ thêm mục). Một bộ test mà
 * xanh hay đỏ tuỳ máy đang rảnh hay bận thì lượt xanh là MAY, không phải bằng
 * chứng.
 *
 * Nay `tests/chay.js` dựng đúng một `mongod` cho cả suite và truyền địa chỉ
 * qua `TEST_MONGO_URI`. Mỗi tiến trình vẫn lấy **database riêng** nên cách ly
 * không đổi. Chạy lẻ một tệp (`node --test tests/foo.test.js`) thì không có
 * biến đó, hàm tự dựng instance riêng như cũ — không ai phải nhớ thêm bước.
 *
 * Set biến env BẮT BUỘC trước khi bất kỳ service nào được require (jwtSecret()
 * và utils/crypto đều throw ngay lúc gọi nếu thiếu) — gọi `setTestEnv()` ở
 * dòng đầu file test, trước mọi `require('../src/...')`.
 */
const { randomUUID } = require('node:crypto')
const { MongoMemoryServer } = require('mongodb-memory-server')
const mongoose = require('mongoose')

let mongod = null

function setTestEnv() {
  process.env.JWT_SECRET ||= 'test-jwt-secret-at-least-32-characters-long'
  process.env.APP_ENCRYPTION_KEY ||= '1'.repeat(64)
  process.env.ADMIN_TOKEN ||= 'test-admin-token'
  process.env.WORKER_INTERNAL_TOKEN ||= 'test-worker-token'
  process.env.PAYOS_CLIENT_ID ||= 'test-client'
  process.env.PAYOS_API_KEY ||= 'test-api-key'
  process.env.PAYOS_CHECKSUM_KEY ||= 'test-checksum-key-0123456789abcdef'
  process.env.PUBLIC_URL ||= 'http://localhost:3001'
}

/**
 * Tên database riêng cho tiến trình này.
 *
 * Không dùng pid trần: hệ điều hành CẤP LẠI pid sau khi tiến trình chết, nên
 * một tệp chết giữa chừng (không kịp `stopDb`) có thể để lại rác cho tệp sau
 * trùng pid. Thêm phần ngẫu nhiên là hết cửa đó.
 */
function tenDbTest() {
  return `voxdub_test_${process.pid}_${randomUUID().replace(/-/g, '').slice(0, 8)}`
}

async function startDb() {
  mongoose.set('bufferCommands', true)
  mongoose.set('strictQuery', true)
  const uriChung = process.env.TEST_MONGO_URI
  if (uriChung) {
    await mongoose.connect(uriChung, { dbName: tenDbTest() })
    return
  }
  mongod = await MongoMemoryServer.create()
  await mongoose.connect(mongod.getUri(), { dbName: tenDbTest() })
}

async function stopDb() {
  await mongoose.connection.dropDatabase()
  await mongoose.connection.close()
  // Chỉ tắt thứ CHÍNH MÌNH dựng. `mongod` dùng chung là của `tests/chay.js`;
  // tệp test tắt nó thì các tệp đang chạy song song mất cơ sở dữ liệu.
  if (mongod) {
    await mongod.stop()
    mongod = null
  }
}

async function clearDb() {
  // Duyệt collection THẬT trong database, không phải danh sách model của
  // mongoose: từ V45 file job nằm trong GridFS (`dubfiles.files`/
  // `dubfiles.chunks`) — 2 collection do driver tạo, không có model nào, nên
  // cách cũ bỏ sót và rác của test trước tràn sang test sau (đã bắt được
  // thật: assert "không sót file cụt" fail vì file của test TRƯỚC).
  const { db } = mongoose.connection
  const names = (await db.listCollections().toArray())
    .map((c) => c.name)
    .filter((n) => !n.startsWith('system.'))
  await Promise.all(names.map((n) => db.collection(n).deleteMany({})))
}

module.exports = { setTestEnv, startDb, stopDb, clearDb, tenDbTest }
