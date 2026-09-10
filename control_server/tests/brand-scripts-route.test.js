'use strict'

/**
 * Mini-spec H3 — `/v1/brand-scripts` qua HTTP thật (fastify.inject).
 *
 * Mock `gateway.assist` (không có key mô hình trong môi trường test) để kiểm
 * đúng phần route tự làm: kiểm chéo ownership CẢ HAI tham chiếu, chặn khi hồ
 * sơ brand thiếu trường, tính trạng thái, và luật "tạo lại một đoạn phải kiểm
 * lại TOÀN BỘ".
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
const BrandScript = require('../src/models/BrandScript')
const BrandProfile = require('../src/models/BrandProfile')
const FlowBlueprint = require('../src/models/FlowBlueprint')
const dauVanTay = require('../src/services/dau-van-tay.service')

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

const NGUON = [
  'Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc chuẩn bị bữa ăn không',
  'MUA NGAY HÔM NAY',
]

async function thietBiMoi(ten) {
  const { device, token } = await deviceService.registerDevice({
    fingerprint: crypto.randomBytes(32).toString('hex'), name: ten,
  })
  await require('../src/models/Device').updateOne(
    { _id: device._id }, { $set: { balance: 1000 } })
  return { device, token }
}

async function hoSoBrand(deviceId, extra = {}) {
  return BrandProfile.create({
    ownerDeviceId: deviceId,
    tenBrand: 'Bếp Nhà Vui',
    moTaSanPham: 'Nồi chiên không dầu 5 lít',
    doiTuongKhach: 'Mẹ bỉm sữa ở thành phố',
    toneGiong: 'Gần gũi như bạn bè',
    usp: 'Làm nóng trong 3 phút',
    rangBuocKhongDuocNoi: ['tốt nhất', 'chữa bệnh'],
    ...extra,
  })
}

async function blueprintCo(deviceId, { vanTay = true, evidenceStatus = 'ok' } = {}) {
  return FlowBlueprint.create({
    ownerDeviceId: deviceId,
    sourceType: 'url',
    sourceReference: 'https://example.com/v',
    status: 'ready',
    beats: [
      { startS: 0, endS: 2, beatType: 'hook', narrativeFunctionVi: 'Mở đầu', evidenceStatus },
      { startS: 2, endS: 5, beatType: 'cta', narrativeFunctionVi: 'Kêu gọi', evidenceStatus },
    ],
    evidenceFingerprint: vanTay ? dauVanTay.taoDauVanTay(NGUON) : null,
  })
}

function goi(method, url, token, body) {
  // KHÔNG ép `content-type: application/json` — GET/DELETE không có thân, mà
  // khai content-type JSON rồi gửi thân rỗng thì fastify trả 400 trước khi
  // route kịp chạy, và test sẽ "đỏ" vì lý do chẳng liên quan gì tới thứ nó
  // định kiểm.
  return app.inject({
    method, url, payload: body,
    headers: token ? { authorization: `Bearer ${token}` } : {},
  })
}

/** Mô hình giả trả kịch bản SẠCH (không đụng nguồn, không đụng cụm cấm). */
function gtSach() {
  return mock.method(gateway, 'assist', async () => ({
    beats: [
      { beatType: 'hook', voiceoverTextVi: 'Buổi sáng của bạn trôi đi vì việc bếp núc lặt vặt phải không', captionSuggestionVi: 'Sáng nào cũng vội', visualBriefVi: 'Cận cảnh gian bếp' },
      { beatType: 'cta', voiceoverTextVi: 'Thử xem, biết đâu buổi sáng nhẹ hơn hẳn', captionSuggestionVi: 'Thử đi', visualBriefVi: 'Sản phẩm trên bàn' },
    ],
    usage: {}, provider: 'fake', model: 'fake', role: 'assist',
  }))
}

function than(jobId, blueprintId, brandId) {
  return { jobId, flowBlueprintId: String(blueprintId), brandProfileId: String(brandId) }
}

// ------------------------------------------------------------- cơ bản ------

test('tạo kịch bản sạch -> ready, gắn đúng chủ, không lộ ownerDeviceId', async () => {
  gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)

  const res = await goi('POST', '/v1/brand-scripts/', a.token, than('js1'.repeat(4), bp._id, br._id))
  assert.equal(res.statusCode, 201)
  const body = res.json()
  assert.equal(body.status, 'ready')
  assert.equal(body.beats.length, 2)
  assert.equal(body.beats[0].originalityFlag, 'clear')
  assert.equal(body.beats[0].complianceFlag, 'clear')
  assert.ok(!('ownerDeviceId' in body))
  assert.equal(body.originalityCheckVersion, dauVanTay.PHIEN_BAN)
})

