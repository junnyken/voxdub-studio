'use strict'

/**
 * Vai `assist` KHÔNG được rơi im lặng sang vai `translate` — MINI-SPEC I1 bước 3.
 *
 * Lỗi thật đã sống trong sản xuất nhiều tháng: thiếu nhà cung cấp cho vai trợ
 * lý thì `gateway.assist()` âm thầm mượn mô hình của vai DỊCH. Lượt gọi vẫn
 * trả lời, người dùng vẫn bị trừ đúng giá tác vụ trợ lý, nhưng phí mô hình
 * phía máy chủ đắt hơn hàng chục lần — và không có triệu chứng nào ngoài một
 * lượt trợ lý trông bình thường. Đo được 22/09/2026 bằng bộ thu bằng chứng:
 * `thiếu assist, có translate` → HTTP 200, 2 Vox, `assistRole = translate`.
 *
 * Bộ test này canh cả ba chiều, vì sửa chuyện trên dễ sửa quá tay:
 *
 *   1. thiếu vai `assist` ⇒ 503 mã RIÊNG, và **không một lượt nào chạm tới
 *      nhà cung cấp của vai dịch** (đếm ở chính máy chủ giả);
 *   2. câu 503 phải NÓI ĐƯỢC VIỆC PHẢI LÀM, và không hẹn "thử lại sau" —
 *      thử lại một lỗi cấu hình là việc chắc chắn hỏng;
 *   3. **thiếu token thiết bị vẫn là 401**, không được biến thành 503. Đây
 *      đúng là kiểu hỏng của một bản vá vội: chặn sớm hơn cả lớp xác thực.
 *
 * Chạy:  node --test tests/tro-ly-khong-roi-vai-dich.test.js
 */
const test = require('node:test')
const { mock } = require('node:test')
const assert = require('node:assert')
const crypto = require('node:crypto')
const http = require('node:http')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')
setTestEnv()

const { build } = require('../src/app')
const deviceService = require('../src/services/device.service')
const gateway = require('../src/services/ai-gateway.service')
const credit = require('../src/services/credit.service')
const config = require('../src/services/config.service')
const AiProvider = require('../src/models/AiProvider')
const BrandProfile = require('../src/models/BrandProfile')
const BrandScript = require('../src/models/BrandScript')
const FlowBlueprint = require('../src/models/FlowBlueprint')
const dauVanTay = require('../src/services/dau-van-tay.service')
const { encrypt } = require('../src/utils/crypto')

let app
let moHinhGia          // máy chủ mô hình giả — ĐẾM số lượt thật sự bị gọi

test.before(async () => {
  await startDb()
  app = await build({ mongo: false, web: false, logger: false })
  await app.ready()
  moHinhGia = await moMoHinhGia()
})
test.after(async () => {
  await app.close()
  await moHinhGia.dong()
  await stopDb()
})
test.beforeEach(async () => {
  await clearDb()
  mock.restoreAll()
  gateway.invalidateProviders()
  moHinhGia.datLai()
})

function moMoHinhGia() {
  let soLuot = 0
  const may = http.createServer((req, res) => {
    req.on('data', () => {})
    req.on('end', () => {
      soLuot += 1
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify({
        choices: [{
          message: {
            content: JSON.stringify({
              results: [{ value: 'Gợi ý mẫu', reason: 'Lý do mẫu đủ dài.' }],
            }),
          },
          finish_reason: 'stop',
        }],
        usage: { prompt_tokens: 10, completion_tokens: 5 },
      }))
    })
  })
  return new Promise((ok) => {
    may.listen(0, '127.0.0.1', () => ok({
      url: `http://127.0.0.1:${may.address().port}/v1`,
      soLuot: () => soLuot,
      datLai: () => { soLuot = 0 },
      dong: () => new Promise((xong) => may.close(xong)),
    }))
  })
}

