'use strict'

/**
 * Enum `action` của JobResult phải phủ MỌI giá trị `remember()` được gọi với.
 *
 * Bug thật, 22/8/2026 — chuỗi hậu quả dài nhất trong dự án tới nay:
 *
 * 1. `assist` (V89) và `product_scene` (C1) thêm route mà quên thêm vào enum.
 * 2. Mongoose ném lỗi validation; `remember()` ném tiếp ra ngoài.
 * 3. Route chết **SAU KHI** đã gọi mô hình và đã trừ tiền.
 * 4. Sổ máy chủ ghi lượt gọi "thành công" (UsageLog viết trước), ví trừ 30
 *    Vox, còn app nhận về lỗi 500 và báo "Không dựng được ảnh nào".
 * 5. Chủ dự án bấm ba lượt, mất 90 Vox, và không lượt nào thấy được ảnh.
 *
 * Không có gì trong bộ test cũ chạm tới chỗ này vì nó chỉ vỡ khi có DB thật
 * và một `action` mới — nên nay có hai lớp: đối chiếu danh sách, và một lớp
 * an toàn để lần sau lỡ quên thì chỉ mất bộ nhớ đệm chứ không mất tiền.
 */
const test = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const { setTestEnv, startDb, stopDb, clearDb } = require('./helpers/db')

setTestEnv()

const JobResult = require('../src/models/JobResult')

const GOC = path.join(__dirname, '..')

test.before(startDb)
test.after(stopDb)
test.beforeEach(clearDb)

// Mọi tệp route CÓ THỂ gọi remember() với một `action` mới — mini-spec H2
// thêm flow-blueprints.js dùng lại đúng remember() (nay ở
// assist-billing.service.js) thay vì viết lại, nên phải quét CẢ file đó,
// không chỉ ai.js như trước khi có H2.
const TEP_CO_THE_GOI_REMEMBER = [
  path.join('src', 'routes', 'ai.js'),
  path.join('src', 'routes', 'flow-blueprints.js'),
  path.join('src', 'routes', 'brand-scripts.js'),
]

/** Mọi `action` mà mã nguồn thật sự gọi `remember()` với. */
function cacActionDangDung() {
  const ra = new Set()
  // Bỏ dòng khai báo hàm: nó cũng khớp `remember(` nhưng không phải lượt gọi.
  const re = /remember\(\s*[\w.]+\s*,\s*[\w.]+\s*,\s*'([^']+)'/g
  for (const tep of TEP_CO_THE_GOI_REMEMBER) {
    const duong = path.join(GOC, tep)
    if (!fs.existsSync(duong)) continue
    const src = fs.readFileSync(duong, 'utf8')
    let m
    while ((m = re.exec(src)) !== null) ra.add(m[1])
  }
  return [...ra].sort()
}

test('enum phủ đủ mọi action mã nguồn đang dùng', () => {
  const trongMa = cacActionDangDung()
  const trongEnum = JobResult.schema.path('action').enumValues

  assert.ok(trongMa.length >= 7, `chỉ tìm thấy ${trongMa.length} action — regex hỏng?`)
  const thieu = trongMa.filter((a) => !trongEnum.includes(a))
  assert.deepStrictEqual(thieu, [],
    `route gọi remember() với ${thieu.join(', ')} mà enum không có — lượt gọi `
    + 'sẽ chết SAU KHI đã trừ tiền')
})

test('hai giá trị đã gây sự cố phải có mặt', () => {
  const trongEnum = JobResult.schema.path('action').enumValues
  assert.ok(trongEnum.includes('assist'), 'thiếu assist (V89)')
  assert.ok(trongEnum.includes('product_scene'), 'thiếu product_scene (C1)')
})

test('lưu được kết quả product_scene thật vào cơ sở dữ liệu', async () => {
  await JobResult.create({
    jobId: 'job-1', fingerprint: 'may-1', action: 'product_scene',
    result: { image: { mimeType: 'image/jpeg', data: 'xx' } }, creditCharged: 30,
  })
  const doc = await JobResult.findOne({ jobId: 'job-1' }).lean()
  assert.strictEqual(doc.action, 'product_scene')
})

test('action lạ vẫn bị chặn — enum không được nới thành "cái gì cũng nhận"', async () => {
  await assert.rejects(
    () => JobResult.create({
      jobId: 'job-2', fingerprint: 'may-1', action: 'tac_vu_khong_co_that',
      result: {}, creditCharged: 0,
    }),
    /enum/i)
})


