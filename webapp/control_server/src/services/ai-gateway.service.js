'use strict'

/**
 * AI Gateway — lớp DUY NHẤT trong hệ thống được biết provider/model/key.
 *
 * App gửi câu thoại thô; ở đây chọn provider theo `priority`, dựng prompt nội
 * bộ, gọi mô hình, đọc kết quả, và trả về đúng phần bản dịch. Không một
 * trường nào về provider, model, token hay chi phí được đưa vào response.
 *
 * Provider lỗi thì tự rơi xuống provider kế tiếp cùng `role` — đổi nhà cung
 * cấp hay hết hạn mức không làm gián đoạn người dùng.
 */
const axios = require('axios')

const AiProvider = require('../models/AiProvider')
const { decrypt } = require('../utils/crypto')
const {
  parseResponseSegments, parseJsonObject, mergeTranslations, containsCjk,
} = require('../utils/json-repair')
const prompts = require('../prompts/translate')
const assistPrompts = require('../prompts/assist')
const scenePrompts = require('../prompts/product_scene')
const transport = require('./image-transport.service')
const visionProbe = require('./vision-probe.service')

//: Tổng base64 của mọi ảnh trong MỘT yêu cầu. Đặt dưới `bodyLimit` (4 MB
//: trong `app.js`) để lỗi luôn rơi vào tầng của mình, nơi còn nói được lý do.
const TRAN_TONG_ANH = 3_200_000
const subtitlePrompts = require('../prompts/subtitle-translate')

class AiError extends Error {
  constructor(code, message, statusCode = 503) {
    super(message)
    this.name = 'AiError'
    this.code = code
    this.statusCode = statusCode
  }
}

const PROVIDER_CACHE_TTL_MS = 60_000
const providerCache = new Map()   // role -> { list, expiresAt }

/** Provider đang bật của một vai trò, đã sắp theo ưu tiên. */
async function providersFor(role) {
  const hit = providerCache.get(role)
  if (hit && hit.expiresAt > Date.now()) return hit.list
  const list = await AiProvider.find({ role, enabled: true })
    .sort({ priority: 1 }).lean()
  providerCache.set(role, { list, expiresAt: Date.now() + PROVIDER_CACHE_TTL_MS })
  return list
}

function invalidateProviders() { providerCache.clear() }

/**
 * Danh sách nơi gọi mô hình cho một vai, ở dạng ĐỌC ĐƯỢC cho người dùng cuối.
 *
 * Cố ý chỉ trả tên và nhãn: app cần đủ để dựng ô chọn, không cần và không
 * được biết khoá API, địa chỉ máy chủ hay tên mô hình — đó là chuyện quản
 * trị. Thứ tự giữ nguyên theo ưu tiên nên mục đầu chính là cái "Tự động" sẽ
 * dùng.
 */
async function danhSachChon(role) {
  const list = await providersFor(role)
  return list.map((p) => ({
    name: p.name,
    label: p.label || p.name,
  }))
}

/**
 * Tìm một nơi gọi theo TÊN trong đúng vai đó.
 *
 * Trả `null` khi không thấy — nơi gọi bị tắt hoặc bị xoá giữa chừng là
 * chuyện thường, và người dùng cần nghe "nơi gọi này không còn" chứ không
 * phải âm thầm rơi về nơi khác. Rơi âm thầm nghĩa là họ tưởng đang dùng mô
 * hình A trong khi tiền trả cho mô hình B.
 */
async function timTheoTen(role, name) {
  if (!name) return null
  const list = await providersFor(role)
  return list.find((p) => p.name === name) || null
}

// ------------------------------------------------------------ gọi mô hình ---

function openAiHeaders(provider, apiKey) {
  const headers = {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  }
  const host = String(provider.baseUrl || '')
  if (host.includes('anthropic.com')) {
    headers['x-api-key'] = apiKey
    headers['anthropic-version'] = '2023-06-01'
  } else if (host.includes('openrouter.ai')) {
    headers['HTTP-Referer'] = 'https://example.com'
    headers['X-Title'] = 'VoxDub Studio'
  }
  return headers
}

/**
 * Một lượt gọi `/chat/completions`. Trả về { content, usage }.
 *
 * 429 → chờ tăng dần rồi thử lại; 5xx → chờ ngắn hơn; 401/403/404 → hỏng cấu
 * hình, báo ngay để rơi xuống provider dự phòng thay vì thử lại vô ích.
 */
