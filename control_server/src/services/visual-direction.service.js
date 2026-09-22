'use strict'

/**
 * Bản chỉ đạo hình ảnh — soi đầu ra mô hình, và dựng bản đem lưu (MINI-SPEC I3).
 *
 * Đây là **ranh giới mà I2 dựng ra để I3 dùng**: catalog là vốn từ đóng, nên
 * mô hình chỉ được CHỌN trong đó. Nhưng mô hình vẫn bịa được — và một mã bịa
 * đi lọt thì hai chuyện xảy ra, cả hai đều âm thầm:
 *
 *   1. người dùng đọc một chỉ dẫn không có thật ("rack focus" chẳng hạn) rồi
 *      tưởng máy làm được;
 *   2. I5 sau này đọc bản chỉ đạo để chọn `kieu_chuyen` sẽ gặp một mã không
 *      map được, ở tận khâu dựng video — nơi xa nhất so với chỗ gây lỗi.
 *
 * Nên luật ở đây là **huỷ CẢ lượt**, không "sửa cho gần đúng". Sửa gần đúng
 * nghĩa là đoán hộ mô hình, mà đoán sai thì không ai biết.
 *
 * Ba thứ tệp này KHÔNG làm, cố ý:
 *   - không gọi mô hình (route làm);
 *   - không trừ tiền (route gọi `charge()` SAU khi soi xong — lượt hỏng thì
 *     chưa có đồng nào bị trừ, nên không cần đường hoàn);
 *   - không dựng bộ soi catalog thứ hai (`visual-catalog.service.js` là nguồn
 *     duy nhất; ở đây chỉ hỏi nó).
 */
const crypto = require('node:crypto')

const catalog = require('./visual-catalog.service')

/** Mã lỗi khi đầu ra mô hình không khớp catalog. Riêng, không gộp vào
 * `BAD_AI_RESPONSE`: ca này nói lên mô hình đang bịa vốn từ, và người vận
 * hành cần phân biệt được nó với "mô hình trả sai khuôn JSON". */
const MA_LOI_SAI_TU_DIEN = 'CHI_DAO_SAI_TU_DIEN'

/** Khoá mang nghĩa thời gian — catalog đã cấm, bản chỉ đạo cũng cấm. Mô hình
 * trả kèm `giay: 3` là đang cố đặt thời lượng, mà thời lượng chỉ có một
 * nguồn: giọng đọc thật (D1). */
const KHOA_THOI_GIAN = ['giay', 'giay_chuyen', 'giay_moi_anh', 'thoi_luong',
  'duration', 'offset', 'start', 'end', 'speed', 'fps', 'thu_tu_moi']

/** Dấu vân tay của kịch bản — đổi lời đọc là bản chỉ đạo cũ hết khớp. */
function bamKichBan(beats) {
  const tho = (beats || []).map((b) => [
    b?.beatType || '', b?.voiceoverTextVi || '', b?.visualBriefVi || '',
  ].join('\u0001')).join('\u0002')
  return crypto.createHash('sha1').update(tho).digest('hex').slice(0, 32)
}

/**
 * Dữ liệu gửi cho mô hình. Cố ý KHÔNG gửi `captionSuggestionVi`: caption là
 * việc của H3, gửi thêm chỉ tốn token mà không đổi được chỉ đạo hình.
 */
function dungInput(kichBan, brand) {
  return {
    catalogVersion: catalog.docCatalog().catalog_version,
    brand: {
      toneGiong: brand?.toneGiong || '',
      rangBuocKhongDuocNoi: Array.isArray(brand?.rangBuocKhongDuocNoi)
        ? brand.rangBuocKhongDuocNoi : [],
    },
    beats: (kichBan?.beats || []).map((b) => ({
      beatType: b?.beatType || 'unknown',
      loiDoc: b?.voiceoverTextVi || '',
      visualBrief: b?.visualBriefVi || '',
    })),
  }
}

/**
 * Soi đầu ra đã chuẩn hoá của `scene_director` rồi dựng bản đem lưu.
 *
 * Trả `{ ok: true, ban }` hoặc `{ ok: false, loi: [...] }`. Không ném: bên
 * gọi là route, cần mã lỗi và câu nói được chứ không cần stack.
 */
