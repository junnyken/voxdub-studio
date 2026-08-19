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
    assert.ok(t.maxResults >= 1 && t.maxResults <= 5, `${ten}: số kết quả vô lý`)
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
