'use strict'

/**
 * Kết quả đã lưu theo jobId — cho phép app retry an toàn (idempotent replay)
 * mà không bị tính phí/gọi AI lần hai. Dựng lại từ routes/ai.js — xem ghi
 * chú Device.js.
 */
const mongoose = require('mongoose')

const jobResultSchema = new mongoose.Schema({
  jobId: { type: String, required: true },
  fingerprint: { type: String, required: true },
  action: {
    type: String,
    // Danh sách này PHẢI phủ mọi giá trị `remember()` được gọi với — có test
    // đối chiếu (`job-result-actions.test.js`).
    //
    // Bug thật, 22/8/2026: `assist` (V89) và `product_scene` (C1) thêm route
    // mà quên thêm ở đây. Mongoose ném lỗi validation, `remember()` ném tiếp,
    // và route chết SAU KHI đã trừ tiền — người dùng mất 30 Vox mỗi lượt, sổ
    // máy chủ ghi "thành công", còn app nhận về lỗi 500 không hiểu nổi. Ba
    // lượt liên tiếp như vậy trước khi tìm ra.
    enum: [
      'translate', 'analyze', 'review', 'generate_post', 'translate_subtitle',
      'assist',         // mini-spec V89
      'product_scene',  // mini-spec C1
    ],
    required: true,
  },
  result: { type: mongoose.Schema.Types.Mixed, required: true },
  creditCharged: { type: Number, default: 0 },
}, { timestamps: true })

// replay() đọc bằng {jobId, fingerprint} — cùng cặp phải là duy nhất,
// remember() dựa vào lỗi 11000 để phát hiện "đã lưu rồi".
jobResultSchema.index({ jobId: 1, fingerprint: 1 }, { unique: true })

module.exports = mongoose.models.JobResult || mongoose.model('JobResult', jobResultSchema)