async function callOpenAiCompat(provider, { system, user, schema, images, maxRetries = 2 }) {
  const apiKey = decrypt(provider.apiKeyEnc)
  if (!apiKey) throw new AiError('PROVIDER_MISCONFIGURED', `Provider ${provider.name} chưa có API key`)
  if (!provider.baseUrl || !provider.model) {
    throw new AiError('PROVIDER_MISCONFIGURED', `Provider ${provider.name} thiếu baseUrl/model`)
  }

  const url = provider.baseUrl.replace(/\/+$/, '').endsWith('/chat/completions')
    ? provider.baseUrl
    : `${provider.baseUrl.replace(/\/+$/, '')}/chat/completions`

  const payload = {
    model: provider.model,
    temperature: provider.temperature,
    max_tokens: provider.maxTokens,
    response_format: schema
      ? { type: 'json_schema', json_schema: { name: 'result', strict: true, schema } }
      : { type: 'json_object' },
    messages: [
      { role: 'system', content: system },
      // Có ảnh thì phần nội dung là MẢNG (chuẩn vision của OpenAI); không có
      // thì giữ nguyên chuỗi như cũ để mọi lời gọi sẵn có không đổi hành vi.
      {
        role: 'user',
        content: (images || []).length
          ? [
            { type: 'text', text: user },
            ...images.map((a) => ({
              type: 'image_url',
              image_url: { url: `data:${a.mimeType};base64,${a.data}` },
            })),
          ]
          : user,
      },
    ],
  }
  if (provider.disableReasoning && url.includes('openrouter.ai')) {
    payload.reasoning = { enabled: false }
  }

  let lastError = ''
  let attempt = 0
  while (attempt < Math.max(1, maxRetries)) {
    let resp
    try {
      resp = await axios.post(url, payload, {
        headers: openAiHeaders(provider, apiKey),
        timeout: provider.timeoutMs || 180_000,
        validateStatus: () => true,
      })
    } catch (err) {
      lastError = `${err.code || 'NETWORK'}: ${err.message}`
      attempt += 1
      if (attempt >= maxRetries) break
      await sleep(Math.min(2 ** attempt * 1000, 8000))
      continue
    }

    if (resp.status === 200) return readOpenAiReply(resp.data, provider)

    if (resp.status === 429) {
      attempt += 1
      if (attempt >= maxRetries) {
        throw new AiError('RATE_LIMITED', `${provider.name} hết hạn mức (429)`)
      }
      await sleep(Math.min(2 ** attempt * 3000, 20_000))
      continue
    }
    if ([400, 401, 403, 404, 402].includes(resp.status)) {
      // Cấu hình sai hoặc hết tiền — thử lại cũng vậy, rơi xuống provider sau.
      const detail = typeof resp.data === 'string'
        ? resp.data.slice(0, 200) : JSON.stringify(resp.data || {}).slice(0, 200)
      throw new AiError('PROVIDER_REJECTED',
        `${provider.name} từ chối request (HTTP ${resp.status}): ${detail}`)
    }
    lastError = `HTTP ${resp.status}`
    attempt += 1
    if (attempt >= maxRetries) break
    await sleep(Math.min(2 ** attempt * 2000, 15_000))
  }
  throw new AiError('PROVIDER_UNAVAILABLE',
    `Không gọi được ${provider.name} sau ${maxRetries} lần — ${lastError}`)
}

function readOpenAiReply(data, provider) {
  const choice = data && data.choices && data.choices[0]
  const content = choice && choice.message && choice.message.content
  if (!content || !String(content).trim()) {
    throw new AiError('EMPTY_RESPONSE', `${provider.name} trả về nội dung rỗng`)
  }
  if (choice.finish_reason === 'length') {
    // Bị cắt vì chạm trần token đầu ra ⇒ JSON chắc chắn hỏng. Báo lỗi để lớp
    // trên chia đôi lô (đầu vào nhỏ hơn thì đầu ra lọt dưới trần).
    throw new AiError('TRUNCATED', `${provider.name} cắt phản hồi giữa chừng`)
  }
  const usage = data.usage || {}
  return {
    content: String(content),
    usage: {
      promptTokens: usage.prompt_tokens || 0,
      completionTokens: usage.completion_tokens || 0,
    },
  }
}

/** Google Gemini — API riêng, không tương thích OpenAI. */
async function callGemini(provider, { system, user, schema, images, maxRetries = 2 }) {
  const apiKey = decrypt(provider.apiKeyEnc)
  if (!apiKey) throw new AiError('PROVIDER_MISCONFIGURED', `Provider ${provider.name} chưa có API key`)

  const base = provider.baseUrl || 'https://generativelanguage.googleapis.com/v1beta'
  const url = `${base.replace(/\/+$/, '')}/models/${provider.model}:generateContent`
  const generationConfig = {
    temperature: provider.temperature,
    maxOutputTokens: provider.maxTokens,
    responseMimeType: 'application/json',
  }
  if (schema) generationConfig.responseSchema = toGeminiSchema(schema)

  // Ảnh (nếu có) đi cùng phần chữ trong CÙNG một lượt hỏi — mini-spec C1.
  // Thứ tự cố ý: chữ trước, ảnh sau, vì lời hướng dẫn phải được đọc trước khi
  // mô hình nhìn ảnh (Gemini đọc parts theo thứ tự).
  const parts = [{ text: user }]
  for (const anh of images || []) {
    parts.push({ inlineData: { mimeType: anh.mimeType, data: anh.data } })
  }

  const payload = {
    systemInstruction: { parts: [{ text: system }] },
    contents: [{ role: 'user', parts }],
    generationConfig,
  }

  let lastError = ''
  for (let attempt = 0; attempt < Math.max(1, maxRetries); attempt += 1) {
    let resp
    try {
      resp = await axios.post(url, payload, {
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': apiKey },
        timeout: provider.timeoutMs || 180_000,
        validateStatus: () => true,
      })
    } catch (err) {
      lastError = `${err.code || 'NETWORK'}: ${err.message}`
      await sleep(Math.min(2 ** (attempt + 1) * 1000, 8000))
      continue
    }
    if (resp.status === 200) {
      const cand = resp.data && resp.data.candidates && resp.data.candidates[0]
      const text = cand && cand.content && cand.content.parts
        && cand.content.parts.map((p) => p.text || '').join('')
      if (!text || !text.trim()) {
        throw new AiError('EMPTY_RESPONSE', `${provider.name} trả về nội dung rỗng`)
      }
      if (cand.finishReason === 'MAX_TOKENS') {
        throw new AiError('TRUNCATED', `${provider.name} cắt phản hồi giữa chừng`)
      }
      const um = resp.data.usageMetadata || {}
      return {
        content: text,
        usage: {
          promptTokens: um.promptTokenCount || 0,
          completionTokens: um.candidatesTokenCount || 0,
        },
      }
    }
    if ([400, 401, 403, 404].includes(resp.status)) {
      throw new AiError('PROVIDER_REJECTED',
        `${provider.name} từ chối request (HTTP ${resp.status})`)
    }
    lastError = `HTTP ${resp.status}`
    await sleep(Math.min(2 ** (attempt + 1) * 2000, 15_000))
  }
  throw new AiError('PROVIDER_UNAVAILABLE', `Không gọi được ${provider.name} — ${lastError}`)
}

