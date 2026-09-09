'use strict'

/**
 * Mini-spec H2 (docs/PLAN.md, Phase H) — `/v1/flow-blueprints` qua HTTP thật
 * (fastify.inject). Mock `gateway.assist` (không gọi AI provider thật —
 * không có key trong môi trường test) để kiểm được đúng phần route tự làm:
 * cách ly theo thiết bị, billing, idempotency theo jobId, và KHÔNG lưu
 * transcript/OCR thô vào response/DB (Constraint 2 của H2).
 *
 * Chạy:  node --test tests/flow-blueprints-route.test.js
 */
const test = require('node:test')
const { mock } = require('node:test')
const assert = require('node:assert')
const crypto = require('node:crypto')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const deviceService = require('../src/services/device.service')
const gateway = require('../src/services/ai-gateway.service')
const FlowBlueprint = require('../src/models/FlowBlueprint')

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
test.beforeEach(async () => {
  await clearDb()
  mock.restoreAll()
})

function vanTay() {
  return crypto.randomBytes(32).toString('hex')
}

async function thietBiMoi(ten) {
  const { device, token } = await deviceService.registerDevice({
    fingerprint: vanTay(), name: ten,
  })
  await require('../src/models/Device').updateOne(
    { _id: device._id }, { $set: { balance: 1000 } })
  return { device, token }
}

function goi(method, url, token, payload) {
  return app.inject({
    method, url, payload,
    headers: token ? { authorization: `Bearer ${token}` } : {},
  })
}

const THAN_MAU = {
  jobId: '',   // điền mỗi test — trùng jobId giữa các test làm lệch idempotency
  sourceType: 'url',
  sourceReference: 'https://www.youtube.com/watch?v=abc123',
  languageSourceDetected: 'en',
  samplingPolicyUsed: '0-5s=0.2,middle=0.5,last-5s=0.2',
  evidenceSummary: 'ASR: 2 câu tiếng Anh. OCR: 1 quan sát.',
  transcript: [
    { start_s: 0, end_s: 2, text: 'Stop wasting money on this.' },
    { start_s: 2, end_s: 5, text: 'Here is what actually works.' },
  ],
  ocrEvidence: [
    { start_s: 0.2, end_s: 0.6, status: 'ok', text: 'STOP SCROLLING' },
  ],
}

function than(jobId) {
  return { ...THAN_MAU, jobId }
}

const BEAT_GIA = {
  beats: [{
    startS: 0, endS: 2, beatType: 'hook',
    narrativeFunctionVi: 'Mở đầu gây chú ý bằng phủ định điều quen thuộc',
    pacingNoteVi: 'Nhịp nhanh, câu ngắn',
    overlayPatternAbstractVi: 'Chữ lớn xuất hiện đột ngột giữa khung',
    spokenPatternAbstractVi: 'Giọng gấp, nhấn từ phủ định',
    evidenceStatus: 'ok',
  }],
  usage: {}, provider: 'fake', model: 'fake-model', role: 'assist',
}

function gtGiaThanhCong() {
  return mock.method(gateway, 'assist', async () => BEAT_GIA)
}

// --------------------------------------------------------- xác thực -------

test('thiếu token -> 401', async () => {
  const res = await goi('POST', '/v1/flow-blueprints/', null, than('j'.repeat(8)))
  assert.equal(res.statusCode, 401)
})

// ------------------------------------------------------------- tạo --------

test('tạo blueprint -> gắn đúng ownerDeviceId, KHÔNG lộ transcript/OCR thô', async () => {
  gtGiaThanhCong()
  const a = await thietBiMoi('Máy A')

  const res = await goi('POST', '/v1/flow-blueprints/', a.token, than('j1'.repeat(4)))
  assert.equal(res.statusCode, 201)
  const body = res.json()
  assert.equal(body.beats.length, 1)
  assert.equal(body.beats[0].beatType, 'hook')
  assert.ok(!('transcript' in body), 'không lộ transcript thô')
  assert.ok(!('ocrEvidence' in body), 'không lộ OCR thô')
  assert.ok(!('ownerDeviceId' in body), 'không lộ id thiết bị')

  const doc = await FlowBlueprint.findById(body.id)
  assert.equal(String(doc.ownerDeviceId), String(a.device._id))
  assert.equal(doc.beats.length, 1)
})

test('thiếu sourceReference -> 400 (schema chặn)', async () => {
  const a = await thietBiMoi('Máy A')
  const { sourceReference, ...con } = than('j2'.repeat(4))
  const res = await goi('POST', '/v1/flow-blueprints/', a.token, con)
  assert.equal(res.statusCode, 400)
})

