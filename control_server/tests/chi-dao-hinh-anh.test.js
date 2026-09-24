'use strict'

/**
 * Bản chỉ đạo hình ảnh — MINI-SPEC I3.
 *
 * Tệp này canh đúng ba thứ mà I3 sinh ra để bảo vệ, và cả ba đều là chuyện
 * "im lặng" nếu hỏng:
 *
 *   1. **Mô hình bịa mã.** Catalog là vốn từ đóng (I2); mô hình vẫn trả được
 *      mã không có thật. Lọt một mã bịa thì người dùng đọc một chỉ dẫn không
 *      tồn tại, và I5 sau này gặp một mã không map được ở tận khâu dựng
 *      video — xa nhất so với chỗ gây lỗi. Luật: huỷ CẢ lượt, KHÔNG trừ tiền,
 *      không "sửa cho gần đúng".
 *   2. **Một lượt cho cả kịch bản.** Kịch bản tới 40 đoạn; gọi từng đoạn là
 *      nhân giá lên 40 lần cho cùng một việc.
 *   3. **Gợi ý cho người ≠ máy dựng được.** 18/25 mục của catalog là gợi ý.
 *      Trộn hai loại là hứa thứ không làm được — đúng lớp lỗi #5/#6 của dự án.
 *
 * Chạy:  node --test tests/chi-dao-hinh-anh.test.js
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
const credit = require('../src/services/credit.service')
const catalog = require('../src/services/visual-catalog.service')
const chiDao = require('../src/services/visual-direction.service')
const dauVanTay = require('../src/services/dau-van-tay.service')
const BrandProfile = require('../src/models/BrandProfile')
const BrandScript = require('../src/models/BrandScript')
const FlowBlueprint = require('../src/models/FlowBlueprint')

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
  gateway.invalidateProviders()
})

const LOI_DOC = [
  'Sáng nào cũng vội, bữa sáng thành ra qua loa cho xong.',
  'Cắm điện chờ ba phút là có ngay đồ ăn nóng cho cả nhà.',
  'Thử một tuần rồi tính tiếp, không hợp thì thôi.',
]

async function thietBiMoi(soDu = 200) {
  const { device, token } = await deviceService.registerDevice({
    fingerprint: crypto.randomBytes(32).toString('hex'), name: 'may-thu',
  })
  await require('../src/models/Device').updateOne(
    { _id: device._id }, { $set: { balance: soDu } })
  return { device, token }
}

async function kichBanSanSang(deviceId, { soDoan = 3 } = {}) {
  const brand = await BrandProfile.create({
    ownerDeviceId: deviceId,
    tenBrand: 'Bếp Nhà Vui',
    moTaSanPham: 'Nồi chiên không dầu 5 lít',
    doiTuongKhach: 'Mẹ bỉm sữa ở thành phố',
    toneGiong: 'Gần gũi như bạn bè',
    usp: 'Làm nóng trong 3 phút',
    rangBuocKhongDuocNoi: ['tốt nhất'],
  })
  const bp = await FlowBlueprint.create({
    ownerDeviceId: deviceId,
    sourceType: 'url',
    sourceReference: 'https://example.com/v',
    status: 'ready',
    beats: Array.from({ length: soDoan }, (_, i) => ({
      startS: i * 3, endS: i * 3 + 3, beatType: ['hook', 'proof', 'cta'][i % 3],
      narrativeFunctionVi: 'vai trò mẫu',
    })),
    evidenceFingerprint: dauVanTay.taoDauVanTay(['Một câu nguồn mẫu đủ dài']),
  })
  const kb = await BrandScript.create({
    ownerDeviceId: deviceId,
    flowBlueprintId: bp._id,
    brandProfileId: brand._id,
    status: 'ready',
    originalityCheckVersion: dauVanTay.PHIEN_BAN,
    brandRulesFingerprint: require('../src/services/kiem-kich-ban.service')
      .vanTayRangBuoc(brand.rangBuocKhongDuocNoi),
    beats: Array.from({ length: soDoan }, (_, i) => ({
      beatType: ['hook', 'proof', 'cta'][i % 3],
      voiceoverTextVi: LOI_DOC[i % LOI_DOC.length],
      captionSuggestionVi: 'Chữ trên hình',
      visualBriefVi: 'Gian bếp buổi sáng',
      originalityFlag: 'clear',
      complianceFlag: 'clear',
    })),
  })
  return { brand, bp, kb }
}

/** Đầu ra hợp lệ của mô hình cho `soDoan` đoạn. */
function traLoiTot(soDoan) {
  return {
    doan: Array.from({ length: soDoan }, (_, i) => ({
      thuTu: i + 1,
      chon: [
        { nhom: 'shot', ma: 'can_canh' },
        { nhom: 'transition', ma: i === 0 ? 'cat_thang' : 'fade_nhe' },
      ],
      lyDo: 'Cận cảnh cho thấy rõ sản phẩm, cắt thẳng giữ nhịp nhanh.',
    })),
    usage: { promptTokens: 100, completionTokens: 50 },
    provider: 'noi-goi-gia',
    model: 'mo-hinh-gia',
    role: 'assist',
  }
}

function gaModel(traVe) {
  let soLuot = 0
  mock.method(gateway, 'assist', async () => { soLuot += 1; return traVe(soLuot) })
  return () => soLuot
}

function goi(method, url, token, payload) {
  return app.inject({
    method, url, payload,
    headers: token ? { authorization: `Bearer ${token}` } : {},
  })
}

const maViec = () => `job-${crypto.randomBytes(8).toString('hex')}`

// ------------------------------------------------------- đường chạy đúng ---