test('beat chép nguyên văn nguồn -> CẢ script blocked, chỉ rõ cụm', async () => {
  mock.method(gateway, 'assist', async () => ({
    beats: [
      { beatType: 'hook', voiceoverTextVi: 'Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc nấu nướng không', captionSuggestionVi: 'x', visualBriefVi: 'y' },
      { beatType: 'cta', voiceoverTextVi: 'Câu này thì hoàn toàn mới và sạch sẽ', captionSuggestionVi: 'x', visualBriefVi: 'y' },
    ],
    usage: {}, provider: 'f', model: 'f', role: 'assist',
  }))
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)

  const res = await goi('POST', '/v1/brand-scripts/', a.token, than('js2'.repeat(4), bp._id, br._id))
  const body = res.json()
  assert.equal(body.status, 'blocked')
  assert.equal(body.beats[0].originalityFlag, 'flagged')
  assert.ok(body.beats[0].flaggedExcerpt, 'phải chỉ ra cụm bị chặn')
  assert.equal(body.beats[1].originalityFlag, 'clear',
    'beat sạch vẫn hiện đúng cờ của nó — chặn ở cấp script, không bôi đen tất cả')
})

test('beat chứa cụm brand tự cấm -> blocked kèm câu ràng buộc đã kích hoạt', async () => {
  mock.method(gateway, 'assist', async () => ({
    beats: [
      { beatType: 'hook', voiceoverTextVi: 'Đây là chiếc nồi tốt nhất bạn từng dùng', captionSuggestionVi: 'x', visualBriefVi: 'y' },
      { beatType: 'cta', voiceoverTextVi: 'Câu sạch', captionSuggestionVi: 'x', visualBriefVi: 'y' },
    ],
    usage: {}, provider: 'f', model: 'f', role: 'assist',
  }))
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)

  const body = (await goi('POST', '/v1/brand-scripts/', a.token, than('js3'.repeat(4), bp._id, br._id))).json()
  assert.equal(body.status, 'blocked')
  assert.equal(body.beats[0].complianceFlag, 'violated')
  assert.equal(body.beats[0].complianceRule, 'tốt nhất')
})

test('Blueprint KHÔNG có dấu vân tay -> unconfirmed, không bao giờ ready', async () => {
  gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id, { vanTay: false })
  const br = await hoSoBrand(a.device._id)

  const body = (await goi('POST', '/v1/brand-scripts/', a.token, than('js4'.repeat(4), bp._id, br._id))).json()
  assert.equal(body.status, 'unconfirmed')
  assert.equal(body.beats[0].lyDoChuaKiem, 'khong_co_dau_van_tay')
})

// -------------------------------------------------- hồ sơ brand thiếu -----

test('hồ sơ brand thiếu USP -> 400, KHÔNG gọi mô hình, KHÔNG bịa hộ', async () => {
  const fn = gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id, { usp: '' })

  const res = await goi('POST', '/v1/brand-scripts/', a.token, than('js5'.repeat(4), bp._id, br._id))
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'HO_SO_BRAND_THIEU')
  assert.ok(res.json().thieu.includes('điểm mạnh (USP)'))
  assert.equal(fn.mock.callCount(), 0, 'không được gọi mô hình khi hồ sơ chưa đủ')
})

// ----------------------------------------------------- cách ly thiết bị ----

test('không tạo được kịch bản từ Blueprint của thiết bị KHÁC', async () => {
  gtSach()
  const a = await thietBiMoi('Máy A')
  const b = await thietBiMoi('Máy B')
  const bpCuaA = await blueprintCo(a.device._id)
  const brCuaB = await hoSoBrand(b.device._id)

  const res = await goi('POST', '/v1/brand-scripts/', b.token,
    than('js6'.repeat(4), bpCuaA._id, brCuaB._id))
  assert.equal(res.statusCode, 404, 'ID có tồn tại nhưng của máy khác vẫn phải 404')
  assert.equal(await BrandScript.countDocuments(), 0)
})

