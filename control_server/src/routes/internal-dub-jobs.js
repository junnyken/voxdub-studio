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
 */
const dubJob = require('../services/dub-job.service')

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
    const paths = dubJob.jobPaths(job._id)
    return {
      job: {
        jobId: job._id,
        inputPath: job.inputPath,
        outputPath: paths.output,
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
