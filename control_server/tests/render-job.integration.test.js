'use strict'

/**
 * Integration test cho cloud rendering (mini-spec V9, xem docs/PLAN.md —
 * POC hẹp: chỉ stage Demucs). Chạm MongoDB thật (in-memory).
 *
 * `submitDemucsJob` thật sự spawn `python3 demucs_worker.py` — mặc định
 * SKIP các test spawn tiến trình con thật (cần torch+demucs cài trong
 * DEMUCS_PYTHON, không phải môi trường CI thông thường). Set biến môi
 * trường VOXDUB_TEST_DEMUCS_PYTHON để chạy thật (đã live-verify tay khi
 * audit V9 — xem docs/TEST_LOG.md mục V9 cho log đầy đủ, bao gồm cả
 * luồng HTTP thật qua curl không lặp lại ở đây để test không cần mạng).
 *
 * Chạy:  node --test tests/render-job.integration.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const DEMUCS_PYTHON = process.env.VOXDUB_TEST_DEMUCS_PYTHON || ''
const HAS_DEMUCS = Boolean(DEMUCS_PYTHON) && fs.existsSync(DEMUCS_PYTHON)
const WORKER_SCRIPT = process.env.VOXDUB_TEST_DEMUCS_WORKER
  || path.join(__dirname, '..', '..', 'autodub', 'media', 'demucs_worker.py')

if (HAS_DEMUCS) {
  process.env.DEMUCS_PYTHON = DEMUCS_PYTHON
  process.env.DEMUCS_WORKER_SCRIPT = WORKER_SCRIPT
}
process.env.RENDER_UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'voxdub-render-test-'))

const Device = require('../src/models/Device')
const RenderJob = require('../src/models/RenderJob')
const config = require('../src/services/config.service')
const renderJob = require('../src/services/render-job.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(async () => { await clearDb(); config.invalidate() })

async function makeDevice(fingerprint, balance = 1000) {
  return Device.create({ fingerprint, balance, status: 'active' })
}

// Sóng sine 1 giây 44.1kHz stereo PCM16 — đủ nhỏ để test nhanh, đủ thật để
// demucs_worker.py xử lý được (không phải fixture giả).
function fakeWavBuffer() {
  const sampleRate = 44100
  const numSamples = sampleRate * 1
  const header = Buffer.alloc(44)
  header.write('RIFF', 0)
  header.writeUInt32LE(36 + numSamples * 4, 4)
  header.write('WAVE', 8)
  header.write('fmt ', 12)
  header.writeUInt32LE(16, 16)
  header.writeUInt16LE(1, 20)
  header.writeUInt16LE(2, 22)
  header.writeUInt32LE(sampleRate, 24)
  header.writeUInt32LE(sampleRate * 4, 28)
  header.writeUInt16LE(4, 32)
  header.writeUInt16LE(16, 34)
  header.write('data', 36)
  header.writeUInt32LE(numSamples * 4, 40)
  const data = Buffer.alloc(numSamples * 4)
  for (let i = 0; i < numSamples; i += 1) {
    const v = Math.round(Math.sin(2 * Math.PI * 440 * (i / sampleRate)) * 10000)
    data.writeInt16LE(v, i * 4)
    data.writeInt16LE(v, i * 4 + 2)
  }
  return Buffer.concat([header, data])
}

test('submitDemucsJob: thiếu Vox thì từ chối, không tạo job, không ghi file', async () => {
  const device = await makeDevice('a'.repeat(64), 10)
  await assert.rejects(
    () => renderJob.submitDemucsJob({ device, fileBuffer: fakeWavBuffer() }),
    (err) => err.code === 'INSUFFICIENT_CREDIT',
  )
  const count = await RenderJob.countDocuments({ fingerprint: device.fingerprint })
  assert.equal(count, 0, 'không được tạo job khi thiếu Vox')
})

test('submitDemucsJob: tắt cloud.render.enabled thì từ chối rõ ràng', async () => {
  const device = await makeDevice('b'.repeat(64), 1000)
  await config.set('cloud.render.enabled', false)
  await assert.rejects(
    () => renderJob.submitDemucsJob({ device, fileBuffer: fakeWavBuffer() }),
    (err) => err.code === 'CLOUD_RENDER_DISABLED',
  )
})

test('cleanupJob: xoá sạch thư mục job, gọi lại lần 2 không lỗi (idempotent)', async () => {
  const device = await makeDevice('c'.repeat(64), 1000)
  const jobId = 'fake-job-id-for-cleanup-test'
  const paths = renderJob.jobPaths(jobId)
  fs.mkdirSync(paths.dir, { recursive: true })
  fs.writeFileSync(paths.input, 'x')
  assert.ok(fs.existsSync(paths.dir))

  await renderJob.cleanupJob(jobId)
  assert.ok(!fs.existsSync(paths.dir))
  await renderJob.cleanupJob(jobId)   // gọi lại — không được ném lỗi
})

test('sweepExpired: dọn đúng job hết hạn, không đụng job còn hạn', async () => {
  const device = await makeDevice('d'.repeat(64), 1000)
  const expired = await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'done', inputPath: '/tmp/x', creditCharged: 50,
    expiresAt: new Date(Date.now() - 1000),
  })
  const fresh = await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'done', inputPath: '/tmp/y', creditCharged: 50,
    expiresAt: new Date(Date.now() + 3600_000),
  })

  const swept = await renderJob.sweepExpired()
  assert.equal(swept, 1)
  assert.equal(await RenderJob.findById(expired._id), null)
  assert.notEqual(await RenderJob.findById(fresh._id), null)
})

test('RenderJob schema: enum status/stage đúng, index {status,expiresAt} có mặt', () => {
  const statuses = RenderJob.schema.path('status').enumValues
  assert.deepEqual([...statuses].sort(), ['done', 'failed', 'queued', 'running'])
  const stages = RenderJob.schema.path('stage').enumValues
  assert.deepEqual(stages, ['demucs'])
  const indexes = RenderJob.schema.indexes().map(([fields]) => JSON.stringify(fields))
  assert.ok(indexes.includes(JSON.stringify({ status: 1, expiresAt: 1 })),
    'thiếu index {status, expiresAt} cho sweeper')
})

test('submitDemucsJob thật: chạy Demucs thật, trừ đúng Vox, sinh 2 file kết quả hợp lệ',
  { skip: !HAS_DEMUCS && 'cần VOXDUB_TEST_DEMUCS_PYTHON trỏ tới python đã cài torch+demucs — xem docs/TEST_LOG.md mục V9' },
  async () => {
    const device = await makeDevice('e'.repeat(64), 1000)
    const cost = await config.get('credit.cost.cloud.demucs')

    const { job, balanceAfter } = await renderJob.submitDemucsJob({
      device, fileBuffer: fakeWavBuffer(),
    })

    assert.equal(job.status, 'done', job.error)
    assert.equal(job.creditCharged, cost)
    assert.equal(balanceAfter, 1000 - cost)
    assert.ok(fs.existsSync(job.resultPaths.vocals))
    assert.ok(fs.existsSync(job.resultPaths.no_vocals))
    assert.ok(fs.statSync(job.resultPaths.vocals).size > 0)

    await renderJob.cleanupJob(job._id)
    assert.ok(!fs.existsSync(job.resultPaths.vocals), 'cleanup phải xoá file thật')
  })