/** JSON Schema → lược đồ Gemini (không nhận `additionalProperties`). */
function toGeminiSchema(schema) {
  if (!schema || typeof schema !== 'object') return schema
  if (Array.isArray(schema)) return schema.map(toGeminiSchema)
  const out = {}
  for (const [k, v] of Object.entries(schema)) {
    if (k === 'additionalProperties') continue
    out[k] = (v && typeof v === 'object') ? toGeminiSchema(v) : v
  }
  return out
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)) }

/**
 * Gọi mô hình qua provider ưu tiên nhất còn dùng được.
 *
 * Trả về { content, usage, provider }. Provider nào lỗi thì ghi lại lý do
 * (để admin nhìn thấy trong dashboard) rồi thử provider kế tiếp; hết provider
 * mới ném lỗi lên trên.
 */
async function callWithFallback(role, args) {
  // `args.chiDinh` = danh sách nơi gọi đã được sàng sẵn. Dùng cho tác vụ có
  // ảnh: chỉ những nơi ĐÃ chứng minh nhìn được ảnh mới được nhận việc, chứ
  // không phải "nơi đầu tiên còn sống".
  const list = args.chiDinh || await providersFor(role)
  if (!list.length) {
    throw new AiError('NO_PROVIDER',
      `Chưa cấu hình nơi gọi mô hình cho "${role}". Thêm qua /v1/admin/providers.`, 503)
  }

  let lastError = null
  for (const provider of list) {
    try {
      const result = provider.type === 'google'
        ? await callGemini(provider, args)
        : await callOpenAiCompat(provider, args)
      AiProvider.updateOne({ _id: provider._id },
        { $set: { lastOkAt: new Date(), lastError: '' } }).catch(() => {})
      return { ...result, provider }
    } catch (err) {
      lastError = err
      AiProvider.updateOne({ _id: provider._id }, {
        $set: { lastErrorAt: new Date(), lastError: String(err.message).slice(0, 300) },
      }).catch(() => {})
    }
  }
  throw lastError || new AiError('AI_UNAVAILABLE', 'Không nơi nào phản hồi')
}

// ---------------------------------------------------------------- dịch lô ---

/**
 * Dịch một lô câu. Trả về { segments, usage, provider, model }.
 *
 * Thiếu câu thì chia đôi lô rồi thử lại đúng phần thiếu — mô hình yếu hay
 * nghẹn ở lô lớn, và một lô 60 câu thiếu 2 câu không đáng phải dịch lại cả 60.
 * Hết hạn mức (RATE_LIMITED) thì KHÔNG chia đôi: chia đôi làm số request tăng
 * gấp đôi, đúng thứ đang bị chặn.
 */
async function translateBatch({ segments, sourceLang, targetKey = 'vi', context,
  cpsBudget, prevContext = [], maxRetries = 2, depth = 0, emotionTone = false }) {
  const { field: targetField } = prompts.resolveTargetLang(targetKey)
  const system = prompts.buildTranslateSystemPrompt({
    sourceLang, targetKey, context, cpsBudget, emotionTone,
  })
  const user = prompts.buildTranslateUserPrompt({ segments, targetField, prevContext })
  const schema = prompts.translateSchema(targetField, { emotionTone })

  const { content, usage, provider } = await callWithFallback('translate',
    { system, user, schema, maxRetries })
  const returned = parseResponseSegments(content)
  const { merged, missing } = mergeTranslations(
    segments, returned, targetField, emotionTone ? ['tone'] : [])
  // Phòng thủ thêm: mô hình lỡ trả nhãn ngoài enum (schema JSON không phải
  // provider nào cũng ép cứng được) -> rơi về "neutral", KHÔNG để lọt giá
  // trị lạ xuống pipeline.py::tone_to_vieneu_style() (dù hàm đó cũng đã tự
  // rơi về an toàn, chặn ở đây sớm hơn và rõ ràng hơn).
  if (emotionTone) {
    const toneSet = new Set(prompts.TONE_VALUES)
    merged.forEach((s) => { if (!toneSet.has(s.tone)) s.tone = 'neutral' })
  }

  if (!missing.length) {
    return { segments: merged, usage, provider: provider.name, model: provider.model }
  }
  if (segments.length === 1 || depth >= 3) {
    // Không chia nhỏ hơn được nữa — trả về phần dịch được, lớp trên quyết
    // định (câu thiếu sẽ được app giữ nguyên bản gốc).
    return { segments: merged, usage, provider: provider.name, model: provider.model, missing }
  }

  const missingSet = new Set(missing.map(String))
  const rest = segments.filter((s) => missingSet.has(String(s.id)))
  const mid = Math.floor(rest.length / 2) || 1
  const halves = [rest.slice(0, mid), rest.slice(mid)].filter((h) => h.length)

  const results = await Promise.all(halves.map((half) => translateBatch({
    segments: half, sourceLang, targetKey, context, cpsBudget,
    prevContext, maxRetries, depth: depth + 1, emotionTone,
  }).catch(() => null)))

  const extra = []
  let extraPrompt = 0
  let extraCompletion = 0
  for (const r of results) {
    if (!r) continue
    extra.push(...r.segments)
    extraPrompt += r.usage.promptTokens
    extraCompletion += r.usage.completionTokens
  }

  const byId = new Map([...merged, ...extra].map((s) => [String(s.id), s]))
  const ordered = segments.map((s) => byId.get(String(s.id))).filter(Boolean)
  return {
    segments: ordered,
    usage: {
      promptTokens: usage.promptTokens + extraPrompt,
      completionTokens: usage.completionTokens + extraCompletion,
    },
    provider: provider.name,
    model: provider.model,
  }
}

