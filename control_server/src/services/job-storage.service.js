'use strict'

/**
 * Nơi cất file của job lồng tiếng (mini-spec V45, docs/PLAN.md Phase G).
 *
 * Vấn đề thật, đã chứng minh bằng thực nghiệm 2026-08-17: nền tảng đang chạy
 * (Vibe Host) KHÔNG có volume bền vững. Job `done`, tải kết quả trước
 * redeploy → 200; redeploy xong tải lại đúng job đó → file biến mất trong
 * khi Mongo vẫn `done` và ví ĐÃ bị trừ. V44's `refundLostResult()` chỉ là
 * lưới an toàn — khách được hoàn tiền nhưng vẫn KHÔNG có hàng, và phải chờ
 * dub lại từ đầu.
 *
 * Vì sao GridFS chứ không phải S3: MongoDB do nền tảng provision là thứ DUY
 * NHẤT trong hệ thống hiện tại thật sự bền vững qua redeploy. S3 sẽ cần
 * credential ngoài + quyết định chi phí của chủ dự án (đã ghi là "quyết định
 * hạ tầng" trong Remaining Limits của V48) — còn GridFS dùng được NGAY với
 * đúng kết nối Mongo sẵn có, không thêm biến môi trường nào. GridFS cũng
 * sinh ra đúng cho việc này: chia file thành chunk 255KB và đọc/ghi theo
 * dòng, nên vẫn giữ nguyên nguyên tắc "không bao giờ nạp cả video vào RAM"
 * của V44.
 *
 * Đánh đổi có chủ đích: video nằm trong database làm DB phình. Chấp nhận
 * được vì file chỉ sống rất ngắn — xoá NGAY sau khi khách tải xong (chính
 * sách dữ liệu V9) và có TTL `cloud.dub.ttl.hours` (mặc định 2 giờ) làm lưới
 * thứ hai. Nếu sau này lượng job lớn tới mức DB không chịu nổi thì đường
 * nâng cấp là đổi đúng module này sang S3, không phải sửa rải rác.
 *
 * Khoá (`storageKey`) có dạng `dub/<jobId>/input.mp4` — vẫn lưu trong đúng 2
 * field `inputPath`/`outputPath` của `DubApiJob` (không đổi schema): trước
 * đây là đường dẫn đĩa, giờ là khoá GridFS. Job cũ còn sót đường dẫn đĩa sẽ
 * đơn giản là "không tìm thấy" → rơi vào đúng nhánh hoàn phí đã có, không
 * crash.
 */
const mongoose = require('mongoose')
const { GridFSBucket } = require('mongodb')

const { writeUploadStream } = require('../utils/upload-stream')

const BUCKET = 'dubfiles'

function bucket() {
  const { db } = mongoose.connection
  if (!db) throw new Error('Chưa kết nối MongoDB')
  return new GridFSBucket(db, { bucketName: BUCKET })
}

function inputKey(jobId) { return `dub/${jobId}/input.mp4` }
function outputKey(jobId) { return `dub/${jobId}/output.mp4` }

/** Stream ghi. Xoá bản cũ cùng khoá trước để không tích tụ nhiều phiên bản
 * (GridFS cho phép trùng filename — im lặng giữ cả hai là cách rò rỉ dung
 * lượng khó thấy nhất). */
async function openWrite(key) {
  await remove(key)
  return bucket().openUploadStream(key)
}

/** Stream đọc, hoặc `null` nếu không có — người gọi tự quyết (nhánh hoàn phí
 * của V44 dựa vào đúng tín hiệu "không có" này). */
async function openRead(key) {
  const file = await findOne(key)
  if (!file) return null
  return bucket().openDownloadStream(file._id)
}

async function findOne(key) {
  const [file] = await bucket().find({ filename: key }).limit(1).toArray()
  return file || null
}

async function exists(key) {
  return Boolean(await findOne(key))
}

async function size(key) {
  const file = await findOne(key)
  return file ? file.length : 0
}

async function remove(key) {
  const files = await bucket().find({ filename: key }).toArray()
  for (const f of files) {
    // eslint-disable-next-line no-await-in-loop
    await bucket().delete(f._id).catch(() => {})
  }
  return files.length
}

/** Xoá mọi chunk thuộc về một lượt ghi (kể cả khi bản ghi file chưa/không
 * bao giờ được tạo). */
async function chunksOf(fileId) {
  if (!fileId) return 0
  const { db } = mongoose.connection
  const res = await db.collection(`${BUCKET}.chunks`).deleteMany({ files_id: fileId })
  return res.deletedCount || 0
}

