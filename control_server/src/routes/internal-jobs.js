'use strict'

/**
 * `/internal/jobs` — API nội bộ cho worker Python (mini-spec V12, xem
 * docs/PLAN.md). KHÔNG dưới prefix `/v1` (không phải API public cho
 * thiết bị/website) — xác thực bằng `X-Worker-Token`
 * (`worker-auth.middleware.js`), tách hẳn khỏi token thiết bị.
 *
 * Node vẫn là chủ sở hữu DUY NHẤT của Mongo (đúng kiến trúc hiện có) —
 * worker Python không bao giờ chạm Mongo trực tiếp, chỉ gọi HTTP nội bộ
 * này. `render-job.service.js` giữ toàn bộ state machine.
 */
const renderJob = require('../services/render-job.service')

module.exports = async function internalJobsRoutes(fastify) {
  const { requireWorker } = require('../middleware/worker-auth.middleware')

  fastify.addHook('preHandler', requireWorker)

  // --- Nhận job kế tiếp (poll) --------------------------------------------
  fastify.post('/claim', async (request, reply) => {
    const workerId = String(request.body && request.body.workerId || '').trim()
    if (!workerId) {
      return reply.code(400).send({ code: 'NO_WORKER_ID', message: 'Thiếu workerId.' })
    }
    const job = await renderJob.claimNextJob(workerId)
    if (!job) return { job: null }
    const paths = renderJob.jobPaths(job._id)
    return {
      job: {
        jobId: job._id,
        stage: job.stage,
        inputPath: job.inputPath,
        vocalsPath: paths.vocals,
        noVocalsPath: paths.noVocals,
      },
    }
  })

  // --- Còn sống (giữa lúc xử lý dài) ---------------------------------------
  fastify.post('/:jobId/heartbeat', async (request, reply) => {
    const workerId = String(request.body && request.body.workerId || '').trim()
    const ok = await renderJob.heartbeat(request.params.jobId, workerId)
    if (!ok) {
      // Sweeper đã coi job này là chết (heartbeat quá trễ) và fail nó rồi —
      // worker nhận biết để dừng xử lý thay vì làm việc vô ích.
      return reply.code(409).send({ code: 'JOB_NOT_OWNED', message: 'Job không còn do worker này giữ.' })
    }
    return { ok: true }
  })

  // --- Báo xong ------------------------------------------------------------
  fastify.post('/:jobId/complete', async (request, reply) => {
    const { workerId, resultPaths } = request.body || {}
    if (!resultPaths || !resultPaths.vocals || !resultPaths.no_vocals) {
      return reply.code(400).send({ code: 'BAD_RESULT', message: 'Thiếu resultPaths.' })
    }
    const job = await renderJob.completeJob(request.params.jobId, String(workerId || ''), resultPaths)
    if (!job) {
      return reply.code(409).send({ code: 'JOB_NOT_OWNED', message: 'Job không còn do worker này giữ.' })
    }
    return { ok: true }
  })

  // --- Báo lỗi ---------------------------------------------------------------
  fastify.post('/:jobId/fail', async (request, reply) => {
    const { workerId, error } = request.body || {}
    const job = await renderJob.failJob(request.params.jobId, String(workerId || ''), error || 'Lỗi không rõ')
    if (!job) {
      return reply.code(409).send({ code: 'JOB_NOT_OWNED', message: 'Job không còn do worker này giữ.' })
    }
    return { ok: true }
  })
}
