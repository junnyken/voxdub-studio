'use strict'

/**
 * Bug thật phát hiện qua Live Verification mini-spec H2 (09/09/2026, xem
 * docs/TEST_LOG.md) — LẦN ĐẦU một provider Gemini thật ('google') chạy qua
 * `callWithFallback` cho vai 'assist'. `toGeminiSchema()` trước đây chỉ bỏ
 * `additionalProperties`, còn `maxItems` trên array thì giữ nguyên — Gemini
 * (model gemini-3.6-flash, API v1beta) từ chối THẲNG mọi request có field
 * này bằng `400 INVALID_ARGUMENT` (đã cô lập bằng cách gửi từng biến thể
 * schema thật lên đúng endpoint, bisect từng field một, không đoán — xem
 * TEST_LOG.md). `minItems` giữ nguyên vì đã xác nhận KHÔNG gây lỗi.
 *
 * Test này mock `axios.post` (biên ngoài hệ thống) nhưng chạy THẬT
 * `gateway.assist()` — đúng ranh giới mock của các test khác trong repo.
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

async function makeGeminiAssistProvider() {
  return AiProvider.create({
    name: 'gemini-assist', role: 'assist', type: 'google',
    model: 'gemini-3.6-flash', apiKeyEnc: encrypt('fake-key'),
    enabled: true, priority: 1,
  })
}

/** Có field này ở BẤT KỲ đâu trong cây schema không — kể cả lồng sâu. */
function coFieldO_dau(obj, ten) {
  if (!obj || typeof obj !== 'object') return false
  if (Object.prototype.hasOwnProperty.call(obj, ten)) return true
  return Object.values(obj).some((v) => coFieldO_dau(v, ten))
}

function geminiOkResponse(beats) {
  return {
    status: 200,
    data: {
      candidates: [{
        content: { parts: [{ text: JSON.stringify({ beats }) }] },
        finishReason: 'STOP',
      }],
      usageMetadata: { promptTokenCount: 10, candidatesTokenCount: 10 },
    },
  }
}

test('REGRESSION: responseSchema gửi lên Gemini KHÔNG được chứa maxItems (400 INVALID_ARGUMENT thật đã đo)', async () => {
  await makeGeminiAssistProvider()
  const beat = {
    start_s: 0, end_s: 3, beat_type: 'hook',
    narrative_function_vi: 'x', pacing_note_vi: 'x',
    overlay_pattern_abstract_vi: 'x', spoken_pattern_abstract_vi: 'x',
  }
  const post = mock.method(axios, 'post', async (url, payload) => geminiOkResponse([beat]))

  await gateway.assist({
    task: 'viral_flow_blueprint',
    input: { transcript: [{ start_s: 0, end_s: 3, text: 'hello' }], ocrEvidence: [] },
  })

  assert.equal(post.mock.calls.length, 1)
  const [, payload] = post.mock.calls[0].arguments
  const schema = payload.generationConfig.responseSchema
  assert.ok(schema, 'phải có responseSchema (task viral_flow_blueprint dùng outputSchema)')
  assert.equal(coFieldO_dau(schema, 'maxItems'), false,
    'maxItems còn sót trong schema gửi Gemini — sẽ bị 400 INVALID_ARGUMENT thật')
  // minItems vẫn phải còn — đã xác nhận KHÔNG gây lỗi, không cần bỏ oan.
  assert.equal(coFieldO_dau(schema, 'minItems'), true,
    'minItems bị bỏ nhầm dù không gây lỗi (giữ ràng buộc "ít nhất 1 beat")')
})

test('gateway.assist với provider Gemini thật (mock HTTP) vẫn trả kết quả đúng khuôn sau khi lọc maxItems', async () => {
  await makeGeminiAssistProvider()
  const beat = {
    start_s: 0, end_s: 3, beat_type: 'cta',
    narrative_function_vi: 'Kêu gọi hành động', pacing_note_vi: 'Nhanh',
    overlay_pattern_abstract_vi: 'Chữ lớn', spoken_pattern_abstract_vi: 'Giọng gấp',
  }
  mock.method(axios, 'post', async () => geminiOkResponse([beat]))

  const result = await gateway.assist({
    task: 'viral_flow_blueprint',
    input: { transcript: [{ start_s: 0, end_s: 3, text: 'buy now' }], ocrEvidence: [] },
  })

  assert.equal(result.beats.length, 1)
  assert.equal(result.beats[0].beatType, 'cta')
})
