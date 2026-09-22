'use strict'

/**
 * MINI-SPEC I2 — Từ điển chỉ đạo hình ảnh v1.
 *
 * Mỗi test dưới đây là một cái chốt, và mỗi cái chốt có một lý do thật:
 *
 *  - `supported` mà không có hàm dựng hình thật = hứa với người dùng một hiệu
 *    ứng không tồn tại. Đây là lỗi mà I2 sinh ra để chặn.
 *  - Một mục "nhịp dựng" đụng được vào thời lượng = đúng cái lỗi "mấy giây
 *    cuối đứng hình" vừa sửa ở D1/H4c-1. Nên catalog bị cấm mang tham số thời
 *    gian, ở mọi nhóm, không chỉ nhóm pacing.
 *  - Mô hình ở I3 sẽ nghĩ ra thuật ngữ điện ảnh (drone, dolly zoom, rack
 *    focus…). Cổng chặn phải nằm ở DỮ LIỆU, trước khi có ai gọi mô hình.
 *
 * Phép đo thật (video ra dài đúng bao nhiêu, khung cuối có đứng hình không)
 * KHÔNG ở đây — nó ở `scripts/kiem_catalog_h4.py`, chạy ffmpeg thật. Test này
 * chỉ giữ cho dữ liệu không nói sai về thứ đã đo được.
 *
 * Chạy:  node --test tests/visual-catalog.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const cat = require('../src/services/visual-catalog.service')
const { build } = require('../src/app')

const TEP = path.join(__dirname, '..', 'src', 'data',
  'visual-direction-catalog.v1.json')

/** Bản SAO đọc thẳng từ đĩa — để sửa thử mà không đụng bản đang chạy. */
function banSao() {
  return JSON.parse(fs.readFileSync(TEP, 'utf8'))
}

function nhom(data, id) {
  return data.groups.find((g) => g.id === id)
}

function moiMuc(data) {
  return data.groups.flatMap((g) => g.values.map((v) => [g, v]))
}

// ----------------------------------------------------------- khuôn dữ liệu ---

test('catalog v1 trên đĩa đạt toàn bộ phép soi', () => {
  assert.deepStrictEqual(cat.kiemTraCatalog(banSao()), [])
})

test('phiên bản là bắt buộc và đọc ra đúng một con số', () => {
  assert.strictEqual(cat.docCatalog().catalog_version, 1)
  const thieu = banSao(); delete thieu.catalog_version
  assert.ok(cat.kiemTraCatalog(thieu).some((l) => l.includes('catalog_version')))
  const chuoi = banSao(); chuoi.catalog_version = '1'
  assert.ok(cat.kiemTraCatalog(chuoi).some((l) => l.includes('catalog_version')),
    'phiên bản dạng chuỗi phải bị loại — "1" và 1 so sánh lỏng là chỗ trôi lệch')
})

test('đủ sáu nhóm, đúng thứ tự mini-spec', () => {
  assert.deepStrictEqual(cat.docCatalog().groups.map((g) => g.id),
    ['shot', 'composition', 'motion', 'pacing', 'transition', 'lighting_color'])
})

test('mã nhóm và mã mục không trùng nhau', () => {
  const ids = moiMuc(cat.docCatalog()).map(([, v]) => v.id)
  assert.strictEqual(new Set(ids).size, ids.length)

  const trung = banSao()
  nhom(trung, 'shot').values.push({ ...nhom(trung, 'shot').values[0] })
  assert.ok(cat.kiemTraCatalog(trung).some((l) => l.includes('trùng')))
})

test('mọi mục đều có nhãn, mô tả, gợi ý dùng và cảnh báo bằng tiếng Việt', () => {
  for (const [g, v] of moiMuc(cat.docCatalog())) {
    for (const truong of ['label_vi', 'description_vi', 'prompt_hint_vi']) {
      assert.ok(v[truong] && v[truong].trim(), `${g.id}.${v.id} thiếu ${truong}`)
    }
    assert.ok(v.recommended_for.length, `${g.id}.${v.id} thiếu recommended_for`)
    assert.ok(v.avoid_when.length, `${g.id}.${v.id} thiếu avoid_when`)
  }
  const cut = banSao()
  nhom(cut, 'shot').values[0].description_vi = '   '
  assert.ok(cat.kiemTraCatalog(cut).some((l) => l.includes('description_vi')))
})

test('recommended_for chỉ dùng vai beat CÓ THẬT của H2/H3', () => {
  const bia = banSao()
  nhom(bia, 'shot').values[0].recommended_for = ['moment_viral']
  assert.ok(cat.kiemTraCatalog(bia).some((l) => l.includes('vai lạ')),
    'vốn từ tự chế phải bị chặn — nếu không, I3 sẽ học theo mà sinh vai không có thật')
})

// ------------------------------------------------- supported vs advisory ---

