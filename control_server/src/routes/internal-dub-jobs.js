'use strict'

/**
 * `/internal/dub-jobs` — API nội bộ cho worker Python lồng tiếng đầy đủ
 * (mini-spec V34a, xem docs/PLAN.md). Cùng khuôn `internal-jobs.js` (V12)
 * — xác thực bằng `X-Worker-Token` (`worker-auth.middleware.js`, TÁI DÙNG
 * NGUYÊN VĂN, không cần token riêng — cơ chế vốn đã tổng quát, không gắn
 * riêng loại worker nào).
 *
 * Node vẫn là chủ sở hữu DUY NHẤT của Mongo — worker Python không chạm DB
 * trực tiếp. `dub-job.service.js` giữ toàn bộ state machine.
 *
 * File input/output đi qua HTTP (`/:jobId/input`, `/:jobId/output`) chứ
 * KHÔNG qua volume dùng chung: V34a giả định worker nằm cùng docker-compose
 * nên đọc thẳng `inputPath` trên đĩa, nhưng khi 2 container chạy tách nhau
 * (nền tảng hosting mỗi service 1 project — xác nhận thật lúc chuyển sang
 * Vibe Host 2026-08-17) thì đường dẫn đó không tồn tại bên worker. Truyền
 * qua HTTP chạy đúng ở CẢ hai kiểu triển khai nên là đường DUY NHẤT, không
 * rẽ nhánh theo môi trường.
 */
const { pipeline } = require('node:stream/promises')
const dubJob = require('../services/dub-job.service')
const storage = require('../services/job-storage.service')
const config = require('../services/config.service')

module.exports = async function internalDubJobsRoutes(fastify) {
  const { requireWorker } = require('../middleware/worker-auth.middleware')

  fastify.addHook('preHandler', requireWorker)

  // --- Nhận job kế tiếp (poll) --------------------------------------------
  fastify.post('/claim', async (request, reply) => {
    const workerId = String(request.body && request.body.workerId || '').trim()
    if (!workerId) {
      return reply.code(400).send({ code: 'NO_WORKER_ID', message: 'Thiếu workerId.' })
    }
    const job = await dubJob.claimNextJob(workerId)
    if (!job) return { job: null }
    return {
      job: {
        jobId: job._id,
        inputPath: job.inputPath,
        outputPath: storage.outputKey(String(job._id)),
        sourceLang: job.sourceLang,
        targetLang: job.targetLang,
        voice: job.voice,
        bgMode: job.bgMode,
      },
    }
  })

  // --- Còn sống (giữa lúc xử lý dài — ASR+dịch+TTS+mux) --------------------
  fastify.post('/:jobId/heartbeat', async (request, reply) => {
    const workerId = String(request.body && request.body.workerId || '').trim()
    const ok = await dubJob.heartbeat(request.params.jobId, workerId)
    if (!ok) {
      return reply.code(409).send({ code: 'JOB_NOT_OWNED', message: 'Job không còn do worker này giữ.' })
    }
    return { ok: true }
  })

  // --- Tải file input về máy worker ----------------------------------------
  // Stream thẳng từ đĩa, không đọc hết vào RAM (video tới 300 MB).
  fastify.get('/:jobId/input', async (request, reply) => {
    const workerId = String(request.query.workerId || '').trim()
    const job = await dubJob.getRunningJobForWorker(request.params.jobId, workerId)
    if (!job) {
      return reply.code(409).send({ code: 'JOB_NOT_OWNED', message: 'Job không còn do worker này giữ.' })
    }
    const input = job.inputPath ? await storage.openRead(job.inputPath) : null
    if (!input) {
      return reply.code(404).send({ code: 'INPUT_NOT_FOUND', message: 'Không còn file input của job này.' })
    }
    reply.header('Content-Type', 'video/mp4')
    return reply.send(input)
  })

  // --- Nhận file kết quả từ worker ------------------------------------------
  // Ghi thẳng xuống đĩa theo stream (KHÔNG `toBuffer()` như route client ở
  // api-v1.js) — video kết quả cỡ trăm MB, giữ nguyên trong RAM sẽ thổi bay
  // container worker lẫn server.
  fastify.post('/:jobId/output', async (request, reply) => {
    const workerId = String(request.query.workerId || '').trim()
    const job = await dubJob.getRunningJobForWorker(request.params.jobId, workerId)
    if (!job) {
      return reply.code(409).send({ code: 'JOB_NOT_OWNED', message: 'Job không còn do worker này giữ.' })
    }

    const maxMb = Number(await config.get('cloud.dub.max.upload.mb')) || 300
    const data = await request.file({ limits: { fileSize: maxMb * 1024 * 1024 } })
    if (!data) {
      return reply.code(400).send({ code: 'NO_FILE', message: 'Thiếu file kết quả.' })
    }

    // V45: kết quả đi thẳng vào GridFS — đĩa container không sống qua
    // redeploy, mà đúng khoảng giữa "worker ghi xong" và "khách tải về" là
    // lúc mất file gây thiệt hại thật (khách đã bị trừ tiền).
    const key = storage.outputKey(request.params.jobId)
    await pipeline(data.file, await storage.openWrite(key))

    // @fastify/multipart cắt ngang khi quá hạn mức thay vì ném lỗi — file
    // lưu lại sẽ là bản CỤT. Phải tự kiểm và xoá, nếu không job sẽ "xong"
    // với video hỏng.
    if (data.file.truncated) {
      await storage.remove(key).catch(() => {})
      return reply.code(413).send({
        code: 'RESULT_TOO_LARGE', message: `File kết quả vượt quá ${maxMb} MB.`,
      })
    }

    return { ok: true, outputPath: key }
  })

  // --- Báo xong ------------------------------------------------------------
  fastify.post('/:jobId/complete', async (request, reply) => {
    const { workerId, outputPath, metrics } = request.body || {}
    if (!outputPath) {
      return reply.code(400).send({ code: 'BAD_RESULT', message: 'Thiếu outputPath.' })
    }
    const job = await dubJob.completeJob(request.params.jobId, String(workerId || ''), { outputPath, metrics })
    if (!job) {
      return reply.code(409).send({ code: 'JOB_NOT_OWNED', message: 'Job không còn do worker này giữ.' })
    }
    return { ok: true }
  })

  // --- Báo lỗi ---------------------------------------------------------------
  fastify.post('/:jobId/fail', async (request, reply) => {
    const { workerId, error } = request.body || {}
    const job = await dubJob.failJob(request.params.jobId, String(workerId || ''), error || 'Lỗi không rõ')
    if (!job) {
      return reply.code(409).send({ code: 'JOB_NOT_OWNED', message: 'Job không còn do worker này giữ.' })
    }
    return { ok: true }
  })
}
