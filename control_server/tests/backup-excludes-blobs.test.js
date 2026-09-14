'use strict'

/**
 * Rà soát chéo V45 ⇄ V48 (2026-08-17).
 *
 * V48 (sao lưu) được viết TRƯỚC V45 (đưa video vào GridFS trong chính
 * database). Nghi vấn: `exportLines()` duyệt MỌI collection không phải
 * `system.*` — sau V45 nghĩa là nó nuốt luôn `dubfiles.files` và
 * `dubfiles.chunks`, tức toàn bộ byte video đang xử lý dở, mã hoá base64
 * trong bản sao lưu.
 *
 * Nếu đúng thì đây là lỗi thật: bản backup phình theo lượng job đang chạy
 * (video hàng trăm MB), trong khi những file đó vốn EPHEMERAL — xoá ngay sau
 * khi khách tải, TTL 2 giờ — khôi phục lại cũng vô nghĩa.
 *
 * Chạy:  node --test tests/backup-excludes-blobs.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const { Readable } = require('node:stream')
const { pipeline } = require('node:stream/promises')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const mongoose = require('mongoose')
const Device = require('../src/models/Device')
const backup = require('../src/services/backup.service')
const storage = require('../src/services/job-storage.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(clearDb)

async function dump() {
  const lines = []
  for await (const line of backup.exportLines()) lines.push(line)
  return lines
}

test('bản sao lưu KHÔNG chứa byte video của job (GridFS)', async () => {
  await Device.create({ fingerprint: 'a'.repeat(64), balance: 100, status: 'active' })
  // 600 KB — đủ để chắc chắn chia thành nhiều chunk GridFS (255 KB/chunk).
  const video = Buffer.alloc(600 * 1024, 9)
  await pipeline(Readable.from([video]), await storage.openWrite('dub/xyz/output.mp4'))

  const lines = await dump()
  const meta = JSON.parse(lines[0]).__meta

  assert.ok(!meta.collections.includes('dubfiles.chunks'),
    'chunks video KHÔNG được nằm trong bản sao lưu')
  assert.ok(!meta.collections.includes('dubfiles.files'),
    'metadata file video cũng không cần sao lưu — file là tạm, xoá sau khi giao')
  assert.ok(meta.collections.includes('devices'), 'dữ liệu nghiệp vụ vẫn phải có')

  // Kiểm bằng KÍCH THƯỚC chứ không chỉ tên collection: 600 KB byte lọt vào
  // dump sẽ thấy ngay (base64 còn phình thêm ~33%).
  const bytes = Buffer.byteLength(lines.join(''))
  assert.ok(bytes < 100 * 1024,
    `bản dump phải nhỏ, không nuốt video — thực tế ${Math.round(bytes / 1024)} KB`)
})

test('upload hỏng giữa chừng KHÔNG để lại chunk mồ côi trong DB', async () => {
  // Nguồn phát NHIỀU chunk rồi mới lỗi — phải đủ để GridFS thật sự ghi vài
  // chunk 255 KB xuống DB trước khi đứt, nếu không thì test "pass" chỉ vì
  // chưa có gì kịp ghi (bản đầu tiên của test này đúng là bị vậy).
  let sent = 0
  const broken = new Readable({
    read() {
      if (sent >= 8) {
        this.destroy(new Error('mất kết nối giữa chừng'))
        return
      }
      sent += 1
      // Nhả theo nhịp macrotask để vòng ghi GridFS kịp chạy xen vào.
      setTimeout(() => this.push(Buffer.alloc(300 * 1024, 1)), 5)
    },
  })

  await assert.rejects(
    () => storage.writeUploadToStorage(broken, 'dub/hong/input.mp4', {
      maxMb: 300,
      makeError: (code, message) => Object.assign(new Error(message), { code }),
      label: 'File video',
    }),
  )

  const chunks = await mongoose.connection.db.collection('dubfiles.chunks').countDocuments()
  const files = await mongoose.connection.db.collection('dubfiles.files').countDocuments()
  assert.equal(files, 0, 'không được để lại bản ghi file')
  assert.equal(chunks, 0,
    `không được để lại chunk mồ côi — còn ${chunks} chunk chiếm chỗ vĩnh viễn`)
})

/**
 * Cùng lỗi trên, nhưng TÁI HIỆN ĐƯỢC THEO Ý MUỐN thay vì chờ may.
 *
 * Test ở trên đỏ trên CI ngày 14/09 (còn 1 chunk mồ côi) rồi 70 lượt chạy lại
 * ở máy tôi — cả lúc rảnh lẫn lúc 24 tiến trình tranh 12 nhân — đều xanh. Một
 * lỗi chỉ hiện 1/12 lượt thì không vá được: không có cách nào biết bản vá có
 * tác dụng hay chỉ vừa may.
 *
 * Cuộc đua, đọc từ mã driver `mongodb` 6.20.0 (`lib/gridfs/upload.js`): mỗi
 * chunk được gửi bằng `insertOne` bất đồng bộ, `++state.outstandingRequests`
 * ngay trước khi gửi và `--` khi có hồi đáp. `isAborted()` chỉ được hỏi TRƯỚC
 * khi gửi — lệnh đã bay thì không ai huỷ được nữa. Nên `abort()` chạy
 * `deleteMany` xong, rồi chunk kia mới hạ cánh, và nằm lại vĩnh viễn: không
 * có bản ghi file nào trỏ tới nó, mọi cách dọn theo `filename` đều mù.
 *
 * Ở đây tôi làm đúng cuộc đua ấy xảy ra CHẮC CHẮN: hoãn việc hạ cánh THẬT của
 * lệnh ghi chunk. Không phải hoãn lời hứa — hoãn lời hứa thì byte vẫn vào DB
 * đúng giờ và `deleteMany` vẫn tóm được, tức là mô phỏng sai cuộc đua.
 */
