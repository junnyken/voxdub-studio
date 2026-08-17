'use strict'

/**
 * State machine cho job lồng tiếng đầy đủ (mini-spec V34a→V34b, xem
 * docs/PLAN.md). Tái dùng NGUYÊN VĂN pattern của `render-job.service.js`
 * (V9→V12) — chỉ đổi identity (ApiKey thay Device) và shape kết quả (1
 * file video thay 2 stem audio). Xem `DubApiJob.js` cho lý do tách model
 * riêng thay vì mở rộng `RenderJob`.
 *
 * Node vẫn là chủ sở hữu DUY NHẤT của Mongo — worker Python (container
 * `control_server/worker-dub/`) không chạm DB trực tiếp, chỉ gọi
 * `/internal/dub-jobs/*` (xác thực `X-Worker-Token`, tái dùng nguyên
 * `worker-auth.middleware.js` của V12 — Context của V34a xác nhận cơ chế
 * này vốn tổng quát, không riêng Demucs).
 *
 * V34b: billing THẬT theo phút video, tính SAU khi job hoàn tất (worker
 * trả về `durationS` đo thật từ chính pipeline — xem `chargeDubUsage()`)
 * — KHÔNG dùng ffprobe ở Node (control_server không có ffmpeg), KHÔNG dùng
 * `ApiKey.quota`/`usageCount` (đó là bộ đếm LƯỢT GỌI của V31, khác đơn vị
 * "phút" — Constraint 2 của V34b).
 */
const fs = require('node:fs/promises')
const path = require('node:path')

const mongoose = require('mongoose')

const DubApiJob = require('../models/DubApiJob')
const DubUsageLedger = require('../models/DubUsageLedger')
const ApiKey = require('../models/ApiKey')
const config = require('./config.service')
const audit = require('./audit.service')

class DubJobError extends Error {
  constructor(code, message, statusCode = 400) {
    super(message)
    this.name = 'DubJobError'
    this.code = code
    this.statusCode = statusCode
  }
}

const UPLOAD_DIR = process.env.DUB_UPLOAD_DIR
  || path.join(require('node:os').tmpdir(), 'voxdub-dub-jobs')

async function ensureUploadDir() {
  await fs.mkdir(UPLOAD_DIR, { recursive: true })
  return UPLOAD_DIR
}

function jobPaths(jobId) {
  const dir = path.join(UPLOAD_DIR, String(jobId))
  return {
    dir,
    input: path.join(dir, 'input.mp4'),
    output: path.join(dir, 'output.mp4'),
  }
}

/**
 * Giữ chỗ N phút quota trên `apiKeyId`, atomic — mini-spec V43. Điều kiện
 * `dubMinutesUsed + dubMinutesReserved + reserveMinutes <= dubMinutesQuota`
 * nằm NGAY trong query của `findOneAndUpdate` (cùng kỹ thuật `balance:
 * {$gte}` của `credit.service.js`), nên nhiều request song song từ CÙNG 1
 * key chỉ đúng số job vừa đủ quota được lọt qua — không còn đọc-rồi-quyết
 * như trước (gap V42 phát hiện). Trả về key đã cập nhật, hoặc `null` nếu
 * không còn đủ chỗ (caller quyết định thông báo gì).
 */
async function reserveDubMinutes(apiKeyId, reserveMinutes) {
  return ApiKey.findOneAndUpdate(
    {
      _id: apiKeyId,
      $expr: {
        $lte: [
          { $add: ['$dubMinutesUsed', '$dubMinutesReserved', reserveMinutes] },
          '$dubMinutesQuota',
        ],
      },
    },
    { $inc: { dubMinutesReserved: reserveMinutes } },
    { new: true },
  )
}

/** Trả lại N phút đã giữ chỗ (job xong/lỗi/hết hạn) — no-op an toàn nếu 0. */
async function releaseDubMinutes(apiKeyId, reservedMinutes) {
  if (!reservedMinutes) return
  await ApiKey.updateOne({ _id: apiKeyId }, { $inc: { dubMinutesReserved: -reservedMinutes } })
}

/**
 * Tạo job mới. V34b: chặn (402) nếu API key chưa được cấp quota phút dub
 * nào hoặc đã dùng hết. V43: kiểm tra giờ là GIỮ CHỖ atomic (không phải
 * đọc-rồi-quyết) — mỗi job giữ trước `estimatedMinutes` (caller tự khai vì
 * họ thường biết thời lượng file của họ) hoặc mặc định cấu hình nếu không
 * khai (không có ffprobe ở Node để tự đo — Constraint 3 của V34a). Đây CHỈ
 * là ngưỡng chặn submit tràn lan — Vox/phút thật luôn tính lại SAU, ở
 * `chargeDubUsage()` (gọi từ `completeJob()`) theo durationS worker đo
 * được; `estimatedCostVox` ở đây chỉ để tham khảo lúc submit.
 */
