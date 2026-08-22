'use strict'

/**
 * Integration test: webhook PayOS end-to-end qua HTTP thật (fastify.inject),
 * chạm MongoDB thật (in-memory) — theo Guardrail 4 của mini-spec V1
 * (docs/PLAN.md): chữ ký hợp lệ, chữ ký sai, replay, payload thiếu field.
 *
 * Không gọi PayOS API thật (createPaymentLink) — đơn được tạo thẳng trong DB
 * để cô lập đúng phần đang test: xử lý webhook, không phải tích hợp PayOS.
 *
 * Chạy:  node --test tests/payos-webhook.integration.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const crypto = require('node:crypto')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()
const CHECKSUM_KEY = process.env.PAYOS_CHECKSUM_KEY

const { build } = require('../src/app')
const Order = require('../src/models/Order')
const ActivationKey = require('../src/models/ActivationKey')

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
test.beforeEach(clearDb)

function sign(data) {
  const raw = Object.keys(data).sort().map((k) => `${k}=${data[k]}`).join('&')
  return crypto.createHmac('sha256', CHECKSUM_KEY).update(raw).digest('hex')
}

async function makeOrder({ orderCode = 'VOX111111', payosOrderCode = 111111, amountVnd = 50000, vox = 5000 } = {}) {
  return Order.create({
    orderCode,
    payosOrderCode,
    amountVnd,
    vox,
    packageId: 'standard',
    packageLabel: 'Phổ thông',
    accessToken: crypto.randomBytes(16).toString('hex'),
    expiresAt: new Date(Date.now() + 3600_000),
    status: 'pending',
  })
}

test('webhook: chữ ký đúng + đơn khớp → chốt đơn paid, sinh key, ví không liên quan (billing không đụng Device)', async () => {
  await makeOrder()
  const data = { orderCode: 111111, amount: 50000, reference: 'FT-OK-1', transactionDateTime: '2026-08-10 10:00:00' }

  const res = await app.inject({
    method: 'POST', url: '/v1/billing/webhook/payos',
    payload: { code: '00', success: true, data, signature: sign(data) },
  })
  assert.equal(res.statusCode, 200)
  assert.deepEqual(res.json(), { success: true })

  const order = await Order.findOne({ orderCode: 'VOX111111' }).lean()
  assert.equal(order.status, 'paid')
  assert.equal(order.paidAmountVnd, 50000)
  assert.ok(order.keyCode, 'phải sinh key sau khi chốt đơn')

  const key = await ActivationKey.findOne({ code: order.keyCode }).lean()
  assert.equal(key.vox, 5000)
  assert.equal(key.status, 'issued')
})

test('webhook: chữ ký sai bị từ chối 401, đơn KHÔNG bị đổi trạng thái', async () => {
  await makeOrder()
  const data = { orderCode: 111111, amount: 50000, reference: 'FT-BAD-SIG' }

  const res = await app.inject({
    method: 'POST', url: '/v1/billing/webhook/payos',
    payload: { code: '00', success: true, data, signature: 'deadbeef00000000' },
  })
  assert.equal(res.statusCode, 401)

  const order = await Order.findOne({ orderCode: 'VOX111111' }).lean()
  assert.equal(order.status, 'pending', 'chữ ký sai không được phép chốt đơn')
})

test('webhook: replay cùng giao dịch không sinh key lần hai, không tính tiền hai lần', async () => {
  await makeOrder({ orderCode: 'VOX222222', payosOrderCode: 222222 })
  const data = { orderCode: 222222, amount: 50000, reference: 'FT-REPLAY' }
  const payload = { code: '00', success: true, data, signature: sign(data) }

  const first = await app.inject({ method: 'POST', url: '/v1/billing/webhook/payos', payload })
  const second = await app.inject({ method: 'POST', url: '/v1/billing/webhook/payos', payload })
  assert.equal(first.statusCode, 200)
  assert.equal(second.statusCode, 200, 'PayOS bắn lại vẫn phải nhận 2xx')

  const order = await Order.findOne({ orderCode: 'VOX222222' }).lean()
  const keys = await ActivationKey.find({ orderId: order._id }).lean()
  assert.equal(keys.length, 1, 'replay không được sinh key thứ hai')
})

test('webhook: số tiền lệch so với đơn thì KHÔNG chốt đơn, ghi lại để admin xử lý tay', async () => {
  await makeOrder({ orderCode: 'VOX333333', payosOrderCode: 333333, amountVnd: 50000 })
  const data = { orderCode: 333333, amount: 10000, reference: 'FT-MISMATCH' }

  const res = await app.inject({
    method: 'POST', url: '/v1/billing/webhook/payos',
    payload: { code: '00', success: true, data, signature: sign(data) },
  })
  assert.equal(res.statusCode, 200, 'vẫn phải trả 2xx cho PayOS dù không khớp tiền')

  const order = await Order.findOne({ orderCode: 'VOX333333' }).lean()
  assert.equal(order.status, 'pending', 'lệch tiền không được tự động chốt đơn')
  assert.equal(order.keyCode, '')
})

test('webhook: payload thiếu orderCode thì bỏ qua an toàn, không throw 500', async () => {
  const data = { amount: 50000, reference: 'FT-NO-ORDERCODE' }
  const res = await app.inject({
    method: 'POST', url: '/v1/billing/webhook/payos',
    payload: { code: '00', success: true, data, signature: sign(data) },
  })
  assert.equal(res.statusCode, 200)
  assert.deepEqual(res.json(), { success: true })
})

test('webhook: đơn không tồn tại (vd payload test lúc đăng ký webhook) vẫn trả 2xx', async () => {
  const data = { orderCode: 999999, amount: 1000 }
  const res = await app.inject({
    method: 'POST', url: '/v1/billing/webhook/payos',
    payload: { code: '00', success: true, data, signature: sign(data) },
  })
  assert.equal(res.statusCode, 200)
})

test('webhook: giao dịch thất bại (success=false) bị bỏ qua, không chạm đơn', async () => {
  await makeOrder({ orderCode: 'VOX444444', payosOrderCode: 444444 })
  const data = { orderCode: 444444, amount: 50000 }
  const res = await app.inject({
    method: 'POST', url: '/v1/billing/webhook/payos',
    payload: { code: '00', success: false, data, signature: sign(data) },
  })
  assert.equal(res.statusCode, 200)
  const order = await Order.findOne({ orderCode: 'VOX444444' }).lean()
  assert.equal(order.status, 'pending')
})
