'use strict'

/**
 * Bộ THU BẰNG CHỨNG cho cổng trợ lý — MINI-SPEC I1 §B2/§B3.
 *
 * Chạy đủ ma trận tác vụ qua **đúng đường HTTP thật** của máy chủ
 * (`POST /v1/ai/assist`), trên một cơ sở dữ liệu DÙNG MỘT LẦN, với một nhà
 * cung cấp thật do chủ dự án cắm khoá — rồi ghi lại từng lượt kèm giá, số dư
 * Vox trước/sau, hold, nhớ đệm, mô hình, token, mã lỗi và độ trễ.
 *
 *     node scripts/thu-bang-chung-assist.js            # cần ASSIST_EVAL_*
 *     node scripts/thu-bang-chung-assist.js --ra duong/toi/tep.json
 *
 * Biến môi trường (CÙNG TÊN với `evals/run.js` — một bộ biến cho cả hai công
 * cụ, không bắt chủ dự án nhớ hai kiểu):
 *
 *     ASSIST_EVAL_BASE_URL   ví dụ https://api.openai.com/v1
 *     ASSIST_EVAL_KEY        khoá API
 *     ASSIST_EVAL_MODEL      tên mô hình
 *     ASSIST_EVAL_TYPE       "google" cho Gemini, để trống cho loại OpenAI
 *
 * ## Ba điều tệp này CÓ chứng minh
 *
 * 1. Mô hình thật trả lời được cho bốn tác vụ của ma trận §B2.
 * 2. Đường TIỀN chạy đúng: giá đúng nguồn cấu hình, nhớ đệm không tính lần
 *    hai, hold hấp thụ được lượt, lượt hỏng không trừ tiền.
 * 3. Hợp đồng lỗi đúng: thiếu nhà cung cấp ra 503 (không phải 401), thiếu
 *    token vẫn 401, mô hình chết ra 503 và không chạm vào ví.
 *
 * ## Ba điều tệp này KHÔNG chứng minh (đừng đọc nhầm)
 *
 * 1. **Không đi qua giao diện desktop.** `character_name` nằm trong hộp thoại
 *    Trình chỉnh sửa, `tighten_line` ở thanh công cụ câu, `scene_script` ở
 *    trang Dựng video, `explain_error` ở hộp báo lỗi. Ở đây chúng được gọi
 *    thẳng qua HTTP với đúng hình dạng dữ liệu mà máy khách gửi
 *    (`tests/test_thu_bang_chung_khop_may_khach.py` canh hình dạng đó khỏi
 *    trôi), nhưng luồng bấm, câu chữ hiện ra và đường lui trên máy thì không.
 * 2. **Không phải ví tiền thật.** Số dư Vox ở đây do chính bộ thu gieo vào cơ
 *    sở dữ liệu dùng một lần. Thứ được chứng minh là LOGIC tính tiền, không
 *    phải một giao dịch thật của người dùng thật.
 * 3. **Không đụng máy chủ đang chạy.** Cố ý: dựng Mongo riêng, khoá mã hoá
 *    riêng sinh ngẫu nhiên, nhà cung cấp riêng, rồi xoá sạch khi xong.
 *
 * ## Vì sao không dùng `evals/run.js`
 *
 * Bộ đo ấy chấm CHẤT LƯỢNG câu trả lời và cố ý **không đụng cơ sở dữ liệu**,
 * nên nó không nhìn thấy ví, hold, nhớ đệm hay mã lỗi HTTP — tức là không
 * nói được gì về §B3. Hai bộ trả lời hai câu hỏi khác nhau; tệp này không
 * chép lại phần việc của nó (và không chấm điểm chất lượng).
 */
const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')

const { cheBiMat, cheTheoGiaTri, timBiMatSotLai } = require('../src/utils/che-bi-mat')