test('một lượt gọi sinh chỉ đạo cho CẢ kịch bản', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 3 })
  const demLuot = gaModel(() => traLoiTot(3))

  const res = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId: maViec() })

  assert.strictEqual(res.statusCode, 201, res.body)
  const than = res.json()
  assert.strictEqual(demLuot(), 1,
    'kịch bản 3 đoạn mà gọi hơn một lượt là nhân giá theo số đoạn')
  assert.strictEqual(than.doan.length, 3)
  assert.strictEqual(than.catalogVersion, catalog.PHIEN_BAN_HIEN_TAI)
  assert.strictEqual(than.creditCharged, 5, 'giá chốt của I3 là 5 Vox')
  assert.strictEqual(than.laCu, false)
})

test('mỗi mã lưu kèm cờ "gợi ý cho người" tính từ CATALOG', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 1 })
  gaModel(() => ({
    doan: [{
      thuTu: 1,
      chon: [{ nhom: 'shot', ma: 'can_canh' },        // advisory_only
        { nhom: 'transition', ma: 'truot_len' }],     // supported (v2)
      lyDo: 'Cận cảnh rõ sản phẩm.',
    }],
    usage: { promptTokens: 1, completionTokens: 1 },
    provider: 'p', model: 'm', role: 'assist',
  }))

  const than = (await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId: maViec() })).json()

  const theoMa = Object.fromEntries(than.doan[0].chon.map((c) => [c.ma, c]))
  assert.strictEqual(theoMa.can_canh.laGoiY, true)
  assert.strictEqual(theoMa.truot_len.laGoiY, false)
  assert.strictEqual(theoMa.can_canh.nhan, 'Cận cảnh',
    'lưu cả nhãn để bản cũ còn đọc được sau khi catalog đổi chữ')
  assert.strictEqual(than.soGoiY, 1)
  assert.strictEqual(than.soMayDungDuoc, 1)
})

test('gọi lại cùng jobId ⇒ đọc đệm, KHÔNG gọi mô hình lần hai', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 2 })
  const demLuot = gaModel(() => traLoiTot(2))
  const jobId = maViec()

  const lan1 = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId })
  const viGiua = await credit.getBalance(device.fingerprint)
  const lan2 = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId })

  assert.strictEqual(lan1.statusCode, 201)
  assert.strictEqual(demLuot(), 1, 'lượt thứ hai vẫn gọi mô hình')
  assert.strictEqual(await credit.getBalance(device.fingerprint), viGiua,
    'gọi lại cùng jobId mà vẫn trừ tiền')
  assert.deepStrictEqual(lan2.json().doan, lan1.json().doan)
})

// ------------------------------------------------- soi lại với từ điển ---

test('mã KHÔNG có trong từ điển ⇒ huỷ cả lượt, không trừ Vox, không lưu', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 2 })
  gaModel(() => ({
    doan: [
      { thuTu: 1, chon: [{ nhom: 'shot', ma: 'drone_shot' }], lyDo: 'Bay trên cao.' },
      { thuTu: 2, chon: [{ nhom: 'shot', ma: 'can_canh' }], lyDo: 'Cận cảnh.' },
    ],
    usage: { promptTokens: 1, completionTokens: 1 },
    provider: 'p', model: 'm', role: 'assist',
  }))
  const truoc = await credit.getBalance(device.fingerprint)

  const res = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId: maViec() })

  assert.strictEqual(res.statusCode, 502)
  assert.strictEqual(res.json().code, 'CHI_DAO_SAI_TU_DIEN')
  assert.strictEqual(await credit.getBalance(device.fingerprint), truoc,
    'lượt bị huỷ mà vẫn trừ tiền')
  const lai = await BrandScript.findById(kb._id).lean()
  assert.strictEqual(lai.visualDirection, null,
    'không được lưu một PHẦN kết quả — nửa vá còn tệ hơn không có')
})

test('hai mã cùng một nhóm cho một đoạn ⇒ huỷ cả lượt', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 1 })
  gaModel(() => ({
    doan: [{
      thuTu: 1,
      chon: [{ nhom: 'transition', ma: 'fade_nhe' },
        { nhom: 'transition', ma: 'cat_thang' }],
      lyDo: 'Vừa mờ chồng vừa cắt thẳng.',
    }],
    usage: { promptTokens: 1, completionTokens: 1 },
    provider: 'p', model: 'm', role: 'assist',
  }))

  const res = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId: maViec() })

  assert.strictEqual(res.statusCode, 502)
  assert.ok(res.json().chiTiet.join(' ').includes('hai lần'), res.body)
})

test('mã mang tham số thời gian ⇒ huỷ cả lượt', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 1 })
  gaModel(() => ({
    doan: [{
      thuTu: 1,
      chon: [{ nhom: 'transition', ma: 'fade_nhe', giay: 3 }],
      lyDo: 'Mờ chồng ba giây.',
    }],
    usage: { promptTokens: 1, completionTokens: 1 },
    provider: 'p', model: 'm', role: 'assist',
  }))

  const res = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId: maViec() })

  assert.strictEqual(res.statusCode, 502)
  assert.ok(res.json().chiTiet.join(' ').includes('thời gian'), res.body)
})

test('số đoạn trả về khác số đoạn gửi đi ⇒ hỏng khuôn, không lưu', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 3 })
  // Cổng trợ lý thật sẽ trả `null` từ `parseResult` ⇒ BAD_AI_RESPONSE; ở đây
  // giả lập đúng thứ đi tới lớp soi: một bản thiếu đoạn.
  gaModel(() => ({
    doan: [{ thuTu: 1, chon: [], lyDo: 'x' }],
    usage: { promptTokens: 1, completionTokens: 1 },
    provider: 'p', model: 'm', role: 'assist',
  }))

  const res = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId: maViec() })

  assert.strictEqual(res.statusCode, 502)
  assert.ok(res.json().chiTiet.join(' ').includes('không ghép theo vị trí'))
})

// ------------------------------------------------------- cổng trước khi gọi ---

