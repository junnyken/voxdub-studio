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
  // "ja" giờ đã có bộ quy tắc riêng (mini-spec V18) — dùng "ko" (chưa có
  // block riêng) để test đúng nhánh generic.
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'ko', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /translate an ASR transcript from zh-CN to ko/)
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

// ----------------------------------------------- mini-spec V28 (Phase G) --
// Tín hiệu cảm xúc per-segment từ LLM, opt-in qua `emotionTone` — mặc định
// TẮT phải giữ NGUYÊN contract cũ (0 regression), bật lên mới thêm field
// `tone` vào schema + prompt.

test('V28: translateSchema mặc định (emotionTone tắt) KHÔNG có field tone — 0 regression', () => {
  const schema = prompts.translateSchema('text_vi')
  assert.ok(!schema.properties.segments.items.properties.tone)
  assert.deepEqual(schema.properties.segments.items.required, ['id', 'text_vi'])
});

test('V28: translateSchema bật emotionTone -> thêm field tone bắt buộc, đúng enum 3 giá trị', () => {
  const schema = prompts.translateSchema('text_vi', { emotionTone: true })
  const toneProp = schema.properties.segments.items.properties.tone
  assert.ok(toneProp)
  assert.deepEqual(toneProp.enum, ['neutral', 'excited', 'serious'])
  assert.ok(schema.properties.segments.items.required.includes('tone'))
});

test('V28: buildTranslateSystemPrompt mặc định KHÔNG nhắc tới tone (0 regression)', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'vi', context: {}, cpsBudget: 12.5,
  })
  assert.doesNotMatch(system, /EMOTIONAL TONE/)
  assert.match(system, /EXACTLY TWO fields/)
});

test('V28: buildTranslateSystemPrompt bật emotionTone -> có hướng dẫn phân loại tone, đúng 3 nhãn', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'vi', context: {}, cpsBudget: 12.5, emotionTone: true,
  })
  assert.match(system, /EMOTIONAL TONE PER SEGMENT/)
  assert.match(system, /EXACTLY THREE fields/)
  assert.match(system, /"neutral", "excited", "serious"/)
});