// ---------------------------------------------------------------- mẫu gửi ---
//
// Hình dạng `input` PHẢI khớp thứ máy khách gửi thật:
//   explain_error   autodub_gui/workers.py:1415
//   character_name  autodub_gui/pages/editor_page.py:1003
//   tighten_line    autodub_gui/pages/editor_page.py:462
//   scene_script    autodub/product_video.py:319
// `tests/test_thu_bang_chung_khop_may_khach.py` đọc cả hai phía và so tên
// trường — bộ thu gửi sai hình dạng thì bằng chứng thu về nói về một cửa
// không tồn tại.
const MAU = {
  explain_error: [
    { message: 'ffmpeg exited with code 1: Invalid data found when processing input',
      step: 'merge_video' },
    { message: 'CUDA out of memory. Tried to allocate 2.00 GiB', step: 'separate' },
  ],
  character_name: [
    { lines: 'Con đã về rồi đây mẹ ơi.\nSao hôm nay con về muộn thế?\n'
        + 'Con ghé chợ mua ít đồ cho bữa tối.',
      lineCount: 3 },
    { lines: 'Báo cáo đại nhân, quân địch đã vượt sông.\n'
        + 'Truyền lệnh cho tiền quân giữ vững phòng tuyến.',
      lineCount: 2 },
  ],
  // SÁU câu khác nhau, không phải hai — và đây là chuyện đã suýt làm hỏng cả
  // bộ thu. Nhớ đệm băm theo NỘI DUNG, nên dùng lại một câu cũ cho ca "thiếu
  // nhà cung cấp" thì máy chủ trả kết quả CŨ (HTTP 200) mà không hề chạm tới
  // nhà cung cấp — phép kiểm 503 sẽ xanh giả theo chiều ngược lại. Mỗi kịch
  // bản một câu riêng; chỉ lượt đệm CÓ CHỦ Ý mới được dùng lại câu số 0.
  tighten_line: [
    { line: 'Thực ra thì cái chuyện này nó cũng không có gì quá là ghê gớm đâu bạn ạ',
      needSeconds: 5.4, roomSeconds: 3.6, trimPercent: 33 },
    { line: 'Nếu bạn đang tìm một giải pháp vừa nhanh vừa tiết kiệm thì đây chính là thứ dành cho bạn',
      needSeconds: 6.8, roomSeconds: 4.5, trimPercent: 34 },
    { line: 'Cái nồi này nhà mình dùng gần hai tháng rồi mà vẫn chưa thấy hỏng hóc gì cả',
      needSeconds: 5.9, roomSeconds: 4.0, trimPercent: 32 },
    { line: 'Buổi sáng mà phải dậy sớm nấu nướng thì đúng là cực kỳ mất thời gian của mọi người',
      needSeconds: 6.2, roomSeconds: 4.1, trimPercent: 34 },
    { line: 'Chỉ cần cắm điện lên rồi chờ đúng ba phút là đã có ngay đồ ăn nóng hổi cho cả nhà',
      needSeconds: 6.0, roomSeconds: 4.2, trimPercent: 30 },
    { line: 'Bạn cứ thử dùng một tuần xem sao, không hợp thì mình hoàn tiền lại ngay cho bạn',
      needSeconds: 5.7, roomSeconds: 3.9, trimPercent: 32 },
  ],
  scene_script: [
    { product: 'Nồi chiên không dầu 5 lít',
      scenes: ['Gian bếp buổi sáng', 'Cận cảnh mẻ gà vừa chín', 'Cả nhà ngồi ăn'] },
    { product: 'Bình giữ nhiệt 500ml',
      scenes: ['Bàn làm việc', 'Rót nước còn bốc hơi', 'Cho vào balo đi làm'] },
  ],
}

function maViec(tien) {
  return `${tien}-${crypto.randomBytes(8).toString('hex')}`
}

/** Vân tay máy đem in ra bằng chứng — giữ 8 ký tự đầu là đủ để đối chiếu. */
function rutGon(chuoi, giu = 8) {
  const s = String(chuoi || '')
  return s.length <= giu ? s : `${s.slice(0, giu)}…`
}

/**
 * Chạy bộ thu. Trả về `{ ok, luot, viPham, tomTat }` — KHÔNG tự thoát tiến
 * trình, để test gọi lại được.
 *
 * `moDb`/`dongDb` tiêm được: bộ test dùng `mongod` chung của cả suite, còn
 * người chạy tay thì để mặc định (tự dựng bản trong bộ nhớ).
 */
