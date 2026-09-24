'use strict'

/**
 * Bộ đo A/B của I7 §6 — chính nó phải đúng trước đã.
 *
 * Một phép đo sai còn tệ hơn không đo: nó cho một con số trông như bằng
 * chứng. Hai chỗ dễ sai nhất, và cả hai đều im lặng:
 *
 *   1. **Ba cấu hình không thật sự khác nhau** — nếu `dungDauVao` sửa tại chỗ
 *      thay vì sao chép, cấu hình sau đo trên đầu vào đã bị cấu hình trước
 *      làm bẩn, và ba cột số trông hợp lý nhưng vô nghĩa.
 *   2. **Ánh xạ mối nối ↔ đoạn bị đảo** — quy ước I5 §11a là mối nối thứ j
 *      dẫn VÀO đoạn j+1. Đảo chiều thì điểm "bám nhịp" chấm đúng thành sai.
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const bo = require('../scripts/do-ab-i7')

const beatDay = (them = {}) => ({
  beatType: 'hook', giay: 2.0, nhip: 'Cắt nhanh',
  khuonChu: 'CHU-MAU', khuonNoi: 'NOI-MAU',
  loiDoc: 'Câu mẫu.', visualBrief: 'Cận cảnh', ...them,
})

const gocMau = () => ({
  catalogVersion: 2,
  brand: { tenBrand: 'Mắt Bão', rangBuocKhongDuocNoi: [], nepChiDao: [] },
  beats: [beatDay(), beatDay({ giay: 7 })],
})

// ------------------------------------------------- ba cấu hình khác nhau ---

test('cấu hình "gốc" bỏ CẢ khuôn lẫn nhịp', () => {
  const goc = gocMau()
  const h3 = bo.dungDauVao(goc, bo.CAU_HINH[0])
  const i3 = bo.dungDauVao(goc, bo.CAU_HINH[0], { choChiDao: true })
  assert.equal(h3.beats[0].khuonNoi, undefined)
  assert.equal(i3.beats[0].giay, null)
  assert.equal(i3.beats[0].nhip, '')
})

test('cấu hình "+§A" giữ nhịp nhưng vẫn bỏ khuôn', () => {
  const goc = gocMau()
  const h3 = bo.dungDauVao(goc, bo.CAU_HINH[1])
  const i3 = bo.dungDauVao(goc, bo.CAU_HINH[1], { choChiDao: true })
  assert.equal(h3.beats[0].khuonNoi, undefined, '+§A không được kèm §8')
  assert.equal(i3.beats[0].giay, 2.0)
})

test('cấu hình "+§A+§8" giữ đủ', () => {
  const goc = gocMau()
  const h3 = bo.dungDauVao(goc, bo.CAU_HINH[2])
  const i3 = bo.dungDauVao(goc, bo.CAU_HINH[2], { choChiDao: true })
  assert.equal(h3.beats[0].khuonNoi, 'NOI-MAU')
  assert.equal(i3.beats[0].giay, 2.0)
})

test('dựng cấu hình KHÔNG làm bẩn dữ liệu gốc', () => {
  // Sửa tại chỗ thì cấu hình sau đo trên đầu vào đã bị cấu hình trước cắt
  // mất — ba cột số trông hợp lý nhưng vô nghĩa.
  const goc = gocMau()
  for (const ch of bo.CAU_HINH) {
    bo.dungDauVao(goc, ch)
    bo.dungDauVao(goc, ch, { choChiDao: true })
  }
  assert.equal(goc.beats[0].khuonNoi, 'NOI-MAU', 'gốc bị cắt mất khuôn')
  assert.equal(goc.beats[0].giay, 2.0, 'gốc bị xoá mất thời lượng')
})

// ------------------------------------------------------ chấm bám nhịp ---

test('mối nối thứ j chấm theo đoạn j+1 — đúng quy ước I5 §11a', () => {
  // 3 đoạn: [ngắn 2s, dài 7s, ngắn 2s] ⇒ 2 mối nối.
  // Mối 0 dẫn VÀO đoạn 1 (7s, dài) · mối 1 dẫn VÀO đoạn 2 (2s, ngắn).
  const giay = [2, 7, 2]
  const d = bo.chamBamNhip(giay, ['fade_nhe', 'cat_thang'])
  assert.equal(d.doanDai, 1)
  assert.equal(d.daiDuocChuyenMem, 100, 'mối 0 (mềm) phải chấm cho đoạn 7s')
  assert.equal(d.doanNgan, 1)
  assert.equal(d.nganDuocCatThang, 100, 'mối 1 (cắt) phải chấm cho đoạn 2s')

  // Đảo lại thì phải chấm SAI hết — nếu không, phép chấm mù chiều.
  const dao = bo.chamBamNhip(giay, ['cat_thang', 'fade_nhe'])
  assert.equal(dao.daiDuocChuyenMem, 0)
  assert.equal(dao.nganDuocCatThang, 0)
})

test('đoạn KHÔNG có thời lượng bị bỏ khỏi phép chấm, không tính là sai', () => {
  const d = bo.chamBamNhip([2, null, 2], ['fade_nhe', 'cat_thang'])
  assert.equal(d.doanDai, 0)
  assert.equal(d.daiDuocChuyenMem, null, 'không có mẫu thì phải là null, không phải 0%')
  assert.equal(d.doanNgan, 1)
})

test('đoạn ở GIỮA hai ngưỡng không tính cho bên nào', () => {
  // 4,5 giây: không ngắn (<3), không dài (>6). Ép nó vào một phía là bịa
  // một tiêu chí không có trong spec.
  const d = bo.chamBamNhip([2, 4.5], ['fade_nhe'])
  assert.equal(d.doanNgan, 0)
  assert.equal(d.doanDai, 0)
  // KHÔNG mẫu nào ⇒ phải là `null`, KHÔNG phải 0%. Trả 0% cho một phép đo
  // chưa có mẫu là dựng ra một con số trông như kết quả xấu — và nó sẽ được
  // đem so với 0% của "chọn mù", hai thứ hoàn toàn khác nghĩa.
  assert.equal(d.nganDuocCatThang, null,
    '0% và "chưa có mẫu" phải phân biệt được')
  assert.equal(d.daiDuocChuyenMem, null)
})

test('chọn mù (mờ chồng hết) phải ra điểm ngắn THẤP', () => {
  const giay = [2, 2, 2, 7]
  const mu = bo.chamBamNhip(giay, ['fade_nhe', 'fade_nhe', 'fade_nhe'])
  assert.equal(mu.nganDuocCatThang, 0, 'phép chấm không phân biệt được chọn mù')
})

// ------------------------------------------------------------ chấm mù ---

test('tệp chấm mù KHÔNG chứa khoá giải', () => {
  const thuMuc = fs.mkdtempSync(path.join(os.tmpdir(), 'i7ab-'))
  const { tBai, tKhoa } = bo.ghiChamMu(thuMuc, [
    { cauHinh: 'goc', kichBan: { beats: [{ voiceoverTextVi: 'AAA' }] } },
    { cauHinh: 'a', kichBan: { beats: [{ voiceoverTextVi: 'BBB' }] } },
    { cauHinh: 'a8', kichBan: { beats: [{ voiceoverTextVi: 'CCC' }] } },
  ])
  const bai = fs.readFileSync(tBai, 'utf8')
  assert.ok(!/goc|a8/.test(bai), `bản chấm lộ cấu hình: ${bai.slice(0, 200)}`)
  assert.match(bai, /"nhan": "A"/)
  const khoa = JSON.parse(fs.readFileSync(tKhoa, 'utf8'))
  assert.equal(khoa.length, 3)
  assert.deepEqual([...khoa.map((k) => k.cauHinh)].sort(), ['a', 'a8', 'goc'])
})

test('xáo trộn giữ ĐỦ phần tử, không mất không nhân đôi', () => {
  for (const hat of [1, 7, 12345, 999999]) {
    const ra = bo.xaoTron(['x', 'y', 'z'], hat)
    assert.deepEqual([...ra].sort(), ['x', 'y', 'z'], `hạt ${hat}`)
  }
})
