'use strict'

/**
 * C4 — phép thử "mô hình có nhìn được ảnh không".
 *
 * Ca hỏng cần chặn: vai `assist` bị cắm một mô hình chỉ đọc chữ, nó vẫn trả
 * lời tác vụ kiểm bao bì, và người bán nhận một phán quyết "đạt" từ mô hình
 * chưa từng nhìn thấy tấm ảnh nào. Không có triệu chứng nào cho tới lúc sàn
 * ra án phạt.
 */
const test = require('node:test')
const assert = require('node:assert')
const zlib = require('node:zlib')

const v = require('../src/services/vision-probe.service')

// -- Ảnh tự vẽ ---------------------------------------------------------------

test('vẽ ra PNG thật, đọc lại được bằng zlib', () => {
  const b64 = v.veSo('1234')
  const buf = Buffer.from(b64, 'base64')
  assert.deepEqual([...buf.slice(0, 8)],
    [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A], 'sai chữ ký PNG')
  assert.equal(buf.slice(12, 16).toString(), 'IHDR')
  assert.ok(buf.includes(Buffer.from('IEND')), 'thiếu chunk kết thúc')
})

test('ảnh giải nén ra đúng kích thước đã khai trong IHDR', () => {
  // Khai một đằng nén một nẻo thì trình đọc ảnh phía nhà cung cấp sẽ từ chối,
  // và ta sẽ tưởng mô hình mù trong khi thật ra là ảnh hỏng.
  const buf = Buffer.from(v.veSo('7'), 'base64')
  const rong = buf.readUInt32BE(16)
  const cao = buf.readUInt32BE(20)
  const dai = buf.readUInt32BE(33)
  const idat = buf.slice(41, 41 + dai)
  assert.equal(zlib.inflateSync(idat).length, (rong + 1) * cao)
})

test('số khác nhau vẽ ra ảnh khác nhau', () => {
  // Nếu mọi số ra cùng một ảnh thì bài thử vô nghĩa: mô hình học thuộc một
  // lần là qua mãi.
  const thay = new Set(['0', '1', '5', '8', '9'].map((n) => v.veSo(n)))
  assert.equal(thay.size, 5)
})

test('có nét cho cả mười chữ số', () => {
  for (let i = 0; i <= 9; i += 1) {
    assert.ok(v.CHU_SO[i], `thiếu nét chữ số ${i}`)
    assert.equal(v.CHU_SO[i].length, 7)
    for (const hang of v.CHU_SO[i]) assert.equal(hang.length, 5)
  }
})

test('ảnh có mực đen thật, không phải tờ giấy trắng', () => {
  // Vẽ trượt toạ độ thì ra ảnh trắng tinh — mô hình nhìn được vẫn trả lời
  // sai, và ta kết tội oan nó là mù.
  const buf = Buffer.from(v.veSo('8'), 'base64')
  const dai = buf.readUInt32BE(33)
  const diem = zlib.inflateSync(buf.slice(41, 41 + dai))
  const den = [...diem].filter((x) => x === 0x00).length
  assert.ok(den > 200, `chỉ có ${den} điểm mực — nhiều khả năng ảnh trắng`)
})

// -- Bài thử -----------------------------------------------------------------

test('mỗi lần thử là một số khác nhau', () => {
  // Số cố định thì mô hình mù chỉ cần đoán trúng một lần là qua vĩnh viễn.
  const so = new Set(Array.from({ length: 40 }, () => v.taoBaiThu().so))
  assert.ok(so.size > 25, `chỉ ${so.size}/40 số khác nhau — thiếu ngẫu nhiên`)
})

test('số thử luôn có 4 chữ số và không mở đầu bằng 0', () => {
  for (let i = 0; i < 50; i += 1) {
    const { so } = v.taoBaiThu()
    assert.match(so, /^[1-9]\d{3}$/)
  }
})

test('bài thử kèm sẵn ảnh dùng gửi được ngay', () => {
  const b = v.taoBaiThu()
  assert.equal(b.image.mimeType, 'image/png')
  assert.ok(b.image.data.length > 100)
})

// -- Chấm bài ----------------------------------------------------------------

test('đọc đúng số thì đạt, dù nằm lẫn trong câu', () => {
  assert.ok(v.doDung('4821', '4821'))
  assert.ok(v.doDung('4821', 'Trong ảnh là dãy số 4821.'))
  assert.ok(v.doDung('4821', '4,821'))
  assert.ok(v.doDung('4821', ' 48 21 '))
})

test('đọc sai, đọc thiếu, hay không đọc gì đều KHÔNG đạt', () => {
  for (const tra of ['4822', '482', 'không thấy số nào', '', null, undefined,
    'Tôi là mô hình ngôn ngữ, tôi không xem được ảnh']) {
    assert.equal(v.doDung('4821', tra), false, String(tra))
  }
})

test('một mô hình mù đoán bừa gần như chắc chắn trượt', () => {
  // 4 chữ số, 9000 khả năng. Đây là lý do chọn 4 chữ số chứ không phải 1.
  let trung = 0
  for (let i = 0; i < 300; i += 1) {
    const { so } = v.taoBaiThu()
    if (v.doDung(so, String(1000 + (i * 7) % 9000))) trung += 1
  }
  assert.ok(trung <= 1, `đoán bừa trúng ${trung}/300 lần — bài thử quá dễ`)
})

// -- Đã nối vào đường kiểm bao bì chưa ---------------------------------------

test('assist gửi ảnh thì PHẢI thử nhìn trước khi gọi thật', () => {
  const fs = require('node:fs')
  const path = require('node:path')
  const src = fs.readFileSync(
    path.join(__dirname, '..', 'src', 'services', 'ai-gateway.service.js'), 'utf8')
  const than = src.slice(src.indexOf('async function assist({'))
  const iThu = than.indexOf('baoDamNhinDuocAnh(')
  const iGoi = than.indexOf('callWithFallback(role, {')
  assert.ok(iThu > 0, 'assist không thử khả năng nhìn')
  assert.ok(iGoi > 0)
  assert.ok(iThu < iGoi, 'phải thử TRƯỚC khi gọi thật, không phải sau')
  assert.match(than.slice(iThu - 120, iThu), /images/,
    'phép thử phải gắn với việc CÓ gửi ảnh, không chạy cho mọi tác vụ')
})

test('mô hình không đọc được thì NÉM LỖI, không trả kết quả', () => {
  const fs = require('node:fs')
  const path = require('node:path')
  const src = fs.readFileSync(
    path.join(__dirname, '..', 'src', 'services', 'ai-gateway.service.js'), 'utf8')
  const than = src.slice(src.indexOf('async function baoDamNhinDuocAnh'))
  assert.match(than.slice(0, than.indexOf('async function assist')),
    /throw new AiError\('MO_HINH_KHONG_NHIN_DUOC_ANH'/)
})
