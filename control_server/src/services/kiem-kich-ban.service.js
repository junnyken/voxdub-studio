'use strict'

/**
 * Hai lớp kiểm của mini-spec H3 + bảng tính trạng thái BrandScript.
 *
 * **Thuần so khớp văn bản, KHÔNG gọi mô hình** (Constraint 12 của H3). Nếu
 * bước kiểm gọi AI thì Constraint 11 ("tạo lại một beat phải kiểm lại TOÀN
 * BỘ script") sẽ vô tình thành một hoá đơn nhân lên theo mỗi lần người dùng
 * sửa một beat.
 *
 * Hai lớp có bản chất khác nhau, đừng gộp:
 *   - **Tuân thủ** (`kiemTuanThu`) so kịch bản với `rangBuocKhongDuocNoi` do
 *     CHÍNH người dùng nhập ⇒ có đủ chữ cả hai phía, trưng ra được cả cụm vi
 *     phạm lẫn câu ràng buộc đã kích hoạt nó.
 *   - **Nguyên gốc** (`kiemNguyenGoc`) so kịch bản với bằng chứng video
 *     NGUỒN, mà bằng chứng đó chỉ còn dạng băm một chiều (mini-spec H2c) ⇒
 *     chỉ trưng được cụm bên kịch bản mới.
 */
const dauVanTay = require('./dau-van-tay.service')

/** Số từ tối thiểu của một ràng buộc để đem đi so khớp. Ràng buộc một từ
 * ("nhất") sẽ bắt oan hàng loạt câu vô hại ("nhất định", "thống nhất") —
 * cùng lý lẽ với việc bỏ dòng bằng chứng một từ ở H2c. Ràng buộc ngắn hơn
 * vẫn được GIỮ trong hồ sơ brand, chỉ là bộ kiểm tự động không dùng nó. */
const SO_TU_TOI_THIEU_RANG_BUOC = 1

/**
 * Tìm cụm vi phạm `rangBuocKhongDuocNoi` trong một đoạn văn bản.
 *
 * So khớp ở mức TỪ sau khi chuẩn hoá (hạ chữ thường, bỏ dấu câu) — dùng
 * chung `chuanHoaSoKhop` với mọi bộ chặn khác, nên chữ hoa hay dấu chấm than
 * không giúp lách. KHÔNG so khớp ở mức ký tự: "tốt nhất" mà so kiểu chuỗi con
 * thô sẽ khớp nhầm bên trong một từ dài hơn.
 *
 * Trả `{ viPham, cum, luat }` — `cum` là đoạn đúng như nó xuất hiện trong văn
 * bản (đã chuẩn hoá), `luat` là câu ràng buộc đã kích hoạt.
 */
function timViPham(vanBan, cacRangBuoc) {
  const tu = dauVanTay.tachTu(vanBan)
  if (!tu.length) return { viPham: false, cum: '', luat: '' }

  for (const luat of cacRangBuoc || []) {
    const tuLuat = dauVanTay.tachTu(luat)
    if (tuLuat.length < SO_TU_TOI_THIEU_RANG_BUOC) continue
    const k = tuLuat.length
    const canTim = tuLuat.join(' ')
    for (let i = 0; i + k <= tu.length; i += 1) {
      if (tu.slice(i, i + k).join(' ') === canTim) {
        return { viPham: true, cum: canTim, luat: String(luat).trim() }
      }
    }
  }
  return { viPham: false, cum: '', luat: '' }
}

/** Gộp các trường sinh ra của một beat thành danh sách đoạn cần kiểm. Kiểm
 * CẢ BA (lời đọc, caption, visual brief): caption là chỗ dễ bê nguyên hook
 * gốc nhất, mà nếu chỉ kiểm lời đọc thì nó lọt thẳng. */
function _cacDoan(beat) {
  return [beat?.voiceoverTextVi, beat?.captionSuggestionVi, beat?.visualBriefVi]
    .map((s) => String(s || '').trim())
    .filter(Boolean)
}