async function submitDubJob({
  apiKey, fileBuffer, sourceLang, targetLang, voice = '', bgMode = 'none',
  estimatedMinutes = 0, ip = '',
}) {
  if (!(await config.get('cloud.dub.enabled'))) {
    throw new DubJobError('CLOUD_DUB_DISABLED', 'API lồng tiếng đang tắt.', 409)
  }

  const cfg = await config.getMany([
    'cloud.dub.reservation.default.minutes', 'cloud.dub.reservation.max.minutes',
  ])
  const declared = Math.round(Number(estimatedMinutes)) || 0
  const reserveMinutes = Math.min(
    Math.max(declared > 0 ? declared : cfg['cloud.dub.reservation.default.minutes'], 1),
    cfg['cloud.dub.reservation.max.minutes'],
  )

  const reserved = await reserveDubMinutes(apiKey._id, reserveMinutes)
  if (!reserved) {
    // Đọc lại số thật (tham số `apiKey` truyền vào có thể đã cũ — chính
    // race condition này là lý do V43 tồn tại) để báo đúng con số hiện tại.
    const fresh = await ApiKey.findById(apiKey._id).lean()
    const used = (fresh && fresh.dubMinutesUsed) || 0
    const heldByOthers = (fresh && fresh.dubMinutesReserved) || 0
    const quota = (fresh && fresh.dubMinutesQuota) || 0
    throw new DubJobError('DUB_QUOTA_EXCEEDED',
      `Không đủ quota phút lồng tiếng còn trống (đã dùng ${used}, đang giữ chỗ `
      + `${heldByOthers} phút cho job khác, hạn mức ${quota} phút). `
      + 'Liên hệ quản trị để cấp thêm quota.', 402)
  }

  const ttlHours = Number(await config.get('cloud.dub.ttl.hours')) || 2
  const perMinuteKey = bgMode === 'demucs'
    ? 'credit.cost.cloud.dub.vox.per.minute.demucs'
    : 'credit.cost.cloud.dub.vox.per.minute'
  const estimate = Number(await config.get(perMinuteKey)) || 0

  // Sinh sẵn _id để biết đường dẫn file TRƯỚC khi ghi document — cùng lý do
  // tránh trạng thái nửa vời đã áp dụng ở render-job.service.js.
  const jobId = new mongoose.Types.ObjectId()
  const paths = jobPaths(String(jobId))

  let job
  try {
    await fs.mkdir(paths.dir, { recursive: true })
    await fs.writeFile(paths.input, fileBuffer)

    const expiresAt = new Date(Date.now() + ttlHours * 3600 * 1000)
    job = await DubApiJob.create({
      _id: jobId,
      apiKeyId: apiKey._id,
      status: 'queued',
      sourceLang,
      targetLang,
      voice,
      bgMode,
      inputPath: paths.input,
      estimatedCostVox: estimate,
      reservedMinutes: reserveMinutes,
      expiresAt,
    })
  } catch (err) {
    // Tạo job hỏng SAU khi đã giữ chỗ thành công — người gọi không được
    // phép mất chỗ quota vì lỗi phía chúng ta (cùng nguyên tắc rollback của
    // activation.service.js khi grant() hỏng sau khi đã chốt key).
    await releaseDubMinutes(apiKey._id, reserveMinutes)
    throw err
  }

  await audit.log({
    action: 'cloud_dub.submit',
    actor: `apikey:${String(apiKey._id).slice(-8)}`,
    target: String(job._id),
    after: {
      status: job.status, estimatedCostVox: estimate, reservedMinutes: reserveMinutes,
      sourceLang, targetLang, bgMode,
    },
    ip,
  })

  return { job }
}

/**
 * Trừ phút/Vox thật SAU khi job hoàn tất (mini-spec V34b) — atomic
 * (`findOneAndUpdate`, cùng kỹ thuật `consumeQuota()` của V31), ghi 1 dòng
 * bất biến vào `DubUsageLedger` (SỐNG ĐỘC LẬP với vòng đời job, xem
 * docstring model). Làm tròn LÊN phút (1 giây cũng tính đủ 1 phút — phút
 * là đơn vị tính phí nhỏ nhất, tối thiểu 1 phút/job để job cực ngắn không
 * miễn phí do làm tròn xuống 0).
 *
 * V43: `reservedMinutes` (số phút job này đã giữ chỗ lúc submit) được giải
 * phóng TRONG CÙNG một `$inc` với việc cộng usage thật — 1 lệnh nguyên tử,
 * không có khoảng hở giữa "giải phóng" và "trừ thật" mà request khác có
 * thể chen vào.
 */