test('remember() KHÔNG được ném lỗi ra ngoài — lớp đệm không giết lượt gọi', () => {
  const { thanHam, boChuoi } = require('./helpers/doc-ma')
  // mini-spec H2: định nghĩa thật của remember() chuyển sang
  // assist-billing.service.js để flow-blueprints.js dùng lại — ai.js giờ chỉ
  // còn CALL SITE, không còn định nghĩa hàm.
  const than = boChuoi(thanHam('src/services/assist-billing.service.js', 'remember'))

  assert.match(than, /catch/, 'không có nhánh bắt lỗi')
  assert.doesNotMatch(than, /throw/,
    'còn ném lỗi ra ngoài: lượt gọi đã trừ tiền sẽ chết vì một lỗi ghi đệm')
  assert.match(than, /error\(/,
    'nuốt lỗi mà không kêu tiếng nào thì lần sau lại mất cả ngày đi tìm')
})

// ---------------------------------------------------------------------------
// B1 + B6 — hai lỗi tìm ra khi rà backlog Phase H (11/09/2026).

test('B1: nhánh nhớ-đệm KHÔNG được đọc biến `result` chưa khai báo', () => {
  // `let result` nằm ở NỬA DƯỚI của handler `/assist`, còn nhánh đọc-từ-đệm
  // ở nửa trên. JS nâng `let` lên đầu khối nhưng để nó trong "vùng chết",
  // nên đọc ở đó ném ReferenceError NGAY LÚC dựng đối số — `.catch()` gắn
  // vào kết quả của `create(...)` không bắt được cú ném xảy ra TRƯỚC khi hàm
  // được gọi ⇒ 500. Và vì khoá đệm băm theo NỘI DUNG, cú 500 đó lặp lại mãi
  // mãi cho đúng bộ ảnh ấy.
  const h = require('./helpers/doc-ma')
  const src = h.doc(path.join('src', 'routes', 'ai.js'))
  const i = src.indexOf('const cuNoiDung = await replay(khoaNoiDung')
  assert.ok(i > 0, 'không thấy nhánh nhớ-đệm theo nội dung')
  const j = src.indexOf('return { ...cuNoiDung', i)
  const nhanh = src.slice(i, j)

  assert.ok(!/\bresult\./.test(h.boChuThich(nhanh)),
    'nhánh nhớ-đệm đọc `result` — biến đó chưa được khai báo ở đây')
  assert.ok(nhanh.includes('cuNoiDung.results'),
    'phải đọc từ kết quả ĐÃ LƯU (`cuNoiDung`)')
})

test('B6: ghi sổ ở nhánh THÀNH CÔNG không bao giờ được giết lượt gọi', () => {
  // `UsageLog.create` trần trong `Promise.all` đứng SAU `charge()`: MongoDB
  // trục trặc đúng khoảng giữa trừ tiền và ghi sổ ⇒ route ném ⇒ người dùng
  // nhận 500, mất kết quả, mà TIỀN ĐÃ TRỪ. Nhánh LỖI ngay trên lại có
  // `.catch(() => {})` — ghi sổ hỏng lúc thất bại thì tha, lúc thành công
  // thì giết cả lượt.
  const h = require('./helpers/doc-ma')
  const conSot = []
  for (const tep of ['ai.js', 'flow-blueprints.js', 'brand-scripts.js']) {
    const src = h.doc(path.join('src', 'routes', tep))
    const re = /await Promise\.all\(\[([\s\S]*?)\n {4}\]\)/g
    let m
    while ((m = re.exec(src)) !== null) {
      const khoi = m[1]
      if (!/UsageLog\.create\(|models\/UsageLog'\)\.create\(/.test(khoi)) continue
      const sau = khoi.split(/UsageLog'\)\.create\(|UsageLog\.create\(/)[1] || ''
      if (!sau.includes('.catch(')) {
        conSot.push(`${tep}: UsageLog.create trần trong Promise.all`)
      }
    }
  }
  assert.deepStrictEqual(conSot, [],
    'dùng `ghiSoDung(...)` — nó không bao giờ ném, và kêu to khi hỏng')
})

test('B6: ghiSoDung nuốt lỗi nhưng KÊU TO, không im lặng', async () => {
  const billing = require('../src/services/assist-billing.service')
  const ghi = []
  // Model chưa nối DB trong lượt test này ⇒ create() ném thật.
  await billing.ghiSoDung({ fingerprint: 'x', action: 'assist' },
    { error: (...a) => ghi.push(a) })
  assert.equal(ghi.length, 1, 'hỏng mà không ghi lại gì là nuốt im lặng')
  assert.match(String(ghi[0][1]), /ghiSoDung\(\) hỏng/)
})
