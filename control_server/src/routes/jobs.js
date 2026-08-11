'use strict'

/**
 * `/v1/jobs` — xử lý cloud rendering (mini-spec V9 → V12, xem docs/PLAN.md
 * — vẫn POC hẹp: CHỈ stage Demucs). Mọi route cần token thiết bị.
 *
 * Không thay thế luồng local hiện có — đây là TUỲ CHỌN thêm (guardrail của
 * mini-spec), người dùng không cấu hình VOXDUB_API_URL vẫn chạy 100% local
 * như trước, route này không được gọi tới.
 *
 * BREAKING CHANGE (V12, có chủ đích — xem Audit Before Build trong
 * docs/PLAN.md mục V12): V9 xử lý ĐỒNG BỘ, response trả về SAU khi Demucs
 * chạy xong (status luôn là "done"/"failed"). V12 trả về NGAY với
 * status:"queued" — client PHẢI tự poll `GET /:jobId` tới khi status là
 * "done"/"failed". Trường `async:true` đánh dấu rõ hợp đồng mới, để một
 * client cũ (giả sử có) nhận ra ngay thay vì đọc nhầm "queued" thành lỗi.
 * An toàn để đổi ngay bây giờ: V9 chưa từng có GUI wiring (audit xác nhận
 * autodub_gui chưa gọi route này lần nào) — đây là client thật ĐẦU TIÊN.
 */
const renderJob = require('../services/render-job.service')

module.exports = async function jobsRoutes(fastify) {
  const { requireDevice } = require('../middleware/auth.middleware')

  fastify.addHook('preHandler', requireDevice)

  // --- Nộp job Demucs (upload audio, TRẢ VỀ NGAY — xử lý bất đồng bộ) -----
  fastify.post('/demucs', {
    config: { rateLimit: { max: 5, timeWindow: '1 minute' } },
  }, async (request, reply) => {
    const data = await request.file({
      limits: { fileSize: 200 * 1024 * 1024 },   // 200 MB — đủ audio 1 video dài
    })
    if (!data) {
      return reply.code(400).send({ code: 'NO_FILE', message: 'Thiếu file audio.' })
    }
    const buffer = await data.toBuffer()
    if (!buffer.length) {
      return reply.code(400).send({ code: 'EMPTY_FILE', message: 'File audio rỗng.' })
    }

    try {
      const { job, balanceAfter } = await renderJob.submitDemucsJob({
        device: request.device, fileBuffer: buffer, ip: request.ip,
      })
      return {
        jobId: job._id,
        status: job.status,
        async: true,
        error: job.error || undefined,
        balanceAfter,
      }
    } catch (err) {
      if (err instanceof renderJob.RenderJobError) {
        return reply.code(err.statusCode).send({ code: err.code, message: err.message })
      }
      if (err.code === 'INSUFFICIENT_CREDIT') {
        return reply.code(402).send({ code: err.code, message: err.message, balance: err.balance })
      }
      throw err
    }
  })

  // --- Trạng thái job ------------------------------------------------------
  fastify.get('/:jobId', async (request, reply) => {
    const job = await renderJob.getJob(request.device.fingerprint, request.params.jobId)
    if (!job) return reply.code(404).send({ code: 'NOT_FOUND' })
    return {
      jobId: job._id, stage: job.stage, status: job.status,
      error: job.error || undefined, creditCharged: job.creditCharged,
      expiresAt: job.expiresAt,
    }
  })

  // --- Tải kết quả — xoá file NGAY sau khi trả (chính sách dữ liệu đã ---
  // chủ dự án duyệt 2026-08-11, xem docs/TEST_LOG.md mục V9) --------------
  fastify.get('/:jobId/result/:stem', async (request, reply) => {
    const { jobId, stem } = request.params
    if (!['vocals', 'no_vocals'].includes(stem)) {
      return reply.code(400).send({ code: 'BAD_STEM', message: 'stem phải là vocals hoặc no_vocals.' })
    }
    const job = await renderJob.getJob(request.device.fingerprint, jobId)
    if (!job) return reply.code(404).send({ code: 'NOT_FOUND' })
    if (job.status !== 'done') {
      return reply.code(409).send({ code: 'NOT_READY', message: `Job đang ở trạng thái ${job.status}.` })
    }
    const filePath = job.resultPaths && job.resultPaths[stem]
    if (!filePath) {
      return reply.code(404).send({ code: 'RESULT_NOT_FOUND' })
    }

    const fs = require('node:fs')
    if (!fs.existsSync(filePath)) {
      return reply.code(410).send({
        code: 'RESULT_EXPIRED',
        message: 'Kết quả đã bị xoá (đã tải trước đó hoặc quá hạn TTL).',
      })
    }
    const stream = fs.createReadStream(filePath)
    reply.header('Content-Type', 'audio/wav')
    reply.header('Content-Disposition', `attachment; filename="${stem}.wav"`)
    await reply.send(stream)

    // Chỉ xoá NGUYÊN CẢ JOB khi đã tải hết cả 2 stem (người dùng thường tải
    // lần lượt vocals rồi no_vocals) — đánh dấu qua field `downloaded`,
    // KHÔNG suy luận qua sự tồn tại file (file vẫn còn tới lúc bị xoá).
    stream.on('close', async () => {
      const RenderJob = require('../models/RenderJob')
      const updated = await RenderJob.findOneAndUpdate(
        { _id: jobId },
        { $set: { [`downloaded.${stem}`]: true } },
        { new: true },
      ).lean()
      if (updated && updated.downloaded.vocals && updated.downloaded.no_vocals) {
        await renderJob.cleanupJob(jobId).catch(() => {})
      }
    })
  })
}
