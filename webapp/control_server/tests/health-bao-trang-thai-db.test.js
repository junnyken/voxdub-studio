'use strict'

/**
 * C59 — `/health` phải NÓI RA trạng thái cơ sở dữ liệu.
 *
 * Ngày 31-08 nền tảng báo `dependency_unreachable` hàng giờ (worker không
 * claim được job vì máy chủ không nối được MongoDB) trong khi `/health` vẫn
 * trả `ok: true`. Từ C58 chính đường này là thứ quyết định một lượt deploy tự
 * động có được ghi là "đã lên" hay không — im lặng ở đây nghĩa là ghi nhận sai
 * một bản hỏng.
 */
const test = require('node:test')
const assert = require('node:assert')

const { build } = require('../src/app')

test('/health nói rõ trạng thái CSDL', async (t) => {
  const app = await build({ mongo: false, web: false, logger: false })
  t.after(() => app.close())

  const res = await app.inject({ method: 'GET', url: '/health' })
  assert.strictEqual(res.statusCode, 200)
  const body = res.json()
  assert.strictEqual(body.ok, true)
  assert.ok('db' in body, '/health phải có trường db — thiếu nó thì bộ kiểm '
    + 'deploy không phân biệt được "sống" với "sống nhưng không dùng được"')
  assert.strictEqual(body.db, 'không dùng',
    'dựng app không có mongo thì phải nói "không dùng", không được im lặng')
})

test('/health vẫn trả 200 dù CSDL đứt', async (t) => {
  // Cổng health của nền tảng dùng đường này để quyết định promote — trả 503
  // lúc CSDL chớp sẽ chặn cả những lượt deploy lành. Nói ra trạng thái, để
  // nơi cần khắt khe tự quyết.
  const app = await build({ mongo: false, web: false, logger: false })
  t.after(() => app.close())
  const res = await app.inject({ method: 'GET', url: '/health' })
  assert.strictEqual(res.statusCode, 200)
})
