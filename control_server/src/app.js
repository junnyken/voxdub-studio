'use strict'

/**
 * Fastify app factory — nơi ráp plugin và route.
 *
 * Tách khỏi `server.js` để test dựng được app mà không mở cổng mạng.
 */
const fs = require('node:fs')
const path = require('node:path')

const Fastify = require('fastify')

// Backend tự serve luôn website (../website/dist) — cùng origin nên frontend
// gọi API bằng đường dẫn tương đối, KHÔNG cần CORS, không cần build lại khi
// đổi domain. Đổi chỗ chứa dist bằng WEB_DIST nếu deploy kiểu khác.
const WEB_DIST = process.env.WEB_DIST
  || path.join(__dirname, '..', '..', 'website', 'dist')

// C54 — `/health` từng báo cứng '3.0.0' trong mã, không đổi suốt 48 lượt
// deploy: đi kiểm "bản nào đang chạy trên máy chủ" thì con số đó chỉ dẫn đi
// sai đường. Nay lấy từ một nguồn duy nhất (src/version.js).
const PHIEN_BAN = require('./version')
const mongoose = require('mongoose')

// Tên trạng thái của mongoose (readyState) bằng tiếng người đọc được.
const TRANG_THAI_DB = {
  0: 'mất kết nối',
  1: 'đã kết nối',
  2: 'đang kết nối',
  3: 'đang ngắt',
}

