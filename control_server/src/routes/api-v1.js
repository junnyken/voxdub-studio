'use strict'

/**
 * `/api/v1` — API dịch thuật công khai cho developer bên thứ 3 (mini-spec
 * V31, docs/PLAN.md Phase G).
 *
 * Phạm vi CHỦ ĐÍCH hẹp: CHỈ dịch văn bản (tái dùng
 * `gateway.translateSubtitleBatch()` đã có từ V14 — prompt ĐƠN GIẢN, không
 * gắn "video context" như luồng dub) — KHÔNG mở ASR/TTS/video (đó là hạ
 * tầng hoàn toàn khác, chưa tồn tại server-side, xem "Audit Before Build"
 * chung đầu Phase G trong docs/PLAN.md).
 *
 * Auth: API key (`requireApiKey`, tách hẳn `requireDevice` của `/v1/ai/*`)
 * — desktop app KHÔNG đụng route này, 0 regression cho `/v1/ai/*`.
 * Billing: `ApiKey.quota`/`ApiUsageLedger` — TÁCH HẲN `CreditLedger` của
 * desktop app (Constraint 3).
 */
const { requireApiKey } = require('../middleware/apikey.middleware')
const { QuotaExceededError, consumeQuota } = require('../services/api-key.service')
const gateway = require('../services/ai-gateway.service')
const config = require('../services/config.service')
const ApiKey = require('../models/ApiKey')

module.exports = async function apiV1Routes(fastify) {
  fastify.addHook('preHandler', requireApiKey)

  fastify.post('/translate', {
    config: { rateLimit: { max: 30, timeWindow: '1 minute' } },
    schema: {
      body: {
        type: 'object',
        required: ['sourceFlores', 'targetFlores', 'items'],
        properties: {
          sourceFlores: { type: 'string', pattern: '^[a-z]{3}_[A-Z][a-z]{3}$' },
          targetFlores: { type: 'string', pattern: '^[a-z]{3}_[A-Z][a-z]{3}$' },
          sourceName: { type: 'string', maxLength: 80 },
          targetName: { type: 'string', maxLength: 80 },
          items: {
            type: 'array',
            minItems: 1,
            items: {
              type: 'object',
              required: ['id', 'text'],
              properties: {
                id: { type: 'integer' },
                text: { type: 'string' },
              },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    const { apiKey } = request
    const { items, sourceFlores, targetFlores, sourceName, targetName } = request.body

    const cfg = await config.getMany([
      'ai.max.segments.per.request', 'ai.max.chars.per.segment', 'ai.max.retries',
    ])
    if (items.length > cfg['ai.max.segments.per.request']) {
      return reply.code(400).send({
        code: 'BATCH_TOO_LARGE',
        message: `Tối đa ${cfg['ai.max.segments.per.request']} dòng mỗi lượt.`,
        maxSegments: cfg['ai.max.segments.per.request'],
      })
    }
    const maxChars = cfg['ai.max.chars.per.segment']
    const tooLong = items.find((s) => String(s.text || '').length > maxChars)
    if (tooLong) {
      return reply.code(400).send({
        code: 'SEGMENT_TOO_LONG',
        message: `Dòng ${tooLong.id} dài quá ${maxChars} ký tự.`,
      })
    }

    // Kiểm nhanh (không atomic — chỉ để KHỎI gọi model tốn tiền khi đã rõ
    // hết quota; chặn THẬT SỰ vẫn là consumeQuota() atomic sau khi model
    // trả về, xử lý đúng race giữa nhiều request song song).
    const fresh = await ApiKey.findById(apiKey._id).lean()
    if (!fresh || fresh.usageCount >= fresh.quota) {
      return reply.code(429).send({
        code: 'QUOTA_EXCEEDED',
        message: `Đã dùng hết quota (${fresh ? fresh.usageCount : 0}/${fresh ? fresh.quota : 0}).`,
        quota: fresh ? fresh.quota : 0,
        usageCount: fresh ? fresh.usageCount : 0,
      })
    }

    let result
    try {
      result = await gateway.translateSubtitleBatch({
        items, sourceFlores, targetFlores, sourceName, targetName,
        maxRetries: cfg['ai.max.retries'],
      })
    } catch (err) {
      request.log.error({ err }, 'api-v1 translate failed')
      return reply.code(err.statusCode || 503).send({
        code: err.code || 'AI_UNAVAILABLE',
        message: 'Dịch vụ dịch tạm thời không phản hồi. Thử lại sau ít phút.',
        retryAfter: 30,
      })
    }

    // Trừ quota SAU khi model gọi thành công — lỗi model thì developer
    // không mất quota (cùng nguyên tắc "trừ credit sau" của /v1/ai/*).
    let updatedKey
    try {
      updatedKey = await consumeQuota(apiKey._id, {
        action: 'translate', ip: request.ip,
        metadata: { segments: result.segments.length },
      })
    } catch (err) {
      if (err instanceof QuotaExceededError) {
        return reply.code(429).send({
          code: 'QUOTA_EXCEEDED',
          message: err.message,
          quota: err.quota,
          usageCount: err.usageCount,
        })
      }
      throw err
    }

    return {
      segments: result.segments,
      quota: updatedKey.quota,
      usageCount: updatedKey.usageCount,
    }
  })
}
