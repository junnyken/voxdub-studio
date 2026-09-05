'use strict'

/**
 * Đọc mã nguồn để kiểm "đã nối dây chưa" — làm cho tử tế (mini-spec C8).
 *
 * `control_server` cố ý chỉ có test thuần (không dựng Mongo), nên đường duy
 * nhất kiểm được một route có gọi đúng thứ nó phải gọi hay không là đọc chính
 * mã nguồn. Cách đó rẻ và bắt được nhiều lỗi thật — nhưng viết tay bằng
 * `indexOf` thì **hỏng theo bốn kiểu**, và trong một ngày tôi mắc đủ cả bốn:
 *
 * 1. `indexOf(a) < indexOf(b)` vẫn đúng khi `a` KHÔNG tồn tại (-1 nhỏ hơn
 *    mọi vị trí) → test xanh ngay cả khi gỡ sạch thứ cần kiểm.
 * 2. Khớp phải chữ nằm trong LỜI CHÚ THÍCH, không phải mã chạy.
 * 3. Cắt thân hàm quá rộng nên đọc lây sang hàm phía sau → đỏ oan.
 * 4. Tìm tên hàm trần nên khớp luôn dòng `def`/`function` của chính nó.
 *
 * Không có bộ phân tích cú pháp JS trong dự án (và thêm một phụ thuộc chỉ để
 * chạy test là cái giá không đáng), nên đây là lớp mỏng làm đúng bốn việc:
 * bỏ chú thích trước khi soi, cắt thân hàm tới hàm kế tiếp, bắt buộc CÓ MẶT
 * trước khi so thứ tự, và tìm lượt gọi có tên đầy đủ.
 */
const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert')

const GOC = path.join(__dirname, '..', '..')

/**
 * Hai tầng, cố ý tách rời:
 *
 * - `boChuThich` bỏ CHÚ THÍCH nhưng GIỮ chuỗi — dùng để TÌM và CẮT, vì đường
 *   dẫn route nằm trong chuỗi (`fastify.post('/product-scene'`). Bản đầu gộp
 *   cả hai việc nên không tìm nổi route nào, và chính test của helper bắt
 *   được.
 * - `boChuoi` moi ruột chuỗi — dùng lúc SOI, để "gọi hàm X" không bị tính khi
 *   X chỉ nằm trong một câu thông báo.
 */
function boChuThich(src) {
  let ra = ''
  let i = 0
  const n = src.length
  while (i < n) {
    const hai = src.slice(i, i + 2)
    if (hai === '//') {
      while (i < n && src[i] !== '\n') i += 1
      continue
    }
    if (hai === '/*') {
      i += 2
      while (i < n && src.slice(i, i + 2) !== '*/') i += 1
      i += 2
      continue
    }
    ra += src[i]
    i += 1
  }
  return ra
}

/** Moi ruột chuỗi, giữ dấu mở/đóng để cấu trúc không vỡ. */
function boChuoi(src) {
  let ra = ''
  let i = 0
  while (i < src.length) {
    const c = src[i]
    if (c === "'" || c === '"' || c === '`') {
      ra += c
      i += 1
      while (i < src.length && src[i] !== c) {
        if (src[i] === '\\') i += 1
        i += 1
      }
      ra += c
      i += 1
      continue
    }
    ra += c
    i += 1
  }
  return ra
}

function doc(duong) {
  return fs.readFileSync(path.join(GOC, duong), 'utf8')
}

/** Mã của một tệp, đã bỏ chú thích và ruột chuỗi. */
function ma(duong) {
  return boChuThich(doc(duong))
}

/**
 * Thân của MỘT hàm, cắt tới khai báo hàm kế tiếp cùng cấp.
 *
 * Nhận cả `async function ten`, `function ten` và `fastify.post('/duong'`.
 */
function thanHam(duong, ten) {
  const src = ma(duong)
  const moc = ten.startsWith('/')
    ? new RegExp(`fastify\\.\\w+\\(\\s*'${ten.replace(/[/]/g, '\\/')}'`)
    : new RegExp(`(async\\s+)?function\\s+${ten}\\b`)
  const m = moc.exec(src)
  assert.ok(m, `không thấy ${ten} trong ${duong}`)
  const dau = m.index
  const ke = ten.startsWith('/')
    ? /fastify\.\w+\(\s*'/g
    : /(async\s+)?function\s+\w+/g
  ke.lastIndex = dau + m[0].length
  const sau = ke.exec(src)
  return src.slice(dau, sau ? sau.index : src.length)
}

/** `a` phải xuất hiện, `b` phải xuất hiện, và `a` phải đứng trước `b`. */
function truoc(than, a, b, vi_sao) {
  const sach = boChuoi(than)
  const ia = sach.indexOf(a)
  const ib = sach.indexOf(b)
  assert.ok(ia >= 0, `không thấy «${a}»`)
  assert.ok(ib >= 0, `không thấy «${b}»`)
  assert.ok(ia < ib, vi_sao || `«${a}» phải đứng trước «${b}»`)
}

/** Đếm số LƯỢT GỌI `ten(` — không đếm nhầm dòng khai báo hàm cùng tên. */
function demGoi(than, ten) {
  const sach = boChuoi(than)
  const re = new RegExp(`(?<!function\\s)(?<!\\.)\\b${ten.replace(/\./g, '\\.')}\\s*\\(`, 'g')
  return (sach.match(re) || []).length
}

module.exports = { doc, ma, thanHam, truoc, demGoi, boChuThich, boChuoi }
