'use strict'

/**
 * Mini-spec H4d — ảnh minh hoạ sinh CHỈ TỪ CHỮ.
 *
 * Cửa này khác `/product-scene` ở đúng chỗ nguy hiểm nhất. Ở đó có ảnh sản
 * phẩm thật làm neo và luật là "đừng đổi gì cả"; ở đây không có neo nào nên
 * luật phải là điều ngược lại: **đừng vẽ sản phẩm nào hết**.
 *
 * Vì sao gắt vậy cho một tấm ảnh nền: nó nằm trong CÙNG một video bán hàng,
 * cạnh sản phẩm thật. Mô hình vẽ ra một hộp có nhãn — dù nhãn bịa — thì máy
 * quét thị giác của TikTok vẫn thấy "sản phẩm" trong video quảng bá, đúng
 * điều khoản đã đẻ ra C1.
 */
const test = require('node:test')
const { mock } = require('node:test')
const assert = require('node:assert')
const crypto = require('node:crypto')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const deviceService = require('../src/services/device.service')
const gateway = require('../src/services/ai-gateway.service')
const config = require('../src/services/config.service')
const story = require('../src/prompts/story_image')
const transport = require('../src/services/image-transport.service')
const assist = require('../src/prompts/assist')
const UsageLog = require('../src/models/UsageLog')
const JobResult = require('../src/models/JobResult')

// ------------------------------------------------ câu lệnh gửi mô hình ----

test('câu lệnh LUÔN mang phần cấm vẽ sản phẩm', () => {
  const p = story.buildPrompt({ brief: 'người phụ nữ vội rời bếp buổi sáng' })
  for (const phai_cam of ['hộp', 'chai', 'lọ', 'túi', 'logo', 'thương hiệu',
    'bao bì']) {
    assert.ok(p.includes(phai_cam), `câu lệnh chưa cấm "${phai_cam}"`)
  }
  // Cấm cả CHỮ, không chỉ cấm nhãn: mô hình sinh ảnh viết chữ sai chính tả
  // rất thường xuyên, và một dòng chữ méo mó vừa lộ là ảnh máy vẽ, vừa có
  // thể trùng tên một thương hiệu thật.
  assert.ok(/chữ, số hay ký tự đọc được/.test(p), 'chưa cấm chữ đọc được')
})

test('gợi ý rỗng thì nổ ngay, không vẽ bừa một tấm ảnh mất tiền', () => {
  assert.throws(() => story.buildPrompt({ brief: '   ' }), /Thiếu gợi ý/)
  assert.throws(() => story.buildPrompt({}), /Thiếu gợi ý/)
})

test('gợi ý dài bị cắt, không cho nhét cả kịch bản vào', () => {
  const p = story.buildPrompt({ brief: 'x'.repeat(5000) })
  assert.ok(p.length < 1200, 'câu lệnh phồng theo gợi ý')
  assert.ok(p.includes(story.KHONG_VE_SAN_PHAM),
    'cắt gợi ý xong thì phần cấm phải còn nguyên')
})

// ------------------------------------------------------- vận chuyển -------

const NOI = (extra) => ({ model: 'm1', apiKey: 'k', ...extra })

test('openai_images đi cửa SINH ảnh, không phải cửa SỬA ảnh', () => {
  const y = transport.dungYeuCauTuChu({ provider: NOI({ type: 'openai_images' }) })
  assert.ok(y.url.endsWith('/images/generations'),
    `đi nhầm cửa: ${y.url}`)
  // `/images/edits` đòi tệp ảnh vào và trả 400 cho lượt gọi không có ảnh —
  // nhưng lỗi đó tới SAU khi đã trừ tiền ở tầng route.
  assert.ok(!y.url.includes('/edits'))
  assert.ok(!('image' in y.body), 'không có ảnh gốc nào để gửi')
})

test('google không nhét ảnh rỗng vào phần inlineData', () => {
  const y = transport.dungYeuCauTuChu({
    provider: NOI({ type: 'google' }), prompt: 'gian bếp' })
  const parts = y.body.contents[0].parts
  assert.equal(parts.length, 1)
  assert.equal(parts[0].text, 'gian bếp')
  assert.ok(!parts.some((p) => p.inlineData), 'gửi inlineData rỗng là 400')
})

