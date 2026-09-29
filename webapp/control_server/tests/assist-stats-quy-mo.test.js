'use strict'

/**
 * D2 — đọc được QUY MÔ đầu vào, chứ không chỉ tổng token.
 *
 * `inputSize` (vd số đoạn của kịch bản) đã được ghi từ lâu và có trong schema,
 * nhưng **chưa đường nào đọc nó ra**. Nên câu hỏi mà D2 phải trả lời — giá
 * phẳng 12 Vox đang bù chéo bao nhiêu giữa kịch bản 5 đoạn và 40 đoạn — vẫn
 * không trả lời được, dù dữ liệu nằm sẵn trong cơ sở dữ liệu.
 *
 * Chạy truy vấn THẬT chứ không soi hình dạng: truy vấn gộp sai vẫn trả về số,
 * chỉ là số sai — đúng lớp hỏng âm thầm mà `assist-stats.test.js` đã cảnh báo,
 * và soi hình dạng thì không bao giờ bắt được lỗi số học.
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const UsageLog = require('../src/models/UsageLog')
const stats = require('../src/services/assist-stats.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(clearDb)

let n = 0
async function ghi({ inputSize, tokenVao = 100, tokenRa = 50, fromCache = false }) {
  n += 1
  await UsageLog.create({
    fingerprint: 'a'.repeat(64), jobId: `j${n}`, action: 'assist',
    assistTask: 'brand_script_rewrite', inputSize,
    promptTokens: tokenVao, completionTokens: tokenRa,
    fromCache, creditCharged: 12, status: 'success',
  })
}

const chay = async () => (await UsageLog.aggregate(stats.theoTacVu(7)))[0]

test('quy mô trung bình tính đúng', async () => {
  await ghi({ inputSize: 5 })
  await ghi({ inputSize: 15 })
  const r = await chay()
  assert.equal(r.quyMoTB, 10)
})

test('token mỗi đơn vị đầu vào — con số D2 thật sự cần', async () => {
  // 2 lượt, tổng 20 đoạn, tổng token (100+50)*2 = 300 ⇒ 15 token/đoạn.
  await ghi({ inputSize: 5 })
  await ghi({ inputSize: 15 })
  const r = await chay()
  assert.equal(r.tokenMoiDonVi, 15)
})

test('LƯỢT DÙNG LẠI không được kéo con số xuống thấp giả', async () => {
  // Lượt dùng lại kết quả cũ tốn 0 token. Gộp nó vào mẫu số thì "token mỗi
  // đoạn" tụt xuống, và ai đọc sẽ tưởng việc này rẻ hơn thực tế.
  await ghi({ inputSize: 10, tokenVao: 100, tokenRa: 50 })
  await ghi({ inputSize: 10, tokenVao: 0, tokenRa: 0, fromCache: true })
  const r = await chay()
  assert.equal(r.quyMoTB, 10, 'quy mô TB phải tính trên lượt gọi thật')
  assert.equal(r.tokenMoiDonVi, 15, '150 token / 10 đoạn')
  assert.equal(r.luot, 2, 'nhưng tổng lượt vẫn phải đếm đủ cả hai')
  assert.equal(r.dungLai, 1)
})

test('chưa có quy mô nào thì trả 0, KHÔNG chia cho 0', async () => {
  await ghi({ inputSize: 0 })
  const r = await chay()
  assert.equal(r.quyMoTB, 0)
  assert.equal(r.tokenMoiDonVi, 0)
  assert.ok(Number.isFinite(r.tokenMoiDonVi))
})

test('TẤT CẢ đều là lượt dùng lại thì vẫn không chia cho 0', async () => {
  await ghi({ inputSize: 10, tokenVao: 0, tokenRa: 0, fromCache: true })
  const r = await chay()
  assert.equal(r.quyMoTB, 0)
  assert.equal(r.tokenMoiDonVi, 0)
})

test('ĐỪNG SỬA QUÁ TAY: các cột cũ không đổi nghĩa', async () => {
  await ghi({ inputSize: 5, tokenVao: 100, tokenRa: 50 })
  await ghi({ inputSize: 15, tokenVao: 200, tokenRa: 100 })
  const r = await chay()
  assert.equal(r.tokenVao, 300)
  assert.equal(r.tokenRa, 150)
  assert.equal(r.vox, 24)
  assert.equal(r.soMay, 1)
})