async function themNoiGoi(role, { baseUrl = '' } = {}) {
  const doc = await AiProvider.create({
    name: `noi-goi-${role}-${crypto.randomBytes(3).toString('hex')}`,
    role,
    type: 'openai_compat',
    baseUrl: baseUrl || moHinhGia.url,
    model: 'mo-hinh-gia',
    apiKeyEnc: encrypt('sk-gia-0123456789'),
    enabled: true,
    priority: 1,
    timeoutMs: 5000,
  })
  gateway.invalidateProviders()
  return doc
}

async function thietBiMoi(soDu = 100) {
  const { device, token } = await deviceService.registerDevice({
    fingerprint: crypto.randomBytes(32).toString('hex'), name: 'may-thu',
  })
  if (soDu > 0) {
    await credit.grant(device.fingerprint, soDu, {
      idempotencyKey: `gieo-${device.fingerprint.slice(0, 12)}`,
      type: 'admin_grant', description: 'gieo cho test',
    })
  }
  return { device, token }
}

function goiTroLy(token, { task = 'tighten_line', input, jobId } = {}) {
  return app.inject({
    method: 'POST',
    url: '/v1/ai/assist',
    headers: token ? { authorization: `Bearer ${token}` } : {},
    payload: {
      jobId: jobId || `job-${crypto.randomBytes(8).toString('hex')}`,
      task,
      input: input || {
        line: `Câu thử ${crypto.randomBytes(4).toString('hex')} dài vừa đủ để gửi đi`,
        needSeconds: 5.4, roomSeconds: 3.6, trimPercent: 33,
      },
    },
  })
}

// ------------------------------------------------ 1. không rơi sang vai dịch ---

test('thiếu vai assist mà có vai translate: 503, KHÔNG mượn mô hình của vai dịch', async () => {
  const { token, device } = await thietBiMoi()
  await themNoiGoi('translate')            // vai dịch SẴN SÀNG, cố ý
  const truoc = await credit.getBalance(device.fingerprint)

  const res = await goiTroLy(token)

  assert.strictEqual(res.statusCode, 503,
    'thiếu vai trợ lý thì phải nói ra, không được mượn vai khác')
  assert.strictEqual(res.json().code, 'CHUA_CO_NOI_GOI_TRO_LY')
  assert.strictEqual(moHinhGia.soLuot(), 0,
    'nhà cung cấp của vai DỊCH vẫn bị gọi — đường rơi im lặng còn sống')
  assert.strictEqual(await credit.getBalance(device.fingerprint), truoc,
    'lượt hỏng không được trừ Vox')
})

test('có vai assist thì chạy bình thường qua đúng vai đó', async () => {
  const { token, device } = await thietBiMoi()
  await themNoiGoi('assist')

  const res = await goiTroLy(token)

  assert.strictEqual(res.statusCode, 200)
  assert.strictEqual(moHinhGia.soLuot(), 1)
  const so = await require('../src/models/UsageLog')
    .findOne({ fingerprint: device.fingerprint, action: 'assist' }).lean()
  assert.strictEqual(so.assistRole, 'assist')
})

// --------------------------------------------- 2. câu 503 phải dùng được ---

test('câu 503 chỉ đúng việc phải làm, và KHÔNG hẹn thử lại', async () => {
  const { token } = await thietBiMoi()
  await themNoiGoi('translate')

  const than = (await goiTroLy(token)).json()

  assert.match(than.message, /assist/,
    'phải gọi đúng tên vai để người quản trị biết thêm dòng nào')
  assert.match(than.message, /Nơi gọi mô hình/,
    'phải chỉ đúng trang cần vào')
  assert.strictEqual(than.retryAfter, undefined,
    'hẹn thử lại cho một lỗi cấu hình là dạy máy khách lặp lại việc chắc hỏng')
})

