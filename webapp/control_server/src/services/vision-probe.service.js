'use strict'

/**
 * Phép thử "mô hình có NHÌN được ảnh không" (mini-spec C4).
 *
 * Vì sao cần: tác vụ `packaging_check` là cổng an toàn duy nhất giữa ảnh AI
 * dựng và tài khoản bán hàng của người dùng. Nếu vai `assist` bị cắm một mô
 * hình chỉ đọc chữ, nó **vẫn trả lời** — và một phán quyết "đạt" từ mô hình
 * chưa từng nhìn thấy tấm ảnh nào là ca hỏng tệ nhất mà hệ thống có thể tạo
 * ra: im lặng, trông như đang hoạt động, và hậu quả rơi xuống người bán vài
 * tuần sau dưới dạng án phạt.
 *
 * Cách kiểm: máy chủ TỰ VẼ một tấm PNG chứa một con số bốn chữ số ngẫu nhiên
 * rồi hỏi mô hình đọc số đó. Không đọc đúng = không dùng cho việc kiểm bao
 * bì. Số ngẫu nhiên mỗi lần nên không đoán mò được, và vì ảnh do chính ta vẽ
 * nên không phụ thuộc tệp ngoài hay mạng.
 *
 * Tự vẽ PNG bằng `zlib` có sẵn của Node thay vì thêm thư viện: một bộ chữ số
 * 5×7 chấm là đủ, và thêm phụ thuộc chỉ để vẽ bốn chữ số là cái giá quá đắt.
 */
const zlib = require('node:zlib')
const crypto = require('node:crypto')

/** Bộ chữ số 5×7 chấm — mỗi chuỗi là một hàng, '1' là điểm mực. */
const CHU_SO = {
  0: ['01110', '10001', '10011', '10101', '11001', '10001', '01110'],
  1: ['00100', '01100', '00100', '00100', '00100', '00100', '01110'],
  2: ['01110', '10001', '00001', '00010', '00100', '01000', '11111'],
  3: ['11111', '00010', '00100', '00010', '00001', '10001', '01110'],
  4: ['00010', '00110', '01010', '10010', '11111', '00010', '00010'],
  5: ['11111', '10000', '11110', '00001', '00001', '10001', '01110'],
  6: ['00110', '01000', '10000', '11110', '10001', '10001', '01110'],
  7: ['11111', '00001', '00010', '00100', '01000', '01000', '01000'],
  8: ['01110', '10001', '10001', '01110', '10001', '10001', '01110'],
  9: ['01110', '10001', '10001', '01111', '00001', '00010', '01100'],
}

const PHONG = 8      // mỗi chấm thành ô 8×8 điểm ảnh
const LE = 16        // viền trắng quanh chữ

/** CRC32 theo chuẩn PNG. */
function crc32(buf) {
  let c = ~0
  for (let i = 0; i < buf.length; i += 1) {
    c ^= buf[i]
    for (let k = 0; k < 8; k += 1) c = (c >>> 1) ^ (0xEDB88320 & -(c & 1))
  }
  return ~c >>> 0
}

function chunk(kieu, du_lieu) {
  const dai = Buffer.alloc(4)
  dai.writeUInt32BE(du_lieu.length)
  const than = Buffer.concat([Buffer.from(kieu, 'ascii'), du_lieu])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(than))
  return Buffer.concat([dai, than, crc])
}

/**
 * Vẽ `chu` (chỉ chữ số) thành ảnh PNG xám, trả base64.
 *
 * Ảnh đen trên nền trắng, chữ to — cố ý dễ đọc tới mức một mô hình nhìn được
 * thật thì không có lý do gì đọc sai. Phép thử này để bắt mô hình MÙ, không
 * phải để thi thị lực.
 */
function veSo(chu) {
  const so = String(chu).split('')
  const rong = LE * 2 + so.length * 6 * PHONG
  const cao = LE * 2 + 7 * PHONG
  // Mỗi hàng điểm ảnh mở đầu bằng một byte kiểu lọc (0 = không lọc).
  const tho = Buffer.alloc((rong + 1) * cao, 0xFF)
  for (let y = 0; y < cao; y += 1) tho[y * (rong + 1)] = 0

  so.forEach((ky_tu, chi_so) => {
    const net = CHU_SO[ky_tu]
    if (!net) return
    for (let hang = 0; hang < 7; hang += 1) {
      for (let cot = 0; cot < 5; cot += 1) {
        if (net[hang][cot] !== '1') continue
        for (let dy = 0; dy < PHONG; dy += 1) {
          for (let dx = 0; dx < PHONG; dx += 1) {
            const y = LE + hang * PHONG + dy
            const x = LE + (chi_so * 6 + cot) * PHONG + dx
            tho[y * (rong + 1) + 1 + x] = 0x00
          }
        }
      }
    }
  })

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(rong, 0)
  ihdr.writeUInt32BE(cao, 4)
  ihdr[8] = 8      // 8 bit mỗi mẫu
  ihdr[9] = 0      // ảnh xám
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(tho)),
    chunk('IEND', Buffer.alloc(0)),
  ]).toString('base64')
}

/** Một bài thử mới: số bốn chữ số ngẫu nhiên + ảnh của nó. */
function taoBaiThu() {
  // Không dùng số bắt đầu bằng 0 để tránh tranh cãi "1234" vs "01234".
  const so = String(1000 + crypto.randomInt(9000))
  return { so, image: { mimeType: 'image/png', data: veSo(so) } }
}

/**
 * Mô hình có đọc ra số không.
 *
 * Chấp nhận rộng rãi ở phần HÌNH THỨC (số nằm lẫn trong câu, có dấu phẩy
 * ngăn nghìn, viết kèm chữ) nhưng nghiêm ngặt ở phần NỘI DUNG: phải đúng con
 * số đó. Mô hình mù có thể đoán bừa một số bốn chữ số — xác suất trúng 1/9000.
 */
function doDung(so, traLoi) {
  const chu = String(traLoi || '').replace(/[.,\s]/g, '')
  return chu.includes(String(so))
}

module.exports = { veSo, taoBaiThu, doDung, CHU_SO }
