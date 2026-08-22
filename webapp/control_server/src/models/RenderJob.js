'use strict'

/**
 * Job xử lý 1 stage nặng trên cloud (mini-spec V9, xem docs/PLAN.md — POC
 * hẹp: CHỈ Demucs, không phải full pipeline). Dựng theo đúng convention
 * model đã dựng lại ở V0 (xem docs/TEST_LOG.md).
 *
 * Chính sách dữ liệu (đã chủ dự án duyệt, 2026-08-11 — guardrail 2 của
 * mini-spec V9): file input/output XOÁ NGAY sau khi trả kết quả cho
 * người dùng, TTL dự phòng `expiresAt` cho trường hợp không ai tới lấy.
 *
 * Mini-spec V12 (docs/PLAN.md): xử lý bất đồng bộ thật — job vào `queued`,
 * 1 worker Python riêng (container khác, poll qua HTTP nội bộ) nhận job,
 * chuyển `running` kèm `workerId`/`heartbeatAt`. Không thêm Redis/broker —
 * chính RenderJob (Mongo) vẫn là nguồn sự thật duy nhất (guardrail 2).
 */
const mongoose = require('mongoose')

const renderJobSchema = new mongoose.Schema({
  fingerprint: { type: String, required: true, index: true },
  deviceId: { type: mongoose.Schema.Types.ObjectId, ref: 'Device', required: true },
  stage: { type: String, enum: ['demucs'], required: true },
  status: {
    type: String,
    enum: ['queued', 'running', 'done', 'failed'],
    default: 'queued',
  },
  inputPath: { type: String, required: true },
  resultPaths: {
    vocals: { type: String, default: '' },
    no_vocals: { type: String, default: '' },
  },
  // Đánh dấu từng stem đã được tải chưa — xoá cả job khi CẢ HAI đã tải,
  // không suy luận qua sự tồn tại của file (file vẫn còn tới lúc bị xoá).
  downloaded: {
    vocals: { type: Boolean, default: false },
    no_vocals: { type: Boolean, default: false },
  },
  error: { type: String, default: '' },
  creditCharged: { type: Number, default: 0 },
  // Worker Python nào đang giữ job này (mini-spec V12) — phát hiện worker
  // chết giữa chừng: heartbeat không cập nhật quá lâu thì sweeper chuyển
  // job sang `failed` thay vì treo mãi ở `running` (guardrail 5).
  workerId: { type: String, default: '' },
  heartbeatAt: { type: Date, default: null },
  startedAt: { type: Date, default: null },
  completedAt: { type: Date, default: null },
  // TTL dự phòng — sweeper (giống expireSweep của CreditHold) xoá file +
  // job quá hạn dù người dùng không bao giờ quay lại tải kết quả.
  expiresAt: { type: Date, required: true },
}, { timestamps: true })

renderJobSchema.index({ status: 1, expiresAt: 1 })
// Sweeper heartbeat-hết-hạn (V12) query { status: 'running', heartbeatAt: {$lt} }.
renderJobSchema.index({ status: 1, heartbeatAt: 1 })
// claimNextJob() lấy job queued CŨ NHẤT trước (FIFO) — index đúng chiều sort.
renderJobSchema.index({ status: 1, createdAt: 1 })

module.exports = mongoose.models.RenderJob
  || mongoose.model('RenderJob', renderJobSchema)
