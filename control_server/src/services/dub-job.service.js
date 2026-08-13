'use strict'

/**
 * State machine cho job lồng tiếng đầy đủ (mini-spec V34a, xem docs/PLAN.md
 * — PoC hẹp, KHÔNG billing thật). Tái dùng NGUYÊN VĂN pattern của
 * `render-job.service.js` (V9→V12) — chỉ đổi identity (ApiKey thay Device)
 * và shape kết quả (1 file video thay 2 stem audio). Xem `DubApiJob.js`
 * cho lý do tách model riêng thay vì mở rộng `RenderJob`.
 *
 * Node vẫn là chủ sở hữu DUY NHẤT của Mongo — worker Python (container
 * `control_server/worker-dub/`) không chạm DB trực tiếp, chỉ gọi
 * `/internal/dub-jobs/*` (xác thực `X-Worker-Token`, tái dùng nguyên
 * `worker-auth.middleware.js` của V12 — Context của V34a xác nhận cơ chế
 * này vốn tổng quát, không riêng Demucs).
 */
const fs = require('node:fs/promises')
const path = require('node:path')

const mongoose = require('mongoose')

const DubApiJob = require('../models/DubApiJob')
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
 * Tạo job mới: KHÔNG trừ Vox/quota thật (Constraint 1 — PoC chưa có số
 * liệu chi phí compute thật để định giá đúng). `estimatedCostVox` CHỈ ghi
 * vào job + audit log để tham khảo, không đụng `ApiKey.usageCount`.
 */
async function submitDubJob({ apiKey, fileBuffer, sourceLang, targetLang, voice = '', ip = '' }) {
  if (!(await config.get('cloud.dub.enabled'))) {
    throw new DubJobError('CLOUD_DUB_DISABLED', 'API lồng tiếng đang tắt.', 409)
  }
  const ttlHours = Number(await config.get('cloud.dub.ttl.hours')) || 2
  const estimate = Number(await config.get('cloud.dub.estimate.vox.per.request')) || 0

  // Sinh sẵn _id để biết đường dẫn file TRƯỚC khi ghi document — cùng lý do
  // tránh trạng thái nửa vời đã áp dụng ở render-job.service.js.
  const jobId = new mongoose.Types.ObjectId()
  const paths = jobPaths(String(jobId))
  await fs.mkdir(paths.dir, { recursive: true })
  await fs.writeFile(paths.input, fileBuffer)

  const expiresAt = new Date(Date.now() + ttlHours * 3600 * 1000)
  const job = await DubApiJob.create({
    _id: jobId,
    apiKeyId: apiKey._id,
    status: 'queued',
    sourceLang,
    targetLang,
    voice,
    inputPath: paths.input,
    estimatedCostVox: estimate,
    expiresAt,
  })

  await audit.log({
    action: 'cloud_dub.submit',
    actor: `apikey:${String(apiKey._id).slice(-8)}`,
    target: String(job._id),
    after: { status: job.status, estimatedCostVox: estimate, sourceLang, targetLang },
    ip,
  })

  return { job }
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
  const job = await DubApiJob.findOneAndUpdate(
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
        },
      },
    },
    { new: true },
  ).lean()
  if (job) {
    await audit.log({
      action: 'cloud_dub.complete',
      actor: `worker:${workerId}`,
      target: String(jobId),
      after: { status: 'done', metrics: job.metrics },
    })
  }
  return job
}

async function failJob(jobId, workerId, error) {
  const job = await DubApiJob.findOneAndUpdate(
    { _id: jobId, workerId, status: 'running' },
    { $set: { status: 'failed', completedAt: new Date(), error: String(error).slice(0, 1000) } },
    { new: true },
  ).lean()
  if (job) {
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
      if (updated) failed += 1
    } catch (err) {
      if (log) log.warn({ err, jobId: j._id }, 'quét dub job running quá hạn heartbeat thất bại')
    }
  }
  return failed
}

module.exports = {
  DubJobError,
  ensureUploadDir,
  jobPaths,
  submitDubJob,
  getJob,
  claimNextJob,
  heartbeat,
  completeJob,
  failJob,
  cleanupJob,
  sweepExpired,
  sweepStaleRunning,
}