/**
 * Chờ cho MỌI lệnh ghi chunk đang bay hạ cánh xong, rồi mới được phép dọn.
 *
 * Đây là mấu chốt của lỗi chunk mồ côi. Driver `mongodb` gửi từng chunk bằng
 * `insertOne` bất đồng bộ và chỉ hỏi `isAborted()` TRƯỚC khi gửi
 * (`lib/gridfs/upload.js`), nên lệnh đã bay thì không ai huỷ được: `abort()`
 * chạy `deleteMany` xong xuôi, rồi chunk kia mới tới, và nằm lại vĩnh viễn —
 * không bản ghi file nào trỏ tới nó, mọi cách dọn theo `filename` đều mù.
 *
 * Xoá thêm một lượt nữa ngay lập tức KHÔNG chữa được, vì lượt ấy đua lại đúng
 * cuộc đua cũ. Chờ một khoảng cố định thì chỉ là đoán. Cách duy nhất chắc chắn
 * là hỏi chính bộ đếm của driver: `state.outstandingRequests` là số lệnh đã
 * gửi mà chưa có hồi đáp. Về 0 nghĩa là không còn gì đang bay, và vì stream đã
 * huỷ nên cũng không lệnh mới nào được gửi nữa — lượt xoá sau đó là lượt cuối
 * cùng thật sự.
 *
 * Trường này là NỘI BỘ của driver. Dùng thầm rồi im lặng là cách để hai năm
 * nữa lỗi quay lại mà không ai hiểu vì sao, nên: vắng mặt thì hàm trả `false`
 * để bên gọi biết mình đang mò, và có một test đỏ thẳng nếu bản driver sau bỏ
 * nó đi (`tests/backup-excludes-blobs.test.js`).
 *
 * @returns `true` nếu chắc chắn không còn lệnh nào bay; `false` nếu hết hạn
 *   chờ hoặc driver không còn bộ đếm — lúc đó bên gọi phải quét bù.
 */
async function choLenhGhiBayXong(dest, hanMs = 5000) {
  const trangThai = dest && dest.state
  if (!trangThai || typeof trangThai.outstandingRequests !== 'number') return false
  const han = Date.now() + hanMs
  while (trangThai.outstandingRequests > 0) {
    if (Date.now() >= han) return false
    // eslint-disable-next-line no-await-in-loop
    await new Promise((r) => { setTimeout(r, 2) })
  }
  return true
}

/** Mọi khoá đang có trong kho — dùng cho test "không sót file mồ côi" và
 * cho việc soi dung lượng khi cần. */
async function listAll() {
  const files = await bucket().find({}).toArray()
  return files.map((f) => f.filename)
}

/**
 * Thống kê dung lượng kho (mini-spec V50) — video giờ nằm TRONG database
 * (V45), nên nếu không ai nhìn thì DB phình âm thầm tới lúc hết chỗ mới
 * biết. Trả về đủ để cảnh báo sớm: tổng byte, số file, file cũ nhất, và
 * phần mồ côi (file không còn job nào trỏ tới — dấu hiệu sweeper sót việc).
 */
async function stats() {
  const files = await bucket().find({}).toArray()
  const totalBytes = files.reduce((sum, f) => sum + (f.length || 0), 0)
  const oldest = files.reduce(
    (min, f) => (!min || f.uploadDate < min ? f.uploadDate : min), null,
  )

  // Job nào còn sống thì khoá của nó còn "có chủ"; khoá không thuộc job nào
  // là rác — đúng thứ cần biết sớm chứ không phải khi hết dung lượng.
  const DubApiJob = require('../models/DubApiJob')
  const jobs = await DubApiJob.find({}, { _id: 1 }).lean()
  const owned = new Set()
  for (const j of jobs) {
    owned.add(inputKey(String(j._id)))
    owned.add(outputKey(String(j._id)))
  }
  const orphans = files.filter((f) => !owned.has(f.filename))

  // Chunk KHÔNG thuộc bản ghi file nào — loại rác nguy hiểm nhất vì mọi cách
  // dọn theo filename đều không thấy nó. Đây chính là thứ đã rò rỉ thật khi
  // upload đứt giữa chừng (rà chéo 2026-08-17); đếm ra đây để lần sau phát
  // hiện bằng số liệu chứ không phải bằng may mắn.
  const { db } = mongoose.connection
  const knownIds = new Set(files.map((f) => String(f._id)))
  const chunkOwners = await db.collection(`${BUCKET}.chunks`).distinct('files_id')
  const orphanChunkOwners = chunkOwners.filter((id) => !knownIds.has(String(id)))
  const orphanChunks = orphanChunkOwners.length
    ? await db.collection(`${BUCKET}.chunks`)
      .countDocuments({ files_id: { $in: orphanChunkOwners } })
    : 0

  return {
    files: files.length,
    orphanChunks,
    totalBytes,
    totalMb: Math.round((totalBytes / 1024 / 1024) * 10) / 10,
    oldestUploadedAt: oldest,
    orphanFiles: orphans.length,
    orphanBytes: orphans.reduce((sum, f) => sum + (f.length || 0), 0),
  }
}

