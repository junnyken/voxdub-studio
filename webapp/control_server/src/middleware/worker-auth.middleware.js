'use strict'

/**
 * Cổng worker nội bộ (mini-spec V12, docs/PLAN.md) — một secret riêng
 * (`WORKER_INTERNAL_TOKEN`) tách hẳn khỏi token thiết bị VÀ khỏi
 * `ADMIN_TOKEN`, đúng nguyên tắc của `admin.middleware.js`. Route
 * `/internal/jobs/*` chỉ dành cho container worker Python trong cùng mạng
 * compose gọi tới — KHÔNG bao giờ lộ ra client thiết bị/website.
 */
const { safeEqual } = require('../utils/crypto')

async function requireWorker(request, reply) {
  const expected = (process.env.WORKER_INTERNAL_TOKEN || '').trim()
  if (!expected) {
    return reply.code(503).send({
      code: 'WORKER_DISABLED',
      message: 'Server chưa đặt WORKER_INTERNAL_TOKEN — cloud rendering không hoạt động.',
    })
  }
  const given = String(request.headers['x-worker-token'] || '')
  if (!safeEqual(given, expected)) {
    request.log.warn({ ip: request.ip, url: request.url }, 'worker auth fail')
    return reply.code(401).send({ code: 'BAD_WORKER_TOKEN', message: 'Sai token worker.' })
  }
}

module.exports = { requireWorker }
