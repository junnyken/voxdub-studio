'use strict'

/**
 * Mini-spec V31 (docs/PLAN.md, Phase G) — `/v1/admin/api-keys` (tạo/liệt
 * kê/thu hồi API key developer bên thứ 3, thủ công qua admin).
 *
 * Chạy:  node --test tests/admin-api-keys-route.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const ApiKey = require('../src/models/ApiKey')

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

test('thiếu X-Admin-Token -> 401', async () => {
  const res = await app.inject({
    method: 'POST', url: '/v1/admin/api-keys', payload: { orgName: 'Acme' },
  })
  assert.equal(res.statusCode, 401)
})

test('tạo API key -> trả plaintext đúng 1 lần, không lưu plaintext trong DB', async () => {
  const res = await adminReq('POST', '/v1/admin/api-keys', { orgName: 'Acme', quota: 500 })
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.ok(body.apiKey.startsWith('vx_live_'))
  assert.ok(body.id)

  const doc = await ApiKey.findById(body.id).lean()
  assert.equal(doc.orgName, 'Acme')
  assert.equal(doc.quota, 500)
  assert.ok(!('apiKey' in doc))
  assert.notEqual(doc.keyHash, body.apiKey, 'DB không được lưu plaintext')
})

test('GET /api-keys liệt kê KHÔNG lộ keyHash', async () => {
  await adminReq('POST', '/v1/admin/api-keys', { orgName: 'Acme' })
  const res = await adminReq('GET', '/v1/admin/api-keys')
  assert.equal(res.statusCode, 200)
  const body = res.json()
  assert.equal(body.total, 1)
  assert.ok(!('keyHash' in body.data[0]), 'danh sách không được lộ keyHash')
  assert.equal(body.data[0].orgName, 'Acme')
})

test('DELETE /api-keys/:id thu hồi -> key không dùng được nữa', async () => {
  const createRes = await adminReq('POST', '/v1/admin/api-keys', { orgName: 'Acme' })
  const { id, apiKey } = createRes.json()

  const delRes = await adminReq('DELETE', `/v1/admin/api-keys/${id}`)
  assert.equal(delRes.statusCode, 200)

  const doc = await ApiKey.findById(id)
  assert.equal(doc.status, 'revoked')

  // Xác nhận key thu hồi thật sự không dùng được ở /api/v1/translate.
  const useRes = await app.inject({
    method: 'POST', url: '/api/v1/translate',
    headers: { authorization: `Bearer ${apiKey}` },
    payload: { sourceFlores: 'eng_Latn', targetFlores: 'vie_Latn', items: [{ id: 1, text: 'hi' }] },
  })
  assert.equal(useRes.statusCode, 403)
})

test('DELETE /api-keys/:id với id không tồn tại -> 404', async () => {
  const res = await adminReq('DELETE', '/v1/admin/api-keys/000000000000000000000000')
  assert.equal(res.statusCode, 404)
})
