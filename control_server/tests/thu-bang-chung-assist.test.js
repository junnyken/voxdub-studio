'use strict'

/**
 * Bộ thu bằng chứng cổng trợ lý phải ĐO THẬT — MINI-SPEC I1 §B2/§B3.
 *
 * Vì sao tệp này tồn tại: một bộ thu chưa bao giờ thấy màu đỏ thì không ai
 * biết nó đang đo hay đang gật. Và bộ thu này sinh ra để cầm bằng chứng cho
 * một quyết định về TIỀN (có đóng đường rơi sang vai `translate` hay không),
 * nên "chắc là nó chạy đúng" không đủ.
 *
 * Ở đây bộ thu chạy với một nhà cung cấp GIẢ dựng ngay trong tiến trình test
 * — không cần khoá API, không gọi ra Internet, nên chạy được ngay hôm nay
 * trong khi khoá thật còn chưa cắm. Lượt đầu chứng minh nó XANH trên một hệ
 * thống lành; bốn lượt sau cố ý làm hỏng đúng bốn thứ mà §B3 bắt phải canh,
 * và đòi bộ thu phải ĐỎ đúng chỗ đó:
 *
 *   1. tác vụ miễn phí bị tính tiền;
 *   2. nhớ đệm chết ⇒ cùng một câu hỏi bị trừ tiền HAI lần;
 *   3. thiếu nhà cung cấp mà vẫn trả lời (đúng hình dạng đường rơi im lặng);
 *   4. khoá API lọt vào câu trả lời của mô hình.
 *
 * Chạy:  node --test tests/thu-bang-chung-assist.test.js
 */
const test = require('node:test')
const assert = require('node:assert')
const http = require('node:http')

const { setTestEnv, startDb, stopDb } = require('./helpers/db')
setTestEnv()

const { thuBangChung } = require('../scripts/thu-bang-chung-assist')

/**
 * Nhà cung cấp GIẢ nói đúng giọng OpenAI-compat.
 *
 * `soanNoiDung(req)` cho phép từng phép thử đổi câu trả lời — phép thử rò rỉ
 * khoá dùng nó để dựng lại đúng ca nhà cung cấp in ngược khoá ra ngoài.
 */
function moNhaCungCapGia({ soanNoiDung = null } = {}) {
  let soLuot = 0
  const may = http.createServer((req, res) => {
    let than = ''
    req.on('data', (c) => { than += c })
    req.on('end', () => {
      soLuot += 1
      const khoa = String(req.headers.authorization || '').replace(/^Bearer\s+/i, '')
      const noiDung = soanNoiDung
        ? soanNoiDung({ khoa, than })
        : JSON.stringify({
          results: [
            { value: 'Gợi ý mẫu của nhà cung cấp giả', reason: 'Lý do mẫu, đủ dài để không bị loại.' },
          ],
        })
      res.writeHead(200, { 'content-type': 'application/json' })
      res.end(JSON.stringify({
        choices: [{ message: { content: noiDung }, finish_reason: 'stop' }],
        usage: { prompt_tokens: 123, completion_tokens: 45 },
      }))
    })
  })
  return new Promise((ok) => {
    may.listen(0, '127.0.0.1', () => ok({
      url: `http://127.0.0.1:${may.address().port}/v1`,
      dong: () => new Promise((xong) => may.close(xong)),
      soLuot: () => soLuot,
    }))
  })
}

const KHOA_GIA = 'sk-thu-nghiem-0123456789abcdef'

function chay(gia, them = {}) {
  return thuBangChung({
    nhaCungCap: { baseUrl: gia.url, apiKey: KHOA_GIA, model: 'mo-hinh-gia', type: '' },
    moDb: startDb,
    dongDb: stopDb,
    ghi: () => {},
    ...them,
  })
}

const coViPham = (ket, cum) => ket.viPham.some((v) => v.includes(cum))

// ------------------------------------------------- 1. hệ thống lành ⇒ XANH ---

