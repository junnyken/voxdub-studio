'use strict'

/**
 * Lỗi kiểm dữ liệu phải nói tiếng Việt — TOÀN BỘ API, không riêng một đường.
 *
 * Lượt chạy thật 12/09 (v3.17.14): người dùng bấm «Bỏ qua, không tốn Vox»,
 * chờ thêm ba phút, rồi nhận nguyên văn:
 *
 *     Dừng lại: must NOT have more than 400 items
 *
 * `src/app.js` CÓ `setErrorHandler` trả `'Dữ liệu gửi lên không hợp lệ.'` —
 * nhưng nó **không bao giờ chạy**. Nó nằm ở dòng 191, sau tất cả
 * `await app.register(routes)` ở 141–168. Mỗi `await app.register(...)` đăng
 * ký xong route TRƯỚC khi tới dòng đó, nên route đã chốt bộ xử lý lỗi mặc
 * định của Fastify.
 *
 * Hậu quả không phải một câu xấu ở một chỗ: **mọi** lỗi kiểm dữ liệu trong
 * cả API đều trả chuỗi ajv tiếng Anh, và người dùng Việt không đọc được gì.
 * Đây là loại lỗi mà test cũ không bắt vì chúng chỉ kiểm `statusCode`.
 */
const test = require('node:test')
const assert = require('node:assert')
const crypto = require('node:crypto')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const deviceService = require('../src/services/device.service')

let app

test.before(async () => {
  await startDb()
  app = await build({ mongo: false, web: false, logger: false })
  await app.ready()
})
test.after(async () => {
  await app.close()
  await stopDb()
})
test.beforeEach(async () => { await clearDb() })

async function thietBi() {
  const { token } = await deviceService.registerDevice({
    fingerprint: crypto.randomBytes(32).toString('hex'), name: 'may-thu',
  })
  return token
}

/** Không chữ tiếng Anh của ajv nào được lọt ra `message`. */
function khongPhaiAjv(b, ctx) {
  for (const cam of ['must NOT', 'must be', 'must have', 'should be']) {
    assert.ok(!String(b.message || '').includes(cam),
      `${ctx}: câu ajv tiếng Anh lọt ra người dùng — `
      + JSON.stringify(b.message))
  }
}

test('vượt trần mảng: nói tiếng Việt, không phải "must NOT have more than"', async () => {
  const token = await thietBi()
  const nhieu = Array.from({ length: 900 }, (_, i) => ({
    start_s: i * 0.1, end_s: i * 0.1 + 0.05, status: 'ok', text: `chu ${i}`,
  }))
  const res = await app.inject({
    method: 'POST', url: '/v1/flow-blueprints',
    headers: { authorization: `Bearer ${token}` },
    payload: {
      jobId: 'job-dai-du-8', sourceType: 'url',
      sourceReference: 'https://vi.du/x', languageSourceDetected: 'vi',
      samplingPolicyUsed: 'p', transcript: [], ocrEvidence: nhieu,
    },
  })

  assert.strictEqual(res.statusCode, 400)
  const b = res.json()
  assert.strictEqual(b.code, 'VALIDATION_ERROR',
    `còn dùng bộ xử lý mặc định của Fastify: ${JSON.stringify(b)}`)
  khongPhaiAjv(b, 'flow-blueprints')
  assert.match(b.message, /không hợp lệ/i)
})

test('trường thiếu/sai kiểu cũng nói tiếng Việt', async () => {
  const token = await thietBi()
  const res = await app.inject({
    method: 'POST', url: '/v1/flow-blueprints',
    headers: { authorization: `Bearer ${token}` },
    payload: { jobId: 'x' },   // quá ngắn + thiếu trường
  })
  const b = res.json()
  assert.strictEqual(b.code, 'VALIDATION_ERROR')
  khongPhaiAjv(b, 'jobId ngắn')
})

test('vẫn giữ `details` để người hỗ trợ lần ra chỗ sai', async () => {
  // Câu cho người dùng phải dễ hiểu, nhưng KHÔNG được vứt hẳn thông tin kỹ
  // thuật — nếu không thì báo lỗi xong không ai biết trường nào hỏng.
  const token = await thietBi()
  const res = await app.inject({
    method: 'POST', url: '/v1/flow-blueprints',
    headers: { authorization: `Bearer ${token}` },
    payload: { jobId: 'x' },
  })
  const b = res.json()
  assert.ok(Array.isArray(b.details) && b.details.length >= 1,
    `mất details: ${JSON.stringify(b)}`)
})

test('đường KHÁC cũng vậy — lỗi nằm ở thứ tự đăng ký, không ở một route', async () => {
  const res = await app.inject({
    method: 'POST', url: '/v1/device/register', payload: { fingerprint: 'ngan' },
  })
  if (res.statusCode === 400) {
    const b = res.json()
    khongPhaiAjv(b, 'device/register')
  }
})