async function thuBangChung({
  nhaCungCap,
  duongRa = '',
  vox = 500,
  ghi = console.log,
  moDb = null,
  dongDb = null,
  tiemLoi = null,
} = {}) {
  if (!nhaCungCap || !nhaCungCap.apiKey || !nhaCungCap.baseUrl || !nhaCungCap.model) {
    throw new Error(
      'Thiếu cấu hình nhà cung cấp. Đặt ba biến môi trường rồi chạy lại:\n'
      + '  ASSIST_EVAL_BASE_URL=…  ASSIST_EVAL_KEY=…  ASSIST_EVAL_MODEL=…\n'
      + '  (ASSIST_EVAL_TYPE=google nếu là Gemini)')
  }

  // --- An toàn: KHÔNG bao giờ chạm máy chủ đang chạy -----------------------
  //
  // Khoá ký và khoá mã hoá sinh MỚI mỗi lượt: bộ thu không đọc bí mật sản
  // xuất, và khoá API của chủ dự án được mã hoá bằng một khoá sống đúng bằng
  // đời của tiến trình này rồi biến mất cùng cơ sở dữ liệu.
  process.env.JWT_SECRET = crypto.randomBytes(32).toString('hex')
  process.env.APP_ENCRYPTION_KEY = crypto.randomBytes(32).toString('hex')
  const uriChung = process.env.TEST_MONGO_URI || ''
  if (uriChung && !/(localhost|127\.0\.0\.1)/.test(uriChung)) {
    throw new Error(`TEST_MONGO_URI trỏ ra ngoài máy (${uriChung}) — từ chối chạy.`)
  }

  const db = require('../tests/helpers/db')
  db.setTestEnv()

  const mongoose = require('mongoose')
  const { build } = require('../src/app')
  const config = require('../src/services/config.service')
  const credit = require('../src/services/credit.service')
  const holds = require('../src/services/hold.service')
  const gateway = require('../src/services/ai-gateway.service')
  const assistPrompts = require('../src/prompts/assist')
  const { encrypt } = require('../src/utils/crypto')
  const AiProvider = require('../src/models/AiProvider')
  const UsageLog = require('../src/models/UsageLog')
  const JobResult = require('../src/models/JobResult')
  const CreditLedger = require('../src/models/CreditLedger')
  const CreditHold = require('../src/models/CreditHold')
  const Device = require('../src/models/Device')

  await (moDb || db.startDb)()
  const app = await build({ mongo: false, web: false, logger: false })
  await app.ready()

  const luot = []
  const viPham = []
  const bao = (dieu, dat, chiTiet = '') => {
    if (!dat) viPham.push(`${dieu}${chiTiet ? ` — ${chiTiet}` : ''}`)
    return dat
  }

  try {
    await config.set('credit.enabled', true)
    await config.set('hold.enabled', true)

    // --- máy thử + ví -----------------------------------------------------
    const vanTay = crypto.randomBytes(32).toString('hex')
    const dangKy = await app.inject({
      method: 'POST', url: '/v1/device/register',
      payload: { fingerprint: vanTay, name: 'thu-bang-chung', appVersion: '0.0.0-thu' },
    })
    if (dangKy.statusCode !== 200) {
      throw new Error(`đăng ký máy thử hỏng: HTTP ${dangKy.statusCode} ${dangKy.body.slice(0, 200)}`)
    }
    const token = dangKy.json().token
    const may = await Device.findOne({ fingerprint: vanTay }).lean()
    await credit.grant(vanTay, vox, {
      idempotencyKey: `thu-bang-chung-${vanTay.slice(0, 12)}`,
      type: 'admin_grant', description: 'Gieo Vox cho lượt thu bằng chứng',
    })

    // --- nhà cung cấp vai assist -----------------------------------------
    const taoNhaCungCap = async (role, baseUrl) => {
      const doc = await AiProvider.create({
        name: `thu-bang-chung-${role}-${crypto.randomBytes(3).toString('hex')}`,
        label: `Thu bằng chứng (${role})`,
        role,
        type: nhaCungCap.type === 'google' ? 'google' : 'openai_compat',
        baseUrl: baseUrl || nhaCungCap.baseUrl,
        model: nhaCungCap.model,
        apiKeyEnc: encrypt(nhaCungCap.apiKey),
        enabled: true,
        priority: 1,
        timeoutMs: nhaCungCap.timeoutMs || 60_000,
      })
      gateway.invalidateProviders()
      return doc
    }
    const xoaNhaCungCap = async (dieuKien = {}) => {
      await AiProvider.deleteMany(dieuKien)
      gateway.invalidateProviders()
    }

    await taoNhaCungCap('assist')

    // Cửa TIÊM LỖI — chỉ bộ test dùng (`tests/thu-bang-chung-assist.test.js`).
    // Một bộ thu chưa bao giờ thấy màu đỏ thì không ai biết nó có đo thật hay
    // không; cửa này để test cố ý làm hỏng hệ thống rồi đòi bộ thu phải kêu.
    if (tiemLoi) await tiemLoi({ config, credit, JobResult, gateway, AiProvider })

    // --- một lượt, và mọi thứ cần ghi lại về nó ---------------------------
    const motLuot = async (ten, {
      task, input, holdId = '', dungToken = true, jobId = maViec(task),
      moTa = '',
    }) => {
      const giaCauHinh = await config.get(assistPrompts.getTask(task).costKey)
      const viTruoc = await credit.getBalance(vanTay)
      const soGhiSoTruoc = await CreditLedger.countDocuments({ fingerprint: vanTay })
      const soHoldTruoc = await CreditHold.countDocuments({ fingerprint: vanTay })
      const usageTruoc = await UsageLog.countDocuments({ fingerprint: vanTay })

      const t0 = Date.now()
      const res = await app.inject({
        method: 'POST',
        url: '/v1/ai/assist',
        headers: dungToken ? { authorization: `Bearer ${token}` } : {},
        payload: { jobId, task, input, ...(holdId ? { holdId } : {}) },
      })
      const doTre = Date.now() - t0

      const viSau = await credit.getBalance(vanTay)
      const soGhiSoSau = await CreditLedger.countDocuments({ fingerprint: vanTay })
      const soHoldSau = await CreditHold.countDocuments({ fingerprint: vanTay })
      const usageSau = await UsageLog.countDocuments({ fingerprint: vanTay })
      const soSo = await UsageLog.findOne({ jobId }).lean()
      const hold = holdId ? await CreditHold.findOne({ holdId }).lean() : null

      let than = null
      try { than = res.json() } catch { than = null }

      const dong = {
        ten,
        mo_ta: moTa,
        tac_vu: task,
        may: rutGon(vanTay),                       // vân tay đã rút gọn
        ma_viec: rutGon(jobId, 10),
        gia_preflight: giaCauHinh,
        vi_truoc: viTruoc,
        vi_sau: viSau,
        da_tru: viTruoc - viSau,
        tru_theo_tra_loi: than && typeof than.creditCharged === 'number'
          ? than.creditCharged : null,
        hold: holdId ? (hold ? `${hold.status} (usage ${(hold.usage || []).length} mục)` : 'không thấy')
          : 'không dùng',
        hold_moi: soHoldSau - soHoldTruoc,
        ghi_so_moi: soGhiSoSau - soGhiSoTruoc,      // số dòng CreditLedger sinh thêm
        dem: than && than.fromCache ? 'ĐỌC ĐỆM' : 'gọi mới',
        khoa_dem: rutGon(assistPrompts.cacheKey(task, input, []), 10),
        phien_ban_loi_nhac: assistPrompts.PROMPT_VERSION,
        ma_http: res.statusCode,
        ma_loi: than && than.code ? than.code : '',
        vai_mo_hinh: soSo ? (soSo.assistRole || '') : '',
        nha_cung_cap: soSo ? (soSo.aiProvider || '') : '',
        mo_hinh: soSo ? (soSo.aiModel || '') : '',
        token_vao: soSo ? (soSo.promptTokens || 0) : 0,
        token_ra: soSo ? (soSo.completionTokens || 0) : 0,
        so_dung_moi: usageSau - usageTruoc,
        do_tre_ms: doTre,
        ket_qua_dau: than && Array.isArray(than.results) && than.results[0]
          ? rutGon(String(than.results[0].value), 60) : '',
      }
      luot.push(dong)
      ghi(`  [${String(res.statusCode).padEnd(3)}] ${ten.padEnd(24)} `
        + `${String(dong.da_tru).padStart(3)} Vox · ${dong.dem} · ${doTre} ms`
        + (dong.ma_loi ? ` · ${dong.ma_loi}` : ''))
      return dong
    }

    // ===================================================== ma trận §B2 ===
    ghi('\n1. Bốn tác vụ của ma trận — mỗi tác vụ hai lượt')

    const mienPhi1 = await motLuot('explain_error #1',
      { task: 'explain_error', input: MAU.explain_error[0], moTa: 'đường miễn phí' })
    const ten1 = await motLuot('character_name #1',
      { task: 'character_name', input: MAU.character_name[0] })
    const ten2 = await motLuot('character_name #2',
      { task: 'character_name', input: MAU.character_name[1] })
    const gon1 = await motLuot('tighten_line #1',
      { task: 'tighten_line', input: MAU.tighten_line[0] })
    const gon2 = await motLuot('tighten_line #2',
      { task: 'tighten_line', input: MAU.tighten_line[1] })
    const canh1 = await motLuot('scene_script #1',
      { task: 'scene_script', input: MAU.scene_script[0] })
    const canh2 = await motLuot('scene_script #2',
      { task: 'scene_script', input: MAU.scene_script[1] })

    ghi('\n2. Nhớ đệm CÓ CHỦ Ý — cùng nội dung, mã việc khác')
    const demLai = await motLuot('tighten_line (đệm)', {
      task: 'tighten_line', input: MAU.tighten_line[0],
      moTa: 'lặp lại y hệt lượt tighten_line #1 nhưng mã việc mới',
    })

    ghi('\n3. Hold hấp thụ lượt — tiền đã thu lúc tạo hold')
    const maHold = maViec('hold')
    await holds.createHold({
      fingerprint: vanTay, deviceId: may._id, holdId: maHold, sentences: 10,
      autoTranslate: true, metadata: false, ip: '127.0.0.1',
    })
    const viSauHold = await credit.getBalance(vanTay)
    const coHold = await motLuot('tighten_line (hold)', {
      task: 'tighten_line', input: MAU.tighten_line[2], holdId: maHold,
      moTa: 'lượt đi kèm hold đang hoạt động',
    })

    ghi('\n4. Ví cạn — tác vụ miễn phí vẫn phải chạy')
    const conLai = await credit.getBalance(vanTay)
    if (conLai > 0) {
      await credit.deduct(vanTay, conLai, {
        type: 'usage', idempotencyKey: `rut-can-${vanTay.slice(0, 12)}`,
        description: 'Rút cạn ví để thử đường miễn phí',
      })
    }
    const mienPhi0 = await motLuot('explain_error (ví 0)', {
      task: 'explain_error', input: MAU.explain_error[1],
      moTa: 'số dư bằng 0 — chính sách nói tác vụ này vẫn chạy',
    })
    await credit.grant(vanTay, vox, {
      idempotencyKey: `gieo-lai-${vanTay.slice(0, 12)}`, type: 'admin_grant',
      description: 'Gieo lại Vox sau phép thử ví cạn',
    })

    // ================================================ hợp đồng lỗi §B3 ===
    ghi('\n5. Hợp đồng lỗi')

    await xoaNhaCungCap({})
    const khongNhaCungCap = await motLuot('thiếu nhà cung cấp', {
      task: 'tighten_line', input: MAU.tighten_line[3],
      jobId: maViec('khong-ncc'),
      moTa: 'không có nhà cung cấp nào cho bất kỳ vai nào',
    })

    const thieuToken = await motLuot('thiếu token máy', {
      task: 'tighten_line', input: MAU.tighten_line[3],
      jobId: maViec('khong-token'), dungToken: false,
      moTa: 'không gửi Authorization',
    })

    await taoNhaCungCap('assist', 'http://127.0.0.1:1/v1')
    const moHinhHong = await motLuot('mô hình không gọi được', {
      task: 'tighten_line', input: MAU.tighten_line[4],
      jobId: maViec('ncc-hong'),
      moTa: 'nhà cung cấp trỏ vào cổng chết — mô phỏng lỗi/timeout',
    })

    // Ca này KHÔNG phải phép kiểm đạt/hỏng của hôm nay: nó ĐO xem đường rơi
    // im lặng sang vai `translate` còn sống không. Bước 3 của phương án A sẽ
    // đóng đường đó lại; tới lúc ấy lượt này phải ra 503.
    await xoaNhaCungCap({})
    await taoNhaCungCap('translate')
    const roiSangDich = await motLuot('thiếu assist, có translate', {
      task: 'tighten_line', input: MAU.tighten_line[5],
      jobId: maViec('roi-vai'),
      moTa: 'đo đường rơi im lặng — sau bước 3 phải là 503',
    })
    await xoaNhaCungCap({})

    // ==================================================== bất biến §B3 ===
    const coPhi = [ten1, ten2, gon1, gon2, canh1, canh2]

    bao('explain_error phải 0 Vox',
      mienPhi1.da_tru === 0 && mienPhi1.tru_theo_tra_loi === 0,
      `trừ ${mienPhi1.da_tru} Vox`)
    bao('explain_error phải chạy được khi ví = 0',
      mienPhi0.ma_http === 200 && mienPhi0.vi_truoc === 0,
      `HTTP ${mienPhi0.ma_http}, ví trước ${mienPhi0.vi_truoc}`)

    for (const d of coPhi) {
      bao(`${d.ten}: phải trả lời được`, d.ma_http === 200,
        `HTTP ${d.ma_http} ${d.ma_loi}`)
      bao(`${d.ten}: trừ đúng giá cấu hình`,
        d.da_tru === d.gia_preflight && d.tru_theo_tra_loi === d.gia_preflight,
        `giá ${d.gia_preflight}, trừ ${d.da_tru}, báo về ${d.tru_theo_tra_loi}`)
      bao(`${d.ten}: có ghi sổ mô hình/token`,
        Boolean(d.nha_cung_cap) && Boolean(d.mo_hinh),
        'sổ dùng thiếu nhà cung cấp hoặc mô hình')
    }

    bao('nhớ đệm phải ĐỌC ĐỆM, không gọi lại',
      demLai.dem === 'ĐỌC ĐỆM', demLai.dem)
    bao('nhớ đệm KHÔNG trừ tiền lần hai',
      demLai.da_tru === 0 && demLai.tru_theo_tra_loi === 0,
      `trừ ${demLai.da_tru} Vox`)
    bao('nhớ đệm KHÔNG sinh dòng ghi sổ mới',
      demLai.ghi_so_moi === 0, `${demLai.ghi_so_moi} dòng`)
    bao('nhớ đệm KHÔNG tạo hold mới',
      demLai.hold_moi === 0, `${demLai.hold_moi} hold`)

    bao('lượt có hold: không trừ ví (hold đã thu trọn lúc tạo)',
      coHold.ma_http === 200 && coHold.da_tru === 0
        && (await credit.getBalance(vanTay)) >= 0 && coHold.vi_truoc === viSauHold,
      `HTTP ${coHold.ma_http}, trừ ${coHold.da_tru}`)
    bao('lượt có hold: hold ghi lại lượt dùng',
      /active/.test(coHold.hold), coHold.hold)

    bao('thiếu nhà cung cấp phải 503, KHÔNG phải 401',
      khongNhaCungCap.ma_http === 503, `HTTP ${khongNhaCungCap.ma_http}`)
    bao('thiếu nhà cung cấp: không trừ Vox',
      khongNhaCungCap.da_tru === 0, `trừ ${khongNhaCungCap.da_tru}`)

    bao('thiếu token máy vẫn phải 401',
      thieuToken.ma_http === 401, `HTTP ${thieuToken.ma_http}`)
    bao('thiếu token máy: không chạm tới mô hình (không sinh sổ dùng)',
      thieuToken.so_dung_moi === 0, `${thieuToken.so_dung_moi} dòng sổ`)

    bao('mô hình hỏng phải 503', moHinhHong.ma_http === 503,
      `HTTP ${moHinhHong.ma_http}`)
    bao('mô hình hỏng: không trừ Vox', moHinhHong.da_tru === 0,
      `trừ ${moHinhHong.da_tru}`)

    // --- che bí mật: quét NGƯỢC toàn bộ thứ sắp ghi ra --------------------
    const soSach = await UsageLog.find({ fingerprint: vanTay }).lean()
    const daLuu = await JobResult.find({ fingerprint: vanTay }).lean()
    const nhaCC = await AiProvider.find({}).lean()
    const lo = timBiMatSotLai(
      JSON.parse(JSON.stringify({ luot, soSach, daLuu, nhaCC })),
      [nhaCungCap.apiKey, token])
    bao('không có bí mật nào lọt vào sổ sách hay bằng chứng',
      lo.length === 0, lo.join('; '))

    // --- kết luận ---------------------------------------------------------
    const goiRealThat = luot.filter((d) => d.nha_cung_cap).length
    const tomTat = {
      luc: new Date().toISOString(),
      so_luot: luot.length,
      so_luot_goi_mo_hinh_that: goiRealThat,
      mo_hinh: nhaCungCap.model,
      loai: nhaCungCap.type === 'google' ? 'google' : 'openai_compat',
      vai_do_duoc_o_ca_roi: roiSangDich.vai_mo_hinh || '(không ghi được)',
      duong_roi_con_song: roiSangDich.ma_http === 200
        && roiSangDich.vai_mo_hinh === 'translate',
      tong_vox_da_tru: luot.reduce((t, d) => t + Math.max(0, d.da_tru), 0),
      so_vi_pham: viPham.length,
    }

    if (tomTat.duong_roi_con_song) {
      ghi('\n⚠ ĐO ĐƯỢC: thiếu vai `assist` mà có `translate` thì lượt trợ lý '
        + 'VẪN chạy bằng vai dịch (HTTP 200). Đây là thứ bước 3 phải đóng — '
        + 'chưa đóng nên KHÔNG tính là vi phạm ở lượt này.')
    }

    // Hai lớp che, theo đúng thứ tự: che theo tên khoá/mẫu trước, rồi che
    // theo ĐÚNG GIÁ TRỊ. Lớp sau tồn tại vì lớp trước mù trước một khoá nằm
    // lẫn trong câu trả lời của mô hình — không tên khoá, không dấu bằng.
    const banGhi = cheTheoGiaTri(
      cheBiMat({ tom_tat: tomTat, luot, vi_pham: viPham }),
      [nhaCungCap.apiKey, token])
    if (duongRa) {
      fs.mkdirSync(path.dirname(path.resolve(duongRa)), { recursive: true })
      fs.writeFileSync(path.resolve(duongRa),
        `${JSON.stringify(banGhi, null, 2)}\n`, 'utf8')
      ghi(`\nBằng chứng: ${path.resolve(duongRa)}`)
    }

    return { ok: viPham.length === 0, luot, viPham, tomTat, banGhi }
  } finally {
    await app.close()
    try { await (dongDb || db.stopDb)() } catch { /* đóng được tới đâu hay tới đó */ }
    if (mongoose.connection.readyState !== 0 && !dongDb) {
      try { await mongoose.connection.close() } catch { /* đã đóng */ }
    }
  }
}