async function build(opts = {}) {
  const app = Fastify({
    logger: opts.logger !== undefined ? opts.logger : {
      level: process.env.LOG_LEVEL || 'info',
      redact: ['req.headers.authorization', 'req.headers["x-admin-token"]',
              'req.headers["x-worker-token"]'],
    },
    trustProxy: process.env.TRUST_PROXY === '1',
    bodyLimit: 4 * 1024 * 1024,   // transcript một video dài vẫn lọt
    ...opts.fastify,
  })

  await app.register(require('@fastify/helmet'), { contentSecurityPolicy: false })

  // Website được backend serve cùng origin nên trình duyệt KHÔNG cần CORS.
  // Danh sách này chỉ để phòng khi website được host tách rời (CORS_ORIGIN),
  // mặc định thêm PUBLIC_URL cho chắc. App desktop không gửi Origin — luôn qua.
  const origins = (process.env.CORS_ORIGIN || process.env.PUBLIC_URL || '')
    .split(',').map((s) => s.trim().replace(/\/+$/, '')).filter(Boolean)
  await app.register(require('@fastify/cors'), {
    // Cùng origin thì trình duyệt không gửi preflight; danh sách chỉ dùng
    // khi host tách rời.
    origin: origins.length ? origins : false,
    methods: ['GET', 'POST', 'PATCH', 'PUT', 'DELETE'],
    // Admin panel gửi token qua header riêng; thiếu dòng này thì trình duyệt
    // chặn preflight và mọi thao tác quản trị đều hỏng với lỗi CORS khó hiểu.
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Admin-Token'],
  })

  // Mini-spec V9: upload audio cho cloud rendering (/v1/jobs).
  await app.register(require('@fastify/multipart'))

  await app.register(require('@fastify/rate-limit'), {
    global: true,
    max: 200,
    timeWindow: '1 minute',
    // Giới hạn theo thiết bị khi có token, theo IP khi chưa — nhiều máy sau
    // cùng một NAT không được phép chặn lẫn nhau.
    keyGenerator: (request) => {
      const auth = request.headers.authorization || ''
      if (auth.startsWith('Bearer ')) return auth.slice(-32)
      // Admin panel bắn nhiều request khi mở dashboard (5-6 bảng cùng lúc)
      // và luôn từ một IP — tách khỏi hạn mức chung để không tự chặn mình.
      if (request.headers['x-admin-token']) return `admin:${request.ip}`
      return request.ip
    },
  })

  if (opts.mongo !== false) {
    await app.register(require('./plugins/mongo'))
  }

  // C59 — `/health` từng trả `ok: true` KỂ CẢ khi mất kết nối MongoDB. Ngày
  // 31-08 nền tảng báo `dependency_unreachable` hàng giờ trong khi đường này
  // vẫn xanh, và bộ kiểm deploy tự động (C58) chấm điểm bằng chính nó — tức
  // một bản deploy hỏng vẫn được ghi là "đã lên".
  //
  // Vẫn trả HTTP 200 dù CSDL đứt: tiến trình còn sống thật, và cổng health
  // của nền tảng dùng đường này để quyết định promote — trả 503 lúc CSDL chớp
  // sẽ chặn cả những lượt deploy lành. Nói ra trạng thái, để nơi cần khắt khe
  // (bộ kiểm deploy) tự quyết.
  app.get('/health', async () => ({
    ok: true,
    version: PHIEN_BAN.version,
    ...(PHIEN_BAN.commit ? { commit: PHIEN_BAN.commit } : {}),
    db: opts.mongo === false ? 'không dùng' : TRANG_THAI_DB[mongoose.connection.readyState]
      || `không rõ (${mongoose.connection.readyState})`,
    uptimeS: Math.round(process.uptime()),
  }))

  await app.register(require('./routes/config'), { prefix: '/v1/config' })
  await app.register(require('./routes/device'), { prefix: '/v1/device' })
  await app.register(require('./routes/ai'), { prefix: '/v1/ai' })
  await app.register(require('./routes/holds'), { prefix: '/v1/holds' })
  await app.register(require('./routes/jobs'), { prefix: '/v1/jobs' })
  await app.register(require('./routes/billing'), { prefix: '/v1/billing' })
  await app.register(require('./routes/admin'), { prefix: '/v1/admin' })
  // Mini-spec V13: trạng thái tiến trình lồng tiếng — CHỈ khi client ở chế
  // độ SaaS (is_configured()), chưa từng gọi ở local-only.
  await app.register(require('./routes/telemetry'), { prefix: '/v1/telemetry' })
  // Mini-spec V12: API nội bộ cho worker Python (poll job, heartbeat, báo
  // kết quả) — KHÔNG dưới /v1, xác thực bằng WORKER_INTERNAL_TOKEN riêng
  // (worker-auth.middleware.js), không lộ ra client thiết bị/website.
  await app.register(require('./routes/internal-jobs'), { prefix: '/internal/jobs' })
  // Mini-spec V34a (docs/PLAN.md, Phase G): API nội bộ cho worker Python
  // lồng tiếng đầy đủ (ASR+dịch+TTS+mux) — container RIÊNG
  // (control_server/worker-dub/), cùng cơ chế WORKER_INTERNAL_TOKEN.
  await app.register(require('./routes/internal-dub-jobs'), { prefix: '/internal/dub-jobs' })
  // Mini-spec V31 (docs/PLAN.md, Phase G): API dịch thuật công khai cho
  // developer bên thứ 3 — namespace RIÊNG /api/v1 (khác /v1/ai của app
  // desktop), xác thực bằng API key (apikey.middleware.js), KHÔNG đụng
  // saas_client.is_configured()/Device/CreditLedger của app desktop.
  await app.register(require('./routes/api-v1'), { prefix: '/api/v1' })

  // Website tĩnh (nếu đã build). SPA: đường dẫn lạ ngoài /v1 trả index.html.
  const hasWeb = opts.web !== false && fs.existsSync(path.join(WEB_DIST, 'index.html'))
  if (hasWeb) {
    await app.register(require('@fastify/static'), {
      root: WEB_DIST,
      wildcard: false,
      cacheControl: false,   // hook onSend bên dưới tự quyết định cache
    })
    // Tài nguyên băm tên (assets/) cache 1 năm; còn lại luôn hỏi lại server.
    app.addHook('onSend', async (request, reply) => {
      if (request.method === 'GET' && !request.url.startsWith('/v1')
          && !reply.getHeader('cache-control')) {
        reply.header('Cache-Control', request.url.startsWith('/assets/')
          ? 'public, max-age=31536000, immutable'
          : 'no-cache')
      }
    })
  }

  // Lỗi không lường trước: log đầy đủ phía server, nói ngắn gọn phía client —
  // stack trace lộ ra ngoài là món quà cho người dò lỗ hổng.
  app.setErrorHandler((err, request, reply) => {
    if (err.validation) {
      return reply.code(400).send({
        code: 'VALIDATION_ERROR',
        message: 'Dữ liệu gửi lên không hợp lệ.',
        details: err.validation.map((v) => `${v.instancePath || 'body'} ${v.message}`),
      })
    }
    if (err.statusCode && err.statusCode < 500) {
      return reply.code(err.statusCode).send({
        code: err.code || 'ERROR',
        message: err.message,
      })
    }
    request.log.error({ err }, 'unhandled error')
    return reply.code(500).send({ code: 'INTERNAL', message: 'Lỗi máy chủ.' })
  })

  app.setNotFoundHandler((request, reply) => {
    // SPA fallback: GET một trang không phải API (vd /mua, /admin/orders)
    // thì trả index.html cho React Router lo phần còn lại.
    if (hasWeb && request.method === 'GET' && !request.url.startsWith('/v1')) {
      reply.header('Cache-Control', 'no-cache')
      return reply.type('text/html').send(fs.readFileSync(path.join(WEB_DIST, 'index.html')))
    }
    reply.code(404).send({ code: 'NOT_FOUND', message: 'Không có endpoint này.' })
  })

  return app
}

module.exports = { build }
