'use strict'

/**
 * Lượt kiểm bao bì CHẠY THẬT phải ghi lại phán quyết và nấc.
 *
 * Bug thật, 22/8/2026 — lộ ra ở đúng lượt kiểm thật đầu tiên của dự án:
 * bản ghi ở đường đọc-từ-đệm có đủ `verdict`/`reason`/`runMode`, còn bản ghi ở
 * đường CHẠY THẬT thì không. Bảng hiệu chỉnh đếm theo đúng ba trường ấy, nên:
 *
 * - mọi lượt kiểm thật rơi vào nhóm `runMode: "khong-ro"`,
 * - `xetDuyet.luot` luôn bằng 0,
 * - và đợt hiệu chỉnh **không bao giờ đủ 20 lượt** dù người bán chạy bao nhiêu
 *   ảnh đi nữa — mỗi ảnh vẫn tốn 33 Vox.
 *
 * Đọc thẳng mã nguồn vì đây là chuyện "có ghi hay không", không phải chuyện
 * tính toán: dựng cả một lượt gọi mô hình thật chỉ để kiểm một trường là giá
 * quá đắt cho thứ một phép đọc bắt được.
 */
const test = require('node:test')
const assert = require('node:assert')

const { thanHam, boChuoi } = require('./helpers/doc-ma')

/** Các khối `UsageLog.create({...})` bên trong đường `/assist`. */
function cacKhoiGhiSo() {
  const than = thanHam('src/routes/ai.js', '/assist')
  return than.split('UsageLog.create(').slice(1)
}

test('có ít nhất hai chỗ ghi sổ trong đường trợ lý', () => {
  assert.ok(cacKhoiGhiSo().length >= 2, 'đọc hụt — hàm cắt sai?')
})

test('mọi bản ghi THÀNH CÔNG đều mang phán quyết và nấc', () => {
  const thieu = []
  for (const khoi of cacKhoiGhiSo()) {
    const dau = khoi.slice(0, 1200)
    if (!/status:\s*'success'/.test(boChuoi(dau).replace(/'/g, "'"))
        && !dau.includes("status: 'success'")) continue
    for (const truong of ['verdict', 'reason', 'runMode']) {
      if (!dau.includes(`${truong}:`)) thieu.push(truong)
    }
  }
  assert.deepStrictEqual(thieu, [],
    `bản ghi thành công thiếu ${thieu.join(', ')} — bảng hiệu chỉnh sẽ không `
    + 'đếm được lượt nào và đợt hiệu chỉnh đứng yên mãi')
})

test('phán quyết chỉ ghi cho đúng tác vụ kiểm bao bì', () => {
  const than = thanHam('src/routes/ai.js', '/assist')
  assert.match(than, /verdict:\s*task === 'packaging_check'/,
    'ghi phán quyết cho mọi tác vụ là làm bẩn bảng hiệu chỉnh')
})
