'use strict'

/**
 * Prompt cho dịch phụ đề rời — mini-spec V14 (docs/PLAN.md).
 *
 * CỐ Ý tách khỏi `prompts/translate.js` (dùng cho pipeline dub): prompt dub
 * đầy luật prosody/CPS budget/pause cho TTS đọc theo — phụ đề rời không có
 * TTS nào đọc, những luật đó không áp dụng và chỉ gây nhiễu cho model.
 * Ngôn ngữ nhận vào là mã FLORES-200 kèm tên hiển thị do caller cung cấp
 * (route `/v1/ai/translate-subtitle` truyền `targetName` từ `flores200.py`
 * phía Python) — file này KHÔNG có bảng tên riêng như `LANGUAGE_RULES` của
 * translate.js (không khả thi cho ~200 ngôn ngữ, xem Constraint 6 của V14).
 */

function buildSystemPrompt({ sourceName, targetName }) {
  return `You are an expert subtitle translator.
Translate subtitle lines from ${sourceName} to ${targetName}.

You will receive a JSON array of subtitle lines, each with an "id" and "text".
Return ONLY JSON: {"segments": [{"id": ..., "text": "..."}]} — one entry per
input line, same "id" values, same count and order.

Rules:
- Faithful, natural ${targetName} — translate the full meaning, don't add or
  drop ideas, don't invent content not present in the source.
- Each line is read independently by a viewer as on-screen text — keep it
  concise and readable, but never sacrifice meaning for brevity.
- Preserve the register and tone of the original (casual stays casual,
  formal stays formal).
- Keep line breaks WITHIN a single subtitle's text if the source has them
  (multi-line cues) — do not merge or split cues.
- Never leave a line untranslated or return the source text unchanged unless
  it's already ${targetName}, a proper noun, or has no translatable content
  (e.g. "♪", "[music]").`
}

function buildUserPrompt({ items }) {
  return JSON.stringify({
    segments: items.map((it) => ({ id: it.id, text: it.text })),
  })
}

function schema() {
  return {
    type: 'object',
    properties: {
      segments: {
        type: 'array',
        items: {
          type: 'object',
          properties: { id: { type: 'integer' }, text: { type: 'string' } },
          required: ['id', 'text'],
          additionalProperties: false,
        },
      },
    },
    required: ['segments'],
    additionalProperties: false,
  }
}

module.exports = { buildSystemPrompt, buildUserPrompt, schema }
