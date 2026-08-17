'use strict'

/**
 * Ghi file upload xuống đĩa THEO DÒNG (mini-spec V44, docs/PLAN.md Phase G).
 *
 * Bối cảnh thật: 2 route nhận file (`POST /api/v1/dub` giới hạn
 * `cloud.dub.max.upload.mb` = 300, `POST /v1/jobs/demucs` giới hạn 200 MB)
 * đều gọi `data.toBuffer()` — nuốt trọn file vào RAM rồi mới ghi đĩa. Đo
 * thật 2026-08-17 trên chính mã này: 1 upload 250 MB đẩy RSS tiến trình
 * tăng **485 MB** (toBuffer gom từng mảnh rồi `concat` nên đỉnh gấp đôi).
 * Container prod `voxdub-app` có 1 GB RAM và rate limit cho phép 5
 * request/phút/key → 2 upload lớn đồng thời là đủ giết cả tiến trình, kéo
 * theo mọi job đang chạy. Cùng phép đo với bản stream: **34.6 MB**.
 *
 * Nghịch lý trước V44: chặng worker ⇄ server đã stream từ trước
 * (`internal-dub-jobs.js`), chỉ còn chặng khách → server là buffer. Hàm này
 * là bản dùng chung của đúng pattern đã có ở đó (`pipeline()` + kiểm
 * `truncated` + xoá bản cụt).
 *
 * `makeError(code, message, statusCode)` để mỗi service tự bọc thành lớp
 * lỗi riêng của mình (`DubJobError`/`RenderJobError`) — util này không biết
 * và không cần biết domain nào đang gọi.
 */
const fsp = require('node:fs/promises')
const { createWriteStream } = require('node:fs')
const { pipeline } = require('node:stream/promises')

async function writeUploadToDisk(fileStream, destPath, { maxMb, makeError, label = 'File' }) {
  if (!fileStream) {
    throw makeError('NO_FILE', `Thiếu ${label.toLowerCase()}.`, 400)
  }

  const tooLarge = () => makeError(
    'UPLOAD_TOO_LARGE', `${label} vượt quá ${maxMb} MB.`, 413,
  )

  try {
    await pipeline(fileStream, createWriteStream(destPath))
  } catch (err) {
    // `@fastify/multipart` có 2 hành vi khi quá hạn mức tuỳ cấu hình/phiên
    // bản: cắt ngang im lặng (đặt cờ `truncated`) hoặc ném
    // `FST_REQ_FILE_TOO_LARGE`. Gom cả 2 về cùng một lỗi — không được để
    // file CỤT lọt xuống worker rồi báo "xong" với kết quả hỏng.
    if (fileStream.truncated || (err && err.code === 'FST_REQ_FILE_TOO_LARGE')) {
      await fsp.unlink(destPath).catch(() => {})
      throw tooLarge()
    }
    await fsp.unlink(destPath).catch(() => {})
    throw err
  }
  if (fileStream.truncated) {
    await fsp.unlink(destPath).catch(() => {})
    throw tooLarge()
  }

  // File rỗng chỉ biết được SAU khi ghi xong (không còn Buffer để đo
  // trước) — vẫn phải chặn ở đây, nếu không worker nhận job không có gì để
  // xử lý và chỉ hỏng ở tận bước nặng nhất.
  const { size } = await fsp.stat(destPath)
  if (!size) {
    await fsp.unlink(destPath).catch(() => {})
    throw makeError('EMPTY_FILE', `${label} rỗng.`, 400)
  }
  return size
}

module.exports = { writeUploadToDisk }
