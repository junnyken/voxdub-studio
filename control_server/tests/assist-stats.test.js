'use strict'

/**
 * Mini-spec V89 giai đoạn 3 — thống kê cổng trợ lý.
 *
 * Truy vấn gộp sai thì KHÔNG kêu lên: nó vẫn trả về số, chỉ là số sai — đúng
 * lớp "hỏng âm thầm" đã dính nhiều lần. Nên phần dựng truy vấn tách hẳn ra để
 * test được không cần cơ sở dữ liệu.
 */
const test = require('node:test')
const assert = require('node:assert')

const stats = require('../src/services/assist-stats.service')

const MOC = new Date('2026-08-19T12:00:00Z')

test('chỉ tính lượt của cổng trợ lý, không lẫn dịch thuật', () => {
  for (const pipeline of [stats.theoTacVu(7, MOC), stats.theoMoHinh(7, MOC),
    stats.theoMaLoi(7, MOC)]) {
    assert.strictEqual(pipeline[0].$match.action, 'assist')
  }
})

test('khoảng ngày bị chặn hai đầu', () => {
  assert.strictEqual(stats.since(0, MOC).getTime(),
    MOC.getTime() - 1 * 24 * 3600_000, 'days=0 phải kẹp về 1')
  assert.strictEqual(stats.since(9999, MOC).getTime(),
    MOC.getTime() - 90 * 24 * 3600_000, 'phải kẹp trần 90 ngày')
  assert.strictEqual(stats.since('bậy', MOC).getTime(),
    MOC.getTime() - 7 * 24 * 3600_000, 'không phải số thì dùng mặc định 7 ngày')
  assert.strictEqual(stats.since(undefined, MOC).getTime(),
    MOC.getTime() - 7 * 24 * 3600_000)
})

test('đếm CẢ lượt hỏng, nếu không tỷ lệ hỏng vĩnh viễn bằng 0', () => {
  const match = stats.theoTacVu(7, MOC)[0].$match
  assert.ok(!('status' in match),
    'lọc sẵn status ở đây là tự bịt mắt trước lúc mô hình xuống cấp')
  const group = stats.theoTacVu(7, MOC)[1].$group
  assert.ok(group.hong, 'phải có ô đếm lượt hỏng')
})

test('gộp theo tác vụ, không phải theo action', () => {
  assert.strictEqual(stats.theoTacVu(7, MOC)[1].$group._id, '$assistTask',
    'mọi lượt trợ lý đều mang action "assist" — gộp theo đó thì không tách '
    + 'được việc nào tốn nhất')
})

test('đếm số MÁY riêng biệt, không phải số lượt', () => {
  const group = stats.theoTacVu(7, MOC)[1].$group
  assert.deepStrictEqual(group.soMay, { $addToSet: '$fingerprint' })
})

test('xếp việc tốn nhiều Vox nhất lên đầu', () => {
  const sort = stats.theoTacVu(7, MOC).at(-1).$sort
  assert.strictEqual(sort.vox, -1)
})

test('tóm tắt cộng đúng và quy ra tiền', () => {
  const t = stats.tomTat([
    { task: 'music_suggest', luot: 10, hong: 1, vox: 20, tokenVao: 6000, tokenRa: 1500 },
    { task: 'video_summary', luot: 4, hong: 3, vox: 20, tokenVao: 9000, tokenRa: 900 },
  ], 10)
  assert.strictEqual(t.luot, 14)
  assert.strictEqual(t.vox, 40)
  assert.strictEqual(t.vnd, 400, '1 Vox = 10 VNĐ')
  assert.strictEqual(t.tyLeHong, 28.6, 'tính trên TỔNG lượt, không phải số dòng')
})

test('chưa có lượt nào thì không chia cho 0', () => {
  const t = stats.tomTat([], 10)
  assert.strictEqual(t.tyLeHong, 0)
  assert.strictEqual(t.vnd, 0)
  assert.strictEqual(t.tacVuTonNhat, '')
})

test('việc tốn nhất tính theo Vox, không theo số lượt', () => {
  const t = stats.tomTat([
    { task: 'explain_error', luot: 100, hong: 0, vox: 0 },
    { task: 'series_glossary', luot: 3, hong: 0, vox: 15 },
  ], 10)
  assert.strictEqual(t.tacVuTonNhat, 'series_glossary',
    'explain_error miễn phí nên gọi nhiều cũng không phải chỗ tốn tiền')
})

test('mã lỗi hay gặp có trần để không đổ cả bảng ra màn hình', () => {
  const limit = stats.theoMaLoi(7, MOC).find((b) => b.$limit)
  assert.ok(limit && limit.$limit <= 20)
})