test('billing: đúng giá config, trừ Vox sau khi gọi mô hình thành công', async () => {
  gtGiaThanhCong()
  const a = await thietBiMoi('Máy A')

  const res = await goi('POST', '/v1/flow-blueprints/', a.token, than('j3'.repeat(4)))
  assert.equal(res.statusCode, 201)
  const body = res.json()
  assert.equal(body.creditCharged, 8, 'giá mặc định credit.cost.assist.viral_flow_blueprint')
  const device = await require('../src/models/Device').findById(a.device._id)
  assert.equal(device.balance, 1000 - 8)
})

test('cùng jobId gọi lại -> trả kết quả cũ, KHÔNG gọi lại gateway/trừ tiền lần 2', async () => {
  const fn = gtGiaThanhCong()
  const a = await thietBiMoi('Máy A')
  const body = than('j4'.repeat(4))

  const r1 = await goi('POST', '/v1/flow-blueprints/', a.token, body)
  assert.equal(r1.statusCode, 201)
  const r2 = await goi('POST', '/v1/flow-blueprints/', a.token, body)
  assert.equal(r2.statusCode, 200)
  assert.deepEqual(r2.json().beats, r1.json().beats)
  assert.equal(fn.mock.callCount(), 1, 'lượt hai phải dùng lại kết quả cũ, không gọi AI lại')

  const device = await require('../src/models/Device').findById(a.device._id)
  assert.equal(device.balance, 1000 - 8, 'không bị trừ tiền lần hai')
})

test('gateway lỗi -> 503, KHÔNG tạo bản ghi, KHÔNG trừ Vox', async () => {
  mock.method(gateway, 'assist', async () => {
    const err = new Error('mô hình không dùng được')
    err.statusCode = 503
    throw err
  })
  const a = await thietBiMoi('Máy A')

  const res = await goi('POST', '/v1/flow-blueprints/', a.token, than('j5'.repeat(4)))
  assert.equal(res.statusCode, 503)
  assert.equal(await FlowBlueprint.countDocuments({}), 0)
  const device = await require('../src/models/Device').findById(a.device._id)
  assert.equal(device.balance, 1000)
})

// -------------------------------------------------- cách ly giữa thiết bị -

test('GET: thiết bị B không thấy blueprint của thiết bị A', async () => {
  gtGiaThanhCong()
  const a = await thietBiMoi('Máy A')
  const b = await thietBiMoi('Máy B')
  await goi('POST', '/v1/flow-blueprints/', a.token, than('j6'.repeat(4)))

  const listA = await goi('GET', '/v1/flow-blueprints/', a.token)
  const listB = await goi('GET', '/v1/flow-blueprints/', b.token)
  assert.equal(listA.json().data.length, 1)
  assert.equal(listB.json().data.length, 0)
})

test('GET/:id: thiết bị B đọc blueprint của A -> 404', async () => {
  gtGiaThanhCong()
  const a = await thietBiMoi('Máy A')
  const b = await thietBiMoi('Máy B')
  const created = (await goi('POST', '/v1/flow-blueprints/', a.token, than('j7'.repeat(4)))).json()

  const res = await goi('GET', `/v1/flow-blueprints/${created.id}`, b.token)
  assert.equal(res.statusCode, 404)
})

test('DELETE: thiết bị B xoá blueprint của A -> 404, bản ghi VẪN CÒN', async () => {
  gtGiaThanhCong()
  const a = await thietBiMoi('Máy A')
  const b = await thietBiMoi('Máy B')
  const created = (await goi('POST', '/v1/flow-blueprints/', a.token, than('j8'.repeat(4)))).json()

  const res = await goi('DELETE', `/v1/flow-blueprints/${created.id}`, b.token)
  assert.equal(res.statusCode, 404)
  assert.ok(await FlowBlueprint.findById(created.id))
})

test('chủ thật đọc/xoá được blueprint của chính mình', async () => {
  gtGiaThanhCong()
  const a = await thietBiMoi('Máy A')
  const created = (await goi('POST', '/v1/flow-blueprints/', a.token, than('j9'.repeat(4)))).json()

  const get = await goi('GET', `/v1/flow-blueprints/${created.id}`, a.token)
  assert.equal(get.statusCode, 200)
  const del = await goi('DELETE', `/v1/flow-blueprints/${created.id}`, a.token)
  assert.equal(del.statusCode, 200)
  assert.equal(await FlowBlueprint.findById(created.id), null)
})

// -------------------------------------------- hồi quy: gỡ kiểm sở hữu -----

test('REGRESSION GIẢ ĐỊNH: truy vấn không lọc theo ownerDeviceId sẽ LỘ dữ liệu', async () => {
  gtGiaThanhCong()
  const a = await thietBiMoi('Máy A')
  await goi('POST', '/v1/flow-blueprints/', a.token, than('ja'.repeat(4)))

  const layKhongLoc = await FlowBlueprint.find({})
  assert.equal(layKhongLoc.length, 1, 'không lọc thì thấy MỌI blueprint — đúng lỗ hổng cần chặn')
})
