'use strict'

/**
 * C3 — ba cách gọi mô hình sinh ảnh.
 *
 * "Chuẩn OpenAI" thống nhất ở phần CHỮ nhưng KHÔNG thống nhất ở phần ẢNH:
 * khác đường dẫn, khác tên trường mang ảnh vào, khác chỗ đặt ảnh ra. Bộ test
 * này khoá từng khác biệt đó lại, vì đọc nhầm một trường thì hệ thống báo
 * "mô hình không trả về ảnh" — y hệt lúc mô hình từ chối vẽ thật, và người
 * cấu hình không có cách nào phân biệt.
 */
const test = require('node:test')
const assert = require('node:assert')

const t = require('../src/services/image-transport.service')

const ANH = { mimeType: 'image/jpeg', data: 'QUJD' }
const nha = (type, extra = {}) => ({ type, model: 'm-1', apiKey: 'k-1', ...extra })

// -- Dựng yêu cầu -----------------------------------------------------------

test('google: gọi :generateContent, ảnh đi trong inlineData', () => {
  const r = t.dungYeuCau({ provider: nha('google'), prompt: 'p', image: ANH })
  assert.match(r.url, /\/models\/m-1:generateContent$/)
  assert.equal(r.headers['x-goog-api-key'], 'k-1')
  assert.equal(r.headers.Authorization, undefined, 'Gemini không dùng Bearer')
  const parts = r.body.contents[0].parts
  assert.equal(parts[1].inlineData.data, 'QUJD')
})

test('openrouter: gọi /images, ảnh gốc là input_references', () => {
  const r = t.dungYeuCau({ provider: nha('openrouter_images'), prompt: 'p', image: ANH })
  assert.match(r.url, /openrouter\.ai\/api\/v1\/images$/)
  assert.equal(r.headers.Authorization, 'Bearer k-1')
  assert.equal(r.body.input_references[0].image_url.url,
    'data:image/jpeg;base64,QUJD')
  assert.equal(r.body.prompt, 'p')
})

test('openai: gọi /images/edits chứ KHÔNG phải /images/generations', () => {
  // `/images/generations` không nhận ảnh vào — dùng nhầm cửa đó thì sản phẩm
  // trong ảnh ra do mô hình bịa ra hoàn toàn, đúng thứ tính năng này sinh ra
  // để chống.
  const r = t.dungYeuCau({ provider: nha('openai_images'), prompt: 'p', image: ANH })
  assert.match(r.url, /\/images\/edits$/)
  assert.doesNotMatch(r.url, /generations/)
  assert.equal(r.body.image, 'data:image/jpeg;base64,QUJD')
})

test('giao thức chỉ-chữ không dựng được yêu cầu sinh ảnh', () => {
  assert.equal(
    t.dungYeuCau({ provider: nha('openai_compat'), prompt: 'p', image: ANH }), null)
  assert.equal(t.dungYeuCau({ provider: nha(''), prompt: 'p', image: ANH }), null)
})

test('địa chỉ máy chủ tự khai được, thừa dấu / vẫn đúng', () => {
  const r = t.dungYeuCau({
    provider: nha('openrouter_images', { baseUrl: 'https://noi-khac.vn/api/v1///' }),
    prompt: 'p', image: ANH })
  assert.equal(r.url, 'https://noi-khac.vn/api/v1/images')
})

// -- Đọc trả lời ------------------------------------------------------------

test('google: ảnh nằm ở candidates[0].content.parts[].inlineData', () => {
  const r = t.docTraLoi({ type: 'google', data: { candidates: [{ content: { parts: [
    { text: 'đây' }, { inlineData: { mimeType: 'image/png', data: 'WA==' } }] } }] } })
  assert.deepEqual(r.image, { mimeType: 'image/png', data: 'WA==' })
})

test('kiểu OpenAI: ảnh nằm ở data[0].b64_json', () => {
  for (const type of ['openrouter_images', 'openai_images']) {
    const r = t.docTraLoi({ type, data: { data: [{ b64_json: 'WA==', media_type: 'image/webp' }] } })
    assert.deepEqual(r.image, { mimeType: 'image/webp', data: 'WA==' }, type)
  }
})

test('không ai nói kiểu ảnh thì mặc định PNG', () => {
  const r = t.docTraLoi({ type: 'openai_images', data: { data: [{ b64_json: 'WA==' }] } })
  assert.equal(r.image.mimeType, 'image/png')
})

test('output_format của OpenAI được đổi thành mime thật', () => {
  const r = t.docTraLoi({
    type: 'openai_images', data: { data: [{ b64_json: 'WA==', output_format: 'jpeg' }] } })
  assert.equal(r.image.mimeType, 'image/jpeg')
})