test('nhà cung cấp assist LỖI TẠM THỜI thì là ca khác, mã khác, có hẹn thử lại', async () => {
  const { token } = await thietBiMoi()
  await themNoiGoi('assist', { baseUrl: 'http://127.0.0.1:1/v1' })

  const res = await goiTroLy(token)
  const than = res.json()

  assert.strictEqual(res.statusCode, 503)
  assert.strictEqual(than.code, 'AI_UNAVAILABLE',
    'hai ca chữa ngược nhau thì phải hai mã — gộp lại là quay về lỗi cũ')
  assert.strictEqual(than.retryAfter, 30)
})

// ------------------------------------- 3. KHÔNG được sửa quá tay: 401 vẫn 401 ---

test('thiếu token thiết bị vẫn là 401, KHÔNG biến thành 503', async () => {
  await themNoiGoi('translate')      // và cũng không có vai assist

  const res = await goiTroLy('')     // không gửi Authorization

  assert.strictEqual(res.statusCode, 401,
    'chốt mới không được chặn sớm hơn cả lớp xác thực')
  assert.notStrictEqual(res.json().code, 'CHUA_CO_NOI_GOI_TRO_LY')
  assert.strictEqual(moHinhGia.soLuot(), 0)
})

test('token rác vẫn là 401 dù đã có vai assist', async () => {
  await themNoiGoi('assist')
  const res = await goiTroLy('day-la-token-rac')
  assert.strictEqual(res.statusCode, 401)
  assert.strictEqual(moHinhGia.soLuot(), 0)
})

// ------------------------------------------ 4. đường miễn phí không bị chặn ---

test('explain_error vẫn chạy khi có vai assist và ví = 0', async () => {
  const { token, device } = await thietBiMoi(0)
  await themNoiGoi('assist')
  // Máy mới được tặng Vox dùng thử, nên phải RÚT CẠN mới đúng ca cần kiểm:
  // người dùng hết tiền đúng lúc gặp lỗi và cần trợ lý giải thích.
  const dangCo = await credit.getBalance(device.fingerprint)
  if (dangCo > 0) {
    await credit.deduct(device.fingerprint, dangCo, {
      type: 'usage', idempotencyKey: `rut-can-${device.fingerprint.slice(0, 12)}`,
      description: 'rút cạn ví cho test',
    })
  }
  assert.strictEqual(await credit.getBalance(device.fingerprint), 0)
  assert.strictEqual(await config.get('credit.cost.assist.explain_error'), 0)

  const res = await goiTroLy(token, {
    task: 'explain_error',
    input: { message: 'ffmpeg exited with code 1', step: 'merge_video' },
  })

  assert.strictEqual(res.statusCode, 200,
    'tác vụ miễn phí phải chạy được đúng lúc người dùng cạn ví')
  assert.strictEqual(res.json().creditCharged, 0)
})

// ------------------------------- 5. ba cửa còn lại cũng nói đúng câu đó ---

test('cửa H2 (flow-blueprints) chuyển nguyên câu, không hẹn thử lại', async (t) => {
  const { token } = await thietBiMoi(1000)
  mock.method(gateway, 'assist', async () => {
    throw new gateway.AiError(gateway.MA_CHUA_CO_NOI_GOI_TRO_LY,
      'Máy chủ chưa có nơi gọi mô hình nào cho vai «trợ lý».', 503)
  })
  t.after(() => mock.restoreAll())

  const res = await app.inject({
    method: 'POST', url: '/v1/flow-blueprints',
    headers: { authorization: `Bearer ${token}` },
    payload: {
      jobId: `job-${crypto.randomBytes(8).toString('hex')}`,
      sourceType: 'url',
      sourceReference: 'https://example.com/v',
      transcript: [{ start_s: 0, end_s: 2, text: 'Một câu thoại mẫu để phân tích.' }],
      ocrEvidence: [],
      languageSourceDetected: 'vi',
      samplingPolicyUsed: 'moi-2-giay',
    },
  })

  assert.strictEqual(res.statusCode, 503)
  assert.strictEqual(res.json().code, 'CHUA_CO_NOI_GOI_TRO_LY')
  assert.strictEqual(res.json().retryAfter, undefined)
})

