'use strict'

/**
 * Job lồng tiếng đầy đủ (ASR→dịch→TTS→mux) cho API bên thứ 3 (mini-spec
 * V34a, xem docs/PLAN.md — PoC hẹp, KHÔNG billing thật, xem Constraint 1).
 *
 * TÁCH RIÊNG khỏi `RenderJob` (đã audit lúc code — xem Scope B của V34a
 * trong docs/PLAN.md): 3 khác biệt đủ lớn để không nhét chung 1 model/enum
 * `stage`:
 *   - Identity: `RenderJob` gắn `Device`/`fingerprint` (app desktop);
 *     job này gắn `ApiKey` (developer bên thứ 3, V31) — hai hệ định danh
 *     khác hẳn nhau, không có `deviceId` nào để gán.
 *   - Hình dạng kết quả: `RenderJob` luôn là 2 stem audio cố định
 *     (`resultPaths.vocals`/`no_vocals`); job này là 1 file VIDEO output
 *     duy nhất, đường dẫn động theo `work_dir` mà `autodub.cli` tự đặt.
 *   - Tham số đầu vào: cần `sourceLang`/`targetLang`/`voice` — không có
 *     trường tương đương nào trong `RenderJob` (Demucs không có "ngôn ngữ").
 *
 * Vẫn TÁI DÙNG NGUYÊN VĂN state machine/queue pattern của `RenderJob`
 * (queued→running→done/failed, claim atomic, heartbeat, sweeper TTL/stale)
 * — chỉ đổi identity + shape, không viết lại cơ chế (Constraint 5 của V34a).
 */
const mongoose = require('mongoose')

const dubApiJobSchema = new mongoose.Schema({
  apiKeyId: { type: mongoose.Schema.Types.ObjectId, ref: 'ApiKey', required: true, index: true },
  status: {
    type: String,
    enum: ['queued', 'running', 'done', 'failed'],
    default: 'queued',
  },
  sourceLang: { type: String, required: true },
  targetLang: { type: String, required: true },
  voice: { type: String, default: '' },
  // Mini-spec V34b (docs/PLAN.md) — tách nhạc nền (Demucs), mặc định "none"
  // giữ đúng giá/hành vi cũ của V34a nếu caller không truyền gì.
  bgMode: { type: String, enum: ['none', 'demucs'], default: 'none' },
  inputPath: { type: String, required: true },
  outputPath: { type: String, default: '' },
  // Số liệu THẬT đo được lúc worker chạy xong (Constraint 3 của V34a: đo
  // thật, không suy đoán) — điền lúc completeJob(), rỗng khi chưa xong.
  // durationS (V34b): thời lượng video gốc đo bởi ASR, dùng để tính phí.
  metrics: {
    inputBytes: { type: Number, default: 0 },
    outputBytes: { type: Number, default: 0 },
    processingMs: { type: Number, default: 0 },
    durationS: { type: Number, default: 0 },
  },
  error: { type: String, default: '' },
  // V34a: chỉ log ước tính (Constraint 1 của V34a — PoC không billing thật).
  // V34b: `costVox` là số Vox THẬT đã trừ sau khi job hoàn tất — 0 nếu job
  // chưa xong hoặc thất bại. estimatedCostVox giữ lại cho tương thích/tham
  // khảo lúc submit (trước khi biết durationS thật).
  estimatedCostVox: { type: Number, default: 0 },
  costVox: { type: Number, default: 0 },
  // Mini-spec V43 — số phút đã giữ chỗ trên `ApiKey.dubMinutesReserved` lúc
  // submit job này. Lưu lại để completeJob()/failJob()/sweeper giải phóng
  // ĐÚNG con số đã giữ (không đoán lại), kể cả khi config reservation đổi
  // giữa lúc submit và lúc job kết thúc.
  reservedMinutes: { type: Number, default: 0 },
  workerId: { type: String, default: '' },
  heartbeatAt: { type: Date, default: null },
  startedAt: { type: Date, default: null },
  completedAt: { type: Date, default: null },
  expiresAt: { type: Date, required: true },
}, { timestamps: true })

dubApiJobSchema.index({ status: 1, expiresAt: 1 })
dubApiJobSchema.index({ status: 1, heartbeatAt: 1 })
dubApiJobSchema.index({ status: 1, createdAt: 1 })

module.exports = mongoose.models.DubApiJob
  || mongoose.model('DubApiJob', dubApiJobSchema)