test('V28: TONE_VALUES export đúng 3 giá trị khớp autodub/text/tone_heuristic.py', () => {
  assert.deepEqual(prompts.TONE_VALUES, ['neutral', 'excited', 'serious'])
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

// ------------------------------------------------- mini-spec V33 (Phase G) --
// voice_hint additive trong ANALYSIS_SCHEMA/buildAnalysisPrompt — gợi ý
// giọng đọc theo nội dung video, KHÔNG đụng 5 field phân tích hiện có.

test('V33: ANALYSIS_SCHEMA có field voice_hint additive, giữ nguyên 5 field cũ', () => {
  const props = prompts.ANALYSIS_SCHEMA.properties
  assert.ok(props.summary && props.domain && props.pronouns
    && props.glossary && props.style_notes, '5 field cũ phải còn nguyên')
  assert.ok(props.voice_hint, 'thiếu field voice_hint mới')
  assert.deepEqual(Object.keys(props.voice_hint.properties).sort(),
    ['gender', 'style'])
});

test('V33: voice_hint.gender chỉ nhận đúng 3 giá trị (male/female/rỗng)', () => {
  const genderEnum = prompts.ANALYSIS_SCHEMA.properties.voice_hint.properties.gender.enum
  assert.deepEqual(genderEnum.sort(), ['', 'female', 'male'])
});

test('V33: voice_hint.style chỉ nhận đúng 3 style THẬT của VieNeu (khớp VOICE_STYLE_VALUES)', () => {
  const styleEnum = prompts.ANALYSIS_SCHEMA.properties.voice_hint.properties.style.enum
  assert.deepEqual(styleEnum.sort(),
    [...prompts.VOICE_STYLE_VALUES, ''].sort())
  assert.deepEqual(prompts.VOICE_STYLE_VALUES, ['tu_nhien', 'tin_tuc', 'doc_truyen'])
});

test('V33: buildAnalysisPrompt có hướng dẫn voice_hint trong JSON mẫu', () => {
  const p = prompts.buildAnalysisPrompt({ lines: 'x', sourceLang: 'en-US', targetKey: 'vi' })
  assert.match(p, /"voice_hint"/)
  assert.match(p, /tu_nhien.*tin_tuc.*doc_truyen/s)
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

// ----------------------------------------------------- mini-spec V18 (Phase E) --
// Mở rộng LANGUAGE_RULES từ {vi, en} sang 10 ngôn ngữ (thêm ja/zh/es/th/id/
// pt/fr/de) — mỗi ngôn ngữ có quy tắc giọng điệu/xưng hô/số đếm RIÊNG, không
// phải bản dịch chữ của bộ quy tắc tiếng Anh. Test khoá: registry đủ 10 khoá,
// mỗi ngôn ngữ mới có nội dung ĐẶC TRƯNG riêng (không lẫn quy tắc ngôn ngữ
// khác), và pass phân tích ngữ cảnh (buildAnalysisPrompt) dùng đúng gợi ý
// ngôn ngữ đó thay vì gợi ý chung bằng tiếng Anh.

test('V18: LANGUAGE_RULES có đúng 10 ngôn ngữ đã nghiên cứu (vi/en + 8 mới)', () => {
  assert.deepEqual(
    Object.keys(prompts.LANGUAGE_RULES).sort(),
    ['de', 'en', 'es', 'fr', 'id', 'ja', 'pt', 'th', 'vi', 'zh'],
  )
});

test('V18: bug thật đã sửa — emphasisExamples của tiếng Việt trước đây là tiếng Anh', () => {
  // Trước V18: LANGUAGE_RULES.vi.emphasisExamples lỡ copy-paste y hệt bản
  // tiếng Anh ('"really", "definitely"...') — nghĩa là prompt yêu cầu model
  // nhấn nhá câu tiếng Việt bằng VÍ DỤ TIẾNG ANH. Khoá lại: giờ phải là từ
  // nhấn mạnh tiếng Việt thật.
  assert.equal(prompts.LANGUAGE_RULES.vi.emphasisExamples.includes('really'), false)
  assert.match(prompts.LANGUAGE_RULES.vi.emphasisExamples, /thật sự|cực kỳ/)
});

test('V18: tiếng Nhật có quy tắc riêng (đọc số theo lượng từ, giữ Kanji tên Trung)', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'ja', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /to Japanese/)
  assert.match(system, /counter/i)
  assert.match(system, /Kanji/)
  assert.doesNotMatch(system, /Sino-Vietnamese/)
  assert.doesNotMatch(system, /tú\/usted/)
});

test('V18: tiếng Trung GIỮ trợ từ 啊呢吧嘛 (khác mọi ngôn ngữ khác chủ động bỏ)', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'en-US', targetKey: 'zh', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /to Chinese/)
  assert.match(system, /are natural, expected parts of spoken Mandarin/)
});

test('V18: tiếng Tây Ban Nha dùng "tú", tiếng Pháp dùng "tu", tiếng Đức dùng "du"', () => {
  const es = prompts.buildTranslateSystemPrompt({
    sourceLang: 'en-US', targetKey: 'es', context: {}, cpsBudget: 12.5 })
  const fr = prompts.buildTranslateSystemPrompt({
    sourceLang: 'en-US', targetKey: 'fr', context: {}, cpsBudget: 12.5 })
  const de = prompts.buildTranslateSystemPrompt({
    sourceLang: 'en-US', targetKey: 'de', context: {}, cpsBudget: 12.5 })
  assert.match(es, /"tú"/)
  assert.match(fr, /"tu"/)
  assert.match(de, /"du"/)
});

test('V18: tiếng Thái nêu rõ ràng buộc ครับ/ค่ะ phải nhất quán theo ngữ cảnh, không tự đoán giới tính', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'en-US', targetKey: 'th', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /ครับ/)
  assert.match(system, /CONSISTENT/)
});

test('V18: 8 ngôn ngữ mới đều có emphasisExamples bằng chính ngôn ngữ đó (không phải tiếng Anh)', () => {
  const newLangs = ['ja', 'zh', 'es', 'th', 'id', 'pt', 'fr', 'de']
  for (const key of newLangs) {
    const ex = prompts.LANGUAGE_RULES[key].emphasisExamples
    assert.ok(ex && ex.length > 0, `${key} thiếu emphasisExamples`)
    assert.equal(ex.includes('"really"'), false, `${key} vẫn dùng ví dụ tiếng Anh`)
  }
});

