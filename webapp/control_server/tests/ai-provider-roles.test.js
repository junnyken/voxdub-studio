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
const h = require('./helpers/doc-ma')

/** Mã nguồn đã BỎ CHÚ THÍCH — xem `helpers/doc-ma.js` để biết vì sao không
 *  đọc thô nữa (mini-spec C8). */
const doc = (p) => h.ma(p)

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

/**
 * Vai "image" phải TỪ CHỐI trước khi gọi mạng nếu giao thức không sinh được
 * ảnh (C2 → mở rộng ở C3).
 *
 * Lịch sử: bản đầu chỉ hỗ trợ Gemini và dựng URL kiểu Gemini cho MỌI nhà
 * cung cấp, nên khai "Chuẩn OpenAI" là nhận 404 không hiểu vì sao. Nay có ba
 * giao thức sinh ảnh; luật còn lại vẫn thế — giao thức không nằm trong bảng
 * thì nói thẳng, đừng gọi mạng rồi đoán.
 */
test('vai image từ chối giao thức không sinh được ảnh, TRƯỚC khi gọi mạng', () => {
  const than = h.thanHam('src/services/ai-gateway.service.js', 'generateScene')
  assert.ok(than.includes('transport.dungYeuCau('),
    'generateScene không dùng bảng giao thức')
  // `truoc()` bắt buộc CẢ HAI phải có mặt rồi mới so thứ tự — viết tay bằng
  // `indexOf` thì -1 nhỏ hơn mọi vị trí và test xanh cả khi nhánh chặn biến
  // mất (mini-spec C8).
  h.truoc(than, 'if (!yeuCau)', 'axios.post(', 'phải chặn TRƯỚC khi gọi mạng')
  const i = than.indexOf('if (!yeuCau)')
  assert.match(than.slice(i, i + 500), /GIAO_THUC/,
    'thông báo phải liệt kê các giao thức dùng được')
})

/** Lỗi của nhà cung cấp phải tới được người cấu hình, không bị nuốt còn mã số. */
test('mã lỗi HTTP đi kèm nguyên văn lý do nhà cung cấp trả về', () => {
  // Chuỗi thông báo bị `ma()` moi ruột, nên tìm theo BIẾN dựng câu chứ không
  // theo lời văn: `resp.data?.error?.message` mới là thứ phải có mặt.
  const than = h.thanHam('src/services/ai-gateway.service.js', 'generateScene')
  assert.match(than, /error\?\.message/,
    '"trả 401" một mình không cho biết là sai khoá, hết tiền, hay sai tên mô '
    + 'hình — ba việc phải xử khác hẳn nhau')
})

/** Khoá bật/tắt tính năng ảnh phải TÌM THẤY được trong trang quản trị. */
test('chốt chuyển pha có mặt trong một nhóm của trang Cấu hình', () => {
  // Rơi xuống nhóm "Khác" nghĩa là người bấm phải lục giữa hàng chục khoá
  // lặt vặt để tìm đúng công tắc quyết định mở tính năng cho người bán thật.
  const cfg = fs.readFileSync(
    path.join(GOC, '..', 'website', 'src', 'pages', 'admin', 'Config.jsx'), 'utf8')
  const nhom = cfg.slice(0, cfg.indexOf('function EditModal'))
  for (const khoa of ['image.scene.stage', 'image.scene.calibration.devices']) {
    assert.ok(nhom.includes(`'${khoa}'`), `khoá «${khoa}» không nằm trong nhóm nào`)
  }
})