async function main() {
  const dsTs = process.argv.slice(2)
  const iRa = dsTs.indexOf('--ra')
  const duongRa = iRa >= 0 && dsTs[iRa + 1] ? dsTs[iRa + 1]
    : path.join(__dirname, '..', 'bang-chung-assist',
      `${new Date().toISOString().replace(/[:.]/g, '-')}.json`)

  console.log('Thu bằng chứng cổng trợ lý — MINI-SPEC I1 §B2/§B3')
  console.log('Cơ sở dữ liệu dùng một lần, KHÔNG đụng máy chủ đang chạy.\n')

  const ket = await thuBangChung({
    nhaCungCap: {
      baseUrl: process.env.ASSIST_EVAL_BASE_URL || '',
      apiKey: process.env.ASSIST_EVAL_KEY || '',
      model: process.env.ASSIST_EVAL_MODEL || '',
      type: process.env.ASSIST_EVAL_TYPE || '',
    },
    duongRa,
  })

  console.log(`\nSố lượt: ${ket.tomTat.so_luot} `
    + `(gọi mô hình thật: ${ket.tomTat.so_luot_goi_mo_hinh_that})`)
  console.log(`Tổng Vox đã trừ: ${ket.tomTat.tong_vox_da_tru}`)
  if (ket.viPham.length) {
    console.log(`\n${ket.viPham.length} BẤT BIẾN BỊ PHÁ:`)
    for (const v of ket.viPham) console.log(`  ✗ ${v}`)
  } else {
    console.log('\nMọi bất biến đều đạt.')
  }
  return ket.ok ? 0 : 1
}

if (require.main === module) {
  main().then((ma) => process.exit(ma)).catch((e) => {
    console.error(`\nHỏng: ${e.message}`)
    process.exit(2)
  })
}

module.exports = { thuBangChung, MAU }
