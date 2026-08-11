'use strict'

/**
 * Mini-spec V13 (docs/PLAN.md) — telemetry.service.js: state machine
 * PipelineEvent (started→started nhiều lần cập nhật stage→completed/failed),
 * phễu theo stage, và định nghĩa "bỏ dở" (guardrail 4 — ước lượng theo
 * updatedAt quá cũ, không phải sự thật tuyệt đối). Chạm MongoDB thật
 * (in-memory).
 *
 * Chạy:  node --test tests/telemetry.integration.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const PipelineEvent = require('../src/models/PipelineEvent')
const telemetry = require('../src/services/telemetry.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(clearDb)

const FP = 'a'.repeat(64)

test('recordEvent: từ chối status lạ', async () => {
  await assert.rejects(
    () => telemetry.recordEvent({ fingerprint: FP, runId: 'r1', status: 'weird', stage: 'acquire' }),
    (err) => err.code === 'BAD_STATUS',
  )
})

test('recordEvent: từ chối stage lạ (chặn nội dung/đường dẫn giả làm stage)', async () => {
  await assert.rejects(
    () => telemetry.recordEvent({
      fingerprint: FP, runId: 'r1', status: 'started', stage: '/home/user/video.mp4',
    }),
    (err) => err.code === 'BAD_STAGE',
  )
})

test('recordEvent: started tạo document mới, startedAt=updatedAt lúc đầu', async () => {
  await telemetry.recordEvent({ fingerprint: FP, runId: 'r1', status: 'started', stage: 'acquire' })
  const doc = await PipelineEvent.findOne({ fingerprint: FP, runId: 'r1' }).lean()
  assert.equal(doc.status, 'started')
  assert.equal(doc.stage, 'acquire')
  assert.equal(doc.completedAt, null)
  assert.ok(doc.startedAt)
});

test('recordEvent: cập nhật stage nhiều lần trong lúc vẫn started — giữ nguyên startedAt', async () => {
  await telemetry.recordEvent({ fingerprint: FP, runId: 'r2', status: 'started', stage: 'acquire' })
  const first = await PipelineEvent.findOne({ fingerprint: FP, runId: 'r2' }).lean()

  await telemetry.recordEvent({ fingerprint: FP, runId: 'r2', status: 'started', stage: 'asr' })
  const second = await PipelineEvent.findOne({ fingerprint: FP, runId: 'r2' }).lean()

  assert.equal(second.stage, 'asr')
  assert.equal(second.status, 'started')
  assert.equal(second.startedAt.getTime(), first.startedAt.getTime(),
    'startedAt không được đổi khi chỉ cập nhật stage')
  // Chỉ có 1 document cho 1 run — upsert theo (fingerprint, runId), không
  // tạo bản ghi mới mỗi lần cập nhật stage.
  const count = await PipelineEvent.countDocuments({ fingerprint: FP, runId: 'r2' })
  assert.equal(count, 1)
});

test('recordEvent: completed đặt completedAt', async () => {
  await telemetry.recordEvent({ fingerprint: FP, runId: 'r3', status: 'started', stage: 'acquire' })
  await telemetry.recordEvent({ fingerprint: FP, runId: 'r3', status: 'completed', stage: 'done' })
  const doc = await PipelineEvent.findOne({ fingerprint: FP, runId: 'r3' }).lean()
  assert.equal(doc.status, 'completed')
  assert.ok(doc.completedAt)
});

test('recordEvent: failed lưu errorStage', async () => {
  await telemetry.recordEvent({ fingerprint: FP, runId: 'r4', status: 'started', stage: 'acquire' })
  await telemetry.recordEvent({ fingerprint: FP, runId: 'r4', status: 'started', stage: 'asr' })
  await telemetry.recordEvent({
    fingerprint: FP, runId: 'r4', status: 'failed', stage: 'translate', errorStage: 'translate',
  })
  const doc = await PipelineEvent.findOne({ fingerprint: FP, runId: 'r4' }).lean()
  assert.equal(doc.status, 'failed')
  assert.equal(doc.errorStage, 'translate')
  assert.ok(doc.completedAt)
});

test('funnel: run dừng ở stage X được tính vào MỌI chặng <= X, không chặng sau', async () => {
  // r1 chỉ tới "acquire", r2 tới "asr", r3 hoàn tất (đi hết tới "done").
  await telemetry.recordEvent({ fingerprint: FP, runId: 'f1', status: 'started', stage: 'acquire' })
  await telemetry.recordEvent({ fingerprint: FP, runId: 'f2', status: 'started', stage: 'asr' })
  await telemetry.recordEvent({ fingerprint: FP, runId: 'f3', status: 'started', stage: 'acquire' })
  await telemetry.recordEvent({ fingerprint: FP, runId: 'f3', status: 'started', stage: 'tts' })
  await telemetry.recordEvent({ fingerprint: FP, runId: 'f3', status: 'completed', stage: 'done' })

  const result = await telemetry.funnel(new Date(0))
  const byStage = Object.fromEntries(result.map((r) => [r.stage, r.count]))
  assert.equal(byStage.acquire, 3, 'cả 3 run đều đạt tới acquire')
  assert.equal(byStage.separate, 2, 'f1 dừng trước separate, chỉ f2+f3 đạt tới')
  assert.equal(byStage.asr, 2)
  assert.equal(byStage.tts, 1, 'chỉ f3 đạt tới tts')
  assert.equal(byStage.merge_video, 1, 'f3 hoàn tất (done) tính là đã qua merge_video')
});

test('abandonedCount: started + updatedAt quá cũ mới tính, completed/failed không bao giờ tính', async () => {
  await PipelineEvent.create({
    fingerprint: FP, runId: 'stale1', status: 'started', stage: 'asr',
    startedAt: new Date(Date.now() - 10 * 3600_000),
    updatedAt: new Date(Date.now() - 8 * 3600_000),
  })
  await PipelineEvent.create({
    fingerprint: FP, runId: 'fresh1', status: 'started', stage: 'asr',
    startedAt: new Date(), updatedAt: new Date(),
  })
  await PipelineEvent.create({
    fingerprint: FP, runId: 'old-but-done', status: 'completed', stage: 'done',
    startedAt: new Date(Date.now() - 10 * 3600_000),
    updatedAt: new Date(Date.now() - 8 * 3600_000),
    completedAt: new Date(Date.now() - 8 * 3600_000),
  })

  const count = await telemetry.abandonedCount(6, new Date(0))
  assert.equal(count, 1, 'chỉ stale1 (started, im lặng > 6h) được tính là bỏ dở')
});

test('overview: gộp đúng phễu + completed/failed/abandoned', async () => {
  await telemetry.recordEvent({ fingerprint: FP, runId: 'o1', status: 'started', stage: 'acquire' });
  await telemetry.recordEvent({ fingerprint: FP, runId: 'o1', status: 'completed', stage: 'done' });
  await telemetry.recordEvent({ fingerprint: FP, runId: 'o2', status: 'started', stage: 'asr' });
  await telemetry.recordEvent({
    fingerprint: FP, runId: 'o2', status: 'failed', stage: 'asr', errorStage: 'asr',
  });

  const result = await telemetry.overview(7, 6);
  assert.equal(result.completed, 1);
  assert.equal(result.failed, 1);
  assert.equal(result.started, 2, '"started" trong overview = số run đạt chặng đầu tiên (acquire)');
});
