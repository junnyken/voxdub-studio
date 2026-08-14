'use strict'

/**
 * Gọi ElevenLabs Sound Effects v2 + Music v2 — mini-spec V37 (docs/PLAN.md,
 * Phase G). API xác nhận THẬT qua tài liệu chính thức lúc audit (không
 * suy đoán):
 *   - `POST https://api.elevenlabs.io/v1/sound-generation` — header
 *     `xi-api-key`, body `{text, duration_seconds?, prompt_influence?}`.
 *   - `POST https://api.elevenlabs.io/v1/music` — cùng header, body
 *     `{prompt, music_length_ms?}`.
 * Cả 2 trả về NHỊ PHÂN (audio, mặc định MP3), KHÔNG phải JSON.
 *
 * Design Choice (V37): server quản lý key (KHÔNG bắt người dùng tự cấp
 * key ElevenLabs) — đúng mô hình SaaS hiện có. Key là 1 provider CỐ ĐỊNH
 * duy nhất (khác `AiProvider` — bảng đó dành cho provider text-generation
 * CÓ THỂ đổi qua Admin), nên đọc thẳng từ biến môi trường
 * `ELEVENLABS_API_KEY`, không qua bảng `AiProvider`/mã hoá DB.
 */
const axios = require('axios')

class ElevenLabsError extends Error {
  constructor(code, message, statusCode = 503) {
    super(message)
    this.name = 'ElevenLabsError'
    this.code = code
    this.statusCode = statusCode
  }
}

const _BASE_URL = 'https://api.elevenlabs.io/v1'
const _TIMEOUT_MS = 60_000

function _apiKey() {
  const key = (process.env.ELEVENLABS_API_KEY || '').trim()
  if (!key) {
    throw new ElevenLabsError('ELEVENLABS_NOT_CONFIGURED',
      'Chưa cấu hình ELEVENLABS_API_KEY trên máy chủ.', 503)
  }
  return key
}

async function _post(path, body) {
  try {
    const resp = await axios.post(`${_BASE_URL}${path}`, body, {
      headers: { 'xi-api-key': _apiKey(), 'Content-Type': 'application/json' },
      responseType: 'arraybuffer',
      timeout: _TIMEOUT_MS,
    })
    return Buffer.from(resp.data)
  } catch (err) {
    if (err instanceof ElevenLabsError) throw err
    const status = err.response && err.response.status
    // Lỗi ElevenLabs trả JSON dù ta xin arraybuffer — decode lại để đọc
    // thông điệp thật thay vì log nhị phân vô nghĩa.
    let detail = err.message
    if (err.response && err.response.data) {
      try {
        detail = JSON.parse(Buffer.from(err.response.data).toString('utf-8')).detail
          || detail
      } catch { /* giữ nguyên err.message nếu không parse được */ }
    }
    throw new ElevenLabsError('ELEVENLABS_REQUEST_FAILED',
      `ElevenLabs lỗi (${status || 'network'}): ${JSON.stringify(detail)}`,
      status === 401 || status === 429 ? status : 503)
  }
}

/** Sinh 1 hiệu ứng âm thanh từ mô tả — trả về Buffer (audio/mpeg). */
async function generateSoundEffect({ text, durationSeconds }) {
  const body = { text: String(text).slice(0, 500) }
  if (durationSeconds) {
    body.duration_seconds = Math.max(0.5, Math.min(30, Number(durationSeconds)))
  }
  return _post('/sound-generation', body)
}

/** Sinh 1 đoạn nhạc nền từ mô tả tâm trạng — trả về Buffer (audio/mpeg). */
async function generateMusic({ prompt, musicLengthMs }) {
  const body = { prompt: String(prompt).slice(0, 2000) }
  if (musicLengthMs) {
    body.music_length_ms = Math.max(3_000, Math.min(600_000, Number(musicLengthMs)))
  }
  return _post('/music', body)
}

module.exports = { ElevenLabsError, generateSoundEffect, generateMusic }
