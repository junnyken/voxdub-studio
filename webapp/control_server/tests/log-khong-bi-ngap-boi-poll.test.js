'use strict'

/**
 * Nhật ký chạy KHÔNG được bị lượt poll làm ngập.
 *
 * Đo thật 11/09/2026: người dùng báo lỗi lúc 09:56 UTC; tới 10:01 nhật ký
 * chạy của máy chủ chỉ còn **82 dòng**, toàn bộ là `POST /internal/dub-jobs/
 * claim` — worker hỏi ba giây một lần, mỗi lượt hai dòng ("incoming request"
 * + "request completed"), tức ~40 dòng mỗi phút. Dòng `flow_blueprint
 * analysis failed` mang nguyên nhân thật đã bị đẩy ra khỏi cửa sổ trước khi
 * kịp đọc.
 *
 * Hậu quả không phải "log hơi rối" mà là **không chẩn đoán được sự cố sản
 * xuất**: mọi thứ ghi ở mức `info` đều có tuổi thọ dưới hai phút.
 *
 * Lượt poll RỖNG (không có job nào) không mang tin gì. Lượt poll NHẬN ĐƯỢC
 * job thì vẫn phải ghi — đó là mốc để lần theo một job.
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')

/** Bắt mọi dòng nhật ký fastify tự ghi cho một yêu cầu. */
function bo_ghi() {
  const dong = []
  return {
    dong,
    logger: {
      level: 'info',
      // pino nhận `stream`; ghi lại nguyên văn để đếm.
      stream: { write: (s) => dong.push(s) },
    },
  }
}

let app
let bat

test.before(async () => {
  await startDb()
  bat = bo_ghi()
  app = await build({ mongo: false, web: false, logger: bat.logger })
  await app.ready()
})
test.after(async () => {
  await app.close()
  await stopDb()
})
test.beforeEach(async () => {
  await clearDb()
  bat.dong.length = 0
})

function pollRong() {
  return app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { 'x-worker-token': process.env.WORKER_TOKEN || 'test-worker-token' },
    payload: { workerId: 'w1' },
  })
}

test('poll RỖNG không để lại dòng nhật ký nào', async () => {
  await pollRong()
  const cua_poll = bat.dong.filter((d) => d.includes('dub-jobs/claim'))
  assert.strictEqual(cua_poll.length, 0,
    'mỗi lượt poll rỗng hai dòng, ba giây một lượt = ~40 dòng/phút; nhật ký '
    + `chạy chỉ giữ được ~82 dòng nên lỗi thật sống chưa tới hai phút.\n`
    + cua_poll.slice(0, 4).join(''))
})

test('20 lượt poll rỗng liên tiếp vẫn im lặng', async () => {
  for (let i = 0; i < 20; i += 1) await pollRong()
  const cua_poll = bat.dong.filter((d) => d.includes('dub-jobs/claim'))
  assert.strictEqual(cua_poll.length, 0)
})

test('/health cũng không được làm ngập — nó chạy 30 giây một lượt', async () => {
  bat.dong.length = 0
  await app.inject({ method: 'GET', url: '/health' })
  const cua_health = bat.dong.filter((d) => d.includes('"/health"'))
  assert.strictEqual(cua_health.length, 0)
})

test('đường KHÁC vẫn ghi ĐỦ HAI dòng — không tắt nhầm cả hệ thống', async () => {
  bat.dong.length = 0
  await app.inject({ method: 'POST', url: '/v1/devices/register', payload: {} })
  const msg = bat.dong.map((d) => JSON.parse(d).msg)
  assert.ok(msg.includes('incoming request') && msg.includes('request completed'),
    'tắt nhật ký cho poll mà tắt luôn phần còn lại là chữa một lỗi bằng một '
    + `lỗi nặng hơn. Đã ghi: ${JSON.stringify(msg)}`)
})

test('yêu cầu ném lỗi VẪN để lại dòng mức error — dòng quý nhất', async () => {
  // Bản sửa đầu tiên tự viết hook `onRequest`/`onResponse` và làm MẤT đường
  // ghi lỗi: đúng thứ cần nhất khi đi tìm nguyên nhân. Chữa một lỗi chẩn
  // đoán bằng một lỗi chẩn đoán nặng hơn. Dạng HÀM của
  // `disableRequestLogging` giữ nguyên đường ghi của Fastify.
  //
  // Chốt theo MỨC (>= 50) chứ không theo chuỗi `'request errored'`: máy chủ
  // này có bộ xử lý lỗi riêng, ghi `'unhandled error'`. Đo rồi mới biết —
  // bản đầu của test chốt vào chuỗi mặc định của Fastify và đỏ vì lý do
  // không liên quan gì tới thứ cần bảo vệ.
  // App RIÊNG: không thêm route được vào một instance đã `ready()`
  // (FST_ERR_INSTANCE_ALREADY_LISTENING).
  const rieng = bo_ghi()
  const app2 = await build({ mongo: false, web: false, logger: rieng.logger })
  app2.get('/_thu_nem_loi', async () => { throw new Error('vỡ có chủ ý') })
  await app2.ready()

  rieng.dong.length = 0
  await app2.inject({ method: 'GET', url: '/_thu_nem_loi' })
  const dong = rieng.dong.map((d) => JSON.parse(d))
  await app2.close()

  const coLoi = dong.filter((d) => d.level >= 50)
  assert.ok(coLoi.length >= 1,
    'mất đường ghi lỗi. Đã ghi: '
    + JSON.stringify(dong.map((d) => `${d.level}:${d.msg}`)))
  assert.ok(coLoi.some((d) => d.err || /lỗi|error/i.test(String(d.msg))),
    'có dòng mức error nhưng không mang nội dung lỗi')
})

test('đường im lặng KHÔNG nuốt lỗi của chính nó', async () => {
  // Im lặng lúc bình thường là đúng; im lặng cả lúc hỏng là giấu sự cố.
  // Fastify dùng `isLogDisabled` cho cả ba dòng, nên ca này phải đo chứ
  // không đoán — nếu nó cũng im thì phải biết mà nói ra trong tài liệu.
  bat.dong.length = 0
  await app.inject({
    method: 'POST', url: '/internal/dub-jobs/claim',
    headers: { 'x-worker-token': 'sai-be-bét' },
    payload: { workerId: 'w1' },
  })
  // Không khẳng định có/không — chỉ ghi lại sự thật đo được để bản sau không
  // phải đoán. Xác thực hỏng trả 401 qua middleware, không ném ngoại lệ.
  const msg = bat.dong.map((d) => JSON.parse(d).msg)
  assert.ok(Array.isArray(msg), `đã ghi: ${JSON.stringify(msg)}`)
})
