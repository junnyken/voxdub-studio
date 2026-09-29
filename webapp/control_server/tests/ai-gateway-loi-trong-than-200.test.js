'use strict'

/**
 * Nhà cung cấp trả HTTP 200 mà kèm LỖI trong thân — cổng phải nói ra lý do.
 *
 * Bug thật, đo ngày 24/09/2026. Chủ dự án cắm GuRouter (MiniMax-M3) vào vai
 * `translate`. Cổng trả **HTTP 200**, `choices: null`, và lý do nằm ở khuôn
 * riêng của MiniMax:
 *
 *     "base_resp": { "status_code": 2056,
 *       "status_msg": "Token Plan usage limit reached: Upgrade your Token
 *                      Plan or purchase Credits for more usage." }
 *
 * Người vận hành chỉ cần NẠP TIỀN. Nhưng phép kiểm mã trạng thái chỉ bắt
 * 4xx, nên lượt này rơi xuống `readOpenAiReply`, chỗ đó chỉ thấy `content`
 * rỗng và báo **"trả về nội dung rỗng"** — một câu không nói gì về việc phải
 * làm. Mất hai lượt đo mới truy ra, và giả thuyết đầu tiên ("model suy
 * luận") sai hoàn toàn.
 *
 * Cùng lớp lỗi với bản vá C58 hôm trước (bộ kích deploy nuốt mất lý do cổng
 * từ chối): nhà cung cấp đã nói đủ, mình vứt đi.
 */
const test = require('node:test')
const { mock } = require('node:test')
const assert = require('node:assert')
const axios = require('axios')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const AiProvider = require('../src/models/AiProvider')
const { encrypt } = require('../src/utils/crypto')
const gateway = require('../src/services/ai-gateway.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(async () => {
  await clearDb()
  mock.restoreAll()
  gateway.invalidateProviders()
})

async function noiGoiChu() {
  return AiProvider.create({
    name: 'cong-ngoai', role: 'translate', type: 'openai_compat',
    baseUrl: 'https://vi-du.test/v1', model: 'mo-hinh-x',
    apiKeyEnc: encrypt('khoa-gia'), enabled: true, priority: 1,
  })
}

/** Giả TẦNG HTTP (axios) — chạy thật phần còn lại của cổng. */
function traVe200(than) {
  mock.method(axios, 'post', async () => ({ status: 200, data: than }))
}

async function batLoi(fn) {
  try { await fn(); return null } catch (e) { return e }
}

const DICH = () => gateway.translateBatch(
  [{ id: 1, text: 'Good morning.' }], { sourceLang: 'en', targetLang: 'vi' })

test('200 + base_resp của MiniMax: nói ĐÚNG lý do, không nói "rỗng"', async () => {
  await noiGoiChu()
  traVe200({
    base_resp: {
      status_code: 2056,
      status_msg: 'Token Plan usage limit reached: Upgrade your Token Plan '
        + 'or purchase Credits for more usage.',
    },
    choices: null, model: 'mo-hinh-x',
  })

  const loi = await batLoi(DICH)

  assert.ok(loi, 'phải ném lỗi')
  assert.match(loi.message, /Token Plan usage limit/,
    `mất lý do của nhà cung cấp: ${loi.message}`)
  assert.match(loi.message, /2056/, 'mất mã lỗi để tra cứu')
  assert.doesNotMatch(loi.message, /nội dung rỗng/,
    'vẫn đang báo "rỗng" trong khi cổng đã nói rõ lý do')
})

test('200 + base_resp.status_code = 0 là THÀNH CÔNG, KHÔNG được coi là lỗi',
  async () => {
    // `status_code: 0` là quy ước THÀNH CÔNG của MiniMax. Coi nó là lỗi thì
    // mọi lượt gọi thành công qua cổng kiểu này đều chết — bản vá chữa một
    // lỗ mà mở một lỗ to hơn.
    //
    // Chốt ở TẦNG `readOpenAiReply`: lượt này phải đi QUA được nó. Không
    // chốt bằng "cả `translateBatch` chạy trót lọt" — làm vậy là buộc test
    // vào khuôn dữ liệu của bước sau, và nó sẽ đỏ oan mỗi lần khuôn đó đổi
    // vì lý do chẳng liên quan gì tới bản vá này.
    await noiGoiChu()
    // `content` phải RỖNG thì nhánh đọc `base_resp` mới chạy tới. Bản đầu
    // của test này để `content` có chữ, nên nó không bao giờ chạm cái chốt
    // mình định canh — xanh vì lý do sai. Phép tiêm lỗi lôi ra.
    traVe200({
      base_resp: { status_code: 0, status_msg: 'success' },
      choices: [{ finish_reason: 'stop', message: { content: '' } }],
    })

    const loi = await batLoi(DICH)

    assert.ok(loi, 'content rỗng thì vẫn phải ném')
    assert.doesNotMatch(loi.message, /success|mã 0/,
      `coi "status_code: 0" (thành công của MiniMax) là lý do lỗi: ${loi.message}`)
    assert.match(loi.message, /nội dung rỗng/,
      `phải rơi về câu "rỗng" vì cổng KHÔNG báo lỗi gì: ${loi.message}`)
  })

test('200 + error.message kiểu OpenAI trong thân: cũng phải nói ra', async () => {
  await noiGoiChu()
  traVe200({ error: { message: 'insufficient_quota: hết tiền', type: 'billing' } })

  const loi = await batLoi(DICH)

  assert.ok(loi)
  assert.match(loi.message, /insufficient_quota|hết tiền/, loi.message)
  assert.doesNotMatch(loi.message, /nội dung rỗng/, loi.message)
})

test('content rỗng mà chữ nằm ở reasoning_content: chỉ đúng chỗ phải sửa',
  async () => {
    await noiGoiChu()
    traVe200({
      choices: [{ finish_reason: 'stop',
        message: { content: '', reasoning_content: 'Để tôi nghĩ đã…' } }],
    })

    const loi = await batLoi(DICH)

    assert.ok(loi)
    assert.match(loi.message, /reasoning_content/, loi.message)
    assert.match(loi.message, /suy luận/, 'phải nói ra việc cần làm')
  })

test('content rỗng mà cổng KHÔNG nói gì: giữ nguyên câu cũ', async () => {
  await noiGoiChu()
  traVe200({ choices: [{ finish_reason: 'stop', message: { content: '   ' } }] })

  const loi = await batLoi(DICH)

  assert.ok(loi)
  assert.match(loi.message, /nội dung rỗng/, loi.message)
})