test('hệ thống lành: chạy trọn ma trận và mọi bất biến đạt', async (t) => {
  const gia = await moNhaCungCapGia()
  t.after(() => gia.dong())

  const ket = await chay(gia)

  assert.deepStrictEqual(ket.viPham, [], 'không được có bất biến nào bị phá')
  assert.strictEqual(ket.ok, true)

  // Ma trận §B2 phải đủ mặt, mỗi tác vụ ít nhất hai lượt.
  for (const tv of ['explain_error', 'character_name', 'tighten_line', 'scene_script']) {
    const so = ket.luot.filter((d) => d.tac_vu === tv).length
    assert.ok(so >= 2, `${tv} mới có ${so} lượt`)
  }
  assert.ok(ket.tomTat.so_luot_goi_mo_hinh_that >= 10,
    `mới ${ket.tomTat.so_luot_goi_mo_hinh_that} lượt chạm mô hình thật, cần ≥ 10`)

  // Số lượt GỌI RA nhà cung cấp phải khớp số lượt bộ thu khai là "gọi mới" —
  // đây là chỗ một bộ thu gật sẽ lệch: nó khai đã gọi mà không ai nhận cuộc.
  const goiMoi = ket.luot.filter((d) => d.dem === 'gọi mới' && d.ma_http === 200).length
  assert.strictEqual(gia.soLuot(), goiMoi,
    `nhà cung cấp giả nhận ${gia.soLuot()} lượt nhưng bộ thu khai ${goiMoi}`)

  // Nhớ đệm: đúng một lượt, và nó KHÔNG chạm tới nhà cung cấp.
  const dem = ket.luot.filter((d) => d.dem === 'ĐỌC ĐỆM')
  assert.strictEqual(dem.length, 1)
  assert.strictEqual(dem[0].da_tru, 0)
  assert.strictEqual(dem[0].ghi_so_moi, 0)

  // Hợp đồng lỗi.
  const ma = (ten) => ket.luot.find((d) => d.ten === ten).ma_http
  assert.strictEqual(ma('thiếu nhà cung cấp'), 503)
  assert.strictEqual(ma('thiếu token máy'), 401)
  assert.strictEqual(ma('mô hình không gọi được'), 503)

  // Mỗi lượt có phí phải ghi đủ trường §B3.
  for (const d of ket.luot.filter((x) => x.gia_preflight > 0 && x.ma_http === 200 && x.dem === 'gọi mới')) {
    for (const truong of ['gia_preflight', 'vi_truoc', 'vi_sau', 'nha_cung_cap',
      'mo_hinh', 'token_vao', 'token_ra', 'do_tre_ms', 'khoa_dem']) {
      assert.ok(d[truong] !== undefined && d[truong] !== '',
        `${d.ten} thiếu trường ${truong}`)
    }
  }
})

test('thiếu vai assist mà có vai dịch: bộ thu đòi 503, không đòi 200', async (t) => {
  const gia = await moNhaCungCapGia()
  t.after(() => gia.dong())

  const ket = await chay(gia)
  const roi = ket.luot.find((d) => d.ten === 'thiếu assist, có translate')

  // I1 bước 3 đã đóng đường rơi (22/09/2026). Trước đó lượt này ra 200 kèm
  // `assistRole = translate` và bộ thu chỉ GHI NHẬN; nay nó là phép KIỂM.
  assert.strictEqual(roi.ma_http, 503)
  assert.strictEqual(roi.ma_loi, 'CHUA_CO_NOI_GOI_TRO_LY')
  assert.strictEqual(roi.da_tru, 0, 'lượt bị chặn không được trừ Vox')
  assert.strictEqual(ket.tomTat.duong_roi_con_song, false)
  assert.ok(!coViPham(ket, 'thiếu vai assist'), JSON.stringify(ket.viPham))
})

test('đường rơi sống lại ⇒ bộ thu ĐỎ', async (t) => {
  const gia = await moNhaCungCapGia()
  const gateway = require('../src/services/ai-gateway.service')
  const that = gateway.assist
  t.after(async () => { gateway.assist = that; await gia.dong() })

  const ket = await chay(gia, {
    tiemLoi: async () => {
      // Dựng lại đúng hành vi CŨ: thiếu vai `assist` thì mượn vai dịch và
      // trả lời như thường. Đây là thứ bộ thu phải kêu, không phải bỏ qua.
      gateway.assist = async () => ({
        results: [{ value: 'trả lời bằng vai dịch', reason: 'rơi vai im lặng' }],
        usage: { promptTokens: 1, completionTokens: 1 },
        provider: 'noi-goi-dich', model: 'mo-hinh-dich', role: 'translate',
      })
    },
  })

  assert.strictEqual(ket.ok, false)
  assert.ok(coViPham(ket, 'KHÔNG được rơi sang vai dịch'), JSON.stringify(ket.viPham))
  assert.strictEqual(ket.tomTat.duong_roi_con_song, true)
})