/**
 * Dịch một lô dòng phụ đề rời (mini-spec V14, docs/PLAN.md) — TÁCH KHỎI
 * `translateBatch` (pipeline dub, có cps/context/prosody không áp dụng ở
 * đây). Cùng chiến lược chia-đôi-lô-khi-thiếu-câu như `translateBatch`, đơn
 * giản hoá phần còn lại (không CJK-leftover-fix pass — xem Remaining Limits
 * V14 trong docs/TEST_LOG.md).
 * ``sourceFlores``/``targetFlores`` là mã FLORES-200; ``sourceName``/
 * ``targetName`` là tên hiển thị (từ `autodub/text/flores200.py` phía
 * client) — rơi về chính mã nếu thiếu, không ném lỗi.
 */
async function translateSubtitleBatch({ items, sourceFlores, targetFlores,
  sourceName, targetName, maxRetries = 2, depth = 0 }) {
  const system = subtitlePrompts.buildSystemPrompt({
    sourceName: sourceName || sourceFlores,
    targetName: targetName || targetFlores,
  })
  const user = subtitlePrompts.buildUserPrompt({ items })
  const schema = subtitlePrompts.schema()

  const { content, usage, provider } = await callWithFallback('translate',
    { system, user, schema, maxRetries })
  const returned = parseResponseSegments(content)
  const { merged, missing } = mergeTranslations(items, returned, 'text')

  if (!missing.length) {
    return { segments: merged, usage, provider: provider.name, model: provider.model }
  }
  if (items.length === 1 || depth >= 3) {
    return { segments: merged, usage, provider: provider.name, model: provider.model, missing }
  }

  const missingSet = new Set(missing.map(String))
  const rest = items.filter((s) => missingSet.has(String(s.id)))
  const mid = Math.floor(rest.length / 2) || 1
  const halves = [rest.slice(0, mid), rest.slice(mid)].filter((h) => h.length)

  const results = await Promise.all(halves.map((half) => translateSubtitleBatch({
    items: half, sourceFlores, targetFlores, sourceName, targetName,
    maxRetries, depth: depth + 1,
  }).catch(() => null)))

  const extra = []
  let extraPrompt = 0
  let extraCompletion = 0
  for (const r of results) {
    if (!r) continue
    extra.push(...r.segments)
    extraPrompt += r.usage.promptTokens
    extraCompletion += r.usage.completionTokens
  }

  const byId = new Map([...merged, ...extra].map((s) => [String(s.id), s]))
  const ordered = items.map((s) => byId.get(String(s.id))).filter(Boolean)
  return {
    segments: ordered,
    usage: {
      promptTokens: usage.promptTokens + extraPrompt,
      completionTokens: usage.completionTokens + extraCompletion,
    },
    provider: provider.name,
    model: provider.model,
  }
}

/** Dịch lại các câu còn sót chữ Hán (lưới cuối trước khi trả về app). */
async function fixCjkLeftovers({ merged, sourceLang, targetKey = 'vi', context, cpsBudget }) {
  const { field: targetField, name: targetName } = prompts.resolveTargetLang(targetKey)
  const bad = merged.filter((s) => containsCjk(s[targetField]))
  if (!bad.length) return { segments: merged, usage: { promptTokens: 0, completionTokens: 0 } }

  const system = prompts.buildTranslateSystemPrompt({ sourceLang, targetKey, context, cpsBudget })
  const schema = prompts.translateSchema(targetField)
  let promptTokens = 0
  let completionTokens = 0

  const fixes = await Promise.all(bad.map(async (seg) => {
    const user = 'Your previous translation still contained Chinese characters: '
      + `${JSON.stringify(seg[targetField])}\n`
      + `Translate this ONE segment again. "${targetField}" must be pure ${targetName} `
      + '(Latin script only). Return ONLY JSON: '
      + `{"segments": [{"id": ..., "${targetField}": "..."}]}\n\n`
      + JSON.stringify({ id: seg.id })
    try {
      const { content, usage } = await callWithFallback('translate',
        { system, user, schema, maxRetries: 2 })
      promptTokens += usage.promptTokens
      completionTokens += usage.completionTokens
      const returned = parseResponseSegments(content)
      const text = returned[0] && String(returned[0][targetField] || '').trim()
      if (text && !containsCjk(text)) return [seg.id, text]
    } catch {
      // Giữ bản cũ — giọng đọc sẽ bỏ qua ký tự lạ, còn hơn mất cả câu.
    }
    return null
  }))

  const fixed = new Map(fixes.filter(Boolean))
  const segments = merged.map((s) => (
    fixed.has(s.id) ? { ...s, [targetField]: fixed.get(s.id) } : s
  ))
  return { segments, usage: { promptTokens, completionTokens } }
}

