'use strict'

/**
 * Trạng thái tiến trình MỘT LƯỢT lồng tiếng (mini-spec V13, xem docs/PLAN.md)
 * — 1 document mỗi run (upsert theo fingerprint+runId). CHỈ ghi ở chế độ
 * SaaS — client (autodub.telemetry) tự chặn gọi khi local-only
 * (is_configured()==False, guardrail 5), server không cần biết chế độ nào.
 *
 * KHÔNG BAO GIỜ chứa nội dung (video/transcript/audio/đường dẫn file) —
 * chỉ (fingerprint, runId, stage, status, timestamp) theo đúng guardrail 2
 * của mini-spec. `routes/telemetry.js` CHẶN field lạ ở tầng validate
 * (không âm thầm bỏ qua) — đây là ranh giới thật ngăn nội dung lọt vào.
 *
 * `stage` là giai đoạn MỚI NHẤT đã qua (khớp autodub.progress.STEPS), cập
 * nhật liên tục trong lúc `status` vẫn "started" — cho phễu biết run dừng/
 * đang ở đâu mà không cần lưu lịch sử từng bước.
 */
const mongoose = require('mongoose')

const pipelineEventSchema = new mongoose.Schema({
  fingerprint: { type: String, required: true, index: true },
  runId: { type: String, required: true },
  status: { type: String, enum: ['started', 'completed', 'failed'], required: true },
  stage: { type: String, required: true },
  errorStage: { type: String, default: '' },   // chỉ có nghĩa khi status=failed
  startedAt: { type: Date, required: true },
  // Nhịp cập nhật cuối — dùng tính "bỏ dở" (guardrail 4: started nhưng
  // updatedAt quá cũ = coi như bỏ dở, ước lượng chứ không phải sự thật
  // tuyệt đối, xem docs/TEST_LOG.md mục V13).
  updatedAt: { type: Date, required: true },
  completedAt: { type: Date, default: null },
})

pipelineEventSchema.index({ fingerprint: 1, runId: 1 }, { unique: true })
pipelineEventSchema.index({ status: 1, updatedAt: 1 })

module.exports = mongoose.models.PipelineEvent
  || mongoose.model('PipelineEvent', pipelineEventSchema)
