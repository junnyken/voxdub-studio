'use strict'

/**
 * Mini-spec V14 (docs/PLAN.md) — prompt builder cho dịch phụ đề rời, tách
 * khỏi `prompts/translate.js` (dùng cho pipeline dub, có luật CPS/prosody
 * không áp dụng ở đây, xem Constraint 3).
 *
 * Chạy:  node --test tests/subtitle-translate-prompts.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const prompts = require('../src/prompts/subtitle-translate')

test('buildSystemPrompt: nhắc đúng ngôn ngữ nguồn/đích theo tên hiển thị', () => {
  const system = prompts.buildSystemPrompt({ sourceName: 'English', targetName: 'Vietnamese' })
  assert.match(system, /from English to Vietnamese/)
})

test('buildSystemPrompt: không có luật CPS/prosody của prompt dub', () => {
  const system = prompts.buildSystemPrompt({ sourceName: 'English', targetName: 'Vietnamese' })
  assert.doesNotMatch(system, /CPS/i)
  assert.doesNotMatch(system, /prosody/i)
})

test('buildUserPrompt: giữ đúng id/text, đúng số lượng và thứ tự', () => {
  const items = [{ id: 1, text: 'Hello' }, { id: 2, text: 'World' }]
  const user = prompts.buildUserPrompt({ items })
  const parsed = JSON.parse(user)
  assert.deepEqual(parsed.segments, items)
})

test('schema(): id + text bắt buộc, additionalProperties=false', () => {
  const s = prompts.schema()
  assert.deepEqual(s.properties.segments.items.required, ['id', 'text'])
  assert.equal(s.properties.segments.items.additionalProperties, false)
})