test('không tạo được kịch bản từ hồ sơ brand của thiết bị KHÁC', async () => {
  gtSach()
  const a = await thietBiMoi('Máy A')
  const b = await thietBiMoi('Máy B')
  const bpCuaB = await blueprintCo(b.device._id)
  const brCuaA = await hoSoBrand(a.device._id)

  const res = await goi('POST', '/v1/brand-scripts/', b.token,
    than('js7'.repeat(4), bpCuaB._id, brCuaA._id))
  assert.equal(res.statusCode, 404)
})

test('thiết bị B không đọc/xoá được kịch bản của A', async () => {
  gtSach()
  const a = await thietBiMoi('Máy A')
  const b = await thietBiMoi('Máy B')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const id = (await goi('POST', '/v1/brand-scripts/', a.token, than('js8'.repeat(4), bp._id, br._id))).json().id

  assert.equal((await goi('GET', `/v1/brand-scripts/${id}`, b.token)).statusCode, 404)
  assert.equal((await goi('DELETE', `/v1/brand-scripts/${id}`, b.token)).statusCode, 404)
  assert.equal((await goi('GET', '/v1/brand-scripts/', b.token)).json().data.length, 0)
  assert.ok(await BrandScript.findById(id), 'bản ghi của A vẫn phải còn nguyên')
})

// ----------------------------------------------- regenerate kiểm toàn bộ ---