test('kịch bản chưa `ready` ⇒ chặn TRƯỚC khi gọi mô hình', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 2 })
  await BrandScript.updateOne({ _id: kb._id }, { $set: { status: 'unconfirmed' } })
  const demLuot = gaModel(() => traLoiTot(2))
  const truoc = await credit.getBalance(device.fingerprint)

  const res = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId: maViec() })

  assert.strictEqual(res.statusCode, 409)
  assert.strictEqual(res.json().code, 'KICH_BAN_CHUA_SAN_SANG')
  assert.strictEqual(demLuot(), 0, 'đã gọi mô hình cho một kịch bản chưa duyệt')
  assert.strictEqual(await credit.getBalance(device.fingerprint), truoc)
})

test('kịch bản của thiết bị KHÁC ⇒ 404, không lộ sự tồn tại', async () => {
  const a = await thietBiMoi()
  const b = await thietBiMoi()
  const { kb } = await kichBanSanSang(a.device._id, { soDoan: 1 })
  gaModel(() => traLoiTot(1))

  const res = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    b.token, { jobId: maViec() })
  assert.strictEqual(res.statusCode, 404)
})

test('thiếu vai assist ⇒ 503 CHUA_CO_NOI_GOI_TRO_LY (chốt I1 còn nguyên)', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 1 })
  // KHÔNG mock gateway.assist: để nó chạy thật và gặp cảnh không có nhà cung
  // cấp nào cho vai `assist`.
  const res = await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId: maViec() })

  assert.strictEqual(res.statusCode, 503)
  assert.strictEqual(res.json().code, 'CHUA_CO_NOI_GOI_TRO_LY')
  assert.strictEqual(res.json().retryAfter, undefined)
})

// ------------------------------------------------------------ bản cũ ---

test('kịch bản đổi lời ⇒ bản chỉ đạo bị đánh dấu CŨ, không tự xoá', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 2 })
  gaModel(() => traLoiTot(2))
  await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`, token,
    { jobId: maViec() })

  await BrandScript.updateOne({ _id: kb._id },
    { $set: { 'beats.0.voiceoverTextVi': 'Một câu hoàn toàn khác đã được viết lại.' } })

  const doc = await BrandScript.findById(kb._id).lean()
  assert.ok(doc.visualDirection, 'bản chỉ đạo bị xoá mất — không được tự xoá')

  const than = (await goi('GET', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token)).json()
  assert.strictEqual(than.laCu, true)
  assert.strictEqual(than.kichBanDaDoi, true)
  assert.strictEqual(than.catalogDaDoi, false)
  assert.strictEqual(than.doan.length, 2, 'nội dung cũ vẫn đọc được')
})

test('catalog lên đời ⇒ bản cũ báo catalogDaDoi, vẫn đọc được', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 1 })
  gaModel(() => traLoiTot(1))
  await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`, token,
    { jobId: maViec() })

  await BrandScript.updateOne({ _id: kb._id },
    { $set: { 'visualDirection.catalogVersion': 1 } })

  const than = (await goi('GET', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token)).json()
  assert.strictEqual(than.catalogDaDoi, true)
  assert.strictEqual(than.laCu, true)
  assert.strictEqual(than.catalogVersionHienTai, catalog.PHIEN_BAN_HIEN_TAI)
})

test('chưa tạo thì GET trả 404 có mã riêng, không phải bản rỗng', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 1 })
  const res = await goi('GET', `/v1/brand-scripts/${kb._id}/visual-direction`, token)
  assert.strictEqual(res.statusCode, 404)
  assert.strictEqual(res.json().code, 'CHUA_CO_CHI_DAO')
})

// ------------------------------------------- lớp soi chạy được một mình ---

test('khoá đệm phân biệt kịch bản khác nhau và catalog khác phiên bản', () => {
  const assistPrompts = require('../src/prompts/assist')
  const beats = [{ beatType: 'hook', voiceoverTextVi: 'Câu một.', visualBriefVi: 'Bếp' }]
  const brand = { toneGiong: 'gần gũi', rangBuocKhongDuocNoi: [] }

  const a = chiDao.dungInput({ beats }, brand)
  const b = chiDao.dungInput({
    beats: [{ beatType: 'hook', voiceoverTextVi: 'Câu HAI.', visualBriefVi: 'Bếp' }],
  }, brand)
  const c = { ...a, catalogVersion: a.catalogVersion + 1 }

  const khoa = (x) => assistPrompts.cacheKey('scene_director', x, [])
  assert.notStrictEqual(khoa(a), khoa(b), 'hai kịch bản khác nhau mà cùng khoá')
  assert.notStrictEqual(khoa(a), khoa(c), 'catalog đổi đời mà khoá không đổi')
  assert.strictEqual(khoa(a), khoa(chiDao.dungInput({ beats }, brand)))
})

test('bản chỉ đạo KHÔNG mang câu chữ nào của kịch bản hay video nguồn', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 3 })
  gaModel(() => traLoiTot(3))

  const than = (await goi('POST', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, { jobId: maViec() })).json()

  const tho = JSON.stringify(than)
  for (const cau of LOI_DOC) {
    assert.ok(!tho.includes(cau),
      'bản chỉ đạo chép lại lời đọc — nó chỉ được mang MÃ và lý do')
  }
  assert.ok(!tho.includes('example.com'), 'lộ nguồn video tham khảo')
})

// ------------------------- câu chữ khi mô hình viết thiếu đoạn (H3) ---

