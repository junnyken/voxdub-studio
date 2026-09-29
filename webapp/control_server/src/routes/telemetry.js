'use strict'

/**
 * `/v1/telemetry` — trạng thái tiến trình lồng tiếng (mini-spec V13, xem
 * docs/PLAN.md). Cần token thiết bị — `fingerprint` lấy từ token đã xác
 * thực (`requireDevice`), KHÔNG tin client tự khai báo fingerprint.
 *
 * Guardrail 2 (docs/PLAN.md mục V13): event CHỈ được chứa đúng 4 field
 * (runId/status/stage/errorStage) — field lạ (nội dung) bị TỪ CHỐI 400,
 * KHÔNG âm thầm bỏ qua. Đây là ranh giới thật chặn nội dung nhạy cảm lọt
 * vào hệ thống telemetry, không chỉ là quy ước phía client.
 */
const telemetry = require('../services/telemetry.service')

const ALLOWED_KEYS = new Set(['runId', 'status', 'stage', 'errorStage'])

module.exports = async function telemetryRoutes(fastify) {
  const { requireDevice } = require('../middleware/auth.middleware')
  fastify.addHook('preHandler', requireDevice)

  fastify.post('/pipeline-event', {
    config: { rateLimit: { max: 60, timeWindow: '1 minute' } },
  }, async (request, reply) => {
    const body = request.body || {}
    const extraKeys = Object.keys(body).filter((k) => !ALLOWED_KEYS.has(k))
    if (extraKeys.length) {
      return reply.code(400).send({
        code: 'FORBIDDEN_FIELD',
        message: `Event không được chứa field: ${extraKeys.join(', ')}. `
          + 'Telemetry chỉ nhận runId/status/stage/errorStage, không bao giờ nội dung.',
      })
    }
    const { runId, status, stage, errorStage } = body
    if (!runId || typeof runId !== 'string' || runId.length > 100) {
      return reply.code(400).send({ code: 'BAD_RUN_ID', message: 'runId không hợp lệ.' })
    }
    try {
      await telemetry.recordEvent({
        fingerprint: request.device.fingerprint, runId, status, stage, errorStage,
      })
    } catch (err) {
      if (err instanceof telemetry.TelemetryError) {
        return reply.code(400).send({ code: err.code, message: err.message })
      }
      throw err
    }
    return { ok: true }
  })
}
