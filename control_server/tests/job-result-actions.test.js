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

/** Mọi `action` mà mã nguồn thật sự gọi `remember()` với. */
function cacActionDangDung() {
  const src = fs.readFileSync(path.join(GOC, 'src', 'routes', 'ai.js'), 'utf8')
  const ra = new Set()
  // Bỏ dòng khai báo hàm: nó cũng khớp `remember(` nhưng không phải lượt gọi.
  const re = /remember\(\s*[\w.]+\s*,\s*[\w.]+\s*,\s*'([^']+)'/g
  let m
  while ((m = re.exec(src)) !== null) ra.add(m[1])
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
  const than = boChuoi(thanHam('src/routes/ai.js', 'remember'))

  assert.match(than, /catch/, 'không có nhánh bắt lỗi')
  assert.doesNotMatch(than, /throw/,
    'còn ném lỗi ra ngoài: lượt gọi đã trừ tiền sẽ chết vì một lỗi ghi đệm')
  assert.match(than, /error\(/,
    'nuốt lỗi mà không kêu tiếng nào thì lần sau lại mất cả ngày đi tìm')
})
