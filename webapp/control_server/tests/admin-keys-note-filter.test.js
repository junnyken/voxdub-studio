'use strict'

/**
 * Bộ lọc `note` cho `GET /v1/admin/keys` — tìm lại nhanh cả lô mã đã phát
 * cùng ghi chú (vd "Công ty X - 3 máy"), giống pattern lọc `code` có sẵn.
 *
 * Chạy:  node --test tests/admin-keys-note-filter.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')

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

function adminReq(method, url, payload) {
  return app.inject({
    method, url, payload, headers: { 'x-admin-token': 'test-admin-token' },
  })
}

test('GET /keys?note= lọc đúng theo ghi chú, không lộ mã khác lô', async () => {
  await adminReq('POST', '/v1/admin/keys', { vox: 1000, count: 2, note: 'Công ty ABC - 2 máy' })
  await adminReq('POST', '/v1/admin/keys', { vox: 500, count: 1, note: 'Tặng KOL Nam' })

  const res = await adminReq('GET', '/v1/admin/keys?note=ABC')
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(body.total, 2)
  assert.ok(body.data.every((k) => k.note === 'Công ty ABC - 2 máy'))
})

test('GET /keys?note= không phân biệt hoa thường', async () => {
  await adminReq('POST', '/v1/admin/keys', { vox: 1000, count: 1, note: 'Công ty XYZ' })
  const res = await adminReq('GET', '/v1/admin/keys?note=xyz')
  assert.equal(res.json().total, 1)
})

test('GET /keys?note= kết hợp status vẫn đúng (AND, không OR)', async () => {
  const issue = await adminReq('POST', '/v1/admin/keys', { vox: 1000, count: 1, note: 'Lô Beta' })
  const { code } = issue.json().keys[0]

  const resBefore = await adminReq('GET', '/v1/admin/keys?note=Beta&status=used')
  assert.equal(resBefore.json().total, 0, 'chưa activate thì status=used phải rỗng dù note khớp')

  await adminReq('DELETE', `/v1/admin/keys/${code}`)
  const resRevoked = await adminReq('GET', '/v1/admin/keys?note=Beta&status=revoked')
  assert.equal(resRevoked.json().total, 1)
})

test('GET /keys không truyền note -> trả toàn bộ như trước (0 regression)', async () => {
  await adminReq('POST', '/v1/admin/keys', { vox: 1000, count: 3, note: 'Bất kỳ' })
  const res = await adminReq('GET', '/v1/admin/keys')
  assert.equal(res.json().total, 3)
})