/** Phân tích ngữ cảnh video (lượt 0). Trả về dict hoặc null. */
async function analyze({ lines, sourceLang, videoTitle, targetKey = 'vi' }) {
  const user = prompts.buildAnalysisPrompt({ lines, sourceLang, videoTitle, targetKey })
  const { content, usage, provider } = await callWithFallback('translate', {
    system: prompts.ANALYSIS_SYSTEM,
    user,
    schema: prompts.ANALYSIS_SCHEMA,
    maxRetries: 2,
  })
  const data = parseJsonObject(content)
  return { analysis: data, usage, provider: provider.name, model: provider.model }
}

/**
 * Rà soát và dịch lại NHIỀU câu trong MỘT lượt gọi (mini-spec V66).
 *
 * Bản cũ (`reviewOne`) gọi riêng từng câu, mỗi lượt gánh trọn system prompt
 * của bước dịch — 2.562 token cho đúng một câu, trong khi dịch chính câu đó
 * chỉ tốn 84. Gom 20 câu + system prompt riêng gọn hơn: đo được **giảm 33
 * lần** token vào.
 *
 * Trả `{ fixes: Map<id, text>, usage }`. Câu nào mô hình không trả về thì
 * đơn giản là không có trong map — caller giữ nguyên bản cũ, đúng như hành vi
 * "một câu hỏng không làm hỏng cả lượt" của bản cũ.
 */
async function reviewBatch({ items, targetKey = 'vi', context, cpsBudget }) {
  const { field: targetField } = prompts.resolveTargetLang(targetKey)
  const system = prompts.buildReviewSystemPrompt({ targetKey, context, cpsBudget })
  const user = prompts.buildReviewBatchUserPrompt({ items, targetField, targetKey })
  const { content, usage } = await callWithFallback('translate', {
    system, user, schema: prompts.translateSchema(targetField), maxRetries: 2,
  })
  const fixes = new Map()
  for (const seg of parseResponseSegments(content)) {
    const id = Number(seg && seg.id)
    const text = String((seg && seg[targetField]) || '').trim()
    if (Number.isFinite(id) && text) fixes.set(id, text)
  }
  return { fixes, usage }
}

/** Rà soát và dịch lại một câu nghi vấn. */
async function reviewOne({ segment, reason, neighbors, sourceLang, targetKey = 'vi',
  context, cpsBudget }) {
  const { field: targetField } = prompts.resolveTargetLang(targetKey)
  const system = prompts.buildTranslateSystemPrompt({ sourceLang, targetKey, context, cpsBudget })
  const user = prompts.buildReviewUserPrompt({ segment, reason, targetField, targetKey, neighbors })
  const { content, usage } = await callWithFallback('translate', {
    system, user, schema: prompts.translateSchema(targetField), maxRetries: 2,
  })
  const returned = parseResponseSegments(content)
  const text = returned[0] && String(returned[0][targetField] || '').trim()
  return { text: text || '', usage }
}

// ------------------------------------------------------ nội dung đăng bài ---

// Emoji và ký hiệu trang trí — người dùng cấm tuyệt đối, prompt đã dặn nhưng
// mô hình vẫn hay lỡ tay, nên đây là lớp bảo đảm cuối.
const EMOJI_RE = /[\u{1F000}-\u{1FAFF}\u{2700}-\u{27BF}\u{2600}-\u{26FF}\u{1F1E6}-\u{1F1FF}\u{FE00}-\u{FE0F}\u{1F3FB}-\u{1F3FF}\u{200D}\u{20E3}\u{2B00}-\u{2BFF}\u{2190}-\u{21FF}\u{2500}-\u{25FF}]+/gu

function stripEmoji(value) {
  if (typeof value === 'string') {
    const cleaned = value.replace(EMOJI_RE, '')
    return cleaned === value ? value : cleaned.split(/\s+/).filter(Boolean).join(' ')
  }
  if (Array.isArray(value)) return value.map(stripEmoji)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, stripEmoji(v)]))
  }
  return value
}

async function generatePost({ scriptOriginal, scriptVi, videoTitle }) {
  const user = prompts.buildContentPrompt({ scriptOriginal, scriptVi, videoTitle })
  // Vai trò "content" có provider riêng thì dùng; chưa cấu hình thì dùng
  // chung với dịch (một provider chạy được cả hai việc).
  const contentProviders = await providersFor('content')
  const role = contentProviders.length ? 'content' : 'translate'
  const { content, usage, provider } = await callWithFallback(role, {
    system: prompts.CONTENT_SYSTEM,
    user,
    schema: prompts.CONTENT_SCHEMA,
    maxRetries: 3,
  })
  const data = parseJsonObject(content)
  if (!data) throw new AiError('BAD_AI_RESPONSE', 'Không đọc được nội dung đăng bài', 502)
  return { metadata: stripEmoji(data), usage, provider: provider.name, model: provider.model }
}