test('V18: buildAnalysisPrompt "học" đúng gợi ý pronouns/domain theo từng ngôn ngữ mới (không rơi về gợi ý chung tiếng Anh)', () => {
  const ja = prompts.buildAnalysisPrompt({ lines: 'x', sourceLang: 'zh-CN', targetKey: 'ja' })
  assert.match(ja, /です\/ます/)
  const zh = prompts.buildAnalysisPrompt({ lines: 'x', sourceLang: 'en-US', targetKey: 'zh' })
  assert.match(zh, /科技测评/)
  const th = prompts.buildAnalysisPrompt({ lines: 'x', sourceLang: 'en-US', targetKey: 'th' })
  assert.match(th, /ครับ\/ค่ะ/)
});

test('V18: buildAnalysisPrompt vẫn rơi về gợi ý CHUNG cho ngôn ngữ thật sự chưa nghiên cứu', () => {
  const p = prompts.buildAnalysisPrompt({ lines: 'x', sourceLang: 'en-US', targetKey: 'ko' })
  assert.match(p, /casual direct-address vs formal/)
});

test('V18: mọi ngôn ngữ mới đều có quy tắc TTS đọc số bằng chữ (không để nguyên chữ số)', () => {
  const newLangs = ['ja', 'zh', 'es', 'th', 'id', 'pt', 'fr', 'de']
  for (const key of newLangs) {
    const system = prompts.buildTranslateSystemPrompt({
      sourceLang: 'en-US', targetKey: key, context: {}, cpsBudget: 12.5,
    })
    assert.match(system, /90%/, `${key} thiếu ví dụ đọc số 90%`)
    assert.match(system, /NUMBERS & UNITS/, `${key} thiếu mục NUMBERS & UNITS`)
  }
});

// ------------------------------------------------------------------- V41 ----
// Audit thật (2026-08-16): quy tắc "bỏ trợ từ tiếng Trung 啊/呢/嘛/吧" đã có ở
// MỌI ngôn ngữ đích trừ zh (giữ nguyên có chủ đích) — nhưng KHÔNG có quy tắc
// tương đương cho từ đệm tiếng Anh nói (um/uh/like/you know...), dù đây là
// tạp âm nguồn phổ biến nhất cho nội dung "YouTube/TikTok creator style" mà
// chính prompt đang nhắm tới. Thêm quy tắc đối xứng, không đổi quy tắc cũ.

test('V41: quy tắc bỏ trợ từ tiếng Trung ĐI KÈM quy tắc bỏ từ đệm tiếng Anh, ở MỌI target trừ zh/en', () => {
  // target=en bị loại có chủ đích, giống hệt zh: rule "bỏ tạp âm tiếng Anh"
  // không có nghĩa khi CHÍNH target đó là tiếng Anh (tương tự target=zh
  // không có rule "bỏ tạp âm tiếng Trung" — xem test riêng bên dưới).
  const targets = ['vi', 'ja', 'es', 'th', 'id', 'pt', 'fr', 'de']
  for (const key of targets) {
    const system = prompts.buildTranslateSystemPrompt({
      sourceLang: 'en-US', targetKey: key, context: {}, cpsBudget: 12.5,
    })
    assert.match(system, /um.*uh.*like.*you know/,
      `${key} thiếu quy tắc bỏ từ đệm tiếng Anh (um/uh/like/you know)`)
  }
});

test('V41: tiếng Trung (target=zh) KHÔNG có quy tắc bỏ từ đệm tiếng Anh (0 regression V18 — modal particles CORRECT here vẫn giữ nguyên)', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'en-US', targetKey: 'zh', context: {}, cpsBudget: 12.5,
  })
  assert.doesNotMatch(system, /um.*uh.*like.*you know/)
  assert.match(system, /are natural, expected parts of spoken Mandarin/)
});

test('V41: tiếng Anh (target=en) KHÔNG có quy tắc bỏ từ đệm tiếng Anh (không có nghĩa khi target CHÍNH LÀ tiếng Anh — 0 regression)', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'zh-CN', targetKey: 'en', context: {}, cpsBudget: 12.5,
  })
  assert.doesNotMatch(system, /um.*uh.*like.*you know/)
});

test('V41: ngôn ngữ chưa có bộ quy tắc riêng (generic fallback) cũng có quy tắc bỏ tạp âm nguồn', () => {
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang: 'en-US', targetKey: 'ko', context: {}, cpsBudget: 12.5,
  })
  assert.match(system, /Drop Source Noise/)
  assert.match(system, /um.*uh.*like.*you know/)
});