test('mô hình viết THIẾU ĐOẠN: nói đúng thứ đo được, không hẹn "thử lại sau"', async (t) => {
  // Đo thật 22/09/2026: cùng một đầu vào, `sonar` trả đủ số đoạn 2/3 lượt ở
  // 20 đoạn và 0/4 lượt ở 40 đoạn (trả 37, 33, 25, 25). Câu cũ — "Chưa viết
  // được kịch bản lúc này. Thử lại sau." — sai với ca này theo hai đường:
  // nó giấu chuyện người dùng KHÔNG bị trừ Vox, và nó hẹn một việc mà ở kịch
  // bản dài đã hỏng 4/4 lượt.
  const { device, token } = await thietBiMoi()
  const brand = await BrandProfile.create({
    ownerDeviceId: device._id, tenBrand: 'Bếp Nhà Vui',
    moTaSanPham: 'Nồi chiên không dầu 5 lít', doiTuongKhach: 'Mẹ bỉm sữa',
    toneGiong: 'Gần gũi', usp: 'Ba phút', rangBuocKhongDuocNoi: ['tốt nhất'],
  })
  const bp = await FlowBlueprint.create({
    ownerDeviceId: device._id, sourceType: 'url',
    sourceReference: 'https://example.com/v', status: 'ready',
    beats: [{ startS: 0, endS: 2, beatType: 'hook', narrativeFunctionVi: 'Mở đầu' }],
    evidenceFingerprint: dauVanTay.taoDauVanTay(['Một câu nguồn mẫu đủ dài']),
  })
  mock.method(gateway, 'assist', async () => {
    // Đúng thứ cổng trợ lý ném khi `parseBrandScriptResult` trả null vì
    // mô hình viết thiếu đoạn.
    throw new gateway.AiError('BAD_AI_RESPONSE', 'Kết quả trả về không dùng được', 502)
  })
  t.after(() => mock.restoreAll())
  const truoc = await credit.getBalance(device.fingerprint)

  const res = await goi('POST', '/v1/brand-scripts/', token, {
    jobId: `job-${crypto.randomBytes(8).toString('hex')}`,
    brandProfileId: String(brand._id), flowBlueprintId: String(bp._id),
  })

  assert.strictEqual(res.statusCode, 502)
  const than = res.json()
  assert.strictEqual(than.code, 'KICH_BAN_THIEU_DOAN')
  assert.match(than.message, /KHÔNG bị trừ Vox/,
    'người dùng phải biết mình không mất tiền — không thì họ tưởng vừa trả tiền cho một lỗi')
  assert.match(than.message, /nhiều đoạn/,
    'phải nói ra chiều hướng đã đo được: càng dài càng hay hỏng')
  assert.ok(!/thử lại sau/i.test(than.message),
    'không được hẹn "thử lại sau" cho ca đã hỏng 4/4 lượt ở kịch bản dài')
  assert.strictEqual(await credit.getBalance(device.fingerprint), truoc,
    'lượt hỏng mà vẫn trừ tiền')
})

// --------------------------------------- ngân sách lời nhắc ở quy mô thật ---

