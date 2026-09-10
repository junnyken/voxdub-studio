'use strict'

/**
 * Bốn hàm dùng chung cho MỌI cửa gọi mô hình AI có tính phí (mini-spec H2 —
 * tách ra từ `routes/ai.js` để `routes/flow-blueprints.js` dùng lại đúng
 * logic billing, không viết lại — hai nơi cùng viết logic trừ Vox là hai cơ
 * hội để lệch nhau).
 *
 * Trật tự bất biến khi dùng bốn hàm này:
 *   1. `replay(jobId)` — đã xử lý rồi thì trả kết quả cũ, KHÔNG tính phí lại.
 *   2. `precheck(...)` — đủ tiền không, TRƯỚC khi gọi mô hình.
 *   3. Gọi mô hình.
 *   4. `charge(...)` — chỉ trừ khi mô hình trả về THÀNH CÔNG.
 *   5. `remember(...)` — lưu kết quả theo jobId để gọi lại không mất tiền lần hai.
 */
const JobResult = require('../models/JobResult')
const credit = require('./credit.service')
const holds = require('./hold.service')

/** Kết quả đã lưu của jobId này, hoặc null. */
async function replay(jobId, fingerprint) {
  if (!jobId) return null
  const doc = await JobResult.findOne({ jobId, fingerprint }).lean()
  return doc ? doc.result : null
}

/**
 * Nhớ kết quả để app gọi lại cùng `jobId` không bị tính tiền lần hai.
 *
 * **Không bao giờ được ném ra ngoài.** Đây là lớp TĂNG TỐC, không phải một
 * phần của việc chính: lượt gọi đã chạy xong, tiền đã trừ, kết quả đang nằm
 * trong tay. Ghi đệm hỏng mà giết cả lượt gọi thì người dùng mất tiền và
 * không nhận được gì — chính xác chuyện đã xảy ra ngày 22/8/2026 khi enum
 * `action` thiếu hai giá trị.
 *
 * Hỏng thì KÊU TO trong log máy chủ (không nuốt im lặng), nhưng người dùng
 * vẫn nhận được kết quả họ đã trả tiền.
 */
async function remember(jobId, fingerprint, action, result, creditCharged, log) {
  if (!jobId) return
  try {
    await JobResult.create({ jobId, fingerprint, action, result, creditCharged })
  } catch (err) {
    if (err.code === 11000) return   // trùng jobId = đã lưu rồi, không sao
    const noi = log || console
    noi.error({ err, action, jobId },
      'remember() hỏng — lượt gọi VẪN trả kết quả, nhưng gọi lại cùng jobId '
      + 'sẽ tính tiền lần nữa')
  }
}

/**
 * Kiểm tra khả năng chi trả TRƯỚC khi gọi mô hình.
 *
 * Hold hấp thụ được lượt này (active, hoặc committed + gói đăng bài cho
 * generate_post — xem `holds.canAbsorb`): đã trả tiền trọn lượt lúc tạo hold,
 * không kiểm tra gì nữa. Không có hold: so với số dư ví (đường dự phòng,
 * xem `walletCost`).
 * Trả về null nếu đủ, ngược lại {balance, required} để route trả 402.
 */
async function precheck(fingerprint, holdId, cost, { action = '', jobId = '' } = {}) {
  if (holdId) {
    const hold = await holds.getHold(fingerprint, holdId)
    if (holds.canAbsorb(hold, action, jobId)) return null
  }
  if (cost <= 0) return null
  const balance = await credit.getBalance(fingerprint)
  if (balance >= cost) return null
  return { balance, required: cost }
}

/**
 * Kết thúc một lượt AI thành công.
 *
 * Hold hấp thụ được (active — hoặc committed + gói đăng bài cho đúng một
 * lượt generate_post): KHÔNG trừ ví. Tiền của cả lượt đã thu lúc tạo hold
 * theo số segment, nên ở đây chỉ ghi `internalVox` vào `hold.usage` để đối
 * soát biên lợi nhuận. `charged: 0` là đúng — app hiện tổng một lần ở bước
 * xuất video, không hiện từng lượt.
 *
 * Hold không hấp thụ được (đã tự chốt sau TTL, hoặc lượt vượt phạm vi):
 * rơi về trừ ví thẳng theo `walletCost` — đường dự phòng cho các lượt lẻ
 * ngoài luồng wizard.
 * Trả về { charged, balanceAfter }.
 */
