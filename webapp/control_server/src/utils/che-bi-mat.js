'use strict'

/**
 * Che bí mật trong tệp bằng chứng — **bản Node của `autodub/bang_chung.py`**.
 *
 * Vì sao phải có bản thứ hai thay vì gọi lại bản Python: bộ thu bằng chứng
 * cho cổng trợ lý (`scripts/thu-bang-chung-assist.js`) chạy trong tiến trình
 * Node, cùng chỗ với máy chủ; gọi sang Python chỉ để che một chuỗi là kéo cả
 * một trình thông dịch vào đường ghi bằng chứng.
 *
 * Nhân đôi là NỢ, và nợ đó được trả bằng `tests/test_che_bi_mat_khop_hai_phia.py`:
 * test đó đẩy CÙNG MỘT bộ mẫu qua cả hai bản rồi so từng ký tự. Sửa một bên
 * mà quên bên kia là đỏ ngay — đúng cách `tests/dub-langs.test.js` giữ danh
 * sách ngôn ngữ khỏi trôi lệch (V49) và `tests/test_h6_ngan_sach_tu.py` giữ
 * hằng số tốc độ đọc.
 *
 * Che theo HAI đường, vì cả hai đều đã gặp thật:
 *   - theo TÊN KHOÁ (`{"api_token": "abc"}`) — dữ liệu có cấu trúc;
 *   - theo NỘI DUNG (`"VOXDUB_TOKEN=abc"`) — dòng nhật ký, tham số dòng lệnh.
 *
 * Danh sách tên khoá cố ý RỘNG: thà che nhầm một đường dẫn vô hại còn hơn để
 * lọt một khoá thật vào tệp bằng chứng đem đi khoe.
 */

const KHOA_BI_MAT = /(token|api[_-]?key|apikey|secret|password|passwd|mat[_-]?khau|authorization|bearer|credential)/i

const GAN_BI_MAT = /\b([A-Za-z0-9_.-]*(?:token|api[_-]?key|apikey|secret|password|passwd|authorization|credential)[A-Za-z0-9_.-]*)\s*([:=]\s*)("[^"]*"|'[^']*'|[^\s,;]+)/gi

/** Chuỗi thay thế — có chữ "che" để người đọc biết là CỐ Ý, không phải rỗng do lỗi. */
const CHE = '***(đã che)'

/** Che mọi `KHOA=giá trị` mang tên bí mật trong một đoạn chữ. */
function cheDong(chuoi) {
  if (!chuoi) return chuoi
  return String(chuoi).replace(GAN_BI_MAT, (_m, k, dau) => `${k}${dau}${CHE}`)
}

/**
 * Bản sao của `duLieu` đã che mọi giá trị bí mật (đệ quy).
 *
 * `tenKhoa` là tên khoá đang chứa giá trị này — chuỗi nằm dưới một khoá mang
 * tên bí mật thì che TRỌN, không cần khớp mẫu `KHOA=giá trị`.
 */
function cheBiMat(duLieu, tenKhoa = '') {
  if (Array.isArray(duLieu)) {
    // Dòng lệnh tách thành hai phần tử: `["--hf-token", "abc"]`. Luật
    // `KHOA=giá trị` không nhìn thấy dạng này — phải che theo CẶP.
    const ra = []
    let truoc = ''
    for (const v of duLieu) {
      if (typeof v === 'string' && truoc.startsWith('-') && KHOA_BI_MAT.test(truoc)) {
        ra.push(CHE)
      } else {
        ra.push(cheBiMat(v, tenKhoa))
      }
      truoc = typeof v === 'string' ? v : ''
    }
    return ra
  }
  if (duLieu && typeof duLieu === 'object') {
    const ra = {}
    for (const [k, v] of Object.entries(duLieu)) ra[k] = cheBiMat(v, String(k))
    return ra
  }
  if (typeof duLieu === 'string') {
    if (tenKhoa && KHOA_BI_MAT.test(tenKhoa)) return duLieu ? CHE : duLieu
    return cheDong(duLieu)
  }
  return duLieu
}

/**
 * Quét MỘT LẦN NỮA, ngay trước khi ghi: chuỗi nào trong `bíMật` còn xuất hiện
 * nguyên văn trong dữ liệu thì đây là lỗ thật.
 *
 * Vì sao cần dù đã che theo tên khoá và theo mẫu: khoá API có thể lọt vào chỗ
 * không mang tên nào gợi ý gì — một câu lỗi của nhà cung cấp in cả URL kèm
 * `?key=…`, một stack trace, một trường `detail` trả về từ máy chủ họ. Lớp
 * này không đoán tên; nó tìm đúng giá trị mình đang giữ.
 *
 * Trả về danh sách mô tả chỗ lọt (rỗng = sạch).
 */
function timBiMatSotLai(duLieu, biMat) {
  const can = (biMat || []).filter((s) => typeof s === 'string' && s.length >= 8)
  if (!can.length) return []
  const thay = []
  const duyet = (x, duong) => {
    if (Array.isArray(x)) { x.forEach((v, i) => duyet(v, `${duong}[${i}]`)); return }
    if (x && typeof x === 'object') {
      for (const [k, v] of Object.entries(x)) duyet(v, duong ? `${duong}.${k}` : k)
      return
    }
    if (typeof x !== 'string') return
    for (const s of can) {
      if (x.includes(s)) thay.push(`${duong || '(gốc)'} còn chứa nguyên văn một giá trị bí mật`)
    }
  }
  duyet(duLieu, '')
  return thay
}

/**
 * Che theo ĐÚNG GIÁ TRỊ — lớp chặn cuối, chạy ngay trước khi ghi ra đĩa.
 *
 * `cheBiMat()` che theo TÊN KHOÁ và theo MẪU `KHOA=giá trị`. Cả hai đều mù
 * trước một khoá API nằm lẫn trong câu trả lời của mô hình hay trong một
 * thông báo lỗi của nhà cung cấp: ở đó không có tên khoá nào, cũng không có
 * dấu bằng nào. Lớp này không đoán — nó tìm đúng chuỗi mình đang giữ.
 *
 * Làm trên chuỗi JSON đã tuần tự hoá để không bỏ sót chỗ nào trong cây.
 */
function cheTheoGiaTri(duLieu, biMat) {
  const can = (biMat || []).filter((s) => typeof s === 'string' && s.length >= 8)
  if (!can.length) return duLieu
  let tho = JSON.stringify(duLieu)
  for (const s of can) tho = tho.split(JSON.stringify(s).slice(1, -1)).join(CHE)
  return JSON.parse(tho)
}

module.exports = {
  CHE, KHOA_BI_MAT, GAN_BI_MAT, cheDong, cheBiMat, cheTheoGiaTri, timBiMatSotLai,
}