test('trả về ĐƯỜNG DẪN ảnh thì nói rõ, không báo chung chung', () => {
  // Ảnh dưới dạng URL là hỏng theo một kiểu KHÁC hẳn "mô hình từ chối vẽ";
  // gộp hai thứ đó làm một là bắt người dùng đoán.
  const r = t.docTraLoi({
    type: 'openrouter_images', data: { data: [{ url: 'https://x/y.png' }] } })
  assert.equal(r.image, null)
  assert.match(r.lyDo, /đường dẫn ảnh/)
})

test('mô hình từ chối vẽ: giữ nguyên lý do nó nói', () => {
  const g = t.docTraLoi({ type: 'google', data: { candidates: [{ content: { parts: [
    { text: 'Tôi không thể tạo ảnh này' }] } }] } })
  assert.equal(g.image, null)
  assert.match(g.lyDo, /không thể/)

  const o = t.docTraLoi({ type: 'openai_images',
    data: { error: { message: 'content_policy_violation' } } })
  assert.equal(o.image, null)
  assert.match(o.lyDo, /content_policy/)
})

test('trả lời rỗng hay méo mó thì không nổ', () => {
  for (const data of [null, undefined, {}, { data: [] }, { candidates: [] }]) {
    for (const type of ['google', 'openai_images', 'openrouter_images']) {
      assert.equal(t.docTraLoi({ type, data }).image, null)
    }
  }
})

// -- Cặp vai ↔ giao thức ----------------------------------------------------

test('vai Sinh ảnh từ chối giao thức chỉ-chữ, nói rõ chọn gì', () => {
  const loi = t.loiCapVaiGiaoThuc('image', 'openai_compat')
  assert.ok(loi)
  for (const nhan of Object.values(t.GIAO_THUC)) {
    assert.ok(loi.includes(nhan), `thiếu gợi ý «${nhan}»`)
  }
})

test('ba giao thức sinh ảnh đều hợp lệ cho vai image', () => {
  for (const type of Object.keys(t.GIAO_THUC)) {
    assert.equal(t.loiCapVaiGiaoThuc('image', type), null, type)
  }
})

test('vai chữ từ chối giao thức chỉ-sinh-ảnh', () => {
  for (const vai of ['translate', 'assist', 'content']) {
    assert.ok(t.loiCapVaiGiaoThuc(vai, 'openrouter_images'), vai)
    assert.ok(t.loiCapVaiGiaoThuc(vai, 'openai_images'), vai)
    assert.equal(t.loiCapVaiGiaoThuc(vai, 'openai_compat'), null, vai)
    assert.equal(t.loiCapVaiGiaoThuc(vai, 'google'), null, vai)
  }
})

test('mọi giao thức sinh ảnh đều LƯU được vào model và route', () => {
  // Chiều đúng của phép kiểm này: dạy hệ thống một cách gọi ảnh mới mà quên
  // mở enum thì Mongoose chặn ngay lúc lưu, và **không ai tạo nổi nhà cung
  // cấp cho nó** — đúng lỗi V94, hệ thống chạy tiếp không triệu chứng.
  //
  // Chiều ngược lại (enum có thêm giá trị lạ) KHÔNG kiểm được ở đây: một
  // giao thức chữ mới hoàn toàn hợp lệ khi không sinh được ảnh. Viết như thế
  // là bộ canh xanh vĩnh viễn.
  const fs = require('node:fs')
  const path = require('node:path')
  const doc = (p2) => fs.readFileSync(path.join(__dirname, '..', p2), 'utf8')

  const model = doc('src/models/AiProvider.js')
  const enumStr = model.slice(model.indexOf('enum: [', model.indexOf('type: {')))
  const trongModel = enumStr.slice(0, enumStr.indexOf(']'))
  const route = doc('src/routes/admin.js')

  for (const ty of Object.keys(t.GIAO_THUC)) {
    assert.ok(trongModel.includes(`'${ty}'`),
      `giao thức «${ty}» sinh được ảnh nhưng model không cho lưu`)
    assert.ok(route.includes(`'${ty}'`),
      `giao thức «${ty}» không có trong schema của route tạo nhà cung cấp`)
  }
})

test('giao thức lạ thì dựng yêu cầu trả null, không đoán bừa', () => {
  for (const ty of ['stability', 'midjourney', 'openai_compat', undefined]) {
    assert.equal(
      t.dungYeuCau({ provider: nha(ty), prompt: 'p', image: ANH }), null, String(ty))
  }
})
