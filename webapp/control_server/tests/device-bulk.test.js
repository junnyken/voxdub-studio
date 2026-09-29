'use strict'

/**
 * C21 — khoá/mở/xoá nhiều máy một lượt.
 *
 * Đây là thao tác **không lùi được** trên dữ liệu thật: xoá một máy là xoá
 * luôn ví Vox của máy đó. Bộ test này không kiểm "nút có chạy không" — nó
 * kiểm những chốt giữ cho một cú bấm nhầm không thành mất mát.
 */
const test = require('node:test')
const assert = require('node:assert')

const s = require('../src/services/device-bulk.service')
const h = require('./helpers/doc-ma')

// -- Chốt trước khi làm ------------------------------------------------------

test('việc lạ bị từ chối, kèm danh sách việc hợp lệ', () => {
  const r = s.xetYeuCau({ fingerprints: ['a'], action: 'nuke' })
  assert.ok(r.loi)
  for (const v of s.VIEC) assert.ok(r.loi.includes(v), `thiếu gợi ý «${v}»`)
})

test('không chọn máy nào thì không chạy', () => {
  for (const ds of [[], null, undefined, ['', '   ']]) {
    assert.ok(s.xetYeuCau({ fingerprints: ds, action: 'delete' }).loi, String(ds))
  }
})

test('vượt trần thì chặn — chống cú bấm "chọn tất cả" rộng hơn người tưởng', () => {
  const nhieu = Array.from({ length: s.TRAN_MOI_LUOT + 1 }, (_, i) => `f${i}`)
  const r = s.xetYeuCau({ fingerprints: nhieu, action: 'delete' })
  assert.ok(r.loi)
  assert.match(r.loi, new RegExp(String(s.TRAN_MOI_LUOT)))

  // Đúng trần thì vẫn cho.
  assert.ok(!s.xetYeuCau({ fingerprints: nhieu.slice(0, s.TRAN_MOI_LUOT),
    action: 'delete' }).loi)
})

test('vân tay trùng chỉ tính một lần', () => {
  // Bấm chọn rồi bỏ rồi chọn lại không được biến thành hai lượt xoá.
  const r = s.xetYeuCau({ fingerprints: ['a', 'a', ' a ', 'b'], action: 'block' })
  assert.deepEqual(r.fingerprints, ['a', 'b'])
})

// -- Máy còn tiền phải được KỂ TÊN ------------------------------------------

test('kể tên từng máy còn số dư, không nói chung chung', () => {
  const ra = s.mayConTien([
    { fingerprint: 'aa', name: 'Máy A', creditBalance: 500 },
    { fingerprint: 'bb', name: 'Máy B', creditBalance: 0 },
    { fingerprint: 'cc', creditBalance: 4469 },
  ])
  assert.equal(ra.length, 2)
  assert.deepEqual(ra.map((d) => d.fingerprint), ['aa', 'cc'])
  assert.equal(ra[0].name, 'Máy A')
  assert.equal(ra[1].creditBalance, 4469)
})

test('số dư 0 hoặc thiếu trường thì không kể nhầm', () => {
  assert.deepEqual(s.mayConTien([{ fingerprint: 'a' }, { fingerprint: 'b', creditBalance: 0 }]),
    [])
  assert.deepEqual(s.mayConTien(null), [])
})

// -- Không im lặng bỏ sót ----------------------------------------------------

test('máy chọn mà không tìm thấy thì phải BÁO', () => {
  // Chọn 25 máy mà chỉ 23 máy đổi trạng thái thì người bấm phải biết hai máy
  // kia đi đâu.
  assert.deepEqual(s.mayKhongThay(['a', 'b', 'c'], [{ fingerprint: 'b' }]), ['a', 'c'])
  assert.deepEqual(s.mayKhongThay(['a'], [{ fingerprint: 'a' }]), [])
})

// -- Cửa đã nối đúng chưa ----------------------------------------------------

test('cửa hàng loạt CHẶN trước khi đụng vào cơ sở dữ liệu', () => {
  const than = h.thanHam('src/routes/admin.js', '/devices/bulk')
  h.truoc(than, 'deviceBulk.xetYeuCau(', 'Device.find(',
    'phải xét yêu cầu TRƯỚC khi đọc/ghi dữ liệu')
})

test('cửa hàng loạt có đường XEM TRƯỚC không đụng gì', () => {
  const than = h.thanHam('src/routes/admin.js', '/devices/bulk')
  h.truoc(than, 'xemTruoc', 'Device.deleteOne(',
    'nhánh xem trước phải đứng trước mọi lệnh ghi')
  assert.match(than, /conTien/, 'xem trước không trả về danh sách máy còn tiền')
})

test('cửa hàng loạt KHÔNG nhận bộ lọc để tự quét', () => {
  // Nhận bộ lọc là mở đường cho "xoá tất cả" bằng một tham số.
  const than = h.thanHam('src/routes/admin.js', '/devices/bulk')
  for (const cam of ['status:', 'search:', 'all:']) {
    assert.ok(!than.includes(`${cam} {`), `cửa nhận bộ lọc «${cam}»`)
  }
  assert.match(than, /fingerprints: \{/, 'phải nhận danh sách vân tay tường minh')
})

test('khoá máy thì thu hồi token ngay', () => {
  // Khoá mà không tăng tokenVersion = máy vẫn dùng được tới khi token cũ hết
  // hạn, tức là "đã khoá" trên màn hình mà chưa khoá thật.
  const than = h.thanHam('src/routes/admin.js', '/devices/bulk')
  assert.match(than, /tokenVersion: 1/)
})

test('mỗi lượt ghi MỘT dòng nhật ký kèm danh sách', () => {
  const than = h.thanHam('src/routes/admin.js', '/devices/bulk')
  assert.match(than, /admin\.device\.bulk\./)
  assert.match(than, /fingerprints: xet\.fingerprints/)
})