test('mục supported phải trỏ vào hàm dựng hình CÓ THẬT', () => {
  for (const [g, v] of moiMuc(cat.docCatalog())) {
    if (v.render_mode !== 'supported') continue
    assert.ok(v.h4_mapping, `${g.id}.${v.id} khai supported mà không có mapping`)
    assert.ok(Object.prototype.hasOwnProperty.call(cat.CACH_DUNG,
      v.h4_mapping.implementation), `${g.id}.${v.id} trỏ vào hàm không có thật`)
  }
})

test('khai supported mà thiếu mapping thì ĐỎ', () => {
  const hong = banSao()
  const t = nhom(hong, 'transition').values.find((v) => v.id === 'fade_nhe')
  t.h4_mapping = null
  assert.ok(cat.kiemTraCatalog(hong).some((l) => l.includes('bắt buộc có h4_mapping')))
})

test('gắn supported cho hiệu ứng điện ảnh không có mapping thì ĐỎ', () => {
  const hong = banSao()
  nhom(hong, 'motion').values.push({
    id: 'zoom_vao_cham',
    label_vi: 'Zoom vào chậm',
    description_vi: 'Phóng dần vào chủ thể suốt cảnh.',
    recommended_for: ['hook'],
    avoid_when: ['ảnh độ phân giải thấp'],
    prompt_hint_vi: 'Chủ thể ở giữa để phóng vào.',
    render_mode: 'supported',
    h4_mapping: { implementation: 'product_video.ken_burns', parameters: {} },
  })
  assert.ok(cat.kiemTraCatalog(hong).some((l) => l.includes('không có')),
    'khâu ghép hình không có bộ lọc zoompan nào — khai supported là nói sai')
})

test('mục advisory_only KHÔNG được có đường thực thi', () => {
  for (const [g, v] of moiMuc(cat.docCatalog())) {
    if (v.render_mode !== 'advisory_only') continue
    assert.strictEqual(v.h4_mapping, null, `${g.id}.${v.id} có mapping`)
    assert.ok(v.advisory_note_vi && v.advisory_note_vi.trim(),
      `${g.id}.${v.id} phải nói rõ vì sao chưa tự làm được`)
  }
  const hong = banSao()
  nhom(hong, 'shot').values[0].h4_mapping = {
    implementation: 'product_video.ghep_anh_nguoi_dung', parameters: {},
  }
  assert.ok(cat.kiemTraCatalog(hong).some((l) => l.includes('advisory_only')))
})

test('không mục nào mang trạng thái ngoài hai trạng thái được ship', () => {
  const hong = banSao()
  nhom(hong, 'shot').values[0].render_mode = 'unavailable'
  assert.ok(cat.kiemTraCatalog(hong).some((l) => l.includes('render_mode')),
    'mục không dùng được thì nằm ở tài liệu tồn đọng, không nằm trong dữ liệu chạy')
})

// ------------------------------------------------------- tiền tuyến D1/H4 ---

test('KHÔNG mapping nào được mang tham số thời gian', () => {
  for (const [g, v] of moiMuc(cat.docCatalog())) {
    const tham = v.h4_mapping ? Object.keys(v.h4_mapping.parameters) : []
    for (const k of tham) {
      assert.ok(!cat.THAM_SO_CAM.includes(k),
        `${g.id}.${v.id} mang tham số thời gian "${k}"`)
    }
  }
  const hong = banSao()
  nhom(hong, 'transition').values.find((v) => v.id === 'fade_nhe')
    .h4_mapping.parameters.giay_chuyen = 1.5
  assert.ok(cat.kiemTraCatalog(hong).some((l) => l.includes('thời lượng')),
    'catalog đặt được thời lượng chuyển cảnh = catalog đặt được độ dài video')
})

test('nhóm pacing không bao giờ được trở thành lệnh dựng', () => {
  for (const v of nhom(cat.docCatalog(), 'pacing').values) {
    assert.strictEqual(v.render_mode, 'advisory_only')
    assert.strictEqual(v.nguon_thoi_luong, 'd1_audio')
  }
  const hong = banSao()
  const p = nhom(hong, 'pacing').values[0]
  p.render_mode = 'supported'
  p.h4_mapping = {
    implementation: 'product_video.ghep_anh_nguoi_dung', parameters: {},
  }
  const loi = cat.kiemTraCatalog(hong)
  assert.ok(loi.some((l) => l.includes('pacing chỉ được advisory_only')),
    'cho pacing thành supported = mở đường ghi đè thời lượng do giọng đọc quyết định')

  const mat = banSao()
  delete nhom(mat, 'pacing').values[0].nguon_thoi_luong
  assert.ok(cat.kiemTraCatalog(mat).some((l) => l.includes('nguon_thoi_luong')))
})

test('chuyển cảnh chỉ chọn KIỂU, không chọn độ dài', () => {
  for (const v of nhom(cat.docCatalog(), 'transition').values) {
    assert.deepStrictEqual(Object.keys(v.h4_mapping.parameters), ['kieu_chuyen'],
      `${v.id}: chuyển cảnh chỉ được mang đúng kiểu — mọi tham số khác là cửa `
      + 'để rút ngắn cảnh cuối')
  }
})

