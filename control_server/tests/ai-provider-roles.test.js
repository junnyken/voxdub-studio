'use strict'

/**
 * Mini-spec V94 — mọi vai trò mà MÃ đang hỏi tới đều phải TẠO ĐƯỢC.
 *
 * Lỗi thật: V89 thêm cổng trợ lý gọi `providersFor('assist')`, nhưng
 * `AiProvider.role` vẫn chỉ nhận `['translate', 'content']`. Mongoose chặn
 * ngay lúc lưu, nên **không ai tạo nổi nhà cung cấp cho vai đó** — trong khi
 * hệ thống vẫn chạy bằng cách dùng chung vai `translate`, đắt hơn hàng chục
 * lần mà không có triệu chứng nào.
 *
 * Tôi đã nhiều lần bảo chủ dự án "thêm một dòng vai assist, 2 phút" — việc đó
 * bất khả thi. Test này đảm bảo không lặp lại: quét mã tìm mọi vai được hỏi,
 * đối chiếu với enum của model VÀ với schema của route.
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const GOC = path.join(__dirname, '..')

function doc(p) {
  return fs.readFileSync(path.join(GOC, p), 'utf8')
}

/** Vai trò mà mã đang thật sự dùng: providersFor('x') và callWithFallback('x'). */
function vaiDangDung() {
  const src = doc('src/services/ai-gateway.service.js')
  const vai = new Set()
  for (const m of src.matchAll(/providersFor\(['"](\w+)['"]\)/g)) vai.add(m[1])
  for (const m of src.matchAll(/callWithFallback\(['"](\w+)['"]/g)) vai.add(m[1])
  return vai
}

function enumCuaModel() {
  const src = doc('src/models/AiProvider.js')
  const m = src.match(/enum:\s*\[([^\]]+)\]/)
  assert.ok(m, 'không đọc được enum role của AiProvider')
  return new Set(m[1].match(/'(\w+)'/g).map((x) => x.replace(/'/g, '')))
}

function enumCuaRoute() {
  const src = doc('src/routes/admin.js')
  const m = src.match(/role:\s*\{\s*type:\s*'string',\s*enum:\s*\[([^\]]+)\]/)
  assert.ok(m, 'không đọc được enum role trong schema route')
  return new Set(m[1].match(/'(\w+)'/g).map((x) => x.replace(/'/g, '')))
}

test('mọi vai trò mã đang hỏi tới đều lưu được vào cơ sở dữ liệu', () => {
  const dung = vaiDangDung()
  const model = enumCuaModel()
  assert.ok(dung.size >= 2, 'không tìm thấy vai nào — regex hỏng?')
  const thieu = [...dung].filter((v) => !model.has(v))
  assert.deepStrictEqual(thieu, [], `AiProvider.role thiếu: ${thieu.join(', ')}`)
})

test('cửa quản trị cũng nhận đúng chừng đó vai', () => {
  const model = enumCuaModel()
  const route = enumCuaRoute()
  const thieu = [...model].filter((v) => !route.has(v))
  assert.deepStrictEqual(thieu, [],
    `schema route chặn vai mà model cho phép: ${thieu.join(', ')}`)
})

test('vai assist có mặt — cổng trợ lý phải cấu hình được', () => {
  assert.ok(enumCuaModel().has('assist'))
  assert.ok(enumCuaRoute().has('assist'))
})

test('giao diện quản trị có lựa chọn cho mọi vai', () => {
  const jsx = fs.readFileSync(
    path.join(GOC, '..', 'website', 'src', 'pages', 'admin', 'Providers.jsx'),
    'utf8')
  for (const vai of enumCuaModel()) {
    assert.ok(jsx.includes(`value="${vai}"`),
      `form thêm nhà cung cấp không có lựa chọn vai '${vai}' — cấu hình được `
      + 'bằng API nhưng không bấm được trên giao diện')
  }
})
