'use strict'

/**
 * Xuất/khôi phục toàn bộ dữ liệu MongoDB (mini-spec V48, docs/PLAN.md).
 *
 * Vì sao cần: bản sao lưu hàng ngày trước đây là TÍNH NĂNG CỦA COOLIFY
 * (docs/PLAN.md ghi "ĐÃ XONG 2026-08-15") — chuyển sang Vibe Host
 * 2026-08-17 là mất trắng, không phải mất một chút. DB này giữ ví/credit
 * của khách, đơn hàng, activation key và khoá nhà cung cấp AI đã mã hoá;
 * ngày chuyển nền tảng đã xoá nhầm 1 lần và mất sạch.
 *
 * Vì sao KHÔNG dump ra đĩa rồi giữ lại: nền tảng hiện tại không có volume
 * bền vững — file dump nằm trong container sẽ bay theo lần redeploy kế
 * tiếp, tức là một bản sao lưu giả vờ. Nên đường duy nhất trung thực là
 * STREAM ra ngoài cho người gọi tự cất giữ.
 *
 * Định dạng: NDJSON nén gzip, mỗi dòng là 1 bản ghi
 * `{"__collection":"...", "doc":{...}}`, tuần tự bằng **EJSON** (không phải
 * JSON thường) để giữ nguyên kiểu `ObjectId`/`Date`/`Decimal` — JSON thường
 * biến `ObjectId` thành chuỗi và khôi phục xong là hỏng mọi quan hệ.
 * NDJSON (không phải 1 mảng JSON khổng lồ) để cả xuất lẫn nhập đều chạy
 * theo dòng, không bao giờ giữ cả DB trong RAM — cùng nguyên tắc V44.
 *
 * KHÔNG có trong bản sao lưu: `APP_ENCRYPTION_KEY`. Khoá nhà cung cấp AI
 * trong DB đã mã hoá bằng khoá đó và khoá đó chỉ nằm ở biến môi trường —
 * mất file dump KHÔNG đồng nghĩa lộ khoá nhà cung cấp, nhưng khôi phục sang
 * máy chủ có `APP_ENCRYPTION_KEY` khác thì các khoá đó thành rác (phải nhập
 * lại). Ghi rõ để không ai tưởng dump là đủ để dựng lại toàn bộ.
 */
const mongoose = require('mongoose')
const { EJSON } = require('bson')

/** Collection nội bộ của Mongo, không phải dữ liệu của mình. */
function isSystemCollection(name) {
  return name.startsWith('system.')
}

/**
 * Sinh từng dòng NDJSON của toàn bộ DB. Generator (không trả mảng) để
 * người gọi pipe thẳng vào gzip → HTTP response, giữ bộ nhớ phẳng bất kể
 * DB to cỡ nào.
 */
async function* exportLines() {
  const { db } = mongoose.connection
  if (!db) throw new Error('Chưa kết nối MongoDB')

  const collections = (await db.listCollections().toArray())
    .map((c) => c.name)
    .filter((n) => !isSystemCollection(n))
    .sort()

  // Dòng đầu là siêu dữ liệu: biết bản dump sinh lúc nào, từ DB nào, gồm
  // những collection gì — kiểm tra được tính đầy đủ mà không phải đọc hết file.
  yield `${EJSON.stringify({
    __meta: {
      version: 1,
      createdAt: new Date(),
      database: db.databaseName,
      collections,
    },
  })}\n`

  for (const name of collections) {
    const cursor = db.collection(name).find({}, { noCursorTimeout: false })
    // eslint-disable-next-line no-await-in-loop, no-restricted-syntax
    for await (const doc of cursor) {
      yield `${EJSON.stringify({ __collection: name, doc })}\n`
    }
  }
}

/**
 * Nhập ngược một dòng NDJSON đã xuất. Trả về thống kê để người gọi đối
 * chiếu với bản gốc — khôi phục mà không đếm lại thì không biết có mất bản
 * ghi nào không.
 *
 * `mode: 'wipe'` xoá sạch collection trước khi nhập (khôi phục thật sự);
 * mặc định `'upsert'` ghi đè theo `_id` và giữ nguyên bản ghi lạ — an toàn
 * hơn khi chỉ muốn vá lại phần thiếu.
 */
async function importLines(lineIterable, { mode = 'upsert' } = {}) {
  const { db } = mongoose.connection
  if (!db) throw new Error('Chưa kết nối MongoDB')

  const counts = {}
  const wiped = new Set()
  let meta = null

  for await (const raw of lineIterable) {
    const line = raw.toString().trim()
    if (!line) continue
    const parsed = EJSON.parse(line)
    if (parsed.__meta) { meta = parsed.__meta; continue }

    const { __collection: name, doc } = parsed
    if (!name || !doc) continue

    if (mode === 'wipe' && !wiped.has(name)) {
      await db.collection(name).deleteMany({})
      wiped.add(name)
    }
    await db.collection(name).replaceOne({ _id: doc._id }, doc, { upsert: true })
    counts[name] = (counts[name] || 0) + 1
  }

  return { meta, counts, total: Object.values(counts).reduce((a, b) => a + b, 0) }
}

module.exports = { exportLines, importLines }
