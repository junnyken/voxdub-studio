'use strict'

/**
 * Cổng đo A/B của MINI-SPEC I7 §6 — BA cấu hình, không phải hai.
 *
 * Vì sao ba: §A (chỉ đạo hình ảnh biết nhịp) và §8 (người viết kịch bản biết
 * khuôn diễn đạt của nguồn) là HAI thay đổi chất lượng chồng lên nhau. Đo
 * chung thì một kết quả tốt lên không nói được cái nào có tác dụng — và một
 * kết quả xấu đi không nói được cái nào phải lùi.
 *
 *     gốc      — như trước I7
 *     +§A      — chỉ đạo hình ảnh nhận thời lượng + nhịp
 *     +§A+§8   — thêm: người viết kịch bản nhận khuôn chữ/khuôn nói của nguồn
 *
 * **Không cần cờ bật/tắt trong mã production.** Cả hai lời nhắc đã bỏ qua
 * trường rỗng, nên ba cấu hình dựng được bằng cách BỎ BỚT trường ở đầu vào —
 * đo được đúng mã đang chạy, không đo một nhánh chỉ tồn tại cho phép đo.
 *
 *     node scripts/do-ab-i7.js --kho          # dựng lời nhắc, KHÔNG gọi mô hình
 *     node scripts/do-ab-i7.js --ra bang.json # chạy thật (TỐN VOX)
 *
 * Chạy thật cần cùng ba biến với bộ thu bằng chứng:
 *     export $(grep -E '^ASSIST_EVAL_' .env | xargs -d '\n')
 *
 * Cái đo ĐƯỢC BẰNG MÁY và cái KHÔNG:
 *
 *   máy đo được — bố cục có bám nhịp không (tỉ lệ đoạn ngắn được gán cắt
 *   thẳng, đoạn dài được gán chuyển mềm), số đoạn trả đúng, ngân sách từ có
 *   vượt không, giá token.
 *
 *   máy KHÔNG đo được — kịch bản có HAY hơn không. Bộ này ghi ra một tệp
 *   CHẤM MÙ: ba bản kịch bản xáo thứ tự, dán nhãn A/B/C, khoá giải nằm ở tệp
 *   riêng. Tự chấm khi biết bản nào là bản mình vừa viết thì không phải đo,
 *   đó là tự khen.
 */
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')

const assistPrompts = require('../src/prompts/assist')

/** Ngưỡng §A2 — suy từ chi phí chuyển cảnh thật, xem `TEST_LOG` I7 §A4. */
const GIAY_NGAN = 3.0
const GIAY_DAI = 6.0

/** Mã chuyển cảnh KHÔNG ăn thời gian (khớp catalog: `cat_thang` -> `khong`). */
const CHUYEN_CUNG = new Set(['cat_thang'])

const CAU_HINH = [
  { ma: 'goc', ten: 'gốc (như trước I7)', nhip: false, khuon: false },
  { ma: 'a', ten: '+§A (chỉ đạo biết nhịp)', nhip: true, khuon: false },
  { ma: 'a8', ten: '+§A+§8 (thêm khuôn nguồn)', nhip: true, khuon: true },
]

/**
 * Đầu vào của MỘT cấu hình, dựng bằng cách BỎ BỚT — không bằng cờ.
 *
 * `structuredClone` chứ không sửa tại chỗ: ba cấu hình phải xuất phát từ
 * cùng một dữ liệu, và một lượt sửa nhầm sẽ làm cấu hình sau đo trên đầu vào
 * của cấu hình trước mà không ai thấy.
 */
function dungDauVao(goc, cauHinh, { choChiDao = false } = {}) {
  const ra = structuredClone(goc)
  ra.beats = (ra.beats || []).map((b) => {
    const m = { ...b }
    if (!cauHinh.khuon) { delete m.khuonChu; delete m.khuonNoi }
    if (choChiDao && !cauHinh.nhip) { m.giay = null; m.nhip = '' }
    return m
  })
  return ra
}

/** Điểm §A: bố cục có bám nhịp không. Chỉ tính trên đoạn CÓ thời lượng. */
function chamBamNhip(giayTungDoan, maChuyenTungMoi) {
  let ngan = 0; let nganDung = 0
  let dai = 0; let daiDung = 0
  // Mối nối thứ j dẫn VÀO đoạn j+1 (quy ước I5 §11a).
  maChuyenTungMoi.forEach((ma, j) => {
    const g = giayTungDoan[j + 1]
    if (!Number.isFinite(g)) return
    if (g < GIAY_NGAN) { ngan += 1; if (CHUYEN_CUNG.has(ma)) nganDung += 1 }
    else if (g > GIAY_DAI) { dai += 1; if (!CHUYEN_CUNG.has(ma)) daiDung += 1 }
  })
  return {
    doanNgan: ngan,
    nganDuocCatThang: ngan ? Math.round((nganDung / ngan) * 100) : null,
    doanDai: dai,
    daiDuocChuyenMem: dai ? Math.round((daiDung / dai) * 100) : null,
  }
}