/** Kiểm tuân thủ một beat. */
function kiemTuanThu(beat, cacRangBuoc) {
  for (const doan of _cacDoan(beat)) {
    const r = timViPham(doan, cacRangBuoc)
    if (r.viPham) {
      return { complianceFlag: 'violated', complianceExcerpt: r.cum, complianceRule: r.luat }
    }
  }
  return { complianceFlag: 'clear', complianceExcerpt: '', complianceRule: '' }
}

/**
 * Kiểm nguyên gốc một beat so với dấu vân tay bằng chứng nguồn.
 *
 * ``evidenceStatusNguon`` là `evidenceStatus` của beat TƯƠNG ỨNG trong
 * Blueprint. Beat nguồn không có bằng chứng xác nhận thì kịch bản viết ra từ
 * nó **không kiểm được**, dù dấu vân tay tổng thể có tồn tại.
 */
const TRANG_THAI_NGUON_KHONG_DU = new Set(['unavailable', 'failed', 'no_text'])

function kiemNguyenGoc(beat, vanTay, evidenceStatusNguon) {
  const chuaKiem = (lyDo) => ({
    originalityFlag: 'unconfirmed', flaggedExcerpt: '', lyDoChuaKiem: lyDo,
  })

  if (!vanTay) return chuaKiem('khong_co_dau_van_tay')
  if (vanTay.v !== dauVanTay.PHIEN_BAN) return chuaKiem('khac_phien_ban')
  if (vanTay.dayTran) return chuaKiem('day_tran')
  if (TRANG_THAI_NGUON_KHONG_DU.has(String(evidenceStatusNguon || ''))) {
    return chuaKiem('bang_chung_khong_du')
  }

  for (const doan of _cacDoan(beat)) {
    const r = dauVanTay.timTrungLap(doan, vanTay)
    // `kiemDuoc: false` ở đây là ca lọt lưới của bốn chốt trên — vẫn phải
    // tôn trọng, KHÔNG được rơi xuống nhánh "clear".
    if (!r.kiemDuoc) return chuaKiem('khac_phien_ban')
    if (r.trung) {
      return { originalityFlag: 'flagged', flaggedExcerpt: r.cum, lyDoChuaKiem: '' }
    }
  }
  return { originalityFlag: 'clear', flaggedExcerpt: '', lyDoChuaKiem: '' }
}

/**
 * Bảng ưu tiên trạng thái toàn script (Constraint 4/5/6 của H3).
 *
 * `blocked` thắng tất cả: một beat bẩn thì cả kịch bản không dùng được, KHÔNG
 * lặng lẽ bỏ riêng beat đó ra — nếu không, người dùng mang một script
 * nửa-sạch-nửa-vi-phạm sang H4 mà không biết (cùng nguyên tắc với C3).
 */
function tinhTrangThai(beats) {
  const ds = beats || []
  if (!ds.length) return 'failed'
  if (ds.some((b) => b.complianceFlag === 'violated' || b.originalityFlag === 'flagged')) {
    return 'blocked'
  }
  if (ds.some((b) => b.originalityFlag === 'unconfirmed')) return 'unconfirmed'
  return 'ready'
}

/**
 * Chạy CẢ HAI lớp kiểm cho TOÀN BỘ script rồi tính lại trạng thái.
 *
 * Luôn kiểm toàn bộ, kể cả khi chỉ vừa tạo lại đúng một beat (Constraint 11):
 * beat mới có thể vô tình trùng với bằng chứng mà một beat khác — đã từng
 * `clear` — không hề đụng tới. Kiểm mỗi beat vừa sửa sẽ tạo ra trạng thái
 * "nửa vá" trông sạch nhưng chưa từng được xác nhận lại toàn bộ.
 */
function kiemToanBo(beats, { rangBuocKhongDuocNoi, vanTay, beatsNguon } = {}) {
  const nguon = beatsNguon || []
  const daKiem = (beats || []).map((b, i) => ({
    ...b,
    ...kiemTuanThu(b, rangBuocKhongDuocNoi || []),
    ...kiemNguyenGoc(b, vanTay, nguon[i]?.evidenceStatus),
  }))
  return { beats: daKiem, status: tinhTrangThai(daKiem) }
}

module.exports = {
  SO_TU_TOI_THIEU_RANG_BUOC,
  timViPham,
  kiemTuanThu,
  kiemNguyenGoc,
  tinhTrangThai,
  kiemToanBo,
}