test('regenerate-beat: beat mới bẩn -> CẢ script chuyển blocked', async () => {
  // Ca mà Constraint 11 sinh ra để chặn: script đang ready, tạo lại đúng một
  // đoạn, đoạn mới vô tình trùng nguồn ⇒ không được giữ ready cũ.
  gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const id = (await goi('POST', '/v1/brand-scripts/', a.token, than('js9'.repeat(4), bp._id, br._id))).json().id
  assert.equal((await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json().status, 'ready')

  mock.restoreAll()
  mock.method(gateway, 'assist', async () => ({
    beats: [
      { beatType: 'hook', voiceoverTextVi: 'Câu sạch giữ nguyên', captionSuggestionVi: 'x', visualBriefVi: 'y' },
      { beatType: 'cta', voiceoverTextVi: 'Bạn có đang mất quá nhiều thời gian mỗi sáng cho việc gì đó', captionSuggestionVi: 'x', visualBriefVi: 'y' },
    ],
    usage: {}, provider: 'f', model: 'f', role: 'assist',
  }))
  const res = await goi('POST', `/v1/brand-scripts/${id}/regenerate-beat`, a.token,
    { jobId: 'jr1'.repeat(4), beatIndex: 1 })
  assert.equal(res.statusCode, 200)
  assert.equal(res.json().status, 'blocked', 'phải kiểm lại TOÀN BỘ, không giữ ready cũ')
  assert.equal(res.json().beats[1].originalityFlag, 'flagged')
})

test('regenerate-beat: chỉ thay đúng đoạn được yêu cầu', async () => {
  gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const id = (await goi('POST', '/v1/brand-scripts/', a.token, than('jsA'.repeat(4), bp._id, br._id))).json().id
  const truoc = (await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json()

  mock.restoreAll()
  mock.method(gateway, 'assist', async () => ({
    beats: [
      { beatType: 'hook', voiceoverTextVi: 'ĐOẠN MỘT MỚI TINH', captionSuggestionVi: 'x', visualBriefVi: 'y' },
      { beatType: 'cta', voiceoverTextVi: 'ĐOẠN HAI MỚI TINH', captionSuggestionVi: 'x', visualBriefVi: 'y' },
    ],
    usage: {}, provider: 'f', model: 'f', role: 'assist',
  }))
  const sau = (await goi('POST', `/v1/brand-scripts/${id}/regenerate-beat`, a.token,
    { jobId: 'jrB'.repeat(4), beatIndex: 0 })).json()

  assert.equal(sau.beats[0].voiceoverTextVi, 'ĐOẠN MỘT MỚI TINH')
  assert.equal(sau.beats[1].voiceoverTextVi, truoc.beats[1].voiceoverTextVi,
    'đoạn không yêu cầu tạo lại phải giữ nguyên')
})

test('regenerate-beat gửi NGỮ CẢNH viết lại, không lặp y hệt đầu vào cũ', async () => {
  // Thiếu ngữ cảnh thì lượt gọi lại có đầu vào y hệt lượt trước, mô hình trả
  // gần như y hệt, và nút "viết lại" trông như hỏng trong khi vẫn tính tiền.
  gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const id = (await goi('POST', '/v1/brand-scripts/', a.token, than('jsI'.repeat(4), bp._id, br._id))).json().id

  mock.restoreAll()
  const daGoi = []
  mock.method(gateway, 'assist', async (args) => {
    daGoi.push(args.input)
    return {
      beats: [
        { beatType: 'hook', voiceoverTextVi: 'Bản viết lại khác hẳn', captionSuggestionVi: 'x', visualBriefVi: 'y' },
        { beatType: 'cta', voiceoverTextVi: 'Đoạn hai', captionSuggestionVi: 'x', visualBriefVi: 'y' },
      ],
      usage: {}, provider: 'f', model: 'f', role: 'assist',
    }
  })
  await goi('POST', `/v1/brand-scripts/${id}/regenerate-beat`, a.token,
    { jobId: 'jrE'.repeat(4), beatIndex: 0 })

  assert.equal(daGoi.length, 1)
  assert.equal(daGoi[0].vietLaiDoan, 1, 'phải nói rõ đoạn nào đang viết lại')
  assert.ok(Array.isArray(daGoi[0].doanDangCo) && daGoi[0].doanDangCo.length === 2,
    'phải gửi các đoạn đang giữ để bản mới còn ăn khớp')

  // ...và lời nhắc dựng ra phải thật sự chứa yêu cầu làm lại
  const spec = require('../src/prompts/assist').getTask('brand_script_rewrite')
  const loi = spec.buildUser(daGoi[0])
  assert.match(loi, /YÊU CẦU LÀM LẠI: viết lại ĐOẠN 1/)
  assert.match(loi, /KHÁC HẲN/)
})

test('regenerate-beat khi Blueprint gốc đã bị xoá -> 409, hạ về unconfirmed', async () => {
  gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const id = (await goi('POST', '/v1/brand-scripts/', a.token, than('jsC'.repeat(4), bp._id, br._id))).json().id

  await FlowBlueprint.deleteOne({ _id: bp._id })
  const res = await goi('POST', `/v1/brand-scripts/${id}/regenerate-beat`, a.token,
    { jobId: 'jrD'.repeat(4), beatIndex: 0 })
  assert.equal(res.statusCode, 409)
  assert.equal(res.json().code, 'NGUON_DA_MAT')
  const doc = await BrandScript.findById(id)
  assert.equal(doc.status, 'unconfirmed', 'nguồn mất thì KHÔNG được giữ ready')
})

// ------------------------------------------------------------ guardrail ----

test('hết hạn mức ngày -> 429, KHÔNG gọi mô hình, KHÔNG trừ tiền', async () => {
  // Lớp chặn chi phí thứ 3. Route này gọi thẳng `gateway.assist()` nên không
  // đi qua chỗ kiểm của `/v1/ai/assist` — thiếu lớp này thì rate-limit theo
  // phút chỉ chặn người bấm dồn dập, không chặn một vòng lặp hỏng chạy cả ngày.
  const fn = gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)

  const config = require('../src/services/config.service')
  const goc = config.getMany
  config.getMany = async (khoa) => {
    const ra = await goc.call(config, khoa)
    if ('assist.daily.limit' in ra) ra['assist.daily.limit'] = 1
    return ra
  }
  const UsageLog = require('../src/models/UsageLog')
  await UsageLog.create({ fingerprint: a.device.fingerprint, jobId: 'cu-1234',
    action: 'assist', assistTask: 'brand_script_rewrite', status: 'success' })

  try {
    const res = await goi('POST', '/v1/brand-scripts/', a.token,
      than('jsK'.repeat(4), bp._id, br._id))
    assert.equal(res.statusCode, 429)
    assert.equal(res.json().code, 'DAILY_LIMIT')
    assert.equal(fn.mock.callCount(), 0, 'không được gọi mô hình khi đã hết hạn mức')
    const device = await require('../src/models/Device').findById(a.device._id)
    assert.equal(device.balance, 1000, 'không được trừ Vox')
  } finally {
    config.getMany = goc
  }
})

test('HỒI QUY: không có đường nào cho client đặt status = ready', async () => {
  gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id, { vanTay: false })  // ⇒ unconfirmed
  const br = await hoSoBrand(a.device._id)
  const id = (await goi('POST', '/v1/brand-scripts/', a.token, than('jsE'.repeat(4), bp._id, br._id))).json().id

  // Thử mọi động tác một client có thể nghĩ ra để tự nâng trạng thái.
  for (const [method, url, body] of [
    ['POST', '/v1/brand-scripts/', { ...than('jsF'.repeat(4), bp._id, br._id), status: 'ready' }],
    ['PUT', `/v1/brand-scripts/${id}`, { status: 'ready' }],
    ['PATCH', `/v1/brand-scripts/${id}`, { status: 'ready' }],
  ]) {
    const res = await goi(method, url, a.token, body)
    if (res.statusCode === 201 || res.statusCode === 200) {
      assert.notEqual(res.json().status, 'ready', `${method} ${url} nâng được trạng thái`)
    }
  }
  assert.notEqual((await BrandScript.findById(id)).status, 'ready')
})

