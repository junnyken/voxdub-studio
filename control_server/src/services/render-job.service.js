'use strict'

/**
 * Xử lý Job cloud rendering (mini-spec V9, xem docs/PLAN.md — POC hẹp: CHỈ
 * stage Demucs, tái dùng ĐÚNG NGUYÊN VĂN `autodub/media/demucs_worker.py`
 * qua subprocess — KHÔNG viết lại logic tách nhạc bằng Node (guardrail 1
 * của mini-spec: không rebuild pipeline).
 *
 * Chính sách dữ liệu (chủ dự án duyệt 2026-08-11): xoá file input/output
 * NGAY sau khi trả kết quả (`cleanupJob`), TTL `expiresAt` chỉ là lưới an
 * toàn dự phòng (sweeper, giống `hold.service.expireSweep`).
 */
const { spawn } = require('node:child_process')
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

// Repo layout: control_server/ và autodub/ là 2 thư mục anh em cùng cấp
// (xem docs/ARCH.md) — ghi đè bằng DEMUCS_WORKER_SCRIPT/DEMUCS_PYTHON nếu
// server triển khai layout khác.
const WORKER_SCRIPT = process.env.DEMUCS_WORKER_SCRIPT
  || path.join(__dirname, '..', '..', '..', 'autodub', 'media', 'demucs_worker.py')
const PYTHON_BIN = process.env.DEMUCS_PYTHON || 'python3'
const UPLOAD_DIR = process.env.RENDER_UPLOAD_DIR
  || path.join(require('node:os').tmpdir(), 'voxdub-render-jobs')

async function ensureUploadDir() {
  await fs.mkdir(UPLOAD_DIR, { recursive: true })
  return UPLOAD_DIR
}

function jobPaths(jobId) {
  const dir = path.join(UPLOAD_DIR, jobId)
  return {
    dir,
    input: path.join(dir, 'input.wav'),
    vocals: path.join(dir, 'vocals.wav'),
    noVocals: path.join(dir, 'no_vocals.wav'),
  }
}

/** Chạy demucs_worker.py thật qua subprocess — đúng CLI contract đã có. */
function runDemucsWorker({ input, vocals, noVocals }) {
  return new Promise((resolve) => {
    const proc = spawn(PYTHON_BIN, [
      WORKER_SCRIPT,
      '--input', input, '--vocals', vocals, '--no-vocals', noVocals,
    ])
    let stdout = ''
    let stderr = ''
    proc.stdout.on('data', (d) => { stdout += d })
    proc.stderr.on('data', (d) => { stderr += d })
    proc.on('close', (code) => {
      const lastLine = stdout.trim().split('\n').pop() || ''
      let parsed = null
      try { parsed = JSON.parse(lastLine) } catch { /* worker crash trước khi in JSON */ }
      if (parsed && parsed.ok) return resolve({ ok: true })
      resolve({
        ok: false,
        error: (parsed && parsed.error) || stderr.slice(-500) || `exit code ${code}`,
      })
    })
    proc.on('error', (err) => resolve({ ok: false, error: String(err.message) }))
  })
}

/**
 * Tạo job mới: trừ Vox NGAY (nguyên tắc giống hold — thu trước, không có
 * gì để hoàn nếu job thất bại vì máy chủ đã tốn tài nguyên xử lý), lưu
 * file input, chạy Demucs NGAY (đồng bộ — POC hẹp chưa cần queue đa tiến
 * trình, xem Remaining Limits trong docs/TEST_LOG.md mục V9).
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
    status: 'running',
    inputPath: paths.input,
    creditCharged: charged.charged,
    startedAt: new Date(),
    expiresAt,
  })

  const result = await runDemucsWorker({
    input: paths.input, vocals: paths.vocals, noVocals: paths.noVocals,
  })

  if (result.ok) {
    job.status = 'done'
    job.resultPaths = { vocals: paths.vocals, no_vocals: paths.noVocals }
  } else {
    job.status = 'failed'
    job.error = String(result.error).slice(0, 1000)
  }
  job.completedAt = new Date()
  await job.save()

  await audit.log({
    action: 'cloud_render.demucs',
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

module.exports = {
  RenderJobError,
  ensureUploadDir,
  jobPaths,
  submitDemucsJob,
  getJob,
  cleanupJob,
  sweepExpired,
}
