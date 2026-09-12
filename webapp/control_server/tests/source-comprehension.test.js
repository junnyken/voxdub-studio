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

// ------------------------------------------- năm đọc theo cặp (sửa bằng mã) --
//
// Đo ngày 28/08 trên gemini-3.5-flash: nói bằng luật trong lời nhắc thì 0/10
// ("năm hai mươi hai mươi tư"), gửi năm dưới dạng chữ số thì 6/6. Nên phần này
// là mã, và mã thì phải có bộ canh.

test('năm nói theo cặp được viết thành chữ số', () => {
  const th = [
    ['The phone came out in twenty twenty-four.', 'The phone came out in 2024.'],
    ['That happened back in nineteen ninety-nine.', 'That happened back in 1999.'],
    ['Released in twenty oh five, believe it or not.', 'Released in 2005, believe it or not.'],
    ['It was nineteen eighty.', 'It was 1980.'],
    ['Back in twenty ten we had nothing.', 'Back in 2010 we had nothing.'],
    ['Twenty twenty-two and twenty twenty-three.', '2022 and 2023.'],
  ]
  for (const [vao, ra] of th) {
    assert.equal(prompts.normalizeSpokenYears(vao), ra)
  }
})

test('KHÔNG đụng vào cụm chỉ là số lượng, hoặc thiếu phần thế kỷ', () => {
  const giu = [
    'I paid twenty twenty-four dollars for it.',   // số tiền, không phải năm
    'She is twenty five years old.',               // tuổi
    'Back in ninety-nine.',                        // thiếu thế kỷ — đoán hộ là bịa
    'It takes twenty minutes.',
    '我们在二零二四年发布。',                        // nguồn tiếng Trung
    '',
  ]
  for (const t of giu) assert.equal(prompts.normalizeSpokenYears(t), t)
})

test('chỉ áp cho nguồn tiếng Anh (và nguồn chưa biết của app đời cũ)', () => {
  const segs = [{ id: 1, text: 'Made in twenty twenty-four.' }]
  assert.equal(prompts.normalizeSourceSegments(segs, 'en-US')[0].text, 'Made in 2024.')
  assert.equal(prompts.normalizeSourceSegments(segs, '')[0].text, 'Made in 2024.')
  assert.equal(prompts.normalizeSourceSegments(segs, 'zh-CN')[0].text,
    'Made in twenty twenty-four.')
})

test('không sửa gì thì trả về ĐÚNG object cũ (không sinh rác)', () => {
  const segs = [{ id: 1, text: 'Nothing to change here.' }]
  assert.strictEqual(prompts.normalizeSourceSegments(segs, 'en-US')[0], segs[0])
})

test('giữ nguyên các trường khác của câu', () => {
  const segs = [{ id: 7, text: 'Since twenty ten.', duration: 3, max_chars: 40 }]
  const ra = prompts.normalizeSourceSegments(segs, 'en-US')[0]
  assert.deepEqual(ra, { id: 7, text: 'Since 2010.', duration: 3, max_chars: 40 })
})
