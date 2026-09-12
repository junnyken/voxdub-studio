'use strict'

/**
 * Mini-spec V28 (docs/PLAN.md, Phase G) — đóng "Remaining Limit" ghi trong
 * docs/TEST_LOG.md: nối tín hiệu cảm xúc TỪ LLM (không còn chỉ heuristic
 * văn bản local-only). Test này gọi `gateway.translateBatch` THẬT (không
 * mock chính hàm đang kiểm), chỉ mock lớp gọi HTTP ra ngoài (`axios.post`)
 * và AiProvider bằng Mongo thật trong bộ nhớ — đúng ranh giới mock của các
 * test khác trong repo (mock ở biên ngoài hệ thống, không mock logic đang
 * test).
 *
 * Chạy:  node --test tests/ai-gateway-emotion-tone.test.js
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

async function makeProvider() {
  return AiProvider.create({
    name: 'test-provider', role: 'translate', type: 'openai_compat',
    baseUrl: 'https://api.example.com/v1', model: 'test-model',
    apiKeyEnc: encrypt('fake-key'), enabled: true, priority: 1,
  })
}

function openAiResponse(segments) {
  return {
    status: 200,
    data: {
      choices: [{
        message: { content: JSON.stringify({ segments }) },
        finish_reason: 'stop',
      }],
      usage: { prompt_tokens: 10, completion_tokens: 10 },
    },
  }
}

test('emotionTone tắt (mặc định): 0 regression — không gửi yêu cầu tone, không có field tone trong kết quả', async () => {
  await makeProvider()
  const post = mock.method(axios, 'post', async () => openAiResponse(
    [{ id: 1, text_vi: 'Xin chào.' }]))

  const result = await gateway.translateBatch({
    segments: [{ id: 1, text: 'Hello.', duration: 2 }],
    sourceLang: 'en-US', targetKey: 'vi',
  })

  assert.equal(result.segments[0].text_vi, 'Xin chào.')
  assert.equal('tone' in result.segments[0], false)
  const sentSchema = post.mock.calls[0].arguments[1].response_format.json_schema.schema
  assert.ok(!sentSchema.properties.segments.items.properties.tone,
    'schema gửi lên model không được có field tone khi tắt cờ')
})

test('emotionTone bật: kết quả mang đúng tone model trả về, theo từng câu', async () => {
  await makeProvider()
  mock.method(axios, 'post', async () => openAiResponse([
    { id: 1, text_vi: 'Tuyệt vời!', tone: 'excited' },
    { id: 2, text_vi: 'Cảnh báo nguy hiểm.', tone: 'serious' },
  ]))

  const result = await gateway.translateBatch({
    segments: [
      { id: 1, text: 'Amazing!', duration: 2 },
      { id: 2, text: 'Danger warning.', duration: 2 },
    ],
    sourceLang: 'en-US', targetKey: 'vi', emotionTone: true,
  })

  assert.equal(result.segments.find((s) => s.id === 1).tone, 'excited')
  assert.equal(result.segments.find((s) => s.id === 2).tone, 'serious')
})

test('emotionTone bật: model trả nhãn ngoài enum -> tự sửa về "neutral" (phòng thủ, không lọt giá trị lạ)', async () => {
  await makeProvider()
  mock.method(axios, 'post', async () => openAiResponse(
    [{ id: 1, text_vi: 'Ổn.', tone: 'angry' }]))

  const result = await gateway.translateBatch({
    segments: [{ id: 1, text: 'Fine.', duration: 2 }],
    sourceLang: 'en-US', targetKey: 'vi', emotionTone: true,
  })

  assert.equal(result.segments[0].tone, 'neutral')
})

test('emotionTone bật: model quên tone ở 1 câu -> câu đó tự rơi về "neutral"', async () => {
  await makeProvider()
  mock.method(axios, 'post', async () => openAiResponse(
    [{ id: 1, text_vi: 'Ổn.' }]))

  const result = await gateway.translateBatch({
    segments: [{ id: 1, text: 'Fine.', duration: 2 }],
    sourceLang: 'en-US', targetKey: 'vi', emotionTone: true,
  })

  assert.equal(result.segments[0].tone, 'neutral')
})

test('emotionTone bật: lô phải chia đôi (thiếu câu) vẫn giữ cờ emotionTone ở lô con', async () => {
  await makeProvider()
  let call = 0
  mock.method(axios, 'post', async (_url, payload) => {
    call += 1
    // Lượt đầu (lô 2 câu): chỉ trả câu 1, thiếu câu 2 -> buộc chia đôi.
    if (call === 1) {
      assert.ok(payload.response_format.json_schema.schema
        .properties.segments.items.properties.tone,
        'lô đầu phải yêu cầu tone')
      return openAiResponse([{ id: 1, text_vi: 'Một.', tone: 'neutral' }])
    }
    // Lượt chia đôi cho câu 2 riêng — vẫn phải yêu cầu tone.
    assert.ok(payload.response_format.json_schema.schema
      .properties.segments.items.properties.tone,
      'lô chia đôi cũng phải yêu cầu tone (emotionTone phải truyền xuống đệ quy)')
    return openAiResponse([{ id: 2, text_vi: 'Hai.', tone: 'excited' }])
  })

  const result = await gateway.translateBatch({
    segments: [{ id: 1, text: 'One.', duration: 2 }, { id: 2, text: 'Two.', duration: 2 }],
    sourceLang: 'en-US', targetKey: 'vi', emotionTone: true,
  })

  assert.equal(result.segments.find((s) => s.id === 1).tone, 'neutral')
  assert.equal(result.segments.find((s) => s.id === 2).tone, 'excited')
})
