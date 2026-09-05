'use strict'

/**
 * Integration test cho cloud rendering (mini-spec V9 → V12, xem docs/PLAN.md
 * — vẫn POC hẹp: chỉ stage Demucs). Chạm MongoDB thật (in-memory).
 *
 * V12: `submitDemucsJob` không còn tự spawn subprocess — chỉ tạo job
 * `queued`. Việc chạy `demucs_worker.py` thật giờ thuộc về
 * `control_server/worker/render_worker.py` (tiến trình Python riêng); test
 * ở đây mô phỏng ĐÚNG luồng đó bằng cách tự spawn subprocess theo cùng CLI
 * contract rồi gọi `claimNextJob`/`completeJob` — không lặp lại logic worker,
 * chỉ xác nhận state machine + Demucs thật khớp nhau.
 *
 * Mặc định SKIP các test spawn tiến trình con thật (cần torch+demucs cài
 * trong DEMUCS_PYTHON). Set biến môi trường VOXDUB_TEST_DEMUCS_PYTHON để
 * chạy thật — xem docs/TEST_LOG.md mục V9/V12 cho log live-verify đầy đủ,
 * bao gồm cả `docker compose up` + HTTP thật, không lặp lại ở đây để test
 * không cần Docker/mạng.
 *
 * Chạy:  node --test tests/render-job.integration.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const { Readable } = require('node:stream')
const { spawnSync } = require('node:child_process')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const DEMUCS_PYTHON = process.env.VOXDUB_TEST_DEMUCS_PYTHON || ''
const HAS_DEMUCS = Boolean(DEMUCS_PYTHON) && fs.existsSync(DEMUCS_PYTHON)
const WORKER_SCRIPT = process.env.VOXDUB_TEST_DEMUCS_WORKER
  || path.join(__dirname, '..', '..', 'autodub', 'media', 'demucs_worker.py')

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

// V44: `submitDemucsJob` nhận STREAM thay vì Buffer — stream chỉ đọc được 1
// lần nên mỗi lần gọi phải dựng mới.
function fakeWavStream() {
  return Readable.from([fakeWavBuffer()])
}

test('submitDemucsJob: thiếu Vox thì từ chối, không tạo job, không ghi file', async () => {
  // V65: mặc định `cloud.render.enabled` là FALSE (không có worker render).
  // Test này kiểm luật TIỀN nên phải bật tính năng lên, nếu không nó dừng ở
  // cổng tắt và không chạm tới thứ đang muốn kiểm.
  await config.set('cloud.render.enabled', true)
  const device = await makeDevice('a'.repeat(64), 10)
  await assert.rejects(
    () => renderJob.submitDemucsJob({ device, fileStream: fakeWavStream() }),
    (err) => err.code === 'INSUFFICIENT_CREDIT',
  )
  const count = await RenderJob.countDocuments({ fingerprint: device.fingerprint })
  assert.equal(count, 0, 'không được tạo job khi thiếu Vox')
})

test('submitDemucsJob: tắt cloud.render.enabled thì từ chối rõ ràng', async () => {
  const device = await makeDevice('b'.repeat(64), 1000)
  await config.set('cloud.render.enabled', false)
  await assert.rejects(
    () => renderJob.submitDemucsJob({ device, fileStream: fakeWavStream() }),
    (err) => err.code === 'CLOUD_RENDER_DISABLED',
  )
})

test('submitDemucsJob (V12): trả về NGAY status=queued, KHÔNG chạy Demucs inline', async () => {
  await config.set('cloud.render.enabled', true)   // V65: mặc định đã tắt
  const device = await makeDevice('q'.repeat(64), 1000)
  const cost = await config.get('credit.cost.cloud.demucs')

  const { job, balanceAfter } = await renderJob.submitDemucsJob({
    device, fileStream: fakeWavStream(),
  })

  assert.equal(job.status, 'queued', 'V12 phải trả về queued ngay, không đợi xử lý')
  assert.equal(job.creditCharged, cost, 'vẫn trừ Vox ngay lúc submit, đúng nguyên tắc hold')
  assert.equal(balanceAfter, 1000 - cost)
  assert.equal(job.workerId, '', 'chưa worker nào nhận job')
  assert.equal(job.heartbeatAt, null)
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
    'thiếu index {status, expiresAt} cho sweeper TTL')
  assert.ok(indexes.includes(JSON.stringify({ status: 1, heartbeatAt: 1 })),
    'thiếu index {status, heartbeatAt} cho sweeper heartbeat (V12)')
})

// ------------------------------------------------ state machine (V12) --- //

test('claimNextJob: FIFO, atomic — 2 lần claim liên tiếp không bao giờ trùng job', async () => {
  const device = await makeDevice('f'.repeat(64), 1000)
  const older = await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'queued', inputPath: '/tmp/a', expiresAt: new Date(Date.now() + 3600_000),
  })
  await new Promise((r) => { setTimeout(r, 5) })
  const newer = await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'queued', inputPath: '/tmp/b', expiresAt: new Date(Date.now() + 3600_000),
  })

  const first = await renderJob.claimNextJob('worker-1')
  assert.equal(String(first._id), String(older._id), 'phải nhận job CŨ NHẤT trước (FIFO)')
  assert.equal(first.status, 'running')
  assert.equal(first.workerId, 'worker-1')
  assert.ok(first.heartbeatAt)

  const second = await renderJob.claimNextJob('worker-2')
  assert.equal(String(second._id), String(newer._id))

  const third = await renderJob.claimNextJob('worker-3')
  assert.equal(third, null, 'hết job queued thì trả null, không lỗi')
})

test('heartbeat: cập nhật đúng khi job vẫn do worker đó giữ, từ chối khi không phải', async () => {
  const device = await makeDevice('g'.repeat(64), 1000)
  await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'queued', inputPath: '/tmp/a', expiresAt: new Date(Date.now() + 3600_000),
  })
  const claimed = await renderJob.claimNextJob('worker-1')

  const ok = await renderJob.heartbeat(claimed._id, 'worker-1')
  assert.equal(ok, true)

  const wrongWorker = await renderJob.heartbeat(claimed._id, 'worker-2')
  assert.equal(wrongWorker, false, 'worker khác không được cập nhật heartbeat của job không phải mình')
})

test('completeJob: chuyển done + lưu resultPaths, từ chối nếu không đúng worker đang giữ', async () => {
  const device = await makeDevice('h'.repeat(64), 1000)
  await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'queued', inputPath: '/tmp/a', expiresAt: new Date(Date.now() + 3600_000),
  })
  const claimed = await renderJob.claimNextJob('worker-1')

  const wrongWorker = await renderJob.completeJob(claimed._id, 'worker-2',
    { vocals: '/tmp/v', no_vocals: '/tmp/nv' })
  assert.equal(wrongWorker, null)

  const done = await renderJob.completeJob(claimed._id, 'worker-1',
    { vocals: '/tmp/v', no_vocals: '/tmp/nv' })
  assert.equal(done.status, 'done')
  assert.equal(done.resultPaths.vocals, '/tmp/v')
  assert.ok(done.completedAt)
})

test('failJob: chuyển failed + lưu lý do', async () => {
  const device = await makeDevice('i'.repeat(64), 1000)
  await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'queued', inputPath: '/tmp/a', expiresAt: new Date(Date.now() + 3600_000),
  })
  const claimed = await renderJob.claimNextJob('worker-1')

  const failed = await renderJob.failJob(claimed._id, 'worker-1', 'CUDA out of memory')
  assert.equal(failed.status, 'failed')
  assert.equal(failed.error, 'CUDA out of memory')
})

test('sweepStaleRunning (guardrail 5): job running mà heartbeat quá cũ tự chuyển failed', async () => {
  const device = await makeDevice('j'.repeat(64), 1000)
  const staleMinutes = await config.get('cloud.render.heartbeat.stale.minutes')
  const stuck = await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'running', workerId: 'dead-worker', inputPath: '/tmp/a',
    heartbeatAt: new Date(Date.now() - (staleMinutes + 1) * 60_000),
    startedAt: new Date(Date.now() - (staleMinutes + 1) * 60_000),
    expiresAt: new Date(Date.now() + 3600_000),
  })
  const alive = await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'running', workerId: 'alive-worker', inputPath: '/tmp/b',
    heartbeatAt: new Date(), startedAt: new Date(),
    expiresAt: new Date(Date.now() + 3600_000),
  })

  const failedCount = await renderJob.sweepStaleRunning()
  assert.equal(failedCount, 1)

  const stuckAfter = await RenderJob.findById(stuck._id).lean()
  assert.equal(stuckAfter.status, 'failed')
  assert.match(stuckAfter.error, /mất kết nối/)

  const aliveAfter = await RenderJob.findById(alive._id).lean()
  assert.equal(aliveAfter.status, 'running', 'job còn heartbeat sống không được đụng tới')
})

test('sweepStaleRunning: job queued (chưa ai nhận) không bị coi là stale', async () => {
  const device = await makeDevice('k'.repeat(64), 1000)
  await RenderJob.create({
    fingerprint: device.fingerprint, deviceId: device._id, stage: 'demucs',
    status: 'queued', inputPath: '/tmp/a', expiresAt: new Date(Date.now() + 3600_000),
  })
  const failedCount = await renderJob.sweepStaleRunning()
  assert.equal(failedCount, 0)
})

// --------------------------------------- Demucs thật + state machine ---- //

test('luồng worker thật: submit → claim → chạy Demucs thật (subprocess) → complete → tải kết quả',
  { skip: !HAS_DEMUCS && 'cần VOXDUB_TEST_DEMUCS_PYTHON trỏ tới python đã cài torch+demucs — xem docs/TEST_LOG.md mục V9/V12' },
  async () => {
    const device = await makeDevice('e'.repeat(64), 1000)
    const cost = await config.get('credit.cost.cloud.demucs')

    const { job: submitted, balanceAfter } = await renderJob.submitDemucsJob({
      device, fileStream: fakeWavStream(),
    })
    assert.equal(submitted.status, 'queued')
    assert.equal(balanceAfter, 1000 - cost)

    // Mô phỏng render_worker.py: claim rồi tự spawn demucs_worker.py với
    // đúng CLI contract (--input/--vocals/--no-vocals), y hệt cách worker
    // thật gọi — KHÔNG lặp lại logic tách nhạc, chỉ xác nhận contract khớp.
    const claimed = await renderJob.claimNextJob('test-worker')
    const paths = renderJob.jobPaths(claimed._id)
    const proc = spawnSync(DEMUCS_PYTHON, [
      WORKER_SCRIPT, '--input', claimed.inputPath,
      '--vocals', paths.vocals, '--no-vocals', paths.noVocals,
    ], { encoding: 'utf-8' })
    const lastLine = (proc.stdout || '').trim().split('\n').pop() || ''
    const parsed = JSON.parse(lastLine)
    assert.equal(parsed.ok, true, `demucs_worker.py lỗi: ${JSON.stringify(parsed)} — stderr: ${proc.stderr}`)

    const done = await renderJob.completeJob(claimed._id, 'test-worker',
      { vocals: paths.vocals, no_vocals: paths.noVocals })
    assert.equal(done.status, 'done')
    assert.ok(fs.existsSync(done.resultPaths.vocals))
    assert.ok(fs.existsSync(done.resultPaths.no_vocals))
    assert.ok(fs.statSync(done.resultPaths.vocals).size > 0)

    await renderJob.cleanupJob(done._id)
    assert.ok(!fs.existsSync(done.resultPaths.vocals), 'cleanup phải xoá file thật')
  })
