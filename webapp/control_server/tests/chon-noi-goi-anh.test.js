'use strict'

/**
 * Chọn NƠI GỌI cho từng lượt sinh ảnh (mini-spec C17).
 *
 * Trước đây nhiều nơi gọi trong cùng một vai chỉ là hàng chờ dự phòng: cái
 * đầu hỏng mới rơi xuống cái sau. Không có cách nói "lượt này dùng OpenAI vì
 * nó vẽ chữ tiếng Việt tốt hơn, lượt kia dùng Gemini vì rẻ hơn mười lần" —
 * đúng câu chủ dự án hỏi ngày 22/8/2026.
 *
 * Hai luật của tính năng này:
 *
 * 1. Chọn tên không còn tồn tại thì **báo lỗi, KHÔNG rơi âm thầm** sang nơi
 *    khác. Rơi âm thầm nghĩa là người dùng tưởng đang trả tiền cho mô hình
 *    mình chọn, thực tế trả cho mô hình khác.
 * 2. Danh sách trả cho app chỉ có tên và nhãn — không khoá API, không địa chỉ
 *    máy chủ, không tên mô hình.
 */
const test = require('node:test')
const assert = require('node:assert')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')

setTestEnv()

const AiProvider = require('../src/models/AiProvider')
const gateway = require('../src/services/ai-gateway.service')

test.before(startDb)
test.after(stopDb)
test.beforeEach(async () => {
  await clearDb()
  gateway.invalidateProviders()
})

async function themNoiGoi(name, { role = 'image', priority = 100, enabled = true,
  label = '' } = {}) {
  return AiProvider.create({
    name, label, role, type: 'google', enabled, priority,
    baseUrl: '', apiKey: 'khoa-gia', model: 'mo-hinh-gia',
  })
}

test('liệt kê đúng các nơi gọi đang bật của vai ảnh', async () => {
  await themNoiGoi('gemini-anh', { priority: 1, label: 'Gemini' })
  await themNoiGoi('openai-anh', { priority: 2, label: 'OpenAI' })
  await themNoiGoi('da-tat', { enabled: false })
  await themNoiGoi('vai-chu', { role: 'translate' })
  gateway.invalidateProviders()

  const ds = await gateway.danhSachChon('image')
  assert.deepStrictEqual(ds.map((x) => x.name), ['gemini-anh', 'openai-anh'],
    'lọt nơi gọi đã tắt hoặc nơi gọi của vai khác')
  assert.deepStrictEqual(ds[0], { name: 'gemini-anh', label: 'Gemini' })
})

test('thứ tự giữ theo ưu tiên — mục đầu chính là cái "Tự động" sẽ dùng', async () => {
  await themNoiGoi('sau', { priority: 50 })
  await themNoiGoi('truoc', { priority: 5 })
  gateway.invalidateProviders()

  const ds = await gateway.danhSachChon('image')
  assert.strictEqual(ds[0].name, 'truoc')
})

test('danh sách KHÔNG lộ khoá API hay địa chỉ máy chủ', async () => {
  await themNoiGoi('gemini-anh')
  gateway.invalidateProviders()

  const [muc] = await gateway.danhSachChon('image')
  assert.deepStrictEqual(Object.keys(muc).sort(), ['label', 'name'])
})

test('nhãn trống thì lấy tên làm nhãn, không trả chuỗi rỗng', async () => {
  await themNoiGoi('khong-nhan')
  gateway.invalidateProviders()

  const [muc] = await gateway.danhSachChon('image')
  assert.strictEqual(muc.label, 'khong-nhan')
})

test('tìm theo tên: đúng vai thì thấy, khác vai thì KHÔNG', async () => {
  await themNoiGoi('gemini-anh')
  await themNoiGoi('gemini-chu', { role: 'translate' })
  gateway.invalidateProviders()

  assert.ok(await gateway.timTheoTen('image', 'gemini-anh'))
  assert.strictEqual(await gateway.timTheoTen('image', 'gemini-chu'), null,
    'chọn được nơi gọi của vai chữ để sinh ảnh là mở một đường hỏng mới')
})

test('nơi gọi đã tắt thì tìm không ra', async () => {
  await themNoiGoi('da-tat', { enabled: false })
  gateway.invalidateProviders()

  assert.strictEqual(await gateway.timTheoTen('image', 'da-tat'), null)
})

test('không truyền tên thì trả null — đường "Tự động" đi tiếp như cũ', async () => {
  await themNoiGoi('gemini-anh')
  gateway.invalidateProviders()

  assert.strictEqual(await gateway.timTheoTen('image', ''), null)
})

test('route CHẶN trước khi trừ tiền khi chọn tên không có thật', () => {
  const { thanHam, truoc } = require('./helpers/doc-ma')
  const than = thanHam('src/routes/ai.js', '/product-scene')

  // Tìm bằng LƯỢT GỌI, không bằng mã lỗi: `truoc()` moi ruột chuỗi trước khi
  // soi (bài học C8), nên chữ nằm trong chuỗi thì không tìm thấy.
  truoc(than, 'timTheoTen', 'charge(',
    'phải tra tên nơi gọi TRƯỚC khi tính tiền')
})