async function charge(device, { holdId, jobId, action, walletCost, internalVox,
  sentences, description, ip }) {
  if (holdId) {
    const res = await holds.accrue({
      holdId,
      fingerprint: device.fingerprint,
      jobId,
      action,
      vox: internalVox,
      sentences,
    })
    if (res) {
      return { charged: 0, balanceAfter: await credit.getBalance(device.fingerprint) }
    }
    // Hold không hấp thụ được lượt này — rơi về đường cũ.
  }
  const amount = walletCost
  if (amount <= 0) {
    return { charged: 0, balanceAfter: await credit.getBalance(device.fingerprint) }
  }
  const prefix = { translate: 'translate', analyze: 'analyze', review: 'review',
    generate_post: 'post' }[action] || action
  try {
    const deducted = await credit.deduct(device.fingerprint, amount, {
      type: 'usage',
      idempotencyKey: `${prefix}-${jobId}`,
      description,
      metadata: { jobId, action, sentences, ip },
    })
    return { charged: amount, balanceAfter: deducted.balanceAfter }
  } catch (err) {
    if (!(err instanceof credit.InsufficientCreditError)) throw err
    // Precheck đã qua nhưng một request song song rút cạn ví trước khi trừ.
    // Mô hình ĐÃ chạy — phí AI phía server đã tiêu. Ném lỗi ở đây nghĩa là
    // route trả 5xx, jobId chưa được remember, app retry → server trả phí AI
    // lần thứ hai cho cùng một việc. Thay vào đó thu trần số dư còn lại và
    // trả kết quả — server không bao giờ chịu lỗ, ví không bao giờ âm.
    const clamp = Math.max(0, err.balance)
    if (clamp === 0) {
      return { charged: 0, balanceAfter: 0 }
    }
    try {
      const deducted = await credit.deduct(device.fingerprint, clamp, {
        type: 'usage',
        idempotencyKey: `${prefix}-${jobId}`,
        description: `${description} (thu được ${clamp}/${amount} Vox)`,
        metadata: { jobId, action, sentences, ip, clamped: true, intended: amount },
      })
      return { charged: clamp, balanceAfter: deducted.balanceAfter }
    } catch (err2) {
      // Ví lại bị rút tiếp giữa hai nhịp — thôi, coi như thu được 0. Kết quả
      // vẫn phải trả về: phí AI đã tiêu, giữ kết quả lại không cứu được gì.
      if (err2 instanceof credit.InsufficientCreditError) {
        return { charged: 0, balanceAfter: Math.max(0, err2.balance) }
      }
      throw err2
    }
  }
}

/**
 * Đếm số lượt trợ lý một máy đã dùng HÔM NAY — lớp chặn chi phí thứ 3.
 *
 * Chuyển từ `routes/ai.js` sang đây (mini-spec H3) để `flow-blueprints` và
 * `brand-scripts` dùng chung. Hai route đó gọi thẳng `gateway.assist()` chứ
 * không đi qua `/v1/ai/assist`, nên trước đây chúng **thiếu hẳn lớp hạn mức
 * ngày**: rate-limit theo phút chỉ chặn được người bấm dồn dập, không chặn
 * được một vòng lặp hỏng chạy cả ngày.
 *
 * Lượt "Thử ngay" của trang quản trị KHÔNG tính: đó là phép kiểm cấu hình của
 * người quản trị, không phải người dùng đang tiêu hạn mức của mình.
 */
async function assistUsedToday(fingerprint, task) {
  const UsageLog = require('../models/UsageLog')
  const dau_ngay = new Date()
  dau_ngay.setHours(0, 0, 0, 0)
  const dieu_kien = {
    fingerprint,
    action: 'assist',
    runMode: { $ne: 'test_now' },
    createdAt: { $gte: dau_ngay },
  }
  if (task) dieu_kien.assistTask = task
  return UsageLog.countDocuments(dieu_kien)
}

/**
 * Kiểm cả hạn mức RIÊNG của tác vụ lẫn hạn mức CHUNG. Trả `null` khi còn
 * lượt, hoặc `{ tran, message }` khi đã hết — bên gọi tự trả 429.
 *
 * Hạn mức riêng đi trước hạn mức chung: tác vụ miễn phí (như `explain_error`)
 * không bị giá Vox chặn nên cần trần riêng.
 */
async function kiemHanMucNgay(config, fingerprint, task) {
  const cfg = await config.getMany(['assist.daily.limit', `assist.daily.limit.${task}`])
  const tranRieng = cfg[`assist.daily.limit.${task}`]
  if (tranRieng > 0 && (await assistUsedToday(fingerprint, task)) >= tranRieng) {
    return { tran: tranRieng,
      message: `Hôm nay đã dùng hết ${tranRieng} lượt cho việc này. Thử lại vào ngày mai.` }
  }
  const tranChung = cfg['assist.daily.limit']
  if (tranChung > 0 && (await assistUsedToday(fingerprint, '')) >= tranChung) {
    return { tran: tranChung,
      message: `Hôm nay đã dùng hết ${tranChung} lượt trợ lý. Thử lại vào ngày mai.` }
  }
  return null
}

module.exports = { replay, remember, precheck, charge, assistUsedToday, kiemHanMucNgay }
