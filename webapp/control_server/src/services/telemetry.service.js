'use strict'

/**
 * Ghi + tổng hợp trạng thái tiến trình lồng tiếng (mini-spec V13, xem
 * docs/PLAN.md). Nguồn dữ liệu DUY NHẤT: `PipelineEvent`, 1 document mỗi
 * run — không lưu lịch sử từng bước, chỉ điểm dừng MỚI NHẤT.
 */
const PipelineEvent = require('../models/PipelineEvent')

// Khớp autodub.progress.STEPS (thứ tự thật của pipeline) — giữ đồng bộ
// tay với autodub/progress.py, đổi 1 bên phải đổi bên kia.
const FULL_STEPS = [
  'acquire', 'extract', 'separate', 'asr', 'translate', 'tts',
  'merge_audio', 'merge_video', 'content', 'done',
]
// 6 chặng hiện trên dashboard (mini-spec V13 Scope D) — tên kỹ thuật giữ
// nguyên "stage" trong DB, UI tự dịch sang "Tải video/Tách nhạc/Nghe.../...".
const FUNNEL_CHECKPOINTS = ['acquire', 'separate', 'asr', 'translate', 'tts', 'merge_video']

const ALLOWED_STAGES = new Set(FULL_STEPS)
const ALLOWED_STATUSES = new Set(['started', 'completed', 'failed'])

class TelemetryError extends Error {
  constructor(code, message) {
    super(message)
    this.name = 'TelemetryError'
    this.code = code
  }
}

function stepIndex(step) {
  const i = FULL_STEPS.indexOf(step)
  return i === -1 ? 0 : i
}

/**
 * Upsert 1 lần cập nhật tiến trình theo (fingerprint, runId). Validate
 * NGHIÊM status/stage — giá trị lạ bị TỪ CHỐI (400), không âm thầm ghi rác.
 */
async function recordEvent({ fingerprint, runId, status, stage, errorStage }) {
  if (!ALLOWED_STATUSES.has(status)) {
    throw new TelemetryError('BAD_STATUS', `status không hợp lệ: ${status}`)
  }
  if (!ALLOWED_STAGES.has(stage)) {
    throw new TelemetryError('BAD_STAGE', `stage không hợp lệ: ${stage}`)
  }
  const now = new Date()
  const update = { status, stage, updatedAt: now }
  if (errorStage) {
    if (!ALLOWED_STAGES.has(errorStage)) {
      throw new TelemetryError('BAD_STAGE', `errorStage không hợp lệ: ${errorStage}`)
    }
    update.errorStage = errorStage
  }
  if (status === 'completed' || status === 'failed') {
    update.completedAt = now
  }
  await PipelineEvent.findOneAndUpdate(
    { fingerprint, runId },
    { $set: update, $setOnInsert: { startedAt: now } },
    { upsert: true },
  )
}

/**
 * Phễu theo stage (mini-spec V13 Scope D) — số run PHÂN BIỆT đã từng đạt
 * tới mỗi chặng, bất kể kết cục cuối cùng (completed/failed/còn "started").
 * "Đạt tới" suy từ điểm dừng MỚI NHẤT (không có lịch sử từng bước): run
 * dừng ở stage X thì coi là đã đạt mọi chặng có thứ tự <= X.
 */
async function funnel(sinceDate) {
  const events = await PipelineEvent.find(
    { startedAt: { $gte: sinceDate } }, { stage: 1 },
  ).lean()
  const counts = FUNNEL_CHECKPOINTS.map(() => 0)
  for (const e of events) {
    const reachedIdx = stepIndex(e.stage)
    FUNNEL_CHECKPOINTS.forEach((cp, i) => {
      if (stepIndex(cp) <= reachedIdx) counts[i] += 1
    })
  }
  return FUNNEL_CHECKPOINTS.map((stage, i) => ({ stage, count: counts[i] }))
}

/**
 * "Bỏ dở" (guardrail 4): `started` nhưng không `completed`/`failed` trong
 * `staleHours`. ƯỚC LƯỢNG, không phải sự thật tuyệt đối — không có sự kiện
 * "abandoned" tường minh nào (không ai bấm nút "tôi bỏ cuộc"), đây là suy
 * luận gián tiếp từ im lặng quá lâu.
 */
async function abandonedCount(staleHours = 6, sinceDate) {
  const staleBefore = new Date(Date.now() - staleHours * 3600_000)
  return PipelineEvent.countDocuments({
    status: 'started',
    updatedAt: { $lt: staleBefore },
    ...(sinceDate ? { startedAt: { $gte: sinceDate } } : {}),
  })
}

/** Tổng quan cho dashboard: phễu + số hoàn thành/lỗi/bỏ dở trong khoảng. */
async function overview(days = 7, staleHours = 6) {
  const sinceDate = new Date(Date.now() - days * 24 * 3600_000)
  const [funnelData, completed, failed, abandoned] = await Promise.all([
    funnel(sinceDate),
    PipelineEvent.countDocuments({ status: 'completed', startedAt: { $gte: sinceDate } }),
    PipelineEvent.countDocuments({ status: 'failed', startedAt: { $gte: sinceDate } }),
    abandonedCount(staleHours, sinceDate),
  ])
  const started = funnelData.length ? funnelData[0].count : 0
  return { days, staleHours, funnel: funnelData, started, completed, failed, abandoned }
}

module.exports = {
  TelemetryError,
  recordEvent,
  funnel,
  abandonedCount,
  overview,
  FULL_STEPS,
  FUNNEL_CHECKPOINTS,
  ALLOWED_STAGES,
  ALLOWED_STATUSES,
}
