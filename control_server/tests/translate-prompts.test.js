'use strict'

/**
 * Mini-spec V15 (docs/PLAN.md) — bug thật tìm ra khi audit cho V14: prompt
 * dịch server-side HARDCODE tiếng Việt bất kể client đang lồng tiếng ngôn
 * ngữ nào (không có `targetLang` trong request, `TARGET_FIELD='text_vi'`
 * là hằng số ở `routes/ai.js`) — ảnh hưởng THẬT tới tính năng lồng tiếng
 * tiếng Anh (V8/V11) khi có SaaS: server vẫn trả `text_vi`, client tìm
 * `text_en` không thấy, coi như câu "không dịch được".
 *
 * Test dưới đây khoá lại: target=vi giữ NGUYÊN hành vi cũ (0 regression),
 * target=en ra field/tên/nội dung ĐÚNG tiếng Anh (không còn rơi về tiếng
 * Việt), và ngôn ngữ lạ (chưa có bộ quy tắc riêng) rơi về quy tắc chung
 * hợp lý thay vì hardcode tiếng Việt.
 *
 * Chạy:  node --test tests/translate-prompts.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const prompts = require('../src/prompts/translate')

// ------------------------------------------------------- resolveTargetLang --

test('resolveTargetLang: vi -> field text_vi, tên Vietnamese', () => {
  const r = prompts.resolveTargetLang('vi')
  assert.deepEqual(r, { key: 'vi', field: 'text_vi', name: 'Vietnamese' })
})

test('resolveTargetLang: en -> field text_en, tên English', () => {
  const r = prompts.resolveTargetLang('en')
  assert.deepEqual(r, { key: 'en', field: 'text_en', name: 'English' })
})

test('resolveTargetLang: thiếu/rỗng mặc định về vi (0 regression cho client cũ)', () => {
  assert.equal(prompts.resolveTargetLang(undefined).key, 'vi')
  assert.equal(prompts.resolveTargetLang('').key, 'vi')
})

test('resolveTargetLang: ngôn ngữ lạ vẫn ra field hợp lệ, KHÔNG rơi về vi', () => {
  const r = prompts.resolveTargetLang('ja')
  assert.equal(r.field, 'text_ja')
  assert.notEqual(r.name, 'Vietnamese')
})

// ---------------------------------------------- buildTranslateSystemPrompt --

test('buildTranslateSystemPrompt target=vi: dịch sang Vietnamese, field text_vi', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'vi', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /translate an ASR transcript from zh-CN to Vietnamese/)
  assert.match(system, /"text_vi"/)
  assert.doesNotMatch(system, /"text_en"/)
});

test('buildTranslateSystemPrompt target=en: dịch sang English, field text_en — KHÔNG còn rơi về Vietnamese', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'en', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /translate an ASR transcript from zh-CN to English/)
  assert.match(system, /"text_en"/)
  assert.doesNotMatch(system, /"text_vi"/)
  assert.doesNotMatch(system, /native Vietnamese content creator/,
    'bug cũ: quality-check vẫn hỏi "Vietnamese" dù target=en')
  assert.match(system, /native English content creator/)
});

test('buildTranslateSystemPrompt target=en: KHÔNG chứa quy tắc riêng tiếng Việt (Hán Việt/xưng hô mình-bạn)', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'en', context: {}, cpsBudget: 12.5,
  })
  assert.doesNotMatch(system, /Sino-Vietnamese/)
  assert.doesNotMatch(system, /mình \/ các bạn/)
});

test('buildTranslateSystemPrompt target=vi: giữ nguyên các quy tắc riêng tiếng Việt (0 regression)', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'vi', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /Sino-Vietnamese/)
  assert.match(system, /mình \/ các bạn/)
});

test('buildTranslateSystemPrompt: ngôn ngữ chưa có bộ quy tắc riêng dùng quy tắc CHUNG, không hardcode Vietnamese', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'ja', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /translate an ASR transcript from zh-CN to ja/)
  assert.doesNotMatch(system, /Vietnamese/)
  assert.doesNotMatch(system, /Sino-Vietnamese/)
});

test('buildTranslateSystemPrompt: mặc định targetKey vẫn là vi khi không truyền (0 regression)', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /to Vietnamese/)
});

// --------------------------------------------------------------- outputFormat/schema --

test('translateSchema: field theo đúng target, không hardcode text_vi', () => {
  const schema = prompts.translateSchema('text_en')
  assert.ok(schema.properties.segments.items.properties.text_en)
  assert.ok(!schema.properties.segments.items.properties.text_vi)
});

// --------------------------------------------------------------- buildAnalysisPrompt --

test('buildAnalysisPrompt target=vi: ví dụ domain/pronouns bằng tiếng Việt (0 regression)', () => {
  const p = prompts.buildAnalysisPrompt({ lines: 'x', sourceLang: 'zh-CN', targetKey: 'vi' })
  assert.match(p, /to Vietnamese \(video dubbing\)/)
  assert.match(p, /review công nghệ/)
});

test('buildAnalysisPrompt target=en: không còn ép ra tiếng Việt', () => {
  const p = prompts.buildAnalysisPrompt({ lines: 'x', sourceLang: 'zh-CN', targetKey: 'en' })
  assert.match(p, /to English \(video dubbing\)/)
  assert.doesNotMatch(p, /review công nghệ/)
});

// --------------------------------------------------------------- buildReviewUserPrompt --

test('buildReviewUserPrompt: lý do "cjk" nêu đúng tên ngôn ngữ đích, không hardcode Vietnamese', () => {
  const viPrompt = prompts.buildReviewUserPrompt({
    segment: { text_vi: 'x' }, reason: 'cjk', targetField: 'text_vi',
    targetKey: 'vi', neighbors: '',
  })
  assert.match(viPrompt, /pure Vietnamese/)

  const enPrompt = prompts.buildReviewUserPrompt({
    segment: { text_en: 'x' }, reason: 'cjk', targetField: 'text_en',
    targetKey: 'en', neighbors: '',
  })
  assert.match(enPrompt, /pure English/)
  assert.doesNotMatch(enPrompt, /pure Vietnamese/)
});
