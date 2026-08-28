'use strict'

/**
 * Mini-spec C44 (docs/PLAN.md) — chất lượng HIỂU NGUỒN.
 *
 * Bug thật đo được trước C44: mọi luật chất lượng của prompt dịch đều gắn với
 * ngôn ngữ ĐÍCH; ngôn ngữ NGUỒN chỉ được nội suy làm một chuỗi. App bật "Để
 * ứng dụng tự nhận ra ngôn ngữ" gửi `sourceLang: ""` (client LUÔN đặt field
 * này nên `default: 'zh-CN'` của Fastify không bao giờ áp), và dòng đầu prompt
 * ra đúng chữ "translate an ASR transcript from  to Vietnamese".
 *
 * Chạy:  node --test tests/source-comprehension.test.js
 */
const test = require('node:test')
const assert = require('node:assert')

const prompts = require('../src/prompts/translate')

// ------------------------------------------------------- resolveSourceLang --

test('resolveSourceLang: zh-CN/zh đều ra tên đầy đủ', () => {
  assert.equal(prompts.resolveSourceLang('zh-CN').name, 'Chinese (Mandarin)')
  assert.equal(prompts.resolveSourceLang('zh').key, 'zh')
})

test('resolveSourceLang: rỗng/auto KHÔNG ra tên rỗng', () => {
  for (const raw of ['', undefined, null, 'auto', '  ']) {
    const r = prompts.resolveSourceLang(raw)
    assert.equal(r.key, '')
    assert.match(r.name, /unidentified language/)
  }
})

test('resolveSourceLang: mã lạ giữ nguyên mã, không bịa tên', () => {
  assert.equal(prompts.resolveSourceLang('xx-YY').name, 'xx-yy')
})

// ------------------------------------------- prompt dịch mang tên nguồn --

test('prompt dịch: nguồn rỗng KHÔNG còn để lại khoảng trắng giữa câu', () => {
  const p = prompts.buildTranslateSystemPrompt({ sourceLang: '', targetKey: 'vi' })
  assert.ok(!p.includes('transcript from  to'),
    'dòng đầu prompt còn khoảng trắng thay cho tên ngôn ngữ nguồn')
  assert.match(p, /transcript from an unidentified language/)
})

test('prompt dịch: mã BCP-47 hiện thành TÊN ngôn ngữ, không phải mã', () => {
  const p = prompts.buildTranslateSystemPrompt({ sourceLang: 'zh-CN', targetKey: 'vi' })
  assert.match(p, /transcript from Chinese \(Mandarin\) to Vietnamese/)
  assert.ok(!p.includes('from zh-CN to'))
})

// ------------------------------------------------ luật đọc hiểu theo nguồn --

test('nguồn tiếng Trung: có luật riêng của tiếng Trung, KHÔNG có luật tiếng Anh', () => {
  const p = prompts.buildTranslateSystemPrompt({ sourceLang: 'zh-CN', targetKey: 'vi' })
  assert.match(p, /Dropped subjects/)      // chủ ngữ ẩn
  assert.match(p, /万 = ten thousand/)      // đơn vị số lớn
  assert.ok(!p.includes('Phrasal verbs'))  // luật của nguồn tiếng Anh
})

test('nguồn tiếng Anh: có luật riêng của tiếng Anh, KHÔNG có luật tiếng Trung', () => {
  const p = prompts.buildTranslateSystemPrompt({ sourceLang: 'en-US', targetKey: 'vi' })
  assert.match(p, /Phrasal verbs/)
  assert.match(p, /"You" is ambiguous/)
  assert.ok(!p.includes('Dropped subjects'))
})

test('mọi nguồn — kể cả chưa có luật riêng — đều được nhắc bản chép lời là của MÁY', () => {
  for (const src of ['zh-CN', 'en-US', 'de', '']) {
    const p = prompts.buildTranslateSystemPrompt({ sourceLang: src, targetKey: 'vi' })
    assert.match(p, /machine transcript, not written text/, `thiếu phần chung với nguồn "${src}"`)
    assert.match(p, /Segment boundaries are timing, not sentences/)
  }
})

test('nguồn lạ KHÔNG được gán luật của ngôn ngữ khác', () => {
  const p = prompts.buildTranslateSystemPrompt({ sourceLang: 'de', targetKey: 'vi' })
  assert.match(p, /transcript from German to/)
  assert.ok(!p.includes('Dropped subjects'))
  assert.ok(!p.includes('Phrasal verbs'))
})

test('luật NGUỒN không đụng luật ĐÍCH: nguồn Anh → đích Việt vẫn đủ luật tiếng Việt', () => {
  const p = prompts.buildTranslateSystemPrompt({ sourceLang: 'en-US', targetKey: 'vi' })
  assert.match(p, /PURE NATURAL VIETNAMESE/)
  assert.match(p, /Phrasal verbs/)
})

// --------------------------------------------------------- prompt phân tích --

test('prompt phân tích: câu vẫn đọc được khi chưa biết ngôn ngữ nguồn', () => {
  const p = prompts.buildAnalysisPrompt({ lines: 'x', sourceLang: '', targetKey: 'vi' })
  assert.match(p, /transcript spoken in an unidentified language/)
  assert.ok(!p.includes('a  video transcript'))
})

test('prompt phân tích: nguồn đã biết thì gọi đúng tên', () => {
  const p = prompts.buildAnalysisPrompt({ lines: 'x', sourceLang: 'zh-CN', targetKey: 'vi' })
  assert.match(p, /spoken in Chinese \(Mandarin\)/)
})