test('kịch bản DÀI vẫn đủ đoạn trong lời nhắc, và không vượt trần', () => {
  const assistPrompts = require('../src/prompts/assist')
  const spec = require('../src/prompts/assist').getTask('scene_director')

  // Trường hợp xấu nhất mà schema cho phép: 40 đoạn, mỗi đoạn kịch trần
  // `maxlength` của `models/BrandScript.js` (lời 1500, mô tả hình 600).
  const beats = Array.from({ length: 40 }, (_, i) => ({
    beatType: 'proof',
    voiceoverTextVi: `${'x'.repeat(1500)}${i}`,
    visualBriefVi: `${'y'.repeat(600)}${i}`,
  }))
  const loiNhac = spec.buildUser(chiDao.dungInput({ beats }, { toneGiong: 'x' }))
  const dongDoan = loiNhac.split('\n').filter((d) => /^\d+\. \[/.test(d))

  // HAI tính chất, và thứ tự ưu tiên giữa chúng là chuyện đã có tiền lệ:
  // H3 từng cắt mù cả chuỗi ở cuối và MẤT 13 đoạn, khiến `parseResult` đòi
  // đủ số đoạn rồi trả null — hỏng cả lượt sau khi đã tốn tiền gọi mô hình.
  assert.strictEqual(dongDoan.length, 40,
    'lời nhắc mất đoạn — mô hình sẽ trả thiếu và cả lượt hỏng')
  assert.ok(loiNhac.length <= assistPrompts.TRAN_LOI_NHAC,
    `lời nhắc ${loiNhac.length} ký tự, vượt trần ${assistPrompts.TRAN_LOI_NHAC}`)

  // Và nó giữ đủ đoạn bằng cách HẠ MỨC mô tả hình, đúng như thiết kế —
  // không phải nhờ may mắn.
  assert.ok(!loiNhac.includes('hình đã tả'),
    'ở 40 đoạn kịch trần thì phần mô tả hình phải được hạ để nhường chỗ')
})

test('ngân sách CẠN thì hạ mức mô tả, KHÔNG bao giờ bỏ bớt đoạn', () => {
  const assistPrompts = require('../src/prompts/assist')
  const beats = Array.from({ length: 40 }, (_, i) => ({
    beatType: 'proof',
    loiDoc: `${'x'.repeat(1500)}${i}`,
    visualBrief: `${'y'.repeat(600)}${i}`,
  }))

  // Ba mức ngân sách, kể cả mức chật hơn cả bản hẹp nhất. Hôm nay lời nhắc
  // thật còn dư ~1.000 ký tự nên phép cắt mù không lộ ra — gọi thẳng hàm
  // dựng với ngân sách nhỏ là dựng lại đúng ngày khoảng dư biến mất.
  for (const nganSach of [4000, 2000, 500]) {
    const khoi = assistPrompts.dungDongDoanChiDao(beats, nganSach)
    assert.strictEqual(khoi.split('\n').length, 40,
      `ngân sách ${nganSach}: mất đoạn — mô hình sẽ trả thiếu và hỏng cả lượt`)
  }

  // Và nó hạ mức THẬT chứ không chỉ may mắn vừa: mức rộng nhất phải dài hơn
  // hẳn mức hẹp nhất.
  const rong = assistPrompts.dungDongDoanChiDao(beats, 1e9)
  const hep = assistPrompts.dungDongDoanChiDao(beats, 500)
  assert.ok(rong.length > hep.length * 2,
    'không thấy cơ chế hạ mức hoạt động')
  assert.ok(rong.includes('hình đã tả') && !hep.includes('hình đã tả'))
})

test('kịch bản ngắn thì GIỮ phần mô tả hình — không hạ mức oan', () => {
  const assistPrompts = require('../src/prompts/assist')
  const beats = Array.from({ length: 5 }, (_, i) => ({
    beatType: 'hook', voiceoverTextVi: `Câu ${i} vừa phải`,
    visualBriefVi: 'Gian bếp buổi sáng có nắng xiên qua cửa sổ',
  }))
  const loiNhac = require('../src/prompts/assist').getTask('scene_director')
    .buildUser(chiDao.dungInput({ beats }, { toneGiong: 'x' }))
  assert.ok(loiNhac.includes('hình đã tả'))
})

test('dungInput KHÔNG gửi caption — caption là việc của H3', () => {
  const vao = chiDao.dungInput({
    beats: [{
      beatType: 'hook', voiceoverTextVi: 'Lời đọc',
      captionSuggestionVi: 'CHU-TREN-HINH-DAC-BIET', visualBriefVi: 'Bếp',
    }],
  }, { toneGiong: 'x' })
  assert.ok(!JSON.stringify(vao).includes('CHU-TREN-HINH-DAC-BIET'))
})

// =========================================================================
// MINI-SPEC I4 — sửa tay bản chỉ đạo
// =========================================================================
//
// Cửa này I2 cố ý chưa mở ("mở cửa ghi bây giờ là mời dữ liệu vào trước khi
// có ai đọc nó"). I5 làm bản chỉ đạo điều khiển đầu ra THẬT, nên điều kiện
// đó hết hiệu lực — và chính I5 mở ra lỗ mà I4 vá: mô hình chọn sai một đoạn
// thì người dùng không có đường sửa nào ngoài trả tiền sinh lại cả bản.
//
// Ba thứ phải canh, cả ba đều im lặng nếu hỏng:
//   1. cửa ghi KHÔNG được nhẹ tay hơn đường tự động — người gõ nhầm mã cũng
//      sai y như mô hình bịa mã, và hậu quả rơi xuống cùng một chỗ;
//   2. sửa tay KHÔNG được đổi `scriptHash` — đổi là bản chỉ đạo tự khai mình
//      đã cũ và I5 từ chối dựng;
//   3. KHÔNG một đồng Vox nào bị trừ: không có lượt gọi mô hình nào.

/** Đặt sẵn một bản chỉ đạo hợp lệ vào kịch bản, không qua mô hình. */
async function datChiDao(kb, soDoan) {
  const soi = chiDao.kiemBanChiDao(traLoiTot(soDoan), {
    soDoan, scriptHash: chiDao.bamKichBan(kb.beats),
  })
  assert.ok(soi.ok, `dựng bản mẫu hỏng: ${(soi.loi || []).join('; ')}`)
  await BrandScript.updateOne({ _id: kb._id }, { $set: { visualDirection: soi.ban } })
  return soi.ban
}

function suaMot(soDoan, chiSo, nhom, ma) {
  return {
    doan: Array.from({ length: soDoan }, (_, i) => ({
      thuTu: i + 1,
      chon: [
        { nhom: 'shot', ma: 'can_canh' },
        { nhom: 'transition',
          ma: i === chiSo && nhom === 'transition' ? ma
            : (i === 0 ? 'cat_thang' : 'fade_nhe') },
      ],
    })),
  }
}

test('I4: sửa tay lưu được, và đánh dấu ĐÚNG chỗ người đã can thiệp', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 3 })
  await datChiDao(kb, 3)

  const res = await goi('PUT', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, suaMot(3, 1, 'transition', 'mo_vong'))

  assert.equal(res.statusCode, 200)
  const than = res.json()
  const doan2 = than.doan[1].chon.find((c) => c.nhom === 'transition')
  assert.equal(doan2.ma, 'mo_vong')
  assert.equal(doan2.suaTay, true, 'mã đã đổi mà không đánh dấu sửa tay')
  // Đoạn không đụng tới thì KHÔNG được mang cờ — cờ bật hết thì mất nghĩa.
  const doan1 = than.doan[0].chon.find((c) => c.nhom === 'transition')
  assert.equal(doan1.suaTay, false)
  assert.equal(than.coSuaTay, true)
})

test('I4: sửa tay KHÔNG đổi scriptHash — nếu không, bản tự khai mình đã cũ',
  async () => {
    const { device, token } = await thietBiMoi()
    const { kb } = await kichBanSanSang(device._id, { soDoan: 3 })
    const truoc = await datChiDao(kb, 3)

    const res = await goi('PUT', `/v1/brand-scripts/${kb._id}/visual-direction`,
      token, suaMot(3, 0, 'transition', 'crossfade_ngan'))
    // Chốt lượt ghi ĐÃ chạy. Thiếu dòng này thì một lượt 400 cũng làm test
    // xanh — hash không đổi vì chẳng có gì được ghi cả.
    assert.equal(res.statusCode, 200, res.body)

    const sau = (await BrandScript.findById(kb._id).lean()).visualDirection
    assert.equal(sau.scriptHash, truoc.scriptHash)
    assert.equal(sau.catalogVersion, truoc.catalogVersion)
    const xem = (await goi('GET', `/v1/brand-scripts/${kb._id}/visual-direction`,
      token)).json()
    assert.equal(xem.laCu, false, 'sửa tay xong bản chỉ đạo hoá cũ')
  })