/**
 * Sinh ảnh sản phẩm trong bối cảnh mới — mini-spec C1.
 *
 * KHÔNG đi qua `callWithFallback`: đường đó ép `responseMimeType:
 * 'application/json'` và đọc phần chữ, còn ở đây thứ cần lấy là phần ẢNH.
 * Cùng lý do `generate_music` tự gọi HTTP riêng thay vì dùng `_request()`.
 *
 * Vai `image` phải được cấu hình riêng (mô hình sinh ảnh khác hẳn mô hình
 * chữ) — KHÔNG có đường lui sang vai khác, vì mô hình chữ không sinh được ảnh
 * và rơi sang đó chỉ đổi một lỗi nói được thành một lỗi khó hiểu.
 */
async function generateScene({ image, scene, mode = 'SAFE', note = '', chiDinh }) {
  // `chiDinh` = chỉ thử đúng một nơi gọi (nút "Thử ngay" của trang quản trị).
  const list = chiDinh || await providersFor('image')
  if (!list.length) {
    throw new AiError('NO_PROVIDER',
      'Chưa cấu hình nơi gọi mô hình cho vai "image". Thêm ở trang Nơi gọi '
      + 'mô hình, vai trò "Sinh ảnh".', 503)
  }
  const prompt = scenePrompts.buildPrompt({ scene, mode, note })

  let lastError = null
  for (const provider of list) {
    try {
      const apiKey = decrypt(provider.apiKeyEnc)
      if (!apiKey) throw new AiError('PROVIDER_MISCONFIGURED', 'thiếu API key')

      // Mỗi nhà cung cấp có một cách gọi sinh ảnh riêng — xem
      // `image-transport.service.js`. Giao thức không sinh được ảnh (vd
      // "Chuẩn OpenAI" = /chat/completions) thì nói thẳng ngay tại đây: để
      // nó đi tiếp chỉ nhận về 404 mà người cấu hình không đoán ra vì sao.
      const yeuCau = transport.dungYeuCau({
        provider: { ...provider.toObject?.() ?? provider, apiKey },
        prompt,
        image,
      })
      if (!yeuCau) {
        throw new AiError('PROVIDER_MISCONFIGURED',
          `Nơi gọi mô hình "${provider.label || provider.name}" đang khai giao `
          + 'thức không sinh được ảnh. Vai "Sinh ảnh" cần một trong: '
          + `${Object.values(transport.GIAO_THUC).join(', ')}.`, 503)
      }

      const resp = await axios.post(yeuCau.url, yeuCau.body, {
        headers: yeuCau.headers,
        timeout: provider.timeoutMs || 120_000,
        validateStatus: () => true,
      })
      if (resp.status !== 200) {
        // Kèm nguyên văn lỗi của nhà cung cấp: "trả 401" một mình không cho
        // biết là sai khoá, hết tiền, hay mô hình không tồn tại.
        const noiDung = resp.data?.error?.message || resp.data?.error?.type || ''
        throw new AiError('AI_UNAVAILABLE',
          `Mô hình sinh ảnh trả ${resp.status}`
          + `${noiDung ? `: ${String(noiDung).slice(0, 200)}` : ''}`, 503)
      }

      const { image: anh, lyDo } = transport.docTraLoi({
        type: provider.type, data: resp.data, provider })
      if (!anh) {
        // Mô hình từ chối vẽ (chính sách nội dung) hay trả về chữ: nói thẳng,
        // đừng để phía app hiểu nhầm là lỗi mạng.
        throw new AiError('KHONG_SINH_DUOC_ANH',
          `Mô hình không trả về ảnh${lyDo ? `: ${String(lyDo).slice(0, 200)}` : ''}`,
          502)
      }

      AiProvider.updateOne({ _id: provider._id },
        { $set: { lastOkAt: new Date(), lastError: '' } }).catch(() => {})
      return {
        image: anh,
        provider: provider.name,
        model: provider.model,
        mode,
        prompt,
      }
    } catch (err) {
      lastError = err
      AiProvider.updateOne({ _id: provider._id }, {
        $set: { lastErrorAt: new Date(), lastError: String(err.message).slice(0, 300) },
      }).catch(() => {})
    }
  }
  throw lastError || new AiError('AI_UNAVAILABLE', 'Không nơi nào sinh được ảnh')
}


/**
 * Thử một nơi gọi mô hình NGAY, quy mô nhỏ nhất có thể (mini-spec C5).
 *
 * Vì sao cần: cấu hình sai — sai khoá, sai tên mô hình, sai giao thức, mô
 * hình không nhìn được ảnh — hiện nay chỉ lộ ra ở lượt chạy thật đầu tiên,
 * mà lượt đó tốn Vox và nằm giữa một mẻ hiệu chỉnh. Nút này kéo chi phí phát
 * hiện lỗi cấu hình xuống gần bằng không.
 *
 * Ảnh mẫu do máy chủ tự vẽ (cùng bộ vẽ với phép thử nhìn) — KHÔNG dùng ảnh
 * của khách. Không ghi vào sổ chính thức, không tính hạn mức, không tính vào
 * lượt hiệu chỉnh.
 *
 * Luôn chấm lại phép thử nhìn cho lượt này, không dùng kết quả cũ: người bấm
 * nút vừa đổi cấu hình, kết quả của bản cũ nói lên đúng con số không.
 */