test('openrouter không gửi input_references rỗng', () => {
  const y = transport.dungYeuCauTuChu({
    provider: NOI({ type: 'openrouter_images' }), prompt: 'gian bếp' })
  // Ảnh gốc ở đường C1 là THAM CHIẾU giữ sản phẩm cho đúng. Ở đây không có
  // sản phẩm nào để giữ, mà nhét một ảnh bất kỳ vào thì nó ghim phong cách
  // của ảnh đó lên mọi khung hình.
  assert.ok(!('input_references' in y.body))
  assert.equal(y.body.prompt, 'gian bếp')
})

test('mẫu tự khai đòi ảnh gốc thì BỊ TỪ CHỐI, không gửi đi', () => {
  // Đây là chỗ hỏng không kêu tiếng nào nếu bỏ qua: `{{image_data_uri}}`
  // không được điền thì thân yêu cầu gửi đi mang NGUYÊN chuỗi
  // "{{image_data_uri}}" làm dữ liệu ảnh, và nhà cung cấp trả một lỗi
  // chẳng liên quan gì.
  const p = NOI({
    type: 'custom_images',
    imagePath: '/images/edits',
    imageResponsePath: 'data.0.b64_json',
    imageBodyTemplate: '{"prompt":"{{prompt}}","image":"{{image_data_uri}}"}',
  })
  assert.equal(transport.dungYeuCauTuChu({ provider: p, prompt: 'x' }), null)
  const loi = transport.loiMauTuChu(p)
  assert.match(loi, /image_data_uri/, 'lý do phải chỉ đúng chỗ khai sai')
  assert.match(loi, /\/images\/generations/, 'phải chỉ ra đường đi đúng')
})

test('mẫu tự khai chỉ dùng chữ thì dựng được, không sót chỗ chưa điền', () => {
  const y = transport.dungYeuCauTuChu({
    provider: NOI({
      type: 'custom_images',
      imagePath: 'images/generations',
      imageResponsePath: 'data.0.b64_json',
      imageBodyTemplate: '{"model":"{{model}}","prompt":"{{prompt}}"}',
    }),
    prompt: 'một gian bếp buổi sáng',
  })
  assert.ok(y.url.endsWith('/images/generations'), 'phải tự thêm dấu /')
  assert.equal(y.body.prompt, 'một gian bếp buổi sáng')
  assert.ok(!JSON.stringify(y.body).includes('{{'), 'còn chỗ chưa điền')
})

test('giao thức không sinh được ảnh thì trả null, không đoán bừa', () => {
  assert.equal(transport.dungYeuCauTuChu({ provider: NOI({ type: 'openai' }) }),
    null)
})

// --------------------------------------------------- cổng kiểm ảnh --------

test('cổng kiểm nhận ĐÚNG một ảnh và chỉ trả hai phán quyết', () => {
  const t = assist.TASKS.kiem_anh_minh_hoa
  assert.ok(t, 'thiếu tác vụ kiểm — H4d không có gì thi hành Guardrail 1')
  assert.equal(t.nhanAnh, true)
  assert.equal(t.soAnhToiDa, 1)
  for (const tu of ['DAT', 'CO_SAN_PHAM']) assert.ok(t.system.includes(tu))
  // Không chắc thì nghiêng về phía an toàn — như `packaging_check`. Đoán sai
  // hướng an toàn mất một tấm ảnh; đoán sai hướng kia là người bán bị phạt.
  assert.match(t.system, /Không chắc thì chọn CO_SAN_PHAM/)
})

// ------------------------------------------------------------ route -------

let app

test.before(async () => {
  await startDb()
  app = await build({ mongo: false, web: false, logger: false })
  await app.ready()
})
test.after(async () => {
  await app.close()
  await stopDb()
})
test.beforeEach(async () => {
  await clearDb()
  mock.restoreAll()
})

async function thietBiMoi() {
  const { device, token } = await deviceService.registerDevice({
    fingerprint: crypto.randomBytes(32).toString('hex'), name: 'may-thu',
  })
  await require('../src/models/Device').updateOne(
    { _id: device._id }, { $set: { balance: 1000 } })
  return { device, token }
}