/** Xoá mọi file của 1 job (input + output) — dùng khi dọn job. */
async function removeJob(jobId) {
  return (await remove(inputKey(jobId))) + (await remove(outputKey(jobId)))
}

/**
 * Nhận 1 upload multipart và ghi thẳng vào kho, theo dòng — bản GridFS của
 * `writeUploadToDisk` (V44). Mọi luật chống-file-cụt dùng chung lõi
 * `writeUploadStream`, ở đây chỉ cắm vào cách xoá/đo của GridFS.
 */
async function writeUploadToStorage(fileStream, key, { maxMb, makeError, label = 'File' }) {
  const dest = await openWrite(key)
  return writeUploadStream(fileStream, {
    dest,
    // Dọn 2 tầng, thiếu tầng nào cũng rò rỉ:
    //  - `abort()` xoá các CHUNK đã ghi dở. GridFS chỉ tạo bản ghi file lúc
    //    stream `finish`, nên upload đứt giữa chừng để lại chunk KHÔNG có
    //    chủ — `remove(key)` tìm theo filename nên không bao giờ thấy chúng,
    //    và bộ đếm mồ côi của V50 (đếm file) cũng không thấy. Đo thật: 1 lần
    //    đứt kết nối để lại 9 chunk nằm vĩnh viễn trong database.
    //  - `remove(key)` cho ca stream ĐÃ finish rồi mới hỏng (vd `truncated`),
    //    lúc đó bản ghi file có thật và `abort()` không còn tác dụng.
    cleanup: async () => {
      // THỨ TỰ Ở ĐÂY LÀ CẢ BẢN VÁ: chờ trước, dọn sau.
      //
      // Bản trước dọn ngay rồi mới hết, nên chunk đang bay hạ cánh SAU lượt
      // dọn và nằm lại. Lỗi ấy chỉ hiện khoảng 1/12 lượt CI, và 70 lượt chạy
      // lại ở máy tôi (cả rảnh lẫn dưới tải) không tái hiện nổi lần nào —
      // nên nó được vá dựa trên mã driver, kèm một test hoãn việc hạ cánh
      // của lệnh ghi để cuộc đua xảy ra CHẮC CHẮN.
      const daLang = await choLenhGhiBayXong(dest)

      try { await dest.abort() } catch { /* stream đã đóng — rơi xuống 2 bước dưới */ }
      await remove(key).catch(() => {})
      // Quét theo `files_id`: chỉ `abort()` thôi vẫn sót. Xoá theo id là cách
      // DUY NHẤT tóm được chunk không có bản ghi file (tìm theo filename
      // không bao giờ thấy chúng).
      await chunksOf(dest.id).catch(() => {})

      // `daLang === false` nghĩa là hết hạn chờ, hoặc driver đã bỏ bộ đếm.
      // Lúc đó lượt xoá trên KHÔNG còn là lượt cuối cùng chắc chắn, nên quét
      // bù vài lượt. Đây là mò, và nó được gọi đúng tên: phần sót lại sau
      // cùng vẫn hiện ra ở `stats().orphanChunks` cho trang quản trị, chứ
      // không biến mất im lặng.
      if (!daLang) {
        for (let i = 0; i < 3; i += 1) {
          // eslint-disable-next-line no-await-in-loop
          await new Promise((r) => { setTimeout(r, 50) })
          // eslint-disable-next-line no-await-in-loop
          await chunksOf(dest.id).catch(() => {})
        }
      }
    },
    getSize: () => size(key),
    maxMb,
    makeError,
    label,
  })
}

module.exports = {
  BUCKET,
  inputKey,
  outputKey,
  openWrite,
  openRead,
  exists,
  size,
  remove,
  removeJob,
  listAll,
  stats,
  writeUploadToStorage,
}