async function thuNgay(provider) {
  const batDau = Date.now()
  const ket = { name: provider.name, role: provider.role, model: provider.model }

  if (provider.role === 'image') {
    try {
      const bai = visionProbe.taoBaiThu()
      const ra = await generateScene({
        image: bai.image,
        scene: scenePrompts.TEN_BOI_CANH[0],
        mode: 'SAFE',
        chiDinh: [provider],
      })
      ket.goiDuoc = true
      ket.coAnh = Boolean(ra.image?.data)
      ket.kichThuocAnh = ra.image?.data ? ra.image.data.length : 0
      ket.kieuAnh = ra.image?.mimeType || ''
    } catch (err) {
      ket.goiDuoc = false
      ket.maLoi = err.code || 'AI_UNAVAILABLE'
      ket.loi = String(err.message).slice(0, 300)
    }
    ket.thoiGianMs = Date.now() - batDau
    return ket
  }

  // Vai chữ: điều đáng lo nhất là mô hình KHÔNG nhìn được ảnh, vì nó vẫn trả
  // lời và phán quyết vẫn trông như thật.
  try {
    const thu = await thuNhinMotNoi(provider)
    ket.goiDuoc = true
    ket.nhinDuocAnh = thu.dat
    ket.docDuoc = thu.traLoi
    ket.soThat = thu.so
    await AiProvider.updateOne({ _id: provider._id }, {
      $set: thu.dat
        ? { visionOkAt: new Date(), visionNote: '' }
        : { visionOkAt: null, visionNote: `đọc "${thu.traLoi}" thay vì ${thu.so}` },
    }).catch(() => {})
    invalidateProviders()
  } catch (err) {
    ket.goiDuoc = false
    ket.maLoi = err.code || 'AI_UNAVAILABLE'
    ket.loi = String(err.message).slice(0, 300)
    // Gọi hỏng KHÔNG phải mù — không đóng dấu, xem `locNoiNhinDuocAnh`.
  }
  ket.thoiGianMs = Date.now() - batDau
  return ket
}

/**
 * Chạy một tác vụ trợ lý (mini-spec V89).
 *
 * Vai "assist" nên trỏ vào mô hình RẺ: các tác vụ này ngắn (vài trăm token)
 * và không đòi chất lượng như dịch thuật — chênh lệch giá giữa hai hạng mô
 * hình tới hàng chục lần. Chưa cấu hình vai riêng thì dùng chung với dịch để
 * tính năng vẫn chạy, đúng cách `generatePost` đã làm.
 */

/** Bao lâu thì thử lại phép nhìn — một mô hình đã nhìn được thì không tự mù. */
const HAN_THU_NHIN_MS = 7 * 24 * 3600_000

/**
 * Thử MỘT nơi gọi cụ thể. Gọi thẳng, KHÔNG qua `callWithFallback`.
 *
 * Vì sao không dùng fallback: fallback trả về nơi nào trả lời được, nên nếu
 * nơi thứ nhất hỏng và nơi thứ hai đáp, ta sẽ ghi kết quả thử lên nhầm bản
 * ghi — đánh dấu một mô hình mù là "nhìn được", hoặc ngược lại. Chấm bài thì
 * phải biết chắc mình đang chấm ai.
 */
async function thuNhinMotNoi(provider) {
  const bai = visionProbe.taoBaiThu()
  const goi = provider.type === 'google' ? callGemini : callOpenAiCompat
  const { content } = await goi(provider, {
    system: 'Bạn đọc chữ số trong ảnh. Trả về JSON đúng khuôn được yêu cầu.',
    user: 'Trong ảnh có một dãy chữ số. Đọc dãy số đó và ghi vào "value"; '
      + 'ghi vào "reason" mô tả ngắn những gì bạn thấy trong ảnh.',
    schema: assistPrompts.resultsSchema(1),
    images: [bai.image],
    maxRetries: 1,
  })
  const data = parseJsonObject(content)
  const traLoi = String(data?.results?.[0]?.value || '')
  return { dat: visionProbe.doDung(bai.so, traLoi), traLoi, so: bai.so }
}

/**
 * Lọc ra những nơi gọi NHÌN ĐƯỢC ẢNH cho vai này (mini-spec C4).
 *
 * Chỉ chạy cho tác vụ có gửi ảnh. Cách kiểm: tự vẽ một tấm ảnh chứa số ngẫu
 * nhiên rồi bảo mô hình đọc — xem `vision-probe.service.js` để biết vì sao
 * đây là chỗ đáng bỏ công.
 *
 * Trả về danh sách đã sàng, để lượt gọi thật KHÔNG rơi được vào một nơi chưa
 * chứng minh. Không nơi nào qua được thì ném lỗi: phía app coi mọi lỗi của
 * bước kiểm là "chưa kiểm được", tức ảnh không được dùng để bán — đúng hướng
 * an toàn.
 */