async function chargeDubUsage(apiKeyId, jobId, bgMode, durationS, reservedMinutes = 0) {
  const perMinuteKey = bgMode === 'demucs'
    ? 'credit.cost.cloud.dub.vox.per.minute.demucs'
    : 'credit.cost.cloud.dub.vox.per.minute'
  const pricePerMinute = Number(await config.get(perMinuteKey)) || 0
  const minutesCharged = Math.max(1, Math.ceil(Number(durationS) / 60))
  const costVox = minutesCharged * pricePerMinute

  const inc = { dubMinutesUsed: minutesCharged }
  if (reservedMinutes) inc.dubMinutesReserved = -reservedMinutes

  const updatedKey = await ApiKey.findOneAndUpdate(
    { _id: apiKeyId },
    { $inc: inc },
    { new: true },
  )
  if (!updatedKey) return { minutesCharged, costVox, dubMinutesUsedAfter: minutesCharged }

  await DubUsageLedger.create({
    apiKeyId, jobId, bgMode, durationS, minutesCharged, costVox,
    dubMinutesUsedAfter: updatedKey.dubMinutesUsed,
  })
  return { minutesCharged, costVox, dubMinutesUsedAfter: updatedKey.dubMinutesUsed }
}

async function getJob(apiKeyId, jobId) {
  return DubApiJob.findOne({ _id: jobId, apiKeyId }).lean()
}

// ---------------------------------------------------------------------- //
// State machine cho worker — gọi từ routes/internal-dub-jobs.js, KHÔNG bao
// giờ lộ ra `/api/v1/*` public (worker xác thực bằng token riêng).
// ---------------------------------------------------------------------- //

async function claimNextJob(workerId) {
  const job = await DubApiJob.findOneAndUpdate(
    { status: 'queued' },
    {
      $set: {
        status: 'running', workerId, heartbeatAt: new Date(), startedAt: new Date(),
      },
    },
    { sort: { createdAt: 1 }, new: true },
  ).lean()
  return job
}

async function heartbeat(jobId, workerId) {
  const updated = await DubApiJob.findOneAndUpdate(
    { _id: jobId, workerId, status: 'running' },
    { $set: { heartbeatAt: new Date() } },
    { new: true },
  ).lean()
  return Boolean(updated)
}

async function completeJob(jobId, workerId, { outputPath, metrics }) {
  const durationS = Number(metrics && metrics.durationS) || 0
  let job = await DubApiJob.findOneAndUpdate(
    { _id: jobId, workerId, status: 'running' },
    {
      $set: {
        status: 'done',
        completedAt: new Date(),
        outputPath,
        metrics: {
          inputBytes: Number(metrics && metrics.inputBytes) || 0,
          outputBytes: Number(metrics && metrics.outputBytes) || 0,
          processingMs: Number(metrics && metrics.processingMs) || 0,
          durationS,
        },
      },
    },
    { new: true },
  ).lean()
  if (!job) return job

  // Tính phí THẬT (V34b) — chỉ khi có durationS đo được (>0); worker cũ/lỗi
  // báo 0 thì bỏ qua billing thay vì tính phí sai (0 phút → vẫn charge tối
  // thiểu 1 phút do Math.max ở chargeDubUsage(), tránh lách phí bằng cách
  // cố tình báo durationS=0 — nhưng job KHÔNG có durationS thật (worker cũ)
  // thì thà bỏ qua billing còn hơn charge sai).
  if (durationS > 0) {
    const charge = await chargeDubUsage(job.apiKeyId, jobId, job.bgMode, durationS, job.reservedMinutes)
    job = await DubApiJob.findOneAndUpdate(
      { _id: jobId },
      { $set: { costVox: charge.costVox } },
      { new: true },
    ).lean()
  } else if (job.reservedMinutes) {
    // Không tính phí (đúng nhánh trên) nhưng job VẪN đã xong — chỗ đã giữ
    // phải được trả lại, không thì rò rỉ quota vĩnh viễn (V43).
    await releaseDubMinutes(job.apiKeyId, job.reservedMinutes)
  }

  await audit.log({
    action: 'cloud_dub.complete',
    actor: `worker:${workerId}`,
    target: String(jobId),
    after: { status: 'done', metrics: job.metrics, costVox: job.costVox },
  })
  return job
}

