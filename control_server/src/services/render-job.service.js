'use strict'

/**
 * Xử lý Job cloud rendering (mini-spec V9 → V12, xem docs/PLAN.md — vẫn CHỈ
 * stage Demucs, tái dùng ĐÚNG NGUYÊN VĂN `autodub/media/demucs_worker.py`
 * qua subprocess — KHÔNG viết lại logic tách nhạc bằng Node, đúng guardrail
 * gốc của cả 2 mini-spec).
 *
 * V9 xử lý ĐỒNG BỘ ngay trong request (giữ HTTP mở suốt lúc chạy Demucs).
 * V12 tách hẳn: `submitDemucsJob` chỉ tạo job `queued` rồi trả về NGAY —
 * một worker Python riêng (container khác, `control_server/worker/
 * render_worker.py`) poll qua HTTP nội bộ (`/internal/jobs/*`,
 * `worker-auth.middleware.js`), tự spawn `demucs_worker.py`, rồi báo kết
 * quả về qua `completeJob`/`failJob`. Node không đụng subprocess Python
 * nữa — service này giờ chỉ còn quản lý STATE MACHINE của job trong Mongo
 * (nguồn sự thật duy nhất, guardrail 2 của V12 — không thêm Redis/broker).
 *
 * Chính sách dữ liệu (chủ dự án duyệt 2026-08-11): xoá file input/output
 * NGAY sau khi trả kết quả (`cleanupJob`), TTL `expiresAt` chỉ là lưới an
 * toàn dự phòng (sweeper, giống `hold.service.expireSweep`).
 */
const fs = require('node:fs/promises')
const path = require('node:path')

const mongoose = require('mongoose')

const RenderJob = require('../models/RenderJob')
const config = require('./config.service')
const audit = require('./audit.service')

class RenderJobError extends Error {
  constructor(code, message, statusCode = 400) {
    super(message)
    this.name = 'RenderJobError'
    this.code = code
    this.statusCode = statusCode
  }
}

const UPLOAD_DIR = process.env.RENDER_UPLOAD_DIR
  || path.join(require('node:os').tmpdir(), 'voxdub-render-jobs')

async function ensureUploadDir() {
  await fs.mkdir(UPLOAD_DIR, { recursive: true })
  return UPLOAD_DIR
}

function jobPaths(jobId) {
  const dir = path.join(UPLOAD_DIR, String(jobId))
  return {
    dir,
    input: path.join(dir, 'input.wav'),
    vocals: path.join(dir, 'vocals.wav'),
    noVocals: path.join(dir, 'no_vocals.wav'),
  }
}

/**
 * Tạo job mới: trừ Vox NGAY (nguyên tắc giống hold — thu trước, không có
 * gì để hoàn nếu job thất bại vì máy chủ đã tốn tài nguyên xử lý), lưu
 * file input, đặt job vào `queued` rồi TRẢ VỀ NGAY (V12 — bất đồng bộ
 * thật, không giữ HTTP mở chờ Demucs chạy xong như V9).
 */
async function submitDemucsJob({ device, fileBuffer, ip = '' }) {
  if (!(await config.get('cloud.render.enabled'))) {
    throw new RenderJobError('CLOUD_RENDER_DISABLED',
      'Xử lý trên cloud đang tắt.', 409)
  }
  const cost = Number(await config.get('credit.cost.cloud.demucs')) || 0
  const ttlHours = Number(await config.get('cloud.render.ttl.hours')) || 2

  const credit = require('./credit.service')
  const idempotencyKey = `cloud-demucs-${device.fingerprint}-${Date.now()}`
  let charged = { charged: 0, balanceAfter: device.balance }
  if (cost > 0) {
    charged = await credit.deduct(device.fingerprint, cost, {
      type: 'usage',
      idempotencyKey,
      description: 'Tách nhạc nền trên cloud (Demucs)',
      metadata: { stage: 'demucs', ip },
    })
  }

  // Sinh sẵn _id để biết đường dẫn file TRƯỚC khi ghi document — tránh
  // trạng thái nửa vời "job đã tạo nhưng chưa có inputPath" (schema đòi
  // inputPath bắt buộc, đúng ra không nên tồn tại lúc nào field đó rỗng).
  const jobId = new mongoose.Types.ObjectId()
  const paths = jobPaths(String(jobId))
  await fs.mkdir(paths.dir, { recursive: true })
  await fs.writeFile(paths.input, fileBuffer)

  const expiresAt = new Date(Date.now() + ttlHours * 3600 * 1000)
  const job = await RenderJob.create({
    _id: jobId,
    fingerprint: device.fingerprint,
    deviceId: device._id,
    stage: 'demucs',
    status: 'queued',
    inputPath: paths.input,
    creditCharged: charged.charged,
    expiresAt,
  })

  await audit.log({
    action: 'cloud_render.demucs.submit',
    actor: `device:${device.fingerprint.slice(0, 8)}`,
    target: String(job._id),
    after: { status: job.status, creditCharged: charged.charged },
    ip,
  })

  return { job, balanceAfter: charged.balanceAfter }
}