test('I4: KHÔNG gọi mô hình và KHÔNG trừ Vox', async () => {
  const { device, token } = await thietBiMoi(200)
  const { kb } = await kichBanSanSang(device._id, { soDoan: 3 })
  await datChiDao(kb, 3)
  const goiMo = mock.method(gateway, 'assist', async () => {
    throw new Error('sửa tay mà vẫn gọi mô hình')
  })

  const res = await goi('PUT', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, suaMot(3, 2, 'transition', 'truot_len'))

  assert.equal(res.statusCode, 200)
  assert.equal(goiMo.mock.callCount(), 0)
  const sau = await require('../src/models/Device').findById(device._id).lean()
  assert.equal(sau.balance, 200, 'sửa tay mà vẫn trừ Vox')
})

test('I4: mã lạ bị TỪ CHỐI và bản cũ KHÔNG suy suyển', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 3 })
  const truoc = await datChiDao(kb, 3)

  const res = await goi('PUT', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, suaMot(3, 1, 'transition', 'rack_focus'))

  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, chiDao.MA_LOI_SUA_TAY)
  const sau = (await BrandScript.findById(kb._id).lean()).visualDirection
  assert.deepEqual(
    sau.doan.map((d) => d.chon.map((c) => c.ma)),
    truoc.doan.map((d) => d.chon.map((c) => c.ma)),
    'lượt sửa hỏng đã ghi đè lên bản cũ')
})

test('I4: số đoạn lệch thì TỪ CHỐI — không ghép theo vị trí được', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 3 })
  await datChiDao(kb, 3)

  const res = await goi('PUT', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, suaMot(2, 0, 'transition', 'crossfade_ngan'))

  assert.equal(res.statusCode, 400)
  assert.match(res.json().message, /3 đoạn.*2/)
})

test('I4: hai mã cùng một nhóm trong một đoạn thì TỪ CHỐI', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 2 })
  await datChiDao(kb, 2)

  const res = await goi('PUT', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, {
      doan: [
        { thuTu: 1, chon: [
          { nhom: 'transition', ma: 'crossfade_ngan' },
          { nhom: 'transition', ma: 'mo_vong' }] },
        { thuTu: 2, chon: [{ nhom: 'transition', ma: 'fade_nhe' }] },
      ],
    })

  assert.equal(res.statusCode, 400)
  assert.match(res.json().message, /hai lần|nhiều nhất một mã/)
})

test('I4: client KHÔNG tự phong được khả năng — laGoiY tính từ catalog',
  async () => {
    const { device, token } = await thietBiMoi()
    const { kb } = await kichBanSanSang(device._id, { soDoan: 2 })
    await datChiDao(kb, 2)

    // `can_canh` là GỢI Ý cho người, máy không dựng được. Client gửi kèm
    // `laGoiY: false` + `dung` để cố khai nó là thứ máy dựng được.
    //
    // Soi KẾT QUẢ chứ không soi mã trạng thái: Fastify GỠ BỎ trường lạ theo
    // `additionalProperties: false` thay vì từ chối, nên lượt này trả 200 —
    // và như vậy là đủ an toàn, miễn là thứ LƯU LẠI do catalog tính. Chốt ở
    // tính chất thì bản sau đổi sang từ chối hẳn cũng không làm test đỏ oan.
    const res = await goi('PUT', `/v1/brand-scripts/${kb._id}/visual-direction`,
      token, {
        doan: [
          { thuTu: 1,
            chon: [{
              nhom: 'shot', ma: 'can_canh', laGoiY: false,
              dung: { implementation: 'product_video.ghep_anh_nguoi_dung',
                      parameters: { kieu_chuyen: 'tan' } },
            }] },
          { thuTu: 2, chon: [{ nhom: 'transition', ma: 'fade_nhe' }] },
        ],
      })

    assert.ok(res.statusCode === 200 || res.statusCode === 400,
      `mã lạ: ${res.statusCode}`)
    if (res.statusCode === 400) return          // từ chối hẳn cũng đạt

    const than = res.json()
    const muc = than.doan[0].chon.find((c) => c.nhom === 'shot')
    assert.equal(muc.laGoiY, true,
      'client tự phong được "máy dựng được" cho một mã chỉ là gợi ý')
    assert.equal(muc.dung, undefined,
      'client tự gắn được cách dựng cho một mã khâu dựng không có')
  })

test('I4: chưa có bản chỉ đạo thì KHÔNG sửa tay thay cho lượt sinh', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 2 })

  const res = await goi('PUT', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token, suaMot(2, 0, 'transition', 'crossfade_ngan'))

  assert.equal(res.statusCode, 404)
  assert.equal(res.json().code, 'CHUA_CO_CHI_DAO')
})

test('I4: kịch bản của thiết bị KHÁC thì không sửa được', async () => {
  const { device } = await thietBiMoi()
  const { token: tokenNguoiLa } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 2 })
  await datChiDao(kb, 2)

  const res = await goi('PUT', `/v1/brand-scripts/${kb._id}/visual-direction`,
    tokenNguoiLa, suaMot(2, 0, 'transition', 'crossfade_ngan'))

  assert.equal(res.statusCode, 404)
})

// =========================================================================
// MINI-SPEC I6 — nếp chỉ đạo của thương hiệu
// =========================================================================
//
// Nếp là THÓI QUEN, không phải lệnh. Ba chỗ nó chạm vào, và cả ba phải
// không được lấn quyền người dùng:
//   1. lời nhắc của `scene_director` — gợi ý, mô hình vẫn chọn khác được;
//   2. chỗ rơi của đoạn bỏ trống — thay «Mờ chồng» cứng, và phải NÓI RA;
//   3. KHÔNG bao giờ đè lên đoạn đã có chỉ đạo.

