'use strict'

/**
 * Mongo trong bộ nhớ cho integration test — mỗi file `node --test` chạy
 * trong tiến trình riêng nên mỗi file tự có instance riêng, không đụng nhau.
 *
 * Set biến env BẮT BUỘC trước khi bất kỳ service nào được require (jwtSecret()
 * và utils/crypto đều throw ngay lúc gọi nếu thiếu) — gọi `setTestEnv()` ở
 * dòng đầu file test, trước mọi `require('../src/...')`.
 */
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

async function startDb() {
  mongod = await MongoMemoryServer.create()
  mongoose.set('bufferCommands', true)
  mongoose.set('strictQuery', true)
  await mongoose.connect(mongod.getUri(), { dbName: 'voxdub_test' })
}

async function stopDb() {
  await mongoose.connection.dropDatabase()
  await mongoose.connection.close()
  if (mongod) await mongod.stop()
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

module.exports = { setTestEnv, startDb, stopDb, clearDb }