async function failJob(jobId, workerId, error) {
  const job = await DubApiJob.findOneAndUpdate(
    { _id: jobId, workerId, status: 'running' },
    { $set: { status: 'failed', completedAt: new Date(), error: String(error).slice(0, 1000) } },
    { new: true },
  ).lean()
  if (job) {
    // Job lỗi = không dùng phút nào — trả lại TOÀN BỘ chỗ đã giữ (V43).
    await releaseDubMinutes(job.apiKeyId, job.reservedMinutes)
    await audit.log({
      action: 'cloud_dub.fail',
      actor: `worker:${workerId}`,
      target: String(jobId),
      after: { status: 'failed', error: job.error },
    })
  }
  return job
}

async function cleanupJob(jobId) {
  const paths = jobPaths(String(jobId))
  await fs.rm(paths.dir, { recursive: true, force: true })
}

async function sweepExpired(log = null) {
  const expired = await DubApiJob.find(
    { expiresAt: { $lt: new Date() }, status: { $in: ['done', 'failed'] } },
    { _id: 1 },
  ).limit(200).lean()
  let done = 0
  for (const j of expired) {
    try {
      await cleanupJob(j._id)
      await DubApiJob.deleteOne({ _id: j._id })
      done += 1
    } catch (err) {
      if (log) log.warn({ err, jobId: j._id }, 'dọn dub job hết hạn thất bại')
    }
  }
  return done
}

async function sweepStaleRunning(log = null) {
  const staleMinutes = Number(await config.get('cloud.dub.heartbeat.stale.minutes')) || 15
  const staleBefore = new Date(Date.now() - staleMinutes * 60 * 1000)
  const stale = await DubApiJob.find(
    { status: 'running', heartbeatAt: { $lt: staleBefore } },
    { _id: 1, workerId: 1 },
  ).limit(200).lean()
  let failed = 0
  for (const j of stale) {
    try {
      const updated = await DubApiJob.findOneAndUpdate(
        { _id: j._id, status: 'running', heartbeatAt: { $lt: staleBefore } },
        {
          $set: {
            status: 'failed',
            completedAt: new Date(),
            error: `Worker (${j.workerId || 'không rõ'}) mất kết nối quá ${staleMinutes} phút — job tự động chuyển lỗi, không treo mãi.`,
          },
        },
        { new: true },
      ).lean()
      if (updated) {
        failed += 1
        await releaseDubMinutes(updated.apiKeyId, updated.reservedMinutes)
      }
    } catch (err) {
      if (log) log.warn({ err, jobId: j._id }, 'quét dub job running quá hạn heartbeat thất bại')
    }
  }
  return failed
}

/**
 * Sweeper V43: job kẹt ở `queued` quá `expiresAt` (không worker nào rảnh
 * claim kịp trong TTL) — không có sweeper nào từng dọn nhánh này trước đây
 * vì hậu quả trước V43 chỉ là "job vẫn nằm đó chờ", vô hại. Từ V43, job
 * `queued` giữ chỗ quota thật ngay lúc submit — không giải phóng thì rò rỉ
 * quota vĩnh viễn cho job không bao giờ chạy. Chuyển `failed` (đúng ý nghĩa
 * hơn "xoá âm thầm" — caller poll `GET /dub/:jobId` vẫn thấy lý do rõ).
 */
async function sweepStaleQueued(log = null) {
  const stale = await DubApiJob.find(
    { status: 'queued', expiresAt: { $lt: new Date() } },
    { _id: 1 },
  ).limit(200).lean()
  let failed = 0
  for (const j of stale) {
    try {
      const updated = await DubApiJob.findOneAndUpdate(
        { _id: j._id, status: 'queued', expiresAt: { $lt: new Date() } },
        {
          $set: {
            status: 'failed',
            completedAt: new Date(),
            error: 'Không worker nào nhận job trong thời hạn — job tự động chuyển lỗi, không treo mãi.',
          },
        },
        { new: true },
      ).lean()
      if (updated) {
        failed += 1
        await releaseDubMinutes(updated.apiKeyId, updated.reservedMinutes)
      }
    } catch (err) {
      if (log) log.warn({ err, jobId: j._id }, 'quét dub job queued quá hạn TTL thất bại')
    }
  }
  return failed
}

module.exports = {
  DubJobError,
  ensureUploadDir,
  jobPaths,
  submitDubJob,
  chargeDubUsage,
  getJob,
  claimNextJob,
  heartbeat,
  completeJob,
  failJob,
  cleanupJob,
  sweepExpired,
  sweepStaleRunning,
  sweepStaleQueued,
  reserveDubMinutes,
  releaseDubMinutes,
}