test('I6: preset hợp lệ lưu được, catalogVersion do MÁY CHỦ đặt', async () => {
  const { device, token } = await thietBiMoi()
  const { brand } = await kichBanSanSang(device._id, { soDoan: 2 })

  const res = await goi('PUT', `/v1/brand-profiles/${brand._id}`, token, {
    tenBrand: brand.tenBrand,
    rangBuocKhongDuocNoi: brand.rangBuocKhongDuocNoi,
    // Client cố đặt catalogVersion = 999 để preset tự khai mình còn mới.
    visualPreset: { chon: [{ nhom: 'transition', ma: 'truot_len' }] },
  })

  assert.equal(res.statusCode, 200)
  const luu = await BrandProfile.findById(brand._id).lean()
  assert.equal(luu.visualPreset.chon[0].ma, 'truot_len')
  assert.equal(luu.visualPreset.catalogVersion,
    catalog.docCatalog().catalog_version)
})

test('I6: preset mang mã lạ bị TỪ CHỐI và hồ sơ cũ KHÔNG suy suyển', async () => {
  const { device, token } = await thietBiMoi()
  const { brand } = await kichBanSanSang(device._id, { soDoan: 2 })

  const res = await goi('PUT', `/v1/brand-profiles/${brand._id}`, token, {
    tenBrand: 'Tên mới hoàn toàn',
    rangBuocKhongDuocNoi: [],
    visualPreset: { chon: [{ nhom: 'transition', ma: 'whip_pan' }] },
  })

  assert.equal(res.statusCode, 400)
  assert.equal(res.json().code, 'PRESET_KHONG_HOP_LE')
  const luu = await BrandProfile.findById(brand._id).lean()
  assert.equal(luu.tenBrand, brand.tenBrand,
    'preset sai đã kéo theo cả tên brand bị ghi đè')
})

test('I6: bản chỉ đạo trả kèm nepMacDinh đã QUY RA tham số dựng', async () => {
  const { device, token } = await thietBiMoi()
  const { brand, kb } = await kichBanSanSang(device._id, { soDoan: 3 })
  await datChiDao(kb, 3)
  await BrandProfile.updateOne({ _id: brand._id }, {
    $set: { visualPreset: {
      catalogVersion: catalog.docCatalog().catalog_version,
      chon: [{ nhom: 'transition', ma: 'crossfade_ngan' }] } },
  })

  const than = (await goi('GET', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token)).json()

  // `crossfade_ngan` map sang `tan` — app KHÔNG được giữ bảng này, nên máy
  // chủ phải nói thẳng tham số.
  assert.equal(than.nepMacDinh, 'tan')
})

test('I6: preset dựng bằng catalog CŨ thì bỏ qua, không rơi vào mã đã gỡ',
  async () => {
    const { device, token } = await thietBiMoi()
    const { brand, kb } = await kichBanSanSang(device._id, { soDoan: 2 })
    await datChiDao(kb, 2)
    await BrandProfile.updateOne({ _id: brand._id }, {
      $set: { visualPreset: {
        catalogVersion: catalog.docCatalog().catalog_version - 1,
        chon: [{ nhom: 'transition', ma: 'crossfade_ngan' }] } },
    })

    const than = (await goi('GET', `/v1/brand-scripts/${kb._id}/visual-direction`,
      token)).json()

    assert.equal(than.nepMacDinh, '',
      'preset của catalog cũ vẫn được dùng làm chỗ rơi')
  })

test('I6: brand chưa đặt nếp thì nepMacDinh rỗng', async () => {
  const { device, token } = await thietBiMoi()
  const { kb } = await kichBanSanSang(device._id, { soDoan: 2 })
  await datChiDao(kb, 2)
  const than = (await goi('GET', `/v1/brand-scripts/${kb._id}/visual-direction`,
    token)).json()
  assert.equal(than.nepMacDinh, '')
})

test('I6: lời nhắc nói nếp là THÓI QUEN, không phải bắt buộc', async () => {
  const assistPrompts = require('../src/prompts/assist')
  const vao = chiDao.dungInput(
    { beats: [{ beatType: 'hook', voiceoverTextVi: 'Xin chào', visualBriefVi: 'Cận' }] },
    { toneGiong: 'Gần gũi',
      rangBuocKhongDuocNoi: [],
      visualPreset: { catalogVersion: catalog.docCatalog().catalog_version,
        chon: [{ nhom: 'transition', ma: 'fade_nhe' }] } })

  assert.deepEqual(vao.brand.nepChiDao, [{ nhom: 'transition', ma: 'fade_nhe' }])
  const loiNhac = require('../src/prompts/assist').getTask('scene_director').buildUser(vao)
  assert.match(loiNhac, /thường dùng/)
  assert.match(loiNhac, /THÓI QUEN, không phải bắt buộc/,
    'ép cứng preset thì nó vô hiệu hoá luôn việc chỉ đạo')
})

test('I6: preset của catalog cũ KHÔNG đi vào lời nhắc', async () => {
  const vao = chiDao.dungInput(
    { beats: [{ beatType: 'hook', voiceoverTextVi: 'Xin chào' }] },
    { visualPreset: { catalogVersion: 1,
      chon: [{ nhom: 'transition', ma: 'fade_nhe' }] } })
  assert.deepEqual(vao.brand.nepChiDao, [],
    'nhắc mô hình dùng một mã có thể đã bị gỡ = tự làm hỏng lượt vừa trả tiền')
})

// =========================================================================
// MINI-SPEC I7 §A — bố cục theo NHỊP
// =========================================================================
//
// Trước I7, `dungInput` gửi cho `scene_director` đúng ba trường mỗi đoạn:
// beatType, loiDoc, visualBrief. KHÔNG thời lượng, KHÔNG nhịp. Nên mô hình
// chọn chuyển cảnh mà không phân biệt được đoạn 2 giây với đoạn 8 giây —
// một cú chuyển mềm 0,3s ăn 15% đoạn ngắn nhưng không đáng kể ở đoạn dài.
//
// Thời lượng chỉ có ở Blueprint gốc; `BrandScript.beats` không lưu nó.

function bpBeats(khoang) {
  return khoang.map(([a, z], i) => ({
    startS: a, endS: z, beatType: ['hook', 'proof', 'cta'][i % 3],
    narrativeFunctionVi: 'vai trò mẫu',
    pacingNoteVi: 'Cắt nhanh, mỗi câu một ý',
  }))
}