// -------------------------------------------------------- khả năng bị cấm ---

test('khả năng bị cấm không lọt được vào dữ liệu chạy', () => {
  for (const ten of ['drone_shot', 'dolly_zoom', 'rack_focus', 'whip_pan']) {
    const hong = banSao()
    nhom(hong, 'shot').values.push({
      id: ten,
      label_vi: 'Cảnh quay thử',
      description_vi: 'Mô tả thử.',
      recommended_for: ['hook'],
      avoid_when: ['thử'],
      prompt_hint_vi: 'Thử.',
      render_mode: 'advisory_only',
      h4_mapping: null,
      advisory_note_vi: 'Thử.',
    })
    assert.ok(cat.kiemTraCatalog(hong).some((l) => l.includes('bị cấm')),
      `${ten} phải bị chặn ngay ở tầng dữ liệu`)
  }
})

test('chữ quảng cáo cũng bị soi, không chỉ mã', () => {
  const hong = banSao()
  nhom(hong, 'motion').values[0].prompt_hint_vi =
    'Dùng AI video dựng thêm chuyển động cho ảnh.'
  assert.ok(cat.kiemTraCatalog(hong).some((l) => l.includes('bị cấm')))
})

// ------------------------------------------- cổng kiểm cho I3 (tương lai) ---

test('cổng kiểm loại mã lạ, nhóm lạ và phiên bản lạ', () => {
  assert.strictEqual(cat.kiemChon(
    { catalog_version: 1, shot: 'can_canh', transition: 'fade_nhe' }).ok, true)

  assert.strictEqual(cat.kiemChon({ catalog_version: 1, shot: 'bay_flycam' }).ok,
    false)
  assert.strictEqual(cat.kiemChon({ catalog_version: 1, camera: 'gimbal' }).ok,
    false)
  assert.strictEqual(cat.kiemChon({ catalog_version: 2, shot: 'can_canh' }).ok,
    false)
  assert.strictEqual(cat.kiemChon({ shot: 'can_canh' }).ok, false)
  assert.strictEqual(cat.kiemChon({ catalog_version: 1 }).ok, false)
  assert.strictEqual(cat.kiemChon('can_canh').ok, false)
})

test('mục gợi ý KHÔNG đi xuống được khâu dựng hình', () => {
  const goi_y = cat.kiemChon({ catalog_version: 1, shot: 'can_canh' },
    { mucDich: 'goi_y' })
  assert.strictEqual(goi_y.ok, true)

  const dung = cat.kiemChon({ catalog_version: 1, shot: 'can_canh' },
    { mucDich: 'dung_hinh' })
  assert.strictEqual(dung.ok, false,
    'cận cảnh là gợi ý chọn ảnh — gửi xuống ffmpeg thì không có gì để thực thi')
  assert.ok(dung.loi[0].includes('advisory_only'))

  assert.strictEqual(cat.kiemChon({ catalog_version: 1, transition: 'fade_nhe' },
    { mucDich: 'dung_hinh' }).ok, true)
})

// ------------------------------------------------------------- cửa đọc API ---

test('GET /v1/config/visual-direction-catalog trả đúng bản đang chạy', async (t) => {
  const app = await build({ mongo: false, web: false, logger: false })
  t.after(() => app.close())

  const res = await app.inject({
    method: 'GET', url: '/v1/config/visual-direction-catalog',
  })
  assert.strictEqual(res.statusCode, 200)
  const than = res.json()
  assert.strictEqual(than.catalog_version, 1)
  assert.strictEqual(than.groups.length, 6)
  assert.deepStrictEqual(cat.kiemTraCatalog(than), [],
    'thứ trả ra API phải đạt đúng phép soi như tệp trên đĩa')
})

test('cửa catalog chỉ ĐỌC — không có đường ghi', async (t) => {
  const app = await build({ mongo: false, web: false, logger: false })
  t.after(() => app.close())

  for (const method of ['POST', 'PUT', 'DELETE']) {
    const res = await app.inject({
      method, url: '/v1/config/visual-direction-catalog', payload: {},
    })
    assert.strictEqual(res.statusCode, 404,
      `${method} không được tồn tại — I2 chưa có gì để lưu`)
  }
})

test('catalog không mang khoá, lời nhắc hay dấu vết thiết bị', async (t) => {
  const app = await build({ mongo: false, web: false, logger: false })
  t.after(() => app.close())

  const res = await app.inject({
    method: 'GET', url: '/v1/config/visual-direction-catalog',
  })
  const tho = res.body.toLowerCase()
  for (const cam of ['api_key', 'apikey', 'system', 'fingerprint', 'token',
    'baseurl', 'prompt"', 'bearer']) {
    assert.ok(!tho.includes(cam), `catalog lộ "${cam}"`)
  }
})
