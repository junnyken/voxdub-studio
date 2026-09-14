'use strict'

/**
 * Nhóm RS-1…RS-6 — sáu phát hiện rà soát Phase H đụng TIỀN và trạng thái
 * `ready` (xem `docs/BACKLOG_PHASE_H.md`). Tệp này chốt bốn mục phía máy chủ;
 * RS-4/RS-5 nằm ở giao diện, chốt ở `tests/test_rs4_rs5_brand_script_page.py`.
 *
 * Điểm chung của cả nhóm: **một phán quyết cũ được giữ lại sau khi cơ sở của
 * nó đã mất**. `ready` là chữ mở cổng sang H4, nên giữ nó quá hạn không phải
 * lỗi hiển thị — đó là cho đi tiếp bằng một kết luận không còn đúng.
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
const Device = require('../src/models/Device')
const dauVanTay = require('../src/services/dau-van-tay.service')
const kiem = require('../src/services/kiem-kich-ban.service')

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

async function thietBiMoi() {
  const { device, token } = await deviceService.registerDevice({
    fingerprint: crypto.randomBytes(32).toString('hex'), name: 'Máy A',
  })
  await Device.updateOne({ _id: device._id }, { $set: { balance: 1000 } })
  return { device, token }
}

async function hoSoBrand(deviceId, rangBuoc = ['tốt nhất', 'chữa bệnh']) {
  return BrandProfile.create({
    ownerDeviceId: deviceId,
    tenBrand: 'Bếp Nhà Vui',
    moTaSanPham: 'Nồi chiên không dầu 5 lít',
    doiTuongKhach: 'Mẹ bỉm sữa ở thành phố',
    toneGiong: 'Gần gũi như bạn bè',
    usp: 'Làm nóng trong 3 phút',
    rangBuocKhongDuocNoi: rangBuoc,
  })
}

async function blueprintCo(deviceId, { vanTay = true } = {}) {
  return FlowBlueprint.create({
    ownerDeviceId: deviceId,
    sourceType: 'url',
    sourceReference: 'https://example.com/v',
    status: 'ready',
    beats: [
      { startS: 0, endS: 2, beatType: 'hook', narrativeFunctionVi: 'Mở đầu', evidenceStatus: 'ok' },
      { startS: 2, endS: 5, beatType: 'cta', narrativeFunctionVi: 'Kêu gọi', evidenceStatus: 'ok' },
    ],
    evidenceFingerprint: vanTay ? dauVanTay.taoDauVanTay(NGUON) : null,
  })
}

function goi(method, url, token, body) {
  return app.inject({
    method, url, payload: body,
    headers: token ? { authorization: `Bearer ${token}` } : {},
  })
}

function gtSach() {
  return mock.method(gateway, 'assist', async () => ({
    beats: [
      { beatType: 'hook', voiceoverTextVi: 'Buổi sáng của bạn trôi đi vì việc bếp núc lặt vặt phải không', captionSuggestionVi: 'Sáng nào cũng vội', visualBriefVi: 'Cận cảnh gian bếp' },
      { beatType: 'cta', voiceoverTextVi: 'Thử xem, biết đâu buổi sáng nhẹ hơn hẳn', captionSuggestionVi: 'Thử đi', visualBriefVi: 'Sản phẩm trên bàn' },
    ],
    usage: {}, provider: 'fake', model: 'fake', role: 'assist',
  }))
}

const than = (jobId, bpId, brId) => ({
  jobId, flowBlueprintId: String(bpId), brandProfileId: String(brId),
})

async function taoKichBanSach(t = 'rs0') {
  gtSach()
  const a = await thietBiMoi()
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const res = await goi('POST', '/v1/brand-scripts/', a.token, than(t.repeat(4), bp._id, br._id))
  assert.equal(res.json().status, 'ready', 'tiền đề: phải ready thì mới kiểm được việc HẠ cấp')
  return { a, bp, br, id: res.json().id }
}

// ---------------------------------------------------------------- RS-1 ----

test('RS-1: thêm cụm cấm mới vào hồ sơ brand -> kịch bản cũ HẾT ready', async () => {
  const { a, br, id } = await taoKichBanSach('rs1')

  // Người dùng nhận ra "buổi sáng" là cụm họ không muốn nói nữa.
  await BrandProfile.updateOne({ _id: br._id },
    { $set: { rangBuocKhongDuocNoi: ['tốt nhất', 'chữa bệnh', 'buổi sáng'] } })

  const body = (await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json()
  assert.equal(body.status, 'unconfirmed',
    'luật đổi rồi mà vẫn ready là nói dối — cổng H4 mở bằng một lần duyệt đã hết hiệu lực')

  const ds = (await goi('GET', '/v1/brand-scripts/', a.token)).json().data
  assert.equal(ds[0].status, 'unconfirmed', 'danh sách phải hạ cấp y như trang chi tiết')

  // Chỉ hạ lúc ĐỌC — bản ghi giữ nguyên lịch sử nó từng được duyệt.
  assert.equal((await BrandScript.findById(id)).status, 'ready')
})

test('RS-1: sửa HOA/THƯỜNG hay dấu câu của cùng ràng buộc thì KHÔNG hạ oan', async () => {
  const { a, br, id } = await taoKichBanSach('rs1b')
  await BrandProfile.updateOne({ _id: br._id },
    { $set: { rangBuocKhongDuocNoi: ['Tốt Nhất!', 'chữa bệnh'] } })

  const body = (await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json()
  assert.equal(body.status, 'ready',
    'luật CÓ HIỆU LỰC không đổi — hạ cấp ở đây là dạy người dùng bỏ qua trạng thái')
})

test('RS-1: thêm ràng buộc MỘT TỪ (bộ kiểm không dùng) thì KHÔNG hạ oan', async () => {
  const { a, br, id } = await taoKichBanSach('rs1c')
  await BrandProfile.updateOne({ _id: br._id },
    { $set: { rangBuocKhongDuocNoi: ['tốt nhất', 'chữa bệnh', 'nhất'] } })

  assert.equal((await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json().status, 'ready',
    'ràng buộc dưới ngưỡng từ bị bộ kiểm bỏ qua — nó không làm phán quyết cũ sai đi')
})

test('RS-1: bản ghi CŨ chưa có dấu vân tay luật thì để nguyên, không đoán', async () => {
  const { a, br, id } = await taoKichBanSach('rs1d')
  await BrandScript.updateOne({ _id: id }, { $set: { brandRulesFingerprint: '' } })
  await BrandProfile.updateOne({ _id: br._id },
    { $set: { rangBuocKhongDuocNoi: ['tốt nhất', 'buổi sáng'] } })

  assert.equal((await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json().status, 'ready',
    'không biết lần đó kiểm bằng luật gì thì hạ cấp là đoán, không phải kết luận')
})

// ---------------------------------------------------------------- RS-2 ----

test('RS-2: xoá hồ sơ brand -> GET và danh sách đều hết ready', async () => {
  const { a, br, id } = await taoKichBanSach('rs2')
  await BrandProfile.deleteOne({ _id: br._id })

  assert.equal((await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json().status,
    'unconfirmed', 'nguồn mất thì không kiểm lại được — không được giữ ready')
  assert.equal((await goi('GET', '/v1/brand-scripts/', a.token)).json().data[0].status,
    'unconfirmed')
})

test('RS-2: xoá Flow Blueprint -> cũng hết ready', async () => {
  const { a, bp, id } = await taoKichBanSach('rs2b')
  await FlowBlueprint.deleteOne({ _id: bp._id })

  assert.equal((await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json().status,
    'unconfirmed')
})

test('RS-2: nguồn CÒN NGUYÊN thì không được hạ oan', async () => {
  const { a, id } = await taoKichBanSach('rs2c')
  assert.equal((await goi('GET', `/v1/brand-scripts/${id}`, a.token)).json().status, 'ready')
  assert.equal((await goi('GET', '/v1/brand-scripts/', a.token)).json().data[0].status, 'ready')
})

// ---------------------------------------------------------------- RS-3 ----

test('RS-3: dấu vân tay SAI PHIÊN BẢN -> chặn trước, không trừ Vox', async () => {
  const fn = gtSach()
  const a = await thietBiMoi()
  const bp = await blueprintCo(a.device._id)
  await FlowBlueprint.updateOne({ _id: bp._id },
    { $set: { 'evidenceFingerprint.v': dauVanTay.PHIEN_BAN + 99 } })
  const br = await hoSoBrand(a.device._id)
  const truoc = (await Device.findById(a.device._id)).balance

  const res = await goi('POST', '/v1/brand-scripts/', a.token, than('rs3'.repeat(4), bp._id, br._id))
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().lyDo, 'khac_phien_ban')
  assert.equal(fn.mock.callCount(), 0)
  assert.equal((await Device.findById(a.device._id)).balance, truoc)
})

test('RS-3: dấu vân tay ĐẦY TRẦN -> chặn trước, không trừ Vox', async () => {
  const fn = gtSach()
  const a = await thietBiMoi()
  const bp = await blueprintCo(a.device._id)
  await FlowBlueprint.updateOne({ _id: bp._id },
    { $set: { 'evidenceFingerprint.dayTran': true } })
  const br = await hoSoBrand(a.device._id)
  const truoc = (await Device.findById(a.device._id)).balance

  const res = await goi('POST', '/v1/brand-scripts/', a.token, than('rs3b'.repeat(3), bp._id, br._id))
  assert.equal(res.statusCode, 400)
  assert.equal(res.json().lyDo, 'day_tran')
  assert.equal(fn.mock.callCount(), 0)
  assert.equal((await Device.findById(a.device._id)).balance, truoc)
})

test('RS-3: câu chặn phải NÓI RÕ chưa trừ Vox và làm gì tiếp', async () => {
  gtSach()
  const a = await thietBiMoi()
  const bp = await blueprintCo(a.device._id, { vanTay: false })
  const br = await hoSoBrand(a.device._id)
  const msg = (await goi('POST', '/v1/brand-scripts/', a.token, than('rs3c'.repeat(3), bp._id, br._id))).json().message

  assert.match(msg, /chưa trừ Vox/i, 'không nói thì người dùng tưởng vừa mất tiền cho một lỗi')
  assert.match(msg, /phân tích lại/i, 'phải nói làm gì tiếp, không chỉ nói hỏng')
})

test('RS-3: blueprint ĐỦ vân tay vẫn chạy bình thường', async () => {
  const fn = gtSach()
  const a = await thietBiMoi()
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)

  const res = await goi('POST', '/v1/brand-scripts/', a.token, than('rs3d'.repeat(3), bp._id, br._id))
  assert.equal(res.statusCode, 201, 'cổng mới không được chặn nhầm đường chạy đúng')
  assert.equal(fn.mock.callCount(), 1)
})

// ---------------------------------------------------------------- RS-6 ----

test('RS-6: nguồn bị xoá KHÔNG được xoá phán quyết `blocked` còn giá trị', async () => {
  // Kịch bản vi phạm ràng buộc brand ⇒ blocked. Ràng buộc do CHÍNH người dùng
  // nhập, cả hai vế vẫn còn sau khi blueprint bị xoá — phán quyết vẫn đúng.
  mock.method(gateway, 'assist', async () => ({
    beats: [
      { beatType: 'hook', voiceoverTextVi: 'Đây là loại tốt nhất bạn từng thấy', captionSuggestionVi: 'x', visualBriefVi: 'y' },
      { beatType: 'cta', voiceoverTextVi: 'Câu này thì hoàn toàn mới và sạch sẽ', captionSuggestionVi: 'x', visualBriefVi: 'y' },
    ],
    usage: {}, provider: 'f', model: 'f', role: 'assist',
  }))
  const a = await thietBiMoi()
  const bp = await blueprintCo(a.device._id)
  const br = await hoSoBrand(a.device._id)
  const id = (await goi('POST', '/v1/brand-scripts/', a.token, than('rs6'.repeat(4), bp._id, br._id))).json().id
  assert.equal((await BrandScript.findById(id)).status, 'blocked', 'tiền đề')

  await FlowBlueprint.deleteOne({ _id: bp._id })
  const res = await goi('POST', `/v1/brand-scripts/${id}/regenerate-beat`, a.token,
    { jobId: 'rs6b'.repeat(3), beatIndex: 0 })
  assert.equal(res.statusCode, 409)

  const sau = await BrandScript.findById(id)
  assert.equal(sau.status, 'blocked',
    'hạ `blocked` xuống `unconfirmed` là đổi "đã kiểm, vi phạm" thành "chưa kiểm được" — nhẹ đi một bậc và sai về thứ đã biết')
  assert.equal(sau.beats[0].complianceFlag, 'violated', 'lớp tuân thủ không mất chỗ dựa')
  assert.equal(sau.beats[0].originalityFlag, 'unconfirmed', 'lớp nguyên gốc thì có')
})

test('RS-6: kịch bản SẠCH mà nguồn bị xoá thì vẫn hạ về unconfirmed', async () => {
  const { a, bp, id } = await taoKichBanSach('rs6c')
  await FlowBlueprint.deleteOne({ _id: bp._id })

  const res = await goi('POST', `/v1/brand-scripts/${id}/regenerate-beat`, a.token,
    { jobId: 'rs6d'.repeat(3), beatIndex: 0 })
  assert.equal(res.statusCode, 409)
  assert.equal((await BrandScript.findById(id)).status, 'unconfirmed',
    'không có vi phạm tuân thủ nào để giữ lại thì phải hạ — bản vá RS-6 không được giữ ready')
})

// ------------------------------------------------- dấu vân tay ràng buộc ---

test('vanTayRangBuoc: đo đúng ĐẠI LƯỢNG có hiệu lực', async () => {
  const a = kiem.vanTayRangBuoc(['tốt nhất', 'chữa bệnh'])
  assert.equal(a, kiem.vanTayRangBuoc(['chữa bệnh', 'tốt nhất']), 'thứ tự nhập không phải thay đổi luật')
  assert.equal(a, kiem.vanTayRangBuoc(['Tốt Nhất!', 'chữa bệnh']), 'hoa/thường + dấu câu không đổi hiệu lực')
  assert.equal(a, kiem.vanTayRangBuoc(['tốt nhất', 'chữa bệnh', 'nhất']), 'ràng buộc 1 từ bị bộ kiểm bỏ qua')
  assert.notEqual(a, kiem.vanTayRangBuoc(['tốt nhất']), 'bớt một luật CÓ hiệu lực thì phải đổi')
  assert.notEqual(kiem.vanTayRangBuoc([]), '', 'rỗng phải ra giá trị ổn định, KHÁC chuỗi rỗng')
})
