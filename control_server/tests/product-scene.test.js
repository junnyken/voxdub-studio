'use strict'

/**
 * Mini-spec C1 — dựng bối cảnh ảnh sản phẩm, có cổng kiểm tuân thủ.
 *
 * Bối cảnh thật: người bán gửi ảnh chụp màn hình TikTok Shop — tài khoản bị
 * **cưỡng chế hủy quyền thương mại điện tử + trừ 1000 điểm CHR** vì "quảng bá
 * sản phẩm không nhất quán": video không khớp sản phẩm đang bán. Enforcement
 * chạy tự động bằng thị giác máy tính, và 6 lần cùng loại trong 90 ngày là
 * mất quyền bán bất kể điểm.
 *
 * Nên tính năng này KHÔNG được là "AI vẽ lại bao bì cho đẹp". Nó phải:
 *   - mặc định giữ nguyên sản phẩm, chỉ đổi bối cảnh;
 *   - nói rõ ảnh nào đã lệch khỏi sản phẩm thật, kèm LÝ DO đọc được;
 *   - chặn số lượng ở chế độ rủi ro, không để "lên trend rồi bị quét cả loạt".
 */
const test = require('node:test')
const assert = require('node:assert')

const scene = require('../src/prompts/product_scene')
const assist = require('../src/prompts/assist')

// ---------------------------------------------- câu lệnh gửi mô hình ------

test('mặc định là SAFE — chế độ rủi ro phải do người dùng CHỌN', () => {
  const p = scene.buildPrompt({ scene: 'ban_go' })
  assert.ok(p.includes('KHÔNG vẽ lại nhãn'),
    'không đặt mode thì phải rơi vào chế độ giữ nguyên bao bì')
})

test('SAFE cấm đúng những thứ TikTok đem ra so', () => {
  const p = scene.buildPrompt({ scene: 'nen_studio', mode: 'SAFE' })
  for (const phai_cam of ['bao bì', 'nhãn', 'màu', 'kiểu dáng', 'chất liệu',
    'khối lượng']) {
    assert.ok(p.includes(phai_cam), `câu lệnh chưa nhắc tới "${phai_cam}"`)
  }
  assert.ok(p.includes('Chỉ thay đổi'), 'phải nói rõ được đổi cái gì')
})

test('SAFE cấm thêm huy hiệu/giải thưởng không có thật', () => {
  const p = scene.buildPrompt({ scene: 'gio_qua' })
  assert.ok(/huy hiệu|tem|giải thưởng/.test(p),
    'thêm huy hiệu giả là "tuyên bố về sản phẩm không có thật" — đúng thứ '
    + 'chính sách AIGC của TikTok cấm')
})

test('CONCEPT nói thẳng là không dùng để đăng bán', () => {
  const p = scene.buildPrompt({ scene: 'ban_go', mode: 'CONCEPT' })
  assert.ok(p.includes('Ý TƯỞNG'))
  assert.ok(p.includes('không dùng để đăng kèm sản phẩm đang bán'))
  assert.ok(!p.includes('KHÔNG vẽ lại nhãn'), 'CONCEPT thì được vẽ lại')
})

test('bối cảnh bịa thì nổ ngay, không âm thầm dựng bừa', () => {
  assert.throws(() => scene.buildPrompt({ scene: 'khong_co_that' }),
    /Không có bối cảnh/)
})

test('ghi chú người bán bị cắt, không cho nhét cả bài văn', () => {
  const p = scene.buildPrompt({ scene: 'ban_go', note: 'x'.repeat(5000) })
  assert.ok(p.length < 2500, `câu lệnh dài ${p.length} ký tự`)
})

// ------------------------------------------------ cổng kiểm bao bì --------

test('tác vụ kiểm bao bì nhận đúng 2 ảnh', () => {
  const t = assist.getTask('packaging_check')
  assert.strictEqual(t.nhanAnh, true)
  assert.strictEqual(t.soAnhToiDa, 2)
})

test('kiểm bao bì: không chắc thì phải chọn CONCEPT', () => {
  const sys = assist.getTask('packaging_check').system
  assert.ok(sys.includes('Không chắc thì chọn CONCEPT'),
    'đoán sai phải nghiêng về phía an toàn cho tài khoản người bán')
})

test('kiểm bao bì trả nhãn + LÝ DO, không trả điểm số', () => {
  const sys = assist.getTask('packaging_check').system
  assert.ok(sys.includes('"SAFE"') && sys.includes('"CONCEPT"'))
  assert.ok(/reason/.test(sys) && /khác chỗ nào/.test(sys),
    'con số 0,58 thì người bán không cãi được với TikTok')
})

test('tác vụ CHỮ không được nhận ảnh', () => {
  for (const ten of ['music_suggest', 'video_summary', 'tighten_line']) {
    assert.ok(!assist.getTask(ten).nhanAnh, `${ten} không nên nhận ảnh`)
  }
})

// --------------------------------------------------- luật ở route --------

const fs = require('node:fs')
const path = require('node:path')
const route = fs.readFileSync(
  path.join(__dirname, '..', 'src', 'routes', 'ai.js'), 'utf8')

test('CONCEPT có hạn mức ngày RIÊNG, kiểm trước hạn mức chung', () => {
  const i = route.indexOf("'/product-scene'")
  assert.ok(i > 0)
  const khuc = route.slice(i, i + 4000)
  const iConcept = khuc.indexOf('image.daily.limit.concept')
  const iChung = khuc.indexOf("cfg['image.daily.limit'] > 0")
  assert.ok(iConcept > 0 && iChung > 0)
  assert.ok(iConcept < iChung,
    'hết trần concept thì vẫn phải dùng được SAFE — kiểm chung trước là chặn '
    + 'nhầm cả chế độ an toàn')
})

test('chế độ được GHI vào nhật ký, nếu không thì đếm hạn mức bằng gì', () => {
  const i = route.indexOf("'/product-scene'")
  const khuc = route.slice(i, i + 5000)
  assert.ok(khuc.includes('assistTask: mode'))
})

test('ảnh gửi lên bị chặn dung lượng ngay ở schema', () => {
  const i = route.indexOf("'/product-scene'")
  const khuc = route.slice(i, i + 1600)
  assert.ok(/maxLength: 2_800_000/.test(khuc), 'thiếu trần dung lượng ảnh')
  assert.ok(/image\/png/.test(khuc), 'phải giới hạn định dạng ảnh')
})

test('lỗi do người gọi sai trả 400, không gộp thành 503', () => {
  const i = route.indexOf("'/assist'")
  const khuc = route.slice(i, i + 6000)
  assert.ok(khuc.includes('err.statusCode === 400'),
    'gộp hết vào 503 thì app không phân biệt được lỗi của mình với lỗi máy chủ')
})
