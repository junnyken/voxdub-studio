'use strict'

/**
 * Xác thực API key bên thứ 3 trên `/api/v1/*` (mini-spec V31, docs/PLAN.md
 * Phase G) — lớp identity THỨ 2, SONG SONG với `auth.middleware.js`
 * (device-fingerprint của app desktop), KHÔNG thay thế. Route nào dùng
 * middleware nào tách rõ theo prefix (`/v1/ai/*` dùng `requireDevice`,
 * `/api/v1/*` dùng `requireApiKey`) — không gộp logic 2 loại xác thực.
 *
 * `request.apiKey` được gắn sẵn cho các handler phía sau (cùng khuôn
 * `request.device` của `auth.middleware.js`).
 */
const { findByPlaintext } = require('../services/api-key.service')

async function requireApiKey(request, reply) {
  const header = request.headers.authorization || ''
  const key = header.startsWith('Bearer ') ? header.slice(7).trim() : ''
  if (!key) {
    return reply.code(401).send({ code: 'NO_API_KEY', message: 'Thiếu API key.' })
  }

  const apiKey = await findByPlaintext(key)
  if (!apiKey) {
    return reply.code(401).send({ code: 'BAD_API_KEY', message: 'API key không hợp lệ.' })
  }
  if (apiKey.status === 'revoked') {
    return reply.code(403).send({ code: 'API_KEY_REVOKED', message: 'API key đã bị thu hồi.' })
  }

  request.apiKey = apiKey
}

module.exports = { requireApiKey }