test('cửa H3 (brand-scripts) chuyển nguyên câu thay vì "thử lại sau"', async (t) => {
  const { token, device } = await thietBiMoi(1000)
  const brand = await BrandProfile.create({
    ownerDeviceId: device._id,
    tenBrand: 'Bếp Nhà Vui',
    moTaSanPham: 'Nồi chiên không dầu 5 lít',
    doiTuongKhach: 'Mẹ bỉm sữa ở thành phố',
    toneGiong: 'Gần gũi như bạn bè',
    usp: 'Làm nóng trong 3 phút',
  })
  const bp = await FlowBlueprint.create({
    ownerDeviceId: device._id,
    sourceType: 'url',
    sourceReference: 'https://example.com/v',
    status: 'ready',
    beats: [
      { startS: 0, endS: 2, beatType: 'hook', narrativeFunctionVi: 'Mở đầu' },
      { startS: 2, endS: 5, beatType: 'cta', narrativeFunctionVi: 'Kêu gọi' },
    ],
    evidenceFingerprint: dauVanTay.taoDauVanTay(['Một câu nguồn mẫu đủ dài']),
  })
  mock.method(gateway, 'assist', async () => {
    throw new gateway.AiError(gateway.MA_CHUA_CO_NOI_GOI_TRO_LY,
      'Máy chủ chưa có nơi gọi mô hình nào cho vai «trợ lý».', 503)
  })
  t.after(() => mock.restoreAll())

  const res = await app.inject({
    method: 'POST', url: '/v1/brand-scripts',
    headers: { authorization: `Bearer ${token}` },
    payload: {
      jobId: `job-${crypto.randomBytes(8).toString('hex')}`,
      brandProfileId: String(brand._id),
      flowBlueprintId: String(bp._id),
    },
  })

  assert.strictEqual(res.statusCode, 503)
  assert.strictEqual(res.json().code, 'CHUA_CO_NOI_GOI_TRO_LY')
  assert.ok(!/thử lại sau/i.test(res.json().message))
})

test('cửa viết lại MỘT đoạn (H3) cũng vậy', async (t) => {
  const { token, device } = await thietBiMoi(1000)
  const brand = await BrandProfile.create({
    ownerDeviceId: device._id,
    tenBrand: 'Bếp Nhà Vui',
    moTaSanPham: 'Nồi chiên không dầu 5 lít',
    doiTuongKhach: 'Mẹ bỉm sữa',
    toneGiong: 'Gần gũi',
    usp: 'Nóng trong 3 phút',
  })
  const bp = await FlowBlueprint.create({
    ownerDeviceId: device._id,
    sourceType: 'url',
    sourceReference: 'https://example.com/v',
    status: 'ready',
    beats: [{ startS: 0, endS: 2, beatType: 'hook', narrativeFunctionVi: 'Mở đầu' }],
    evidenceFingerprint: dauVanTay.taoDauVanTay(['Một câu nguồn mẫu đủ dài']),
  })
  const kb = await BrandScript.create({
    ownerDeviceId: device._id,
    flowBlueprintId: bp._id,
    brandProfileId: brand._id,
    status: 'ready',
    beats: [{ beatType: 'hook', voiceoverTextVi: 'Câu mở đầu hiện tại.' }],
  })
  mock.method(gateway, 'assist', async () => {
    throw new gateway.AiError(gateway.MA_CHUA_CO_NOI_GOI_TRO_LY,
      'Máy chủ chưa có nơi gọi mô hình nào cho vai «trợ lý».', 503)
  })
  t.after(() => mock.restoreAll())

  const res = await app.inject({
    method: 'POST', url: `/v1/brand-scripts/${kb._id}/regenerate-beat`,
    headers: { authorization: `Bearer ${token}` },
    payload: {
      jobId: `job-${crypto.randomBytes(8).toString('hex')}`,
      beatIndex: 0,
    },
  })

  assert.strictEqual(res.statusCode, 503)
  assert.strictEqual(res.json().code, 'CHUA_CO_NOI_GOI_TRO_LY')
})