async function getJob(fingerprint, jobId) {
  return RenderJob.findOne({ _id: jobId, fingerprint }).lean()
}

// ---------------------------------------------------------------------- //
// State machine cho worker (mini-spec V12) — gọi từ routes/internal-jobs.js,
// KHÔNG bao giờ lộ ra `/v1/*` public (worker xác thực bằng token riêng,
// xem worker-auth.middleware.js — hoàn toàn tách khỏi token thiết bị).
// ---------------------------------------------------------------------- //

/**
 * Nhận 1 job `queued` cũ nhất (FIFO), atomic — 2 worker gọi cùng lúc
 * không bao giờ nhận trùng cùng 1 job (findOneAndUpdate là atomic ở tầng
 * Mongo, không cần lock riêng).
 */
async function claimNextJob(workerId) {
  const job = await RenderJob.findOneAndUpdate(
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

/** Chỉ cập nhật heartbeat nếu job vẫn do ĐÚNG worker này giữ — worker đã bị
 * sweeper coi là chết (job bị nhận lại/fail) thì heartbeat trễ không được
 * hồi sinh job đó, tránh 2 worker cùng đụng vào 1 job. */
async function heartbeat(jobId, workerId) {
  const updated = await RenderJob.findOneAndUpdate(
    { _id: jobId, workerId, status: 'running' },
    { $set: { heartbeatAt: new Date() } },
    { new: true },
  ).lean()
  return Boolean(updated)
}

async function completeJob(jobId, workerId, resultPaths) {
  const job = await RenderJob.findOneAndUpdate(
    { _id: jobId, workerId, status: 'running' },
    {
      $set: {
        status: 'done', completedAt: new Date(),
        resultPaths: { vocals: resultPaths.vocals, no_vocals: resultPaths.no_vocals },
      },
    },
    { new: true },
  ).lean()
  if (job) {
    await audit.log({
      action: 'cloud_render.demucs.complete',
      actor: `worker:${workerId}`,
      target: String(jobId),
      after: { status: 'done' },
    })
  }
  return job
}

async function failJob(jobId, workerId, error) {
  const job = await RenderJob.findOneAndUpdate(
    { _id: jobId, workerId, status: 'running' },
    { $set: { status: 'failed', completedAt: new Date(), error: String(error).slice(0, 1000) } },
    { new: true },
  ).lean()
  if (job) {
    await audit.log({
      action: 'cloud_render.demucs.fail',
      actor: `worker:${workerId}`,
      target: String(jobId),
      after: { status: 'failed', error: job.error },
    })
  }
  return job
}

/** Xoá file input/output của 1 job — gọi ngay sau khi trả kết quả cho
 * người dùng (chính sách dữ liệu đã chủ dự án duyệt). */
async function cleanupJob(jobId) {
  const paths = jobPaths(String(jobId))
  await fs.rm(paths.dir, { recursive: true, force: true })
}

/** Sweeper: dọn job đã hết hạn TTL mà không ai tới lấy — lưới an toàn dự
 * phòng, giống hold.service.expireSweep(). */
async function sweepExpired(log = null) {
  const expired = await RenderJob.find(
    { expiresAt: { $lt: new Date() }, status: { $in: ['done', 'failed'] } },
    { _id: 1 },
  ).limit(200).lean()
  let done = 0
  for (const j of expired) {
    try {
      await cleanupJob(j._id)
      await RenderJob.deleteOne({ _id: j._id })
      done += 1
    } catch (err) {
      if (log) log.warn({ err, jobId: j._id }, 'dọn render job hết hạn thất bại')
    }
  }
  return done
}

/**
 * Sweeper (mini-spec V12, guardrail 5): worker chết giữa chừng (crash, mất
 * mạng, container bị kill) để lại job kẹt mãi ở `running` — không ai chờ
 * mãi được. Job `running` mà `heartbeatAt` quá cũ so với ngưỡng thì coi là
 * worker đã chết, chuyển `failed` với lý do rõ ràng (không phải lỗi Demucs
 * thật, để người dùng/hỗ trợ phân biệt được).
 */
async function sweepStaleRunning(log = null) {
  const staleMinutes = Number(await config.get('cloud.render.heartbeat.stale.minutes')) || 5
  const staleBefore = new Date(Date.now() - staleMinutes * 60 * 1000)
  const stale = await RenderJob.find(
    { status: 'running', heartbeatAt: { $lt: staleBefore } },
    { _id: 1, workerId: 1 },
  ).limit(200).lean()
  let failed = 0
  for (const j of stale) {
    try {
      const updated = await RenderJob.findOneAndUpdate(
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
      if (log) log.warn({ err, jobId: j._id }, 'quét job running quá hạn heartbeat thất bại')
    }
  }
  return failed
}

module.exports = {
  RenderJobError,
  ensureUploadDir,
  jobPaths,
  submitDemucsJob,
  getJob,
  claimNextJob,
  heartbeat,
  completeJob,
  failJob,
  cleanupJob,
  sweepExpired,
  sweepStaleRunning,
}