const kbGia = (soDoan) => ({
  beats: Array.from({ length: soDoan }, () => ({
    beatType: 'hook', voiceoverTextVi: 'Câu mẫu.', visualBriefVi: 'Cận cảnh',
  })),
})

test('I7: thời lượng lần đúng từ Blueprint theo VỊ TRÍ', async () => {
  const giay = chiDao.giayTungDoan(kbGia(3), { beats: bpBeats([[0, 2], [2, 5.5], [5.5, 12]]) })
  assert.deepEqual(giay, [2, 3.5, 6.5])
})

test('I7: KHÔNG có Blueprint thì bỏ trống, không đoán', async () => {
  assert.deepEqual(chiDao.giayTungDoan(kbGia(3), null), [])
  assert.deepEqual(chiDao.giayTungDoan(kbGia(3), { beats: [] }), [])
})

test('I7: Blueprint LỆCH số đoạn thì bỏ trống CẢ LƯỢT, không ghép phần nào',
  async () => {
    // Blueprint sinh lại sau khi kịch bản đã tạo ⇒ số đoạn khác. Ghép theo
    // vị trí lúc này là gán thời lượng của đoạn KHÁC — mô hình sẽ chọn bố
    // cục tự tin trên một con số sai, và không ai nhìn ra.
    const giay = chiDao.giayTungDoan(kbGia(3), { beats: bpBeats([[0, 2], [2, 5]]) })
    assert.deepEqual(giay, [], 'ghép nhầm còn tệ hơn không ghép')
  })

test('I7: mốc hỏng thì đoạn đó là null, các đoạn khác vẫn có', async () => {
  const giay = chiDao.giayTungDoan(kbGia(3), {
    beats: [{ startS: 0, endS: 2 }, { startS: 5, endS: 5 }, { startS: 5, endS: 9 }],
  })
  assert.deepEqual(giay, [2, null, 4], 'endS <= startS phải thành null')
})

test('I7: dungInput đưa được giây + nhịp xuống mô hình', async () => {
  const vao = chiDao.dungInput(
    kbGia(2), { toneGiong: 'Gần gũi', rangBuocKhongDuocNoi: [] },
    { beats: bpBeats([[0, 2], [2, 9]]) })
  assert.equal(vao.beats[0].giay, 2)
  assert.equal(vao.beats[1].giay, 7)
  assert.match(vao.beats[0].nhip, /Cắt nhanh/)
})

test('I7: không có Blueprint thì giay là null, nhip rỗng — KHÔNG phải 0',
  async () => {
    const vao = chiDao.dungInput(kbGia(2), {}, null)
    assert.equal(vao.beats[0].giay, null,
      'giay = 0 sẽ được đọc thành "đoạn dài 0 giây", một con số SAI')
    assert.equal(vao.beats[0].nhip, '')
  })

test('I7: lời nhắc IN thời lượng, và bỏ HẲN dòng khi không có', async () => {
  const spec = require('../src/prompts/assist').getTask('scene_director')
  const u = spec.buildUser({
    catalogVersion: catalog.docCatalog().catalog_version,
    brand: { toneGiong: '', rangBuocKhongDuocNoi: [], nepChiDao: [] },
    beats: [
      { beatType: 'hook', giay: 2, nhip: '', loiDoc: 'A.', visualBrief: 'B' },
      { beatType: 'cta', giay: null, nhip: '', loiDoc: 'C.', visualBrief: 'D' },
    ],
  })
  const dong = u.split('\n').filter((l) => /^\d+\. \[/.test(l))
  assert.match(dong[0], /2\.0 giây/)
  assert.doesNotMatch(dong[1], /giây/,
    'đoạn không có thời lượng mà vẫn in "0.0 giây" là bịa một con số')
})

test('I7: thời lượng SỐNG SÓT qua sức ép ngân sách ở 40 đoạn', async () => {
  // Thời lượng cố ý nằm NGOÀI bậc ngân sách. Nếu nó chịu cắt như mô tả hình
  // thì kịch bản dài quay về đúng tình trạng chọn bố cục mù.
  const spec = require('../src/prompts/assist').getTask('scene_director')
  const beats = Array.from({ length: 40 }, (_, i) => ({
    beatType: 'hook', giay: 3.5,
    nhip: 'Cắt nhanh, mỗi câu một ý, chữ hiện cùng trọng âm của câu nói',
    loiDoc: 'Sáng nào cũng vội, bữa sáng thành ra qua loa cho xong việc.',
    visualBrief: 'Cận cảnh nồi trên mặt bàn bếp, tay mở nắp, ánh sáng cửa sổ',
  }))
  const u = spec.buildUser({
    catalogVersion: catalog.docCatalog().catalog_version,
    brand: { toneGiong: 'Gần gũi', rangBuocKhongDuocNoi: [], nepChiDao: [] },
    beats,
  })
  const dong = u.split('\n').filter((l) => /^\d+\. \[/.test(l))
  assert.equal(dong.length, 40, 'mất đoạn')
  assert.equal(dong.filter((l) => /3\.5 giây/.test(l)).length, 40,
    'thời lượng bị cắt mất khi chạm trần ngân sách')
})

test('I7: lời nhắc DẠY mô hình dùng con số đó, không chỉ đưa số', async () => {
  const sys = require('../src/prompts/assist').getTask('scene_director').system
  assert.match(sys, /NGẮN/, 'không nói gì về đoạn ngắn')
  assert.match(sys, /DÀI/, 'không nói gì về đoạn dài')
  assert.match(sys, /cat_thang/, 'không chỉ ra việc phải làm với đoạn ngắn')
  assert.match(sys, /KHÔNG kèm thời lượng/,
    'không dặn gì cho đoạn thiếu thời lượng — mô hình sẽ tự suy từ độ dài câu')
})
