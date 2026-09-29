'use strict'

/**
 * V45-b (15/09/2026) — DỌN chunk mồ côi, chứ không chỉ đếm.
 *
 * Bản vá 14/09 bịt chỗ rò chính (chờ mọi lệnh ghi hạ cánh xong rồi mới dọn),
 * nhưng đường lùi của nó — dùng khi driver `mongodb` bỏ bộ đếm lệnh đang bay —
 * vẫn là phỏng đoán theo thời gian, nên chunk hạ cánh muộn hơn vẫn lọt.
 * `stats().orphanChunks` từ trước tới nay mới ĐẾM, chưa ai DỌN, nên phần lọt
 * nằm lại vĩnh viễn: không bản ghi file nào trỏ tới nó, mọi cách dọn theo
 * `filename` đều mù.
 *
 * Bẫy lớn nhất của vòng quét này: upload ĐANG CHẠY DỞ trông y hệt upload đã
 * chết — GridFS chỉ tạo bản ghi `files` lúc luồng ghi KẾT THÚC. Quét theo
 * "không có bản ghi file" mà không có mốc thời gian là xoá giữa chừng dữ liệu
 * của người đang tải lên, hỏng nặng hơn hẳn thứ nó định dọn.
 */
const test = require('node:test')
const assert = require('node:assert')
const { ObjectId } = require('mongodb')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const mongoose = require('mongoose')
const storage = require('../src/services/job-storage.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(clearDb)

const BUCKET = 'dubfiles'
const chunks = () => mongoose.connection.db.collection(`${BUCKET}.chunks`)
const files = () => mongoose.connection.db.collection(`${BUCKET}.files`)

/** Chunk với dấu thời gian đặt được — ObjectId mang sẵn thời điểm tạo.
 *
 * KHÔNG dùng thẳng `ObjectId.createFromTime`: nó zero hoá 8 byte sau, nên hai
 * chunk cùng mốc thời gian sẽ trùng `_id` và lượt chèn thứ hai ném E11000.
 * (Đúng lỗi này đã làm hai test đầu tiên của tôi đỏ — lỗi của ĐỒ GIẢ, không
 * phải của vòng quét.) Ghép tay: 4 byte thời gian + 8 byte đếm tăng dần.
 */
let _dem = 0
async function themChunk(filesId, { phutTruoc = 0, n = 0 } = {}) {
  const giay = Math.floor(Date.now() / 1000) - phutTruoc * 60
  const _id = new ObjectId(
    giay.toString(16).padStart(8, '0') + (++_dem).toString(16).padStart(16, '0'))
  await chunks().insertOne({ _id, files_id: filesId, n, data: Buffer.alloc(8, 1) })
  return _id
}

async function themFile(filesId, ten = 'dub/x/input.mp4') {
  await files().insertOne({
    _id: filesId, filename: ten, length: 8, chunkSize: 255 * 1024,
    uploadDate: new Date(),
  })
}

test('chunk mồ côi ĐÃ GIÀ thì bị dọn', async () => {
  const chu = new ObjectId()
  await themChunk(chu, { phutTruoc: 120, n: 0 })
  await themChunk(chu, { phutTruoc: 120, n: 1 })

  const daXoa = await storage.quetChunkMoCoi()
  assert.equal(daXoa, 2)
  assert.equal(await chunks().countDocuments(), 0)
})

test('CHỐT AN TOÀN: upload ĐANG CHẠY DỞ không bị đụng tới', async () => {
  // Chưa có bản ghi `files` — y hệt một upload đã chết. Khác nhau ở MỖI tuổi.
  const dangTai = new ObjectId()
  await themChunk(dangTai, { phutTruoc: 0, n: 0 })
  await themChunk(dangTai, { phutTruoc: 1, n: 1 })

  const daXoa = await storage.quetChunkMoCoi()
  assert.equal(daXoa, 0, 'vòng quét vừa xoá dữ liệu của người đang tải lên')
  assert.equal(await chunks().countDocuments(), 2)
})

test('file LÀNH MẠNH không bao giờ bị đụng, dù chunk rất cũ', async () => {
  const chu = new ObjectId()
  await themFile(chu)
  await themChunk(chu, { phutTruoc: 9999, n: 0 })

  assert.equal(await storage.quetChunkMoCoi(), 0)
  assert.equal(await chunks().countDocuments(), 1)
  assert.equal(await files().countDocuments(), 1)
})

test('trộn lẫn: chỉ phần mồ côi già bị dọn, phần còn lại nguyên vẹn', async () => {
  const lanh = new ObjectId()
  const moCoi = new ObjectId()
  const dangTai = new ObjectId()
  await themFile(lanh)
  await themChunk(lanh, { phutTruoc: 300, n: 0 })
  await themChunk(moCoi, { phutTruoc: 300, n: 0 })
  await themChunk(dangTai, { phutTruoc: 0, n: 0 })

  assert.equal(await storage.quetChunkMoCoi(), 1)
  assert.equal(await chunks().countDocuments({ files_id: lanh }), 1)
  assert.equal(await chunks().countDocuments({ files_id: dangTai }), 1)
  assert.equal(await chunks().countDocuments({ files_id: moCoi }), 0)
})

test('hạn quá hạn chỉnh được, và mặc định rộng hơn hẳn hạn tải lên thật', async () => {
  const chu = new ObjectId()
  await themChunk(chu, { phutTruoc: 10 })

  assert.equal(await storage.quetChunkMoCoi(null, { quaHanPhut: 60 }), 0)
  assert.equal(await storage.quetChunkMoCoi(null, { quaHanPhut: 5 }), 1)

  // Hạn tải lên thật là 600 giây (UPLOAD_TIMEOUT_S của worker) = 10 phút.
  assert.ok(storage.PHUT_QUA_HAN_MAC_DINH >= 60,
    'mặc định phải rộng hơn nhiều hạn tải lên, nếu không sẽ xoá nhầm')
})

test('không có gì để dọn thì trả 0 và KHÔNG xả log', async () => {
  const dong = []
  const log = { warn: (...a) => dong.push(a) }
  assert.equal(await storage.quetChunkMoCoi(log), 0)
  assert.deepEqual(dong, [], 'vòng quét rỗng mà vẫn kêu thì log sẽ thành rác')
})

test('dọn được thì NÓI TO — đây là hậu quả của một chỗ rò', async () => {
  const dong = []
  const log = { warn: (...a) => dong.push(a) }
  await themChunk(new ObjectId(), { phutTruoc: 300 })

  assert.equal(await storage.quetChunkMoCoi(log), 1)
  assert.equal(dong.length, 1)
  assert.equal(dong[0][0].chunks, 1)
})

test('sau khi dọn, stats().orphanChunks về 0', async () => {
  await themChunk(new ObjectId(), { phutTruoc: 300 })
  assert.equal((await storage.stats()).orphanChunks, 1, 'tiền đề: bộ đếm thấy nó')

  await storage.quetChunkMoCoi()
  assert.equal((await storage.stats()).orphanChunks, 0)
})
