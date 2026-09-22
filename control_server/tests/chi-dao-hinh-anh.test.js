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

// --------------------------------------- ngân sách lời nhắc ở quy mô thật ---

test('kịch bản DÀI vẫn đủ đoạn trong lời nhắc, và không vượt trần', () => {
  const assistPrompts = require('../src/prompts/assist')
  const spec = assistPrompts.getTask('scene_director')

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
  const loiNhac = assistPrompts.getTask('scene_director')
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