/** Điểm rào chắn: những thứ I7 KHÔNG được phép làm hỏng. */
function chamRaoChan(kichBan, soDoanMongMuon, giayTungDoan) {
  const doan = (kichBan && kichBan.beats) || []
  let vuotNganSach = 0
  doan.forEach((b, i) => {
    const soTu = assistPrompts.tranDoDaiBeat
      ? assistPrompts.tranDoDaiBeat(giayTungDoan[i])
      : null
    if (!soTu) return
    const dem = String(b.voiceoverTextVi || '').trim().split(/\s+/).filter(Boolean).length
    if (dem > soTu) vuotNganSach += 1
  })
  return {
    duSoDoan: doan.length === soDoanMongMuon,
    soDoan: doan.length,
    doanVuotNganSachTu: vuotNganSach,
  }
}

function xaoTron(ds, hat) {
  const r = [...ds]
  let s = hat
  for (let i = r.length - 1; i > 0; i -= 1) {
    s = (s * 1103515245 + 12345) & 0x7fffffff
    const j = s % (i + 1)
    ;[r[i], r[j]] = [r[j], r[i]]
  }
  return r
}

/** Hai tệp: bản chấm mù (xáo, dán nhãn) và KHOÁ GIẢI (để riêng). */
function ghiChamMu(thuMuc, ketQua) {
  const hat = crypto.randomInt(1e9)
  const nhan = ['A', 'B', 'C']
  const xao = xaoTron(ketQua.map((k, i) => ({ i, ...k })), hat)
  const bai = xao.map((k, vt) => ({ nhan: nhan[vt], kichBan: k.kichBan }))
  const khoa = xao.map((k, vt) => ({ nhan: nhan[vt], cauHinh: k.cauHinh }))
  fs.mkdirSync(thuMuc, { recursive: true })
  const tBai = path.join(thuMuc, 'cham-mu.json')
  const tKhoa = path.join(thuMuc, 'cham-mu-KHOA.json')
  fs.writeFileSync(tBai, JSON.stringify(bai, null, 2), 'utf8')
  fs.writeFileSync(tKhoa, JSON.stringify(khoa, null, 2), 'utf8')
  return { tBai, tKhoa }
}

module.exports = {
  CAU_HINH, GIAY_NGAN, GIAY_DAI, CHUYEN_CUNG,
  dungDauVao, chamBamNhip, chamRaoChan, xaoTron, ghiChamMu,
}

// ------------------------------------------------------------ chạy tay ---

if (require.main === module) {
  const kho = process.argv.includes('--kho')
  if (!kho) {
    console.error('Chạy thật chưa nối — cần blueprint + brand thật và khoá mô hình.')
    console.error('Dùng --kho để kiểm ba cấu hình dựng đúng mà KHÔNG tốn Vox.')
    process.exit(2)
  }

  const beat = (i) => ({
    beatType: ['hook', 'problem', 'proof', 'cta'][i % 4],
    giay: [2.0, 4.0, 7.0, 2.5][i % 4],
    nhip: 'Cắt nhanh, mỗi câu một ý',
    narrativeFunctionVi: 'Mở đầu bằng câu cảnh báo ngắn rồi hứa lợi ích',
    pacingNoteVi: 'Cắt nhanh, mỗi câu một ý',
    khuonChu: 'Chữ to hiện từng cụm 2-3 từ',
    khuonNoi: 'Câu hỏi ngắn rồi ngắt một nhịp',
    loiDoc: 'Sáng nào cũng vội, bữa sáng qua loa.',
    visualBrief: 'Cận cảnh sản phẩm trên bàn',
  })
  const goc = {
    catalogVersion: 2,
    brand: { tenBrand: 'Mắt Bão', toneGiong: 'Thẳng thắn',
      rangBuocKhongDuocNoi: [], nepChiDao: [] },
    beats: Array.from({ length: 8 }, (_, i) => beat(i)),
  }

  console.log('Ba cấu hình — dựng bằng cách BỎ BỚT trường, không bằng cờ:\n')
  for (const ch of CAU_HINH) {
    const vaoH3 = dungDauVao(goc, ch)
    const vaoI3 = dungDauVao(goc, ch, { choChiDao: true })
    const uH3 = assistPrompts.getTask('brand_script_rewrite').buildUser(vaoH3)
    const uI3 = assistPrompts.getTask('scene_director').buildUser(vaoI3)
    console.log(`  ${ch.ten}`)
    console.log(`    kịch bản : ${String(uH3.length).padStart(5)} ký tự · `
      + `khuôn nguồn ${/khuôn nói nguồn/.test(uH3) ? 'CÓ ' : '—  '}`)
    console.log(`    chỉ đạo  : ${String(uI3.length).padStart(5)} ký tự · `
      + `thời lượng ${/giây/.test(uI3) ? 'CÓ ' : '—  '}`)
  }
  console.log('\nChấm bám nhịp (thử trên một bản chỉ đạo giả):')
  const giay = goc.beats.map((b) => b.giay)
  for (const [ten, ma] of [
    ['chọn mù (mờ chồng hết)', Array(7).fill('fade_nhe')],
    ['bám nhịp (ngắn->cắt thẳng)', giay.slice(1).map((g) => (g < GIAY_NGAN ? 'cat_thang' : 'fade_nhe'))],
  ]) {
    const d = chamBamNhip(giay, ma)
    console.log(`  ${ten.padEnd(28)} ngắn đúng ${String(d.nganDuocCatThang).padStart(3)}% `
      + `(${d.doanNgan} đoạn) · dài đúng ${String(d.daiDuocChuyenMem).padStart(3)}% (${d.doanDai} đoạn)`)
  }
}
