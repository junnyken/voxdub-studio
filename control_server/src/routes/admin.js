'use strict'

/**
 * `/v1/admin` — quản trị. Yêu cầu header `X-Admin-Token`.
 *
 * Mọi hành động làm thay đổi tiền hay quyền đều ghi AuditLog trước khi trả
 * lời: nếu sau này có tranh cãi "ai đã cộng credit cho máy này", nhật ký là
 * thứ duy nhất trả lời được.
 */
const { createGzip } = require('node:zlib')
const { Readable } = require('node:stream')
const { pipeline: pipelineStream } = require('node:stream/promises')

const mongoose = require('mongoose')

const Device = require('../models/Device')
const ActivationKey = require('../models/ActivationKey')
const Order = require('../models/Order')
const AiProvider = require('../models/AiProvider')
const UsageLog = require('../models/UsageLog')
const AuditLog = require('../models/AuditLog')
const CreditLedger = require('../models/CreditLedger')
const ApiKey = require('../models/ApiKey')

const credit = require('../services/credit.service')
const config = require('../services/config.service')
const activation = require('../services/activation.service')
const gateway = require('../services/ai-gateway.service')
const audit = require('../services/audit.service')
const holdService = require('../services/hold.service')
const backup = require('../services/backup.service')
const storage = require('../services/job-storage.service')
const { createApiKey } = require('../services/api-key.service')
const { encrypt } = require('../utils/crypto')

