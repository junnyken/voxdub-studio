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

/** Mọi khoá đang có trong kho — dùng cho test "không sót file mồ côi" và
 * cho việc soi dung lượng khi cần. */
async function listAll() {
  const files = await bucket().find({}).toArray()
  return files.map((f) => f.filename)
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
  return writeUploadStream(fileStream, {
    dest: await openWrite(key),
    cleanup: () => remove(key).catch(() => {}),
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
  writeUploadToStorage,
}