test('chunk hạ cánh SAU lượt dọn vẫn không được nằm lại (đua tất định)', async () => {
  const { Collection } = require('mongodb')
  const goc = Collection.prototype.insertOne
  const laChunkGridFS = (doc) => doc && doc.files_id && typeof doc.n === 'number'
  const HOAN_MS = 150

  Collection.prototype.insertOne = function (doc, opts) {
    if (!laChunkGridFS(doc)) return goc.call(this, doc, opts)
    return new Promise((ok, hong) => {
      setTimeout(() => goc.call(this, doc, opts).then(ok, hong), HOAN_MS)
    })
  }

  try {
    let sent = 0
    const broken = new Readable({
      read() {
        if (sent >= 4) { this.destroy(new Error('mất kết nối giữa chừng')); return }
        sent += 1
        setTimeout(() => this.push(Buffer.alloc(300 * 1024, 1)), 5)
      },
    })

    await assert.rejects(
      () => storage.writeUploadToStorage(broken, 'dub/dua/input.mp4', {
        maxMb: 300,
        makeError: (code, message) => Object.assign(new Error(message), { code }),
        label: 'File video',
      }),
    )

    // Chờ QUÁ hạn hoãn: mọi lệnh ghi còn bay đều đã hạ cánh xong tại đây. Nếu
    // lượt dọn có tác dụng thì phải không còn gì, kể cả chunk tới muộn.
    await new Promise((r) => setTimeout(r, HOAN_MS * 4))

    const { db } = mongoose.connection
    const chunks = await db.collection('dubfiles.chunks').countDocuments()
    const files = await db.collection('dubfiles.files').countDocuments()
    assert.equal(files, 0, 'không được để lại bản ghi file')
    assert.equal(chunks, 0,
      `chunk tới sau lượt dọn vẫn phải bị dọn — còn ${chunks} chunk mồ côi`)
  } finally {
    Collection.prototype.insertOne = goc
  }
})

/**
 * Bản vá trên dựa vào `state.outstandingRequests` — một trường NỘI BỘ của
 * driver `mongodb`. Bản driver sau bỏ nó đi thì bản vá âm thầm mất tác dụng
 * và lỗi chunk mồ côi quay lại y như cũ, chỉ khác là lần này không ai biết vì
 * sao. Test này để lượt nâng driver báo ngay chứ không để prod báo hộ.
 */
test('driver còn bộ đếm lệnh ghi đang bay — bản vá dựa vào nó', async () => {
  const dest = await storage.openWrite('dub/dem/probe.mp4')
  try {
    assert.equal(typeof dest.state.outstandingRequests, 'number',
      'driver mongodb đã bỏ `state.outstandingRequests`: đọc lại cleanup của '
      + 'writeUploadToStorage trong job-storage.service.js trước khi nâng bản')
  } finally {
    await dest.abort().catch(() => {})
  }
})