function goi(token, body) {
  return app.inject({
    method: 'POST', url: '/v1/ai/story-image', payload: body,
    headers: token ? { authorization: `Bearer ${token}` } : {},
  })
}

const ANH_GIA = { mimeType: 'image/png', data: 'AAAA' }

function moCua() {
  return config.set('image.scene.stage', 'production')
}

test('cửa đang tắt thì 409 — và chặn TRƯỚC cả kết quả cũ', async () => {
  const { device, token } = await thietBiMoi()
  // Dựng sẵn một kết quả cũ đúng jobId: đóng cửa mà vẫn trả hàng qua khe
  // `replay` thì không gọi là đóng.
  await JobResult.create({
    jobId: 'job-cu-12345678',
    fingerprint: device.fingerprint,
    action: 'story_image',
    result: { jobId: 'job-cu-12345678', image: ANH_GIA },
  })
  const r = await goi(token, { jobId: 'job-cu-12345678', brief: 'gian bếp' })
  assert.equal(r.statusCode, 409)
  assert.equal(r.json().code, 'IMAGE_STAGE_OFF')
})

test('mở cửa thì vẽ được — nhưng ảnh trả về KHAI RÕ là chưa kiểm', async () => {
  const { token } = await thietBiMoi()
  await moCua()
  mock.method(gateway, 'generateStoryImage', async () => ({
    image: ANH_GIA, provider: 'noi-1', model: 'm1', prompt: 'p' }))

  const r = await goi(token, { jobId: 'job-moi-12345678', brief: 'gian bếp' })
  assert.equal(r.statusCode, 200, r.body)
  const b = r.json()
  assert.deepEqual(b.image, ANH_GIA)
  // Trả về mỗi tấm ảnh thì phía gọi rất dễ hiểu nhầm là đã xong, mà bước
  // kiểm mới là chỗ Guardrail 1 được thi hành.
  assert.equal(b.daKiem, false, 'cửa này KHÔNG được tự nhận là đã kiểm')
  assert.equal(b.creditCharged, 30)

  const ghi = await UsageLog.findOne({ action: 'story_image' })
  assert.ok(ghi, 'không ghi sổ thì lúc bị sàn gắn cờ không tra lại được')
  assert.equal(ghi.status, 'success')
  // Bẫy đã cắn ở H3: thiếu giá trị trong enum `action` thì `remember()` hỏng
  // IM LẶNG sau khi đã trừ tiền.
  assert.ok(await JobResult.findOne({ jobId: 'job-moi-12345678' }),
    'không nhớ được kết quả — lượt gọi lại sẽ trừ tiền lần nữa')
})

test('trần ngày đếm GỘP hai đường sinh ảnh', async () => {
  const { device, token } = await thietBiMoi()
  await moCua()
  await config.set('image.daily.limit', 3)
  // Ba ảnh đã sinh hôm nay đều ở đường KIA. Đếm tách theo `action` thì trần
  // 3 thành 6 mà không ai quyết định điều đó.
  for (let i = 0; i < 3; i += 1) {
    await UsageLog.create({
      fingerprint: device.fingerprint, jobId: `cu-${i}`,
      action: 'product_scene', status: 'success',
    })
  }
  const goiThat = mock.method(gateway, 'generateStoryImage', async () => ({
    image: ANH_GIA, provider: 'n', model: 'm' }))

  const r = await goi(token, { jobId: 'job-tran-12345678', brief: 'gian bếp' })
  assert.equal(r.statusCode, 429)
  assert.equal(r.json().code, 'DAILY_LIMIT')
  assert.equal(goiThat.mock.callCount(), 0, 'chặn rồi mà vẫn gọi mô hình')
})

test('gợi ý dài quá bị chặn ở cổng, KHÔNG tính tiền', async () => {
  const { token } = await thietBiMoi()
  await moCua()
  const goiThat = mock.method(gateway, 'generateStoryImage', async () => ({
    image: ANH_GIA, provider: 'n', model: 'm' }))

  const r = await goi(token, {
    jobId: 'job-dai-12345678', brief: 'x'.repeat(story.DAI_TOI_DA + 1) })
  assert.equal(r.statusCode, 400)
  assert.equal(goiThat.mock.callCount(), 0)
  assert.equal(await UsageLog.countDocuments({ action: 'story_image' }), 0)
})
