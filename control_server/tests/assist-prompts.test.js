'use strict'

/**
 * Mini-spec V89 — danh mục tác vụ của cổng trợ lý.
 *
 * Đây là lớp giữ cho chi phí đoán được: danh sách ĐÓNG, mỗi tác vụ tự khai
 * trần đầu vào và khoá giá. Test chạy thuần (không DB) đúng quy ước của
 * control_server.
 */
const test = require('node:test')
const assert = require('node:assert')

const assist = require('../src/prompts/assist')

test('chỉ nhận tác vụ có trong danh sách', () => {
  assert.ok(assist.getTask('music_suggest'))
  assert.strictEqual(assist.getTask('khong_co_that'), null)
  // Không được lọt qua bằng thuộc tính của Object
  assert.strictEqual(assist.getTask('toString'), null)
  assert.strictEqual(assist.getTask('constructor'), null)
})

test('mỗi tác vụ khai đủ trần và khoá giá', () => {
  for (const ten of assist.TASK_NAMES) {
    const t = assist.getTask(ten)
    assert.ok(t.costKey.startsWith('credit.cost.assist.'), `${ten}: thiếu khoá giá`)
    assert.ok(t.maxInput > 0 && t.maxInput <= 8000, `${ten}: trần đầu vào vô lý`)
    // Trần 6 chứ không phải 5: `scene_script` trả một câu dẫn cho MỖI cảnh,
    // mà một video ghép được tới 6 cảnh. Trần này để chặn tác vụ đòi mô hình
    // đẻ ra hàng chục mục, không phải để ghim một con số đẹp.
    assert.ok(t.maxResults >= 1 && t.maxResults <= 6, `${ten}: số kết quả vô lý`)
    assert.ok(t.system.length > 80, `${ten}: mô tả vai trò quá sơ sài`)
    assert.strictEqual(typeof t.buildUser, 'function')
  }
})

test('cắt đầu vào trước khi gọi mô hình, không để trả tiền rồi mới biết', () => {
  const dai = 'x'.repeat(50000)
  const user = assist.getTask('music_suggest').buildUser({ transcript: dai })
  assert.ok(user.length < 5000, `còn ${user.length} ký tự — chưa cắt`)
})

test('khuôn kết quả luôn ép có lý do', () => {
  const schema = assist.resultsSchema(3)
  const item = schema.properties.results.items
  assert.deepStrictEqual(item.required, ['value', 'reason'])
  assert.strictEqual(schema.properties.results.maxItems, 3)
})

test('lời hướng dẫn cấm mô hình bịa cách sửa lỗi', () => {
  const sys = assist.getTask('explain_error').system.toLowerCase()
  assert.ok(sys.includes('không chắc'), 'phải cho phép nói "chưa rõ nguyên nhân"')
  assert.ok(sys.includes('bịa') || sys.includes('tuyệt đối'), 'phải cấm bịa')
  assert.ok(sys.includes('github'), 'phải cấm đẩy người dùng đi báo lỗi GitHub')
})

test('gợi ý nhạc không được nhắc bài hát có thật', () => {
  const sys = assist.getTask('music_suggest').system.toLowerCase()
  assert.ok(sys.includes('bản quyền') || sys.includes('nghệ sĩ'),
    'máy sinh nhạc không dùng được tên bài hát, và dễ đụng bản quyền')
})

test('cat() giữ nguyên chuỗi ngắn và thêm dấu lược khi cắt', () => {
  assert.strictEqual(assist.cat('ngắn', 100), 'ngắn')
  assert.strictEqual(assist.cat('abcdef', 3), 'abc…')
  assert.strictEqual(assist.cat(null, 10), '')
})

// -- Nhớ đệm theo nội dung + phiên bản prompt (V89 hoàn thiện) --------------

test('cùng câu hỏi thì cùng khoá, bất kể thứ tự trường', () => {
  const a = assist.cacheKey('music_suggest', { transcript: 'abc', videoTitle: 'x' })
  const b = assist.cacheKey('music_suggest', { videoTitle: 'x', transcript: 'abc' })
  assert.strictEqual(a, b, '{a,b} và {b,a} là cùng một câu hỏi')
})

test('đổi một chữ trong dữ liệu là đổi khoá', () => {
  const a = assist.cacheKey('music_suggest', { transcript: 'abc' })
  const b = assist.cacheKey('music_suggest', { transcript: 'abd' })
  assert.notStrictEqual(a, b)
})

test('hai tác vụ khác nhau không dùng chung kết quả', () => {
  const a = assist.cacheKey('music_suggest', { transcript: 'abc' })
  const b = assist.cacheKey('video_summary', { transcript: 'abc' })
  assert.notStrictEqual(a, b)
})

test('khoá mang theo phiên bản prompt', () => {
  // Sửa câu chữ hướng dẫn mô hình mà nhớ đệm vẫn trả kết quả cũ là hỏng âm
  // thầm: đo thấy tệ hơn cũng không hiểu vì sao.
  const crypto = require('node:crypto')
  const chuan = JSON.stringify({ transcript: 'abc' }, ['transcript'])
  // Định dạng khoá có thêm phần băm ẢNH ở cuối (mini-spec C1) — rỗng khi
  // tác vụ không gửi ảnh.
  const mong_doi = `assist-cache-${crypto.createHash('sha1')
    .update(`music_suggest|${assist.PROMPT_VERSION}|${chuan}|`)
    .digest('hex').slice(0, 32)}`
  assert.strictEqual(assist.cacheKey('music_suggest', { transcript: 'abc' }),
    mong_doi)
})

test('khoá đủ ngắn để làm _id và không lẫn với jobId của app', () => {
  const k = assist.cacheKey('music_suggest', { transcript: 'abc' })
  assert.ok(k.startsWith('assist-cache-'))
  assert.ok(k.length <= 100)
})

test('đổi ẢNH thì khoá phải đổi — nếu không, kết luận cũ được dùng lại', () => {
  const a = assist.cacheKey('packaging_check', {}, [{ data: 'AAAA' }])
  const b = assist.cacheKey('packaging_check', {}, [{ data: 'BBBB' }])
  const khong_anh = assist.cacheKey('packaging_check', {})
  assert.notStrictEqual(a, b, 'hai ảnh khác nhau mà cùng khoá')
  assert.notStrictEqual(a, khong_anh)
})

test('dữ liệu rỗng vẫn ra khoá hợp lệ, không nổ', () => {
  assert.ok(assist.cacheKey('music_suggest', undefined).startsWith('assist-cache-'))
  assert.ok(assist.cacheKey('music_suggest', {}).startsWith('assist-cache-'))
})
