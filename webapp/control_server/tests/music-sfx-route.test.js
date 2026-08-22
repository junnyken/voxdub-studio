'use strict'

/**
 * Mini-spec V37 (docs/PLAN.md, Phase G) — `/v1/ai/sound-effect` +
 * `/v1/ai/music` qua HTTP thật (fastify.inject). Mock
 * `elevenlabs-audio.service.js` (không gọi ElevenLabs thật — tốn tiền
 * thật mỗi lần chạy test) để kiểm đúng phần route tự làm: validate, cờ
 * bật/tắt tính năng (opt-in, Constraint 2), precheck/billing, trả về NHỊ
 * PHÂN đúng Content-Type.
 *
 * Chạy:  node --test tests/music-sfx-route.test.js
 */
const test = require('node:test')
const { mock } = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const Device = require('../src/models/Device')
const UsageLog = require('../src/models/UsageLog')
const elevenlabs = require('../src/services/elevenlabs-audio.service')
const config = require('../src/services/config.service')

let app
let deviceToken
let fingerprint

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
  config.invalidate()
  fingerprint = 'd'.repeat(64)
  await Device.create({ fingerprint, balance: 1000, status: 'active' })
  const res = await app.inject({
    method: 'POST', url: '/v1/device/register',
    payload: { fingerprint, name: 'music-sfx-test', appVersion: '3.0.0' },
  })
  deviceToken = res.json().token
  await Device.updateOne({ fingerprint }, { $set: { balance: 1000 } })
  await config.set('cloud.music_match.enabled', true)
})

function post(path, payload) {
  return app.inject({
    method: 'POST', url: `/v1/ai${path}`,
    headers: { authorization: `Bearer ${deviceToken}` },
    payload,
  })
}

const FAKE_AUDIO = Buffer.from('fake-mp3-bytes-not-real-audio')

// ------------------------------------------------------- sound-effect ----

test('POST /sound-effect: tính năng tắt (mặc định) -> 409 MUSIC_MATCH_DISABLED', async () => {
  await config.set('cloud.music_match.enabled', false)
  const res = await post('/sound-effect', { text: 'tiếng vỗ tay' })
  assert.equal(res.statusCode, 409)
  assert.equal(res.json().code, 'MUSIC_MATCH_DISABLED')
})

test('POST /sound-effect: thiếu token thiết bị -> 401', async () => {
  const res = await app.inject({
    method: 'POST', url: '/v1/ai/sound-effect', payload: { text: 'tiếng vỗ tay' },
  })
  assert.equal(res.statusCode, 401)
})

test('POST /sound-effect: thiếu text -> 400 (validate schema)', async () => {
  const res = await post('/sound-effect', {})
  assert.equal(res.statusCode, 400)
})

test('POST /sound-effect: thành công -> trả nhị phân audio/mpeg, trừ đúng Vox', async () => {
  mock.method(elevenlabs, 'generateSoundEffect', async () => FAKE_AUDIO)
  const cost = await config.get('credit.cost.cloud.sound_effect')

  const res = await post('/sound-effect', { text: 'tiếng vỗ tay', jobId: 'sfx-job-1' })
  assert.equal(res.statusCode, 200)
  assert.equal(res.headers['content-type'], 'audio/mpeg')
  assert.equal(res.headers['x-credit-charged'], String(cost))
  assert.equal(Buffer.compare(res.rawPayload, FAKE_AUDIO), 0)

  const device = await Device.findOne({ fingerprint }).lean()
  assert.equal(device.balance, 1000 - cost)

  const log = await UsageLog.findOne({ jobId: 'sfx-job-1' }).lean()
  assert.equal(log.action, 'sound_effect')
  assert.equal(log.creditCharged, cost)
  assert.equal(log.aiProvider, 'elevenlabs')
})

test('POST /sound-effect: thiếu Vox -> 402, KHÔNG gọi ElevenLabs (không tốn tiền thật)', async () => {
  await Device.updateOne({ fingerprint }, { $set: { balance: 0 } })
  const called = mock.method(elevenlabs, 'generateSoundEffect', async () => FAKE_AUDIO)

  const res = await post('/sound-effect', { text: 'tiếng vỗ tay' })
  assert.equal(res.statusCode, 402)
  assert.equal(res.json().code, 'INSUFFICIENT_CREDIT')
  assert.equal(called.mock.callCount(), 0, 'chặn TRƯỚC khi gọi API tốn tiền thật')
})

test('POST /sound-effect: ElevenLabs lỗi -> route trả đúng mã lỗi, KHÔNG trừ Vox', async () => {
  mock.method(elevenlabs, 'generateSoundEffect', async () => {
    throw new elevenlabs.ElevenLabsError('ELEVENLABS_REQUEST_FAILED', 'lỗi giả lập', 503)
  })

  const res = await post('/sound-effect', { text: 'tiếng vỗ tay' })
  assert.equal(res.statusCode, 503)
  assert.equal(res.json().code, 'ELEVENLABS_REQUEST_FAILED')

  const device = await Device.findOne({ fingerprint }).lean()
  assert.equal(device.balance, 1000, 'API lỗi thì không trừ Vox — mô hình chưa trả kết quả')
})

// -------------------------------------------------------------- music ----

test('POST /music: thành công -> trả nhị phân audio/mpeg, trừ đúng Vox (giá riêng, khác SFX)', async () => {
  mock.method(elevenlabs, 'generateMusic', async () => FAKE_AUDIO)
  const costMusic = await config.get('credit.cost.cloud.music')
  const costSfx = await config.get('credit.cost.cloud.sound_effect')
  assert.notEqual(costMusic, costSfx, 'nhạc và SFX phải có giá riêng biệt')

  const res = await post('/music', { prompt: 'nhạc nền vui tươi, tempo nhanh', jobId: 'music-job-1' })
  assert.equal(res.statusCode, 200)
  assert.equal(res.headers['content-type'], 'audio/mpeg')
  assert.equal(res.headers['x-credit-charged'], String(costMusic))

  const device = await Device.findOne({ fingerprint }).lean()
  assert.equal(device.balance, 1000 - costMusic)

  const log = await UsageLog.findOne({ jobId: 'music-job-1' }).lean()
  assert.equal(log.action, 'music')
})

test('POST /music: tính năng tắt -> 409, thiếu prompt -> 400', async () => {
  await config.set('cloud.music_match.enabled', false)
  const res1 = await post('/music', { prompt: 'nhạc buồn' })
  assert.equal(res1.statusCode, 409)

  await config.set('cloud.music_match.enabled', true)
  const res2 = await post('/music', {})
  assert.equal(res2.statusCode, 400)
})

test('jobId tự sinh khi client không truyền (vẫn ghi UsageLog hợp lệ)', async () => {
  mock.method(elevenlabs, 'generateSoundEffect', async () => FAKE_AUDIO)
  const res = await post('/sound-effect', { text: 'tiếng chuông' })
  assert.equal(res.statusCode, 200)
  const count = await UsageLog.countDocuments({ action: 'sound_effect' })
  assert.equal(count, 1)
})