test('script ready bằng phiên bản bộ kiểm CŨ -> đọc lại thành unconfirmed', async () => {
  gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const id = (await goi('POST', '/v1/brand-scripts/', a.token, than('jsG'.repeat(4), bp._id, br._id))).json().id

  await BrandScript.updateOne({ _id: id },
    { $set: { originalityCheckVersion: dauVanTay.PHIEN_BAN - 1 } })

  assert.equal((await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json().status, 'unconfirmed')
  assert.equal((await goi('GET', '/v1/brand-scripts/', a.token)).json().data[0].status, 'unconfirmed')
})

test('ghi đủ SỐ LIỆU ĐỊNH GIÁ vào sổ, cả lượt tạo lẫn lượt viết lại', async () => {
  // Giá hiện là 12 Vox PHẲNG trong khi kịch bản 40 đoạn tốn hơn hẳn 5 đoạn.
  // Không ghi số liệu từ bây giờ thì tới lúc cần định giá lại sẽ không có gì
  // để dựa vào ngoài phỏng đoán. Và lượt "viết lại đoạn" trước đây không ghi
  // sổ gì cả — số lần regenerate không đếm được.
  mock.method(gateway, 'assist', async () => ({
    beats: [
      { beatType: 'hook', voiceoverTextVi: 'Câu mới một', captionSuggestionVi: 'a', visualBriefVi: 'b' },
      { beatType: 'cta', voiceoverTextVi: 'Câu mới hai', captionSuggestionVi: 'a', visualBriefVi: 'b' },
    ],
    usage: { promptTokens: 1234, completionTokens: 567 },
    provider: 'nha-cung-cap-X', model: 'mo-hinh-Y', role: 'assist',
  }))
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const UsageLog = require('../src/models/UsageLog')

  const id = (await goi('POST', '/v1/brand-scripts/', a.token,
    than('jsL'.repeat(4), bp._id, br._id))).json().id

  const so = await UsageLog.findOne({ assistTask: 'brand_script_rewrite' }).lean()
  assert.ok(so, 'lượt tạo phải ghi sổ')
  assert.equal(so.inputSize, 2, 'phải ghi số đoạn — đây là thứ chi phối chi phí')
  assert.equal(so.aiProvider, 'nha-cung-cap-X')
  assert.equal(so.aiModel, 'mo-hinh-Y')
  assert.equal(so.promptTokens, 1234)
  assert.equal(so.completionTokens, 567)
  assert.ok(so.durationMs >= 0 && so.durationMs < 60000)
  assert.equal(so.creditCharged, 12)
  assert.equal(so.verdict, 'ready', 'ghi phán quyết để đếm tỉ lệ bị chặn')

  await goi('POST', `/v1/brand-scripts/${id}/regenerate-beat`, a.token,
    { jobId: 'jrF'.repeat(4), beatIndex: 0 })
  const soLuot = await UsageLog.countDocuments({ assistTask: 'brand_script_rewrite' })
  assert.equal(soLuot, 2, 'lượt viết lại cũng phải ghi sổ, nếu không thì không đếm được')
})

test('cùng jobId gọi lại -> trả kết quả cũ, KHÔNG gọi mô hình lần 2', async () => {
  const fn = gtSach()
  const a = await thietBiMoi('Máy A')
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const body = than('jsH'.repeat(4), bp._id, br._id)

  const r1 = await goi('POST', '/v1/brand-scripts/', a.token, body)
  const r2 = await goi('POST', '/v1/brand-scripts/', a.token, body)
  assert.equal(r1.json().id, r2.json().id)
  assert.equal(fn.mock.callCount(), 1)
  assert.equal(await BrandScript.countDocuments(), 1)
})