// ------------------------------------------------- 2. bốn ca hỏng ⇒ ĐỎ ---

test('tác vụ miễn phí bị tính tiền ⇒ bộ thu ĐỎ', async (t) => {
  const gia = await moNhaCungCapGia()
  t.after(() => gia.dong())

  const ket = await chay(gia, {
    tiemLoi: async ({ config }) => {
      await config.set('credit.cost.assist.explain_error', 5)
    },
  })

  assert.strictEqual(ket.ok, false)
  assert.ok(coViPham(ket, 'explain_error phải 0 Vox'),
    `chờ vi phạm về tác vụ miễn phí, nhận: ${JSON.stringify(ket.viPham)}`)
})

test('nhớ đệm chết ⇒ cùng câu hỏi bị trừ tiền hai lần ⇒ bộ thu ĐỎ', async (t) => {
  const gia = await moNhaCungCapGia()
  const JobResult = require('../src/models/JobResult')
  const that = JobResult.findOne.bind(JobResult)
  t.after(async () => { JobResult.findOne = that; await gia.dong() })

  const ket = await chay(gia, {
    tiemLoi: async () => {
      // Giả lập đệm hỏng: mọi lượt tra đệm đều trượt. Đây đúng là hình dạng
      // sự cố 22/8/2026 (`remember()` ném vì enum thiếu giá trị) — lượt sau
      // trả tiền lần nữa cho cùng một câu hỏi.
      JobResult.findOne = () => ({ lean: async () => null })
    },
  })

  assert.strictEqual(ket.ok, false)
  assert.ok(coViPham(ket, 'nhớ đệm phải ĐỌC ĐỆM'), JSON.stringify(ket.viPham))
  assert.ok(coViPham(ket, 'nhớ đệm KHÔNG trừ tiền lần hai'), JSON.stringify(ket.viPham))
})

test('thiếu nhà cung cấp mà vẫn trả lời ⇒ bộ thu ĐỎ', async (t) => {
  const gia = await moNhaCungCapGia()
  const gateway = require('../src/services/ai-gateway.service')
  const that = gateway.assist
  t.after(async () => { gateway.assist = that; await gia.dong() })

  const ket = await chay(gia, {
    tiemLoi: async () => {
      // Đúng hình dạng của đường rơi im lặng: không có nhà cung cấp cho vai
      // `assist` mà cửa vẫn trả kết quả như thường.
      gateway.assist = async () => ({
        results: [{ value: 'trả lời bằng vai khác', reason: 'im lặng rơi vai' }],
        usage: { promptTokens: 1, completionTokens: 1 },
        provider: 'khac', model: 'khac', role: 'translate',
      })
    },
  })

  assert.strictEqual(ket.ok, false)
  assert.ok(coViPham(ket, 'thiếu nhà cung cấp phải 503'), JSON.stringify(ket.viPham))
})

test('khoá API lọt vào câu trả lời ⇒ bộ thu ĐỎ và tệp ghi ra vẫn sạch', async (t) => {
  const os = require('node:os')
  const fs = require('node:fs')
  const path = require('node:path')

  const gia = await moNhaCungCapGia({
    // Nhà cung cấp in ngược khoá ra — đã gặp thật ở các API trả nguyên URL
    // kèm `?key=…` trong thông báo lỗi.
    soanNoiDung: ({ khoa }) => JSON.stringify({
      results: [{ value: `Gợi ý kèm khoá ${khoa}`, reason: 'Lý do mẫu đủ dài.' }],
    }),
  })
  const duongRa = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'thu-bc-')), 'bc.json')
  t.after(() => gia.dong())

  const ket = await chay(gia, { duongRa })

  assert.strictEqual(ket.ok, false)
  assert.ok(coViPham(ket, 'bí mật'), JSON.stringify(ket.viPham))

  const daGhi = fs.readFileSync(duongRa, 'utf8')
  assert.ok(!daGhi.includes(KHOA_GIA),
    'tệp bằng chứng ghi ra vẫn còn khoá nguyên văn — lớp che theo giá trị hỏng')
  assert.ok(daGhi.includes('đã che'), 'phải thấy dấu vết che có chủ ý')
})