module.exports = async function adminRoutes(fastify) {
  const { requireAdmin } = require('../middleware/admin.middleware')

  fastify.addHook('preHandler', requireAdmin)

  /**
   * Kiểm tra token — trang đăng nhập admin gọi để biết token đúng hay không.
   *
   * Không có endpoint này thì trang login phải gọi bừa một route dữ liệu và
   * đoán ý nghĩa của mã lỗi. Rate limit chặt vì đây chính là điểm để dò token.
   */
  fastify.get('/whoami', {
    config: { rateLimit: { max: 10, timeWindow: '1 minute' } },
  }, async () => ({ ok: true, serverVersion: '3.0.0' }))

  // ---------------------------------------------------------- thiết bị ---
  fastify.get('/devices', async (request) => {
    const { search = '', status = '', page = 1, limit = 20 } = request.query
    const filter = {}
    if (status) filter.status = status
    if (search) {
      filter.$or = [
        { fingerprint: new RegExp(escapeRe(search), 'i') },
        { name: new RegExp(escapeRe(search), 'i') },
        { contactEmail: new RegExp(escapeRe(search), 'i') },
      ]
    }
    const skip = (Math.max(1, Number(page)) - 1) * Number(limit)
    const [data, total] = await Promise.all([
      Device.find(filter).sort({ lastSeenAt: -1 }).skip(skip).limit(Number(limit)).lean(),
      Device.countDocuments(filter),
    ])
    return { total, page: Number(page), data }
  })

  fastify.get('/devices/:fingerprint', async (request, reply) => {
    const device = await Device.findOne({ fingerprint: request.params.fingerprint }).lean()
    if (!device) return reply.code(404).send({ code: 'NOT_FOUND' })
    const [ledger, usage, keys] = await Promise.all([
      CreditLedger.find({ fingerprint: device.fingerprint })
        .sort({ createdAt: -1 }).limit(50).lean(),
      UsageLog.find({ fingerprint: device.fingerprint })
        .sort({ createdAt: -1 }).limit(50).lean(),
      ActivationKey.find({ usedByFingerprint: device.fingerprint })
        .sort({ usedAt: -1 }).lean(),
    ])
    return { device, ledger, usage, keys }
  })

  fastify.patch('/devices/:fingerprint/status', {
    schema: {
      body: {
        type: 'object',
        required: ['status'],
        properties: {
          status: { type: 'string', enum: ['active', 'blocked'] },
          reason: { type: 'string', maxLength: 500 },
        },
      },
    },
  }, async (request, reply) => {
    const { status, reason = '' } = request.body
    const device = await Device.findOne({ fingerprint: request.params.fingerprint })
    if (!device) return reply.code(404).send({ code: 'NOT_FOUND' })

    const before = { status: device.status, blockedReason: device.blockedReason }
    device.status = status
    device.blockedReason = status === 'blocked' ? reason : ''
    // Khóa máy = thu hồi mọi token đã cấp, có hiệu lực ngay lập tức.
    if (status === 'blocked') device.tokenVersion += 1
    await device.save()

    await audit.log({
      action: 'admin.device.status',
      target: device.fingerprint,
      before,
      after: { status, blockedReason: device.blockedReason },
      ip: request.ip,
      note: reason,
    })
    return { ok: true, device: { fingerprint: device.fingerprint, status: device.status } }
  })

  fastify.post('/devices/:fingerprint/credit', {
    schema: {
      body: {
        type: 'object',
        required: ['delta', 'reason'],
        properties: {
          delta: { type: 'integer' },
          reason: { type: 'string', minLength: 1, maxLength: 500 },
        },
      },
    },
  }, async (request, reply) => {
    const { delta, reason } = request.body
    const fingerprint = request.params.fingerprint
    if (delta === 0) return reply.code(400).send({ code: 'ZERO_DELTA' })

    const device = await Device.findOne({ fingerprint })
    if (!device) return reply.code(404).send({ code: 'NOT_FOUND' })

    // Khóa idempotency phải là duy nhất cho mỗi lần admin bấm, khác với các
    // luồng tự động (ở đó khóa gắn với jobId/orderCode).
    const key = `admin-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    try {
      const result = delta > 0
        ? await credit.grant(fingerprint, delta, {
          type: 'admin_grant', idempotencyKey: key, description: reason,
        })
        : await credit.deduct(fingerprint, -delta, {
          type: 'admin_deduct', idempotencyKey: key, description: reason,
        })
      await audit.log({
        action: delta > 0 ? 'admin.credit.grant' : 'admin.credit.deduct',
        target: fingerprint,
        before: { balance: device.balance },
        after: { balance: result.balanceAfter, delta },
        ip: request.ip,
        note: reason,
      })
      return { ok: true, balanceAfter: result.balanceAfter }
    } catch (err) {
      if (err.code === 'INSUFFICIENT_CREDIT') {
        return reply.code(400).send({ code: err.code, message: err.message, balance: err.balance })
      }
      throw err
    }
  })

  /**
   * Chuyển toàn bộ credit sang máy mới (người dùng đổi/hỏng máy).
   *
   * Đây là ngoại lệ DUY NHẤT với quy tắc "credit thuộc về thiết bị" — và nó
   * đi qua tay admin, có nhật ký, chứ không phải một nút tự phục vụ.
   */
  fastify.post('/devices/:fingerprint/transfer', {
    schema: {
      body: {
        type: 'object',
        required: ['toFingerprint', 'reason'],
        properties: {
          toFingerprint: { type: 'string', minLength: 64, maxLength: 64 },
          reason: { type: 'string', minLength: 1, maxLength: 500 },
        },
      },
    },
  }, async (request, reply) => {
    const from = request.params.fingerprint
    const { toFingerprint: to, reason } = request.body
    if (from === to) return reply.code(400).send({ code: 'SAME_DEVICE' })

    const [src, dst] = await Promise.all([
      Device.findOne({ fingerprint: from }),
      Device.findOne({ fingerprint: to }),
    ])
    if (!src) return reply.code(404).send({ code: 'SOURCE_NOT_FOUND' })
    if (!dst) return reply.code(404).send({ code: 'TARGET_NOT_FOUND', message: 'Máy mới chưa mở app lần nào.' })
    if (src.balance <= 0) return reply.code(400).send({ code: 'EMPTY_WALLET' })

    const amount = src.balance
    const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    // Trừ trước rồi mới cộng: thứ tự này bảo đảm không bao giờ nhân đôi tiền
    // nếu server chết giữa chừng (tệ nhất là mất, và nhật ký chỉ ra ngay).
    await credit.deduct(from, amount, {
      type: 'transfer_out',
      idempotencyKey: `transfer-out-${stamp}`,
      description: `Chuyển ${amount} Vox sang máy ${to.slice(0, 12)}…`,
    })
    const result = await credit.grant(to, amount, {
      type: 'transfer_in',
      idempotencyKey: `transfer-in-${stamp}`,
      description: `Nhận ${amount} Vox từ máy ${from.slice(0, 12)}…`,
    })
    // Máy cũ coi như bỏ: khóa lại để không ai dùng tiếp bằng token cũ.
    src.status = 'blocked'
    src.blockedReason = 'Đã chuyển credit sang thiết bị khác'
    src.tokenVersion += 1
    await src.save()

    await audit.log({
      action: 'admin.credit.transfer',
      target: from,
      after: { to, amount, balanceAfter: result.balanceAfter },
      ip: request.ip,
      note: reason,
    })
    return { ok: true, amount, toBalance: result.balanceAfter }
  })

  // ---------------------------------------------------------------- key --
  fastify.get('/keys', async (request) => {
    const {
      status = '', code = '', note = '', page = 1, limit = 20,
    } = request.query
    const filter = {}
    if (status) filter.status = status
    if (code) filter.code = new RegExp(escapeRe(code.toUpperCase()), 'i')
    if (note) filter.note = new RegExp(escapeRe(note), 'i')
    const skip = (Math.max(1, Number(page)) - 1) * Number(limit)
    const [data, total] = await Promise.all([
      ActivationKey.find(filter).sort({ createdAt: -1 }).skip(skip).limit(Number(limit)).lean(),
      ActivationKey.countDocuments(filter),
    ])
    return { total, page: Number(page), data }
  })

  /** Phát key tay — bồi thường sự cố, tặng KOL, bán ngoài luồng. */
  fastify.post('/keys', {
    schema: {
      body: {
        type: 'object',
        required: ['vox'],
        properties: {
          vox: { type: 'integer', minimum: 1 },
          count: { type: 'integer', minimum: 1, maximum: 100, default: 1 },
          note: { type: 'string', maxLength: 300 },
        },
      },
    },
  }, async (request) => {
    const { vox, count = 1, note = '' } = request.body
    const keys = []
    for (let i = 0; i < count; i += 1) {
      const key = await activation.issueKey({ vox, source: 'admin', note })
      keys.push({ code: key.code, vox: key.vox })
    }
    await audit.log({
      action: 'admin.key.issue',
      after: { count, vox, codes: keys.map((k) => k.code) },
      ip: request.ip,
      note,
    })
    return { ok: true, keys }
  })

  fastify.delete('/keys/:code', async (request, reply) => {
    const code = String(request.params.code).toUpperCase()
    const key = await ActivationKey.findOne({ code })
    if (!key) return reply.code(404).send({ code: 'NOT_FOUND' })
    if (key.status === 'used') {
      return reply.code(409).send({
        code: 'KEY_ALREADY_USED',
        message: 'Mã đã được kích hoạt — không thu hồi được. Trừ credit của thiết bị nếu cần.',
      })
    }
    key.status = 'revoked'
    key.revokedAt = new Date()
    await key.save()
    await audit.log({ action: 'admin.key.revoke', target: code, ip: request.ip })
    return { ok: true }
  })

  // ------------------------------------------------------------ đơn hàng --
  fastify.get('/orders', async (request) => {
    const { status = '', orderCode = '', page = 1, limit = 20 } = request.query
    const filter = {}
    if (status) filter.status = status
    if (orderCode) filter.orderCode = String(orderCode).toUpperCase()
    const skip = (Math.max(1, Number(page)) - 1) * Number(limit)
    const [data, total] = await Promise.all([
      // `-accessToken`: bí mật của trình duyệt người mua, admin không cần
      // thấy và không nên thấy (giảm bề mặt rò rỉ qua log/màn hình).
      Order.find(filter).select('-accessToken')
        .sort({ createdAt: -1 }).skip(skip).limit(Number(limit)).lean(),
      Order.countDocuments(filter),
    ])
    return { total, page: Number(page), data }
  })

  // ---------------------------------------------------------- hold Vox ----
  // Hỗ trợ khách: xem hold đang treo/đã chốt (không lộ khóa giải mã).
  fastify.get('/holds', async (request) => {
    const { status = '', page = 1, limit = 50 } = request.query
    return holdService.listHolds({
      status: status || undefined,
      page: Math.max(1, Number(page)),
      limit: Math.min(200, Math.max(1, Number(limit))),
    })
  })

  // ------------------------------------------------------------ đối soát ---
  // Ví ↔ sổ cái: chạy tay khi nghi ngờ, timer trong server.js chạy hằng ngày.
  fastify.get('/reconcile', async () => {
    const credit = require('../services/credit.service')
    return credit.reconcile()
  })

  /** Duyệt tay một đơn (webhook PayOS lỗi / gián đoạn — lối thoát hỗ trợ). */
  fastify.post('/orders/:orderCode/approve', {
    schema: {
      body: {
        type: 'object',
        properties: { note: { type: 'string', maxLength: 300 } },
      },
    },
  }, async (request, reply) => {
    const orderCode = String(request.params.orderCode).toUpperCase()
    const order = await Order.findOne({ orderCode })
    if (!order) return reply.code(404).send({ code: 'NOT_FOUND' })
    if (order.status === 'paid') {
      return { ok: true, keyCode: order.keyCode, alreadyPaid: true }
    }

    const claimed = await Order.findOneAndUpdate(
      { orderCode, status: { $in: ['pending', 'expired'] } },
      { $set: { status: 'paid', paidAt: new Date(), bankGateway: 'manual' } },
      { new: true },
    )
    if (!claimed) {
      const fresh = await Order.findOne({ orderCode })
      return { ok: true, keyCode: fresh.keyCode, alreadyPaid: true }
    }
    const key = await activation.issueKey({
      vox: claimed.vox,
      source: 'order',
      orderId: claimed._id,
      packageId: claimed.packageId,
      amountVnd: claimed.amountVnd,
      note: request.body.note || 'Duyệt tay',
    })
    claimed.keyCode = key.code
    await claimed.save()

    await audit.log({
      action: 'admin.order.approve',
      target: orderCode,
      after: { keyCode: key.code, vox: claimed.vox },
      ip: request.ip,
      note: request.body.note || '',
    })
    if (claimed.email) {
      require('../services/email.service').sendActivationKey({
        to: claimed.email,
        keyCode: key.code,
        vox: claimed.vox,
        orderCode,
        amountVnd: claimed.amountVnd,
      }).catch(() => {})
    }
    return { ok: true, keyCode: key.code }
  })

  // ------------------------------------------------------------- config --
  fastify.get('/config', async () => ({ items: await config.all() }))

  fastify.put('/config/:key', {
    schema: {
      body: {
        type: 'object',
        required: ['value'],
        properties: { value: {} },
      },
    },
  }, async (request) => {
    const key = request.params.key
    const before = await config.get(key)
    await config.set(key, request.body.value)
    await audit.log({
      action: 'admin.config.update',
      target: key,
      before: { value: before },
      after: { value: request.body.value },
      ip: request.ip,
    })
    return { ok: true, key, value: request.body.value }
  })

  // ----------------------------------------------------------- provider --
  fastify.get('/providers', async () => {
    const list = await AiProvider.find({}).sort({ role: 1, priority: 1 }).lean()
    // apiKeyEnc không bao giờ rời server, kể cả với admin — chỉ báo có/không.
    return {
      data: list.map(({ apiKeyEnc, ...rest }) => ({ ...rest, hasApiKey: Boolean(apiKeyEnc) })),
    }
  })

  fastify.post('/providers', {
    schema: {
      body: {
        type: 'object',
        required: ['name', 'model'],
        properties: {
          name: { type: 'string', minLength: 1, maxLength: 60 },
          label: { type: 'string', maxLength: 120 },
          role: { type: 'string', enum: ['translate', 'content'], default: 'translate' },
          type: { type: 'string', enum: ['openai_compat', 'google'], default: 'openai_compat' },
          baseUrl: { type: 'string', maxLength: 300 },
          apiKey: { type: 'string', maxLength: 400 },
          model: { type: 'string', minLength: 1, maxLength: 120 },
          temperature: { type: 'number', minimum: 0, maximum: 2, default: 0.3 },
          maxTokens: { type: 'integer', minimum: 256, maximum: 200000, default: 16384 },
          priority: { type: 'integer', default: 100 },
          enabled: { type: 'boolean', default: true },
          timeoutMs: { type: 'integer', minimum: 5000, maximum: 600000, default: 180000 },
        },
      },
    },
  }, async (request, reply) => {
    const { apiKey, ...rest } = request.body
    try {
      const doc = await AiProvider.create({ ...rest, apiKeyEnc: encrypt(apiKey || '') })
      gateway.invalidateProviders()
      await audit.log({
        action: 'admin.provider.create',
        target: doc.name,
        after: { model: doc.model, role: doc.role },
        ip: request.ip,
      })
      return { ok: true, id: doc._id, name: doc.name }
    } catch (err) {
      if (err.code === 11000) {
        return reply.code(409).send({ code: 'DUPLICATE_NAME', message: 'Tên provider đã tồn tại.' })
      }
      throw err
    }
  })

  fastify.patch('/providers/:id', async (request, reply) => {
    const { apiKey, ...rest } = request.body || {}
    const update = { ...rest }
    // apiKey rỗng = giữ nguyên key cũ. Không có quy ước này thì mỗi lần sửa
    // model là vô tình xóa mất API key.
    if (apiKey) update.apiKeyEnc = encrypt(apiKey)
    delete update.apiKeyEnc_

    const doc = await AiProvider.findByIdAndUpdate(request.params.id, { $set: update }, { new: true })
    if (!doc) return reply.code(404).send({ code: 'NOT_FOUND' })
    gateway.invalidateProviders()
    await audit.log({
      action: 'admin.provider.update',
      target: doc.name,
      after: { ...rest },
      ip: request.ip,
    })
    return { ok: true }
  })

  fastify.delete('/providers/:id', async (request, reply) => {
    const doc = await AiProvider.findByIdAndDelete(request.params.id)
    if (!doc) return reply.code(404).send({ code: 'NOT_FOUND' })
    gateway.invalidateProviders()
    await audit.log({ action: 'admin.provider.delete', target: doc.name, ip: request.ip })
    return { ok: true }
  })

  // ---------------------------------------------------------- analytics --
  fastify.get('/analytics/overview', async (request) => {
    const days = Math.min(90, Math.max(1, Number(request.query.days) || 7))
    const since = new Date(Date.now() - days * 24 * 3600_000)

    const [revenue, orders, devices, newDevices, activeDevices, ledger, usage, keys] =
      await Promise.all([
        Order.aggregate([
          { $match: { status: 'paid', paidAt: { $gte: since } } },
          { $group: { _id: null, total: { $sum: '$amountVnd' }, count: { $sum: 1 } } },
        ]),
        Order.aggregate([
          { $match: { createdAt: { $gte: since } } },
          { $group: { _id: '$status', count: { $sum: 1 } } },
        ]),
        Device.countDocuments({}),
        Device.countDocuments({ createdAt: { $gte: since } }),
        Device.countDocuments({ lastSeenAt: { $gte: since } }),
        CreditLedger.aggregate([
          { $match: { createdAt: { $gte: since } } },
          {
            $group: {
              _id: null,
              issued: { $sum: { $cond: [{ $gt: ['$delta', 0] }, '$delta', 0] } },
              consumed: { $sum: { $cond: [{ $lt: ['$delta', 0] }, { $abs: '$delta' }, 0] } },
            },
          },
        ]),
        UsageLog.aggregate([
          { $match: { createdAt: { $gte: since } } },
          {
            $group: {
              _id: '$status',
              requests: { $sum: 1 },
              sentences: { $sum: '$inputSize' },
              promptTokens: { $sum: '$promptTokens' },
              completionTokens: { $sum: '$completionTokens' },
            },
          },
        ]),
        ActivationKey.aggregate([
          { $group: { _id: '$status', count: { $sum: 1 }, vox: { $sum: '$vox' } } },
        ]),
      ])

    const outstanding = await Device.aggregate([
      { $group: { _id: null, total: { $sum: '$balance' } } },
    ])

    return {
      days,
      revenue: {
        vnd: revenue[0] ? revenue[0].total : 0,
        paidOrders: revenue[0] ? revenue[0].count : 0,
      },
      orders: Object.fromEntries(orders.map((o) => [o._id, o.count])),
      devices: { total: devices, new: newDevices, active: activeDevices },
      credit: {
        issued: ledger[0] ? ledger[0].issued : 0,
        consumed: ledger[0] ? ledger[0].consumed : 0,
        outstanding: outstanding[0] ? outstanding[0].total : 0,
      },
      ai: Object.fromEntries(usage.map((u) => [u._id, {
        requests: u.requests,
        sentences: u.sentences,
        promptTokens: u.promptTokens,
        completionTokens: u.completionTokens,
      }])),
      keys: Object.fromEntries(keys.map((k) => [k._id, { count: k.count, vox: k.vox }])),
    }
  })

  fastify.get('/analytics/usage', async (request) => {
    const days = Math.min(90, Math.max(1, Number(request.query.days) || 14))
    const since = new Date(Date.now() - days * 24 * 3600_000)
    const data = await UsageLog.aggregate([
      { $match: { createdAt: { $gte: since } } },
      {
        $group: {
          _id: {
            date: { $dateToString: { format: '%Y-%m-%d', date: '$createdAt' } },
            action: '$action',
          },
          requests: { $sum: 1 },
          sentences: { $sum: '$inputSize' },
          credit: { $sum: '$creditCharged' },
          promptTokens: { $sum: '$promptTokens' },
          completionTokens: { $sum: '$completionTokens' },
        },
      },
      { $sort: { '_id.date': 1 } },
    ])
    return { days, data }
  })

  // Mini-spec V10 (docs/PLAN.md) — retention cohort theo tuần, dùng lại
  // Device.firstSeenAt/lastSeenAt đã có sẵn (không thu thập gì mới).
  // Mini-spec V89 giai đoạn 3 — bảng theo dõi cổng trợ lý. `analytics/usage`
  // gộp theo `action`, mà mọi lượt trợ lý đều mang action 'assist', nên
  // không tách được việc nào tốn nhất. Đây là chỗ trả lời đúng ba câu đã hứa
  // trong bản kế hoạch: tốn bao nhiêu, việc nào tốn nhất, mô hình nào hay hỏng.
  fastify.get('/analytics/assist', async (request) => {
    const stats = require('../services/assist-stats.service')
    const days = Math.min(90, Math.max(1, Number(request.query.days) || 7))
    const [theoTacVu, theoMoHinh, theoVaiTro, maLoi, cfg] = await Promise.all([
      UsageLog.aggregate(stats.theoTacVu(days)),
      UsageLog.aggregate(stats.theoMoHinh(days)),
      UsageLog.aggregate(stats.theoVaiTro(days)),
      UsageLog.aggregate(stats.theoMaLoi(days)),
      config.getMany(['credit.vox.to.vnd', 'assist.daily.limit']),
    ])
    // Còn lượt nào chạy bằng vai "translate" nghĩa là chưa cấu hình vai
    // "assist" — đắt hơn nhiều lần mà không ai để ý.
    const dungChungVaiDich = theoVaiTro.some((r) => r.vai === 'translate')
    return {
      days,
      tomTat: stats.tomTat(theoTacVu, cfg['credit.vox.to.vnd']),
      tacVu: theoTacVu,
      moHinh: theoMoHinh,
      maLoi,
      vaiTro: theoVaiTro,
      dungChungVaiDich,
      hanMucNgay: cfg['assist.daily.limit'],
    }
  })

  fastify.get('/analytics/retention', async (request) => {
    const weeks = Math.min(26, Math.max(1, Number(request.query.weeks) || 8))
    const { computeWeeklyRetention } = require('../services/retention.service')
    const devices = await Device.find({}, { firstSeenAt: 1, lastSeenAt: 1 }).lean()
    return { weeks, cohorts: computeWeeklyRetention(devices, weeks, new Date()) }
  })

  // Mini-spec V13 (docs/PLAN.md) — phễu hoàn thành/bỏ dở theo stage, dữ
  // liệu thật từ PipelineEvent (autodub.telemetry, chỉ ghi ở chế độ SaaS).
  fastify.get('/analytics/pipeline-funnel', async (request) => {
    const days = Math.min(90, Math.max(1, Number(request.query.days) || 7))
    const staleHours = Math.min(72, Math.max(1, Number(request.query.staleHours) || 6))
    const telemetry = require('../services/telemetry.service')
    return telemetry.overview(days, staleHours)
  })

  fastify.get('/audit-log', async (request) => {
    const { action = '', target = '', page = 1, limit = 50 } = request.query
    const filter = {}
    if (action) filter.action = new RegExp(escapeRe(action), 'i')
    if (target) filter.target = new RegExp(escapeRe(target), 'i')
    const skip = (Math.max(1, Number(page)) - 1) * Number(limit)
    const [data, total] = await Promise.all([
      AuditLog.find(filter).sort({ createdAt: -1 }).skip(skip).limit(Number(limit)).lean(),
      AuditLog.countDocuments(filter),
    ])
    return { total, page: Number(page), data }
  })

  // -------------------------------------------- API key developer (V31) --
  // Đặt tên "/api-keys" (khác "/keys" ở trên — đó là ActivationKey, mã kích
  // hoạt Vox, KHÔNG liên quan) để tránh nhầm 2 khái niệm hoàn toàn khác
  // nhau. Mini-spec V31 (docs/PLAN.md, Phase G) — "thủ công qua admin lúc
  // đầu, chưa cần self-service portal".
  fastify.get('/api-keys', async (request) => {
    const { status = '', page = 1, limit = 20 } = request.query
    const filter = {}
    if (status) filter.status = status
    const skip = (Math.max(1, Number(page)) - 1) * Number(limit)
    const [data, total] = await Promise.all([
      ApiKey.find(filter).sort({ createdAt: -1 }).skip(skip).limit(Number(limit))
        .select('-keyHash').lean(),
      ApiKey.countDocuments(filter),
    ])
    return { total, page: Number(page), data }
  })

  /** Tạo API key mới — plaintext CHỈ trả về đúng 1 LẦN, không đọc lại được sau. */
  fastify.post('/api-keys', {
    schema: {
      body: {
        type: 'object',
        required: ['orgName'],
        properties: {
          orgName: { type: 'string', minLength: 1, maxLength: 200 },
          contactEmail: { type: 'string', maxLength: 200, default: '' },
          quota: { type: 'integer', minimum: 1, default: 1000 },
          // Mini-spec V34b — quota phút lồng tiếng, TÁCH HẲN `quota` ở trên
          // (đó là lượt gọi dịch văn bản V31). Mặc định 0 = opt-in, admin
          // phải chủ động điền > 0 mới bật được API dub cho key này.
          dubMinutesQuota: { type: 'integer', minimum: 0, default: 0 },
        },
      },
    },
  }, async (request) => {
    const { orgName, contactEmail = '', quota = 1000, dubMinutesQuota = 0 } = request.body
    const { plaintext, doc } = await createApiKey({
      orgName, contactEmail, quota, dubMinutesQuota, createdIp: request.ip,
    })
    await audit.log({
      action: 'admin.apikey.create',
      target: String(doc._id),
      after: { orgName, quota, dubMinutesQuota },
      ip: request.ip,
    })
    return { ok: true, apiKey: plaintext, id: doc._id, keyPrefix: doc.keyPrefix }
  })

  /** Cấp/chỉnh quota phút lồng tiếng cho key ĐÃ TỒN TẠI (mini-spec V34b) —
   * tính năng dub là opt-in, key tạo trước V34b luôn có dubMinutesQuota=0,
   * cần đường này để admin bật lên mà không phải tạo lại key (mất plaintext
   * cũ, phá vỡ tích hợp phía developer). CHỈ đổi hạn mức, KHÔNG đụng
   * `dubMinutesUsed` (lịch sử đã dùng giữ nguyên khi tăng/giảm hạn mức). */
  fastify.patch('/api-keys/:id/dub-quota', {
    schema: {
      body: {
        type: 'object',
        required: ['dubMinutesQuota'],
        properties: {
          dubMinutesQuota: { type: 'integer', minimum: 0 },
        },
      },
    },
  }, async (request, reply) => {
    const { dubMinutesQuota } = request.body
    const key = await ApiKey.findByIdAndUpdate(
      request.params.id, { $set: { dubMinutesQuota } }, { new: true },
    ).select('-keyHash')
    if (!key) return reply.code(404).send({ code: 'NOT_FOUND' })
    await audit.log({
      action: 'admin.apikey.dub_quota_update',
      target: String(key._id),
      after: { dubMinutesQuota },
      ip: request.ip,
    })
    return { ok: true, id: key._id, dubMinutesQuota: key.dubMinutesQuota, dubMinutesUsed: key.dubMinutesUsed }
  })

  fastify.delete('/api-keys/:id', async (request, reply) => {
    const key = await ApiKey.findById(request.params.id)
    if (!key) return reply.code(404).send({ code: 'NOT_FOUND' })
    key.status = 'revoked'
    await key.save()
    await audit.log({
      action: 'admin.apikey.revoke', target: String(key._id), ip: request.ip,
    })
    return { ok: true }
  })

  // ---------------------------------------------------- dung lượng kho ---
  /**
   * Dung lượng kho file job (mini-spec V50). Từ V45 video nằm TRONG database
   * (GridFS) — tiện vì bền vững qua redeploy, nhưng cũng nghĩa là DB phình
   * theo lượng job. Không có chỗ nhìn thì chỉ phát hiện khi hết dung lượng.
   *
   * `orphanFiles` > 0 nghĩa là có file không còn job nào trỏ tới — sweeper
   * sót việc, cần xem log; đây là con số đáng theo dõi hơn cả tổng dung lượng.
   */
  fastify.get('/storage', async () => {
    const s = await storage.stats()
    const warnMb = Number(await config.get('storage.warn.mb')) || 2048
    return {
      ...s,
      warnMb,
      overWarnThreshold: s.totalMb > warnMb,
    }
  })

  // ------------------------------------------------------- sao lưu DB ---
  /**
   * Tải toàn bộ dữ liệu về máy người gọi (mini-spec V48).
   *
   * Đây là đường sao lưu KHÔNG phụ thuộc nền tảng: cơ chế backup hàng ngày
   * cũ là tính năng của Coolify, chuyển sang Vibe Host là mất; nền tảng mới
   * không có volume bền vững nên dump ra đĩa trong container cũng vô nghĩa
   * (bay theo lần redeploy kế tiếp). Cách trung thực duy nhất là stream ra
   * ngoài để người gọi tự cất giữ ở nơi sống lâu hơn container.
   *
   * Rate limit chặt: đây là endpoint đọc TOÀN BỘ dữ liệu, không phải thứ
   * cần gọi nhiều lần một phút, và siết lại thì dò/lạm dụng cũng chậm theo.
   */
  fastify.get('/backup', {
    config: { rateLimit: { max: 3, timeWindow: '1 minute' } },
  }, async (request, reply) => {
    const stamp = new Date().toISOString().replace(/[:.]/g, '-')
    await audit.log({
      action: 'admin.backup.export',
      target: mongoose.connection?.db?.databaseName || 'unknown',
      ip: request.ip,
    })

    reply
      .header('content-type', 'application/gzip')
      .header('content-disposition', `attachment; filename="voxdub-backup-${stamp}.ndjson.gz"`)

    // Nén ngay trên đường ra, không dựng file tạm: vừa không cần đĩa (nền
    // tảng không có volume), vừa giữ bộ nhớ phẳng theo đúng nguyên tắc V44.
    const gzip = createGzip()
    pipelineStream(Readable.from(backup.exportLines()), gzip).catch((err) => {
      request.log.error({ err }, 'backup export hỏng giữa chừng')
      gzip.destroy(err)
    })
    return reply.send(gzip)
  })
}

/** Thoát ký tự đặc biệt trước khi nhét chuỗi tìm kiếm vào RegExp. */
function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