async function locNoiNhinDuocAnh(role) {
  const list = await providersFor(role)
  if (!list.length) {
    throw new AiError('NO_PROVIDER',
      `Chưa cấu hình nơi gọi mô hình cho "${role}".`, 503)
  }

  const dungDuoc = []
  let loiCuoi = null
  let coNoiMu = false
  for (const provider of list) {
    const okLuc = provider.visionOkAt ? new Date(provider.visionOkAt).getTime() : 0
    if (okLuc && Date.now() - okLuc < HAN_THU_NHIN_MS) {
      dungDuoc.push(provider)
      continue
    }
    let ket
    try {
      ket = await thuNhinMotNoi(provider)
    } catch (err) {
      // Gọi hỏng ≠ mô hình mù. Không kết tội oan: bỏ qua nơi này lượt nay,
      // KHÔNG ghi là mù, và giữ lỗi lại phòng khi chẳng nơi nào qua được.
      loiCuoi = err
      continue
    }
    await AiProvider.updateOne({ _id: provider._id }, {
      $set: ket.dat
        ? { visionOkAt: new Date(), visionNote: '' }
        : { visionOkAt: null, visionNote: `đọc "${ket.traLoi}" thay vì ${ket.so}` },
    }).catch(() => {})
    if (ket.dat) dungDuoc.push({ ...provider, visionOkAt: new Date() })
    else coNoiMu = true
  }
  // Bộ nhớ đệm đang giữ bản cũ (visionOkAt rỗng); không dọn thì lượt sau lại
  // thử lại từ đầu, tốn thêm một lượt gọi mỗi lần cho tới khi hết hạn đệm.
  invalidateProviders()

  if (!dungDuoc.length) {
    if (coNoiMu) {
      throw new AiError('MO_HINH_KHONG_NHIN_DUOC_ANH',
        `Mô hình đang gán cho vai "${role}" không đọc được nội dung ảnh `
        + '(bài thử: đọc một dãy số in rõ trong ảnh). Bước kiểm bao bì bắt buộc '
        + 'phải nhìn được ảnh — đổi sang mô hình có thị giác ở trang Nơi gọi '
        + 'mô hình.', 503)
    }
    throw new AiError('KHONG_THU_DUOC_NHIN',
      'Chưa thử được khả năng nhìn ảnh của mô hình '
      + `(${String(loiCuoi?.message || '').slice(0, 120)})`, 503)
  }
  return dungDuoc
}

async function assist({ task, input, images }) {
  const spec = assistPrompts.getTask(task)
  if (!spec) throw new AiError('UNKNOWN_TASK', `Không có tác vụ "${task}"`, 400)
  // Tác vụ không khai `nhanAnh` mà lại được gửi ảnh: chặn thẳng thay vì âm
  // thầm bỏ ảnh đi — bỏ im lặng thì mô hình trả lời dựa trên mỗi phần chữ,
  // nghe vẫn hợp lý nhưng sai hoàn toàn mục đích (mini-spec C1).
  if ((images || []).length && !spec.nhanAnh) {
    throw new AiError('TASK_KHONG_NHAN_ANH',
      `Tác vụ "${task}" không nhận ảnh`, 400)
  }
  if (spec.nhanAnh && (images || []).length > spec.soAnhToiDa) {
    throw new AiError('QUA_NHIEU_ANH',
      `Tác vụ "${task}" nhận tối đa ${spec.soAnhToiDa} ảnh`, 400)
  }
  // Trần TỔNG, không chỉ trần từng ảnh. Fastify chặn thân yêu cầu quá 4 MB ở
  // tầng vận chuyển — chặn ở đó thì người gọi nhận một lỗi trống không, không
  // có mã lỗi nào của mình và không có câu nào giải thích. Chặn tại đây để
  // nói được là gửi quá nặng (mini-spec C7).
  const tongByte = (images || []).reduce(
    (t, a) => t + String(a?.data || '').length, 0)
  if (tongByte > TRAN_TONG_ANH) {
    throw new AiError('ANH_QUA_NANG',
      `Tổng dung lượng ảnh ${Math.round(tongByte / 1024)} KB, vượt trần `
      + `${Math.round(TRAN_TONG_ANH / 1024)} KB. Thu nhỏ ảnh rồi gửi lại.`, 413)
  }

  const assistProviders = await providersFor('assist')
  const role = assistProviders.length ? 'assist' : 'translate'

  // Có gửi ảnh thì mô hình PHẢI nhìn được ảnh. Sàng TRƯỚC khi gọi thật, và
  // giao đúng danh sách đã sàng cho lượt gọi: một phán quyết "đạt" từ mô hình
  // mù là ca hỏng tệ nhất hệ thống này tạo ra được — im lặng, trông như đang
  // chạy, hậu quả rơi xuống người bán vài tuần sau dưới dạng án phạt.
  const chiDinh = (images || []).length ? await locNoiNhinDuocAnh(role) : null

  const { content, usage, provider } = await callWithFallback(role, {
    chiDinh,
    system: spec.system,
    user: spec.buildUser(input || {}),
    schema: assistPrompts.resultsSchema(spec.maxResults),
    images: images || [],
    maxRetries: 2,
  })

  const data = parseJsonObject(content)
  const results = Array.isArray(data && data.results) ? data.results : []
  const sach = results
    .map((r) => ({
      value: String((r && r.value) || '').trim(),
      reason: String((r && r.reason) || '').trim(),
    }))
    .filter((r) => r.value && r.reason)
    .slice(0, spec.maxResults)

  // Mô hình trả sai khuôn thì tính là LỖI, không im lặng đưa mảng rỗng: phía
  // app còn đường lui (tầng luật), nhưng chỉ khi biết là đường này hỏng.
  if (!sach.length) {
    throw new AiError('BAD_AI_RESPONSE', 'Kết quả trả về không dùng được', 502)
  }
  return { results: sach, usage, provider: provider.name, model: provider.model, role }
}

module.exports = {
  danhSachChon,
  timTheoTen,
  thuNgay,
  AiError,
  assist,
  generateScene,
  translateBatch,
  translateSubtitleBatch,
  fixCjkLeftovers,
  analyze,
  reviewOne,
  reviewBatch,
  generatePost,
  invalidateProviders,
  providersFor,
}
