'use strict'

/**
 * Mini-spec V66 — gom bước rà soát vào MỘT lượt gọi thay vì mỗi câu một lượt.
 *
 * Đo ngày 18-08: bản cũ gửi trọn system prompt của bước DỊCH (2.562 token)
 * cho ĐÚNG MỘT câu, trong khi dịch chính câu đó chỉ tốn 84 — bước sửa đắt gấp
 * ~31 lần bước nó đi sửa.
 *
 * Mock ở đúng biên ngoài hệ thống (`axios.post`) như các test gateway khác,
 * không mock chính hàm đang kiểm.
 *
 * Chạy:  node --test tests/ai-gateway-review-batch.test.js
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
const prompts = require('../src/prompts/translate')

test.before(startDb)
test.after(stopDb)
test.beforeEach(async () => {
  await clearDb()
  mock.restoreAll()
  gateway.invalidateProviders()
})

async function makeProvider() {
  return AiProvider.create({
    name: 'test-provider', role: 'translate', type: 'openai_compat',
    baseUrl: 'https://api.example.com/v1', model: 'test-model',
    apiKeyEnc: encrypt('fake-key'), enabled: true, priority: 1,
  })
}

function reply(segments) {
  return {
    status: 200,
    data: {
      choices: [{ message: { content: JSON.stringify({ segments }) }, finish_reason: 'stop' }],
      usage: { prompt_tokens: 100, completion_tokens: 20 },
    },
  }
}

const ITEMS = [
  { id: 1, reason: 'cjk', text: 'source one', text_vi: '还有中文', duration: 2, max_chars: 30 },
  { id: 2, reason: 'over_budget', text: 'source two', text_vi: 'Bản dịch dài dòng lê thê', duration: 2, max_chars: 20 },
  { id: 3, reason: 'too_short', text: 'source three', text_vi: 'Ngắn', duration: 3, max_chars: 40 },
]

test('reviewBatch: 3 câu đi trong MỘT lượt gọi, không phải ba', async () => {
  await makeProvider()
  const post = mock.method(axios, 'post', async () => reply([
    { id: 1, text_vi: 'Đã sửa một' },
    { id: 2, text_vi: 'Sửa hai' },
    { id: 3, text_vi: 'Đã sửa đủ nghĩa câu ba' },
  ]))

  const { fixes } = await gateway.reviewBatch({ items: ITEMS, targetKey: 'vi' })

  assert.equal(post.mock.callCount(), 1, 'phải gom vào 1 lượt gọi')
  assert.equal(fixes.size, 3)
  assert.equal(fixes.get(2), 'Sửa hai')
})

test('reviewBatch: câu mô hình bỏ sót thì KHÔNG có trong kết quả', async () => {
  await makeProvider()
  mock.method(axios, 'post', async () => reply([{ id: 1, text_vi: 'Chỉ sửa câu một' }]))

  const { fixes } = await gateway.reviewBatch({ items: ITEMS, targetKey: 'vi' })

  assert.equal(fixes.size, 1, 'caller giữ nguyên bản cũ cho câu bị bỏ sót')
  assert.ok(!fixes.has(2))
})

test('reviewBatch: bản dịch rỗng bị bỏ, không ghi đè bằng chuỗi rỗng', async () => {
  await makeProvider()
  mock.method(axios, 'post', async () => reply([
    { id: 1, text_vi: '   ' },
    { id: 2, text_vi: 'Có nội dung' },
  ]))

  const { fixes } = await gateway.reviewBatch({ items: ITEMS, targetKey: 'vi' })

  assert.ok(!fixes.has(1), 'chuỗi rỗng mà ghi đè thì mất luôn bản dịch cũ')
  assert.equal(fixes.get(2), 'Có nội dung')
})

test('prompt review RIÊNG phải gọn hơn hẳn prompt dịch', async () => {
  const sysDich = prompts.buildTranslateSystemPrompt({ sourceLang: 'en', targetKey: 'vi' })
  const sysReview = prompts.buildReviewSystemPrompt({ targetKey: 'vi' })

  assert.ok(sysReview.length * 5 < sysDich.length,
    `prompt review (${sysReview.length}) phải nhỏ hơn 1/5 prompt dịch (${sysDich.length}) `
    + '— đây chính là khoản tiết kiệm của V66')
})

test('prompt review vẫn giữ ràng buộc không thể bỏ', async () => {
  const sys = prompts.buildReviewSystemPrompt({
    targetKey: 'vi', cpsBudget: 14, context: { pronouns: 'gọi nhau là anh/em' },
  })
  assert.match(sys, /14/, 'ngân sách ký tự phải còn — bỏ là phụ đề tràn khỏi chỗ trống')
  assert.match(sys, /max_chars/, 'giới hạn ký tự từng câu phải còn')
  assert.match(sys, /anh\/em/, 'xưng hô người dùng đặt phải còn — bỏ là phá văn phong cả video')
  assert.match(sys, /text_vi/, 'phải nói rõ định dạng JSON trả về')
})

test('prompt gom lô mang theo LÝ DO riêng của từng câu', async () => {
  const user = prompts.buildReviewBatchUserPrompt({
    items: ITEMS, targetField: 'text_vi', targetKey: 'vi',
  })
  assert.match(user, /Chinese characters/, 'câu lỗi chữ Hán phải nói rõ lỗi đó')
  assert.match(user, /TOO LONG/, 'câu quá dài phải nói rõ lỗi đó')
  assert.match(user, /DROPPED/, 'câu rụng nghĩa phải nói rõ lỗi đó')
  assert.ok(user.includes('"id":1') || user.includes('"id": 1'), 'phải kèm id để ghép lại')
})

test('nearby_lines chỉ là ngữ cảnh, không được nằm trong danh sách phải sửa', async () => {
  const user = prompts.buildReviewBatchUserPrompt({
    items: [{ ...ITEMS[0], neighbors: 'câu bên cạnh' }],
    targetField: 'text_vi', targetKey: 'vi',
  })
  assert.match(user, /never translate it/i)
})
