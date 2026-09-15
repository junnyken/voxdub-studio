'use strict'

/**
 * H2 — máy chủ phải NÓI RA vì sao không phân tích được.
 *
 * Người dùng chạy thật 11/09/2026 trên `youtube.com/shorts/9iB1Io8InXg`:
 * tải video, chép lời (10 đoạn), đọc chữ 65 khung — gần sáu phút và ~88 Vox —
 * rồi nhận đúng một câu: *"Không phân tích được lúc này. Thử lại sau."*
 *
 * Câu đó không cho biết nên đợi mạng, đổi video, hay báo lỗi. Máy chủ BIẾT
 * nguyên nhân (`AiError` mang `code` và câu riêng) nhưng nhánh `catch` ném đi
 * hết, thay mọi thứ không phải 400 bằng một mã 503 duy nhất.
 *
 * Ba ca dưới đây phải nói ba câu KHÁC nhau, vì ba cách chữa khác nhau:
 * đổi video / báo lỗi phần mềm / đợi rồi thử lại.
 *
 * Chạy:  node --test tests/flow-blueprint-noi-ro-ly-do.test.js
 */
const test = require('node:test')
const { mock } = require('node:test')
const assert = require('node:assert')
const crypto = require('node:crypto')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const deviceService = require('../src/services/device.service')
const gateway = require('../src/services/ai-gateway.service')
const Device = require('../src/models/Device')

let app

test.before(async () => {
  await startDb()
  app = await build({ mongo: false, web: false, logger: false })
  await app.ready()
})
test.after(async () => {
  await app.close()
  await stopDb()
})
test.beforeEach(async () => {
  await clearDb()
  mock.restoreAll()
})

const VI_DAU_KY = 1000

async function thietBiMoi() {
  const { device, token } = await deviceService.registerDevice({
    fingerprint: crypto.randomBytes(32).toString('hex'), name: 'may-thu',
  })
  await Device.updateOne({ _id: device._id }, { $set: { balance: VI_DAU_KY } })
  return { device, token }
}

/** Dữ liệu THẬT lấy từ nhật ký người dùng gửi kèm (11/09, 16:51). */
function than() {
  return {
    jobId: `job-${crypto.randomBytes(6).toString('hex')}`,
    sourceType: 'url',
    sourceReference: 'https://www.youtube.com/shorts/9iB1Io8InXg',
    languageSourceDetected: 'vi',
    samplingPolicyUsed: '0-5s=0.2,middle=0.5,last-5s=0.2',
    evidenceSummary: 'ASR: 10 đoạn tiếng Việt. OCR: 65 đoạn chữ.',
    transcript: [
      { start_s: 0.1, end_s: 3.4, text: 'Super sale đơn nổ mà sao mặt mày thế' },
      { start_s: 4.5, end_s: 5.9, text: 'Mệt mỏi thật sự không ạ' },
    ],
    ocrEvidence: [
      { start_s: 0.2, end_s: 3, status: 'ok', text: 'hóa đơn' },
    ],
  }
}

function goi(token) {
  return app.inject({
    method: 'POST', url: '/v1/flow-blueprints', payload: than(),
    headers: { authorization: `Bearer ${token}` },
  })
}

/** Cho `gateway.assist` ném đúng lỗi cần đo. */
function assistNem({ message, code, statusCode }) {
  mock.method(gateway, 'assist', async () => {
    const e = new Error(message)
    if (code) e.code = code
    if (statusCode) e.statusCode = statusCode
    throw e
  })
}

test('sao chép nguyên văn: nói RÕ là sao chép, không phải "thử lại sau"', async () => {
  const { token } = await thietBiMoi()
  assistNem({
    message: 'Đoạn 2 lặp lại cụm "hóa đơn" có trong bằng chứng nguồn',
    code: 'SAO_CHEP_NGUYEN_VAN', statusCode: 422,
  })

  const res = await goi(token)

  assert.notStrictEqual(res.statusCode, 503,
    'sao chép nguyên văn KHÔNG phải sự cố tạm thời — bảo "thử lại sau" là '
    + 'lời khuyên sai, thử lại bao nhiêu lần cũng ra đúng kết quả đó')
  const b = res.json()
  assert.strictEqual(b.code, 'SAO_CHEP_NGUYEN_VAN')
  assert.match(b.message, /hóa đơn/,
    'phải nói RA cụm nào bị coi là chép — không nói thì người dùng không có '
    + 'gì để sửa')
})

test('mô hình trả sai khuôn: nói là lỗi mô hình, KHÁC lỗi mạng', async () => {
  const { token } = await thietBiMoi()
  assistNem({
    message: 'Kết quả trả về không dùng được',
    code: 'BAD_AI_RESPONSE', statusCode: 502,
  })

  const b = (await goi(token)).json()
  assert.strictEqual(b.code, 'BAD_AI_RESPONSE',
    'gộp vào AI_UNAVAILABLE là mất phân biệt "mô hình trả rác" với "mạng hỏng"')
})

test('lỗi trần (không mã) thì VẪN là 503 và vẫn khuyên thử lại', async () => {
  const { token } = await thietBiMoi()
  assistNem({ message: 'socket hang up' })

  const res = await goi(token)
  assert.strictEqual(res.statusCode, 503,
    'lỗi mạng thật thì "thử lại sau" mới là lời khuyên đúng')
  assert.strictEqual(res.json().code, 'AI_UNAVAILABLE')
})

test('PROVIDER_UNAVAILABLE — đường THẬT khi mọi nơi gọi đều chết', async () => {
  // `callWithFallback` ném `AiError('PROVIDER_UNAVAILABLE', …, 503)` khi hết
  // nhà cung cấp (ai-gateway.service.js:349). Đây mới là ca hay gặp nhất
  // trong thực tế — ba test trên đều dùng lỗi tự dựng, nên không chạm tới nó.
  const { token } = await thietBiMoi()
  assistNem({
    message: 'Không gọi được openai sau 2 lần — ECONNRESET: socket hang up',
    code: 'PROVIDER_UNAVAILABLE', statusCode: 503,
  })

  const res = await goi(token)
  assert.strictEqual(res.statusCode, 503,
    'sự cố nhà cung cấp PHẢI giữ 503 — đổi sang 502 là nói với máy khách '
    + 'rằng lỗi nằm ở phía nó, và mất luôn lời khuyên thử lại')
  const b = res.json()
  assert.strictEqual(b.retryAfter, 30,
    'mất `retryAfter` là mất chỗ duy nhất nói khi nào nên thử lại')
  assert.match(b.message, /ECONNRESET|socket hang up/,
    'vẫn phải nói RA lý do thật, không quay về câu chung chung')
})

test('KHÔNG trừ Vox khi phân tích hỏng, dù hỏng vì lý do nào', async () => {
  const { device, token } = await thietBiMoi()
  assistNem({
    message: 'chép nguyên văn', code: 'SAO_CHEP_NGUYEN_VAN', statusCode: 422,
  })

  await goi(token)

  const sau = await Device.findById(device._id).lean()
  assert.strictEqual(sau.balance, VI_DAU_KY,
    'hỏng mà vẫn trừ tiền là lớp lỗi tệ nhất hệ thống này tạo ra được')
})

test('lỗi 400 của tầng dưới vẫn đi thẳng như cũ', async () => {
  const { token } = await thietBiMoi()
  assistNem({
    message: 'Không có tác vụ "x"', code: 'UNKNOWN_TASK', statusCode: 400,
  })

  const res = await goi(token)
  assert.strictEqual(res.statusCode, 400)
  assert.strictEqual(res.json().code, 'UNKNOWN_TASK')
})