function kiemBanChiDao(ketQua, { soDoan, scriptHash }) {
  const loi = []
  const cat_ = catalog.docCatalog()
  const doan = ketQua && Array.isArray(ketQua.doan) ? ketQua.doan : null
  if (!doan) return { ok: false, loi: ['đầu ra không có danh sách đoạn'] }
  if (doan.length !== soDoan) {
    return { ok: false, loi: [`kịch bản có ${soDoan} đoạn nhưng chỉ đạo trả `
      + `về ${doan.length} — không ghép theo vị trí được`] }
  }

  const ra = []
  let soGoiY = 0
  let soMayDungDuoc = 0

  doan.forEach((d, i) => {
    const ten = `đoạn ${i + 1}`
    const daThayNhom = new Set()
    const chon = []

    for (const c of (d.chon || [])) {
      const la = Object.keys(c).filter((k) => k !== 'nhom' && k !== 'ma')
      const thoiGian = la.filter((k) => KHOA_THOI_GIAN.includes(k))
      if (thoiGian.length) {
        loi.push(`${ten}: mục "${c.ma}" mang tham số thời gian `
          + `${thoiGian.join(', ')} — thời lượng do giọng đọc thật quyết định`)
        continue
      }
      if (la.length) {
        loi.push(`${ten}: mục "${c.ma}" có trường lạ ${la.join(', ')}`)
        continue
      }
      if (daThayNhom.has(c.nhom)) {
        loi.push(`${ten}: nhóm "${c.nhom}" được chọn hai lần — mỗi nhóm nhiều `
          + 'nhất một mã')
        continue
      }
      daThayNhom.add(c.nhom)

      const ket = catalog.kiemChon(
        { catalog_version: cat_.catalog_version, [c.nhom]: c.ma },
        { mucDich: 'goi_y' })
      if (!ket.ok) {
        loi.push(`${ten}: ${ket.loi.join('; ')}`)
        continue
      }
      const muc = catalog.timMuc(c.nhom, c.ma)
      const laGoiY = muc.render_mode !== 'supported'
      if (laGoiY) soGoiY += 1; else soMayDungDuoc += 1
      chon.push({
        nhom: c.nhom,
        ma: c.ma,
        nhan: muc.label_vi,
        // Cờ tính từ CATALOG, không phải do mô hình khai: giao diện không bao
        // giờ phải đoán mục nào là gợi ý, và mô hình không tự phong cho mình
        // khả năng "máy dựng được".
        laGoiY,
      })
    }

    ra.push({ thuTu: i + 1, chon, lyDo: String(d.lyDo || '').trim() })
  })

  if (loi.length) return { ok: false, loi }

  return {
    ok: true,
    ban: {
      catalogVersion: cat_.catalog_version,
      scriptHash,
      taoLuc: new Date(),
      soGoiY,
      soMayDungDuoc,
      doan: ra,
    },
  }
}

/**
 * Bản chỉ đạo này còn khớp với kịch bản và catalog hiện tại không.
 *
 * KHÔNG tự xoá và KHÔNG tự chạy lại khi lệch — chạy lại là tiêu tiền của
 * người dùng cho một việc họ chưa yêu cầu. Chỉ nói ra để giao diện đánh dấu.
 */
function trangThaiBan(ban, beatsHienTai) {
  if (!ban) return null
  const hienTai = catalog.docCatalog().catalog_version
  const hashMoi = bamKichBan(beatsHienTai)
  const kichBanDaDoi = Boolean(ban.scriptHash) && ban.scriptHash !== hashMoi
  const catalogDaDoi = ban.catalogVersion !== hienTai
  return {
    laCu: kichBanDaDoi || catalogDaDoi,
    kichBanDaDoi,
    catalogDaDoi,
    catalogVersionHienTai: hienTai,
  }
}

module.exports = {
  MA_LOI_SAI_TU_DIEN,
  KHOA_THOI_GIAN,
  bamKichBan,
  dungInput,
  kiemBanChiDao,
  trangThaiBan,
}
