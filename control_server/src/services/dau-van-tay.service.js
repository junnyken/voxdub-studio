'use strict'

/**
 * Dấu vân tay bằng chứng — mini-spec H2c (10/09/2026), dọn đường cho H3.
 *
 * **Bài toán.** H3 (viết lại kịch bản cho brand) cần kiểm kịch bản MỚI có vô
 * tình trùng câu chữ với video tham khảo gốc không. Nhưng H2 **cố ý KHÔNG
 * lưu** transcript/OCR thô (Constraint 2/Scope B: không biến máy chủ thành
 * kho câu chữ nguyên văn của người khác) — nên H3 không có gì để so.
 *
 * **Cách gỡ đã chọn (chủ dự án chốt 10/09).** Lưu **dấu vân tay một chiều**
 * của bằng chứng: băm từng cụm từ, không giữ chữ. Đủ để phát hiện trùng,
 * nhưng không đọc ngược ra được thành văn bản dùng lại.
 *
 * **Cái giá phải trả, nói thẳng từ đầu.** Không giữ chữ nghĩa là **không thể
 * trưng ra cụm gốc** trong video tham khảo. H3 chỉ chỉ được đúng cụm trong
 * kịch bản MỚI bị chặn (thứ người dùng cần sửa), không hiện được side-by-side
 * với nguồn. Đây là đánh đổi có chủ đích, không phải thiếu sót.
 *
 * **Tính chất bảo mật — KHÔNG được nói quá.** Băm SHA-256 có muối riêng từng
 * bản ghi thì:
 *   - KHÔNG đọc ngược ra văn bản được ⇒ máy chủ không còn là kho copy-ready;
 *   - KHÔNG dò được bằng kho câu có sẵn từ bên ngoài (muối chặn bảng tra sẵn).
 * NHƯNG người đã có CẢ cơ sở dữ liệu (nên có luôn muối) LẪN video gốc thì vẫn
 * xác nhận được "video này ứng với bản ghi kia". Đây là chống TÍCH TRỮ NGUYÊN
 * VĂN, không phải chống một kẻ tấn công có chủ đích.
 */
const crypto = require('node:crypto')

/** Đổi số này khi đổi cách chuẩn hoá/băm. Bản ghi mang phiên bản khác sẽ bị
 * coi là KHÔNG kiểm được (chứ không phải "sạch") — xem `timTrungLap`. */
//: Phiên bản luật băm. **Bump khi `chuanHoaSoKhop` đổi** — vân tay cũ băm
//: theo luật cũ nên so với luật mới sẽ trượt im lặng, và `timTrungLap` phải
//: trả `kiemDuoc: false` ("chưa kiểm được") thay vì `trung: false` ("đã kiểm,
//: sạch"). Hai chuyện đó khác hẳn nhau.
//:
//: 1 → 2 (10/09/2026): `chuanHoaSoKhop` chuyển sang bóc mọi `\p{P}\p{S}`
//: thay cho danh sách trắng thiếu `…`, `/`, `%`, `*`, `&`.
const PHIEN_BAN = 2

/** Bằng đúng `NGUONG_TU_LIEN_TIEP` của gate H2 (`prompts/assist.js`). Hai bộ
 * chặn phải cùng ngưỡng, nếu không sẽ có ca H2 bắt mà H3 tha. */
const SO_TU_CUM_DAI = 6

/** Dòng bằng chứng NGẮN (caption/hook/CTA điển hình: "STOP SCROLLING") không
 * đủ 6 từ để tạo cụm dài. Gate H2 xử lý bằng phép "chứa nguyên vẹn"; ở đây
 * không có chữ để mà `includes`, nên băm CẢ DÒNG kèm số từ, rồi bên kiểm sinh
 * mọi cửa sổ cùng độ dài — tương đương phép chứa ở mức TỪ. */
const SO_TU_NGAN_MIN = 2
const SO_TU_NGAN_MAX = 5

/** 12 ký tự hex = 48 bit. Đo bằng số chứ không đoán: với 20.000 băm lưu sẵn
 * và 300 cụm đem đi hỏi, kỳ vọng số va chạm giả ≈ 20000×300/2^48 ≈ 2×10⁻⁸ —
 * nhỏ hơn nhiều bậc so với mọi nguồn sai khác trong chuỗi này. */
const DAI_BAM = 12

/** Trần số băm mỗi bản ghi. Vượt trần thì KHÔNG cắt âm thầm — đặt cờ
 * `dayTran` để H3 biết vùng phủ không đầy đủ và đánh dấu `unconfirmed` thay
 * vì `clear` (đúng luật "không kiểm được thì coi như không dùng được"). */
const SO_BAM_TOI_DA = 20000

/**
 * Chuẩn hoá text để so khớp — hạ chữ thường, gộp khoảng trắng, bỏ dấu câu.
 *
 * **Giữ nguyên dấu thanh tiếng Việt.** Trước H2b thì OCR đọc mất dấu nên câu
 * tiếng Việt có dấu gần như không bao giờ trùng; nay bằng chứng đã có dấu đầy
 * đủ nên phép so mới thật sự có tác dụng với tiếng Việt.
 *
 * Ở ĐÂY là nguồn sự thật DUY NHẤT của phép chuẩn hoá — `prompts/assist.js`
 * nhập lại hàm này. Hai bản chuẩn hoá song song sẽ trôi lệch nhau sau vài lần
 * sửa, và lúc đó không ai biết bộ chặn nào mới là bộ đang bảo vệ mình.
 */
function chuanHoaSoKhop(text) {
  // Bóc MỌI dấu câu và ký hiệu theo thuộc tính Unicode, không dùng danh sách
  // trắng ký tự.
  //
  // Lỗi thật đo được 10/09/2026: danh sách cũ liệt kê `.,!?;:"'“”‘’()-–—`
  // nhưng THIẾU `…`, `/`, `%`, `*`, `&`. Hậu quả là H2 bắt mà H3 tha, đúng
  // ca mà chú thích ở đầu tệp này cấm:
  //
  //     nguồn    "MUA NGAY HÔM NAY"
  //     kịch bản "mua ngay hôm nay… giá sốc"
  //     H2 coSaoChepNguyenVan -> true  (chặn)
  //     H3 timTrungLap        -> false (THA)
  //
  // Vì `…` dính liền vào `nay`, cụm bốn từ thành `mua ngay hôm nay…` và
  // không khớp băm của `mua ngay hôm nay`. Chép nguyên văn caption gốc rồi
  // thêm một dấu ba chấm là lọt cả hai lớp chống sao chép.
  //
  // `\p{P}` (dấu câu) + `\p{S}` (ký hiệu) không đụng tới chữ cái hay dấu
  // thanh tiếng Việt (`\p{L}`/`\p{M}`), cũng không đụng chữ số.
  return String(text || '').toLowerCase()
    .replace(/[\p{P}\p{S}]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function tachTu(text) {
  return chuanHoaSoKhop(text).split(' ').filter(Boolean)
}

function _bam(muoi, chuoi) {
  return crypto.createHash('sha256').update(`${muoi}|${chuoi}`)
    .digest('hex').slice(0, DAI_BAM)
}

/**
 * Dựng dấu vân tay từ các dòng bằng chứng ĐÃ ĐƯỢC LỌC (bên gọi tự bỏ dòng
 * chưa xác nhận — xem `locBangChungDaXacNhan`).
 *
 * Trả `null` khi không có dòng nào dùng được: KHÔNG trả về một dấu vân tay
 * rỗng, vì "rỗng" và "không có gì để kiểm" là hai chuyện khác nhau — dấu vân
 * tay rỗng sẽ làm mọi kịch bản trông như đã kiểm và sạch.
 */
function taoDauVanTay(cacDong) {
  const dong = (cacDong || [])
    .map((d) => String(d == null ? '' : d))
    .filter((d) => d.trim())
  if (!dong.length) return null

  const muoi = crypto.randomBytes(16).toString('hex')
  const dai = new Set()
  const ngan = new Set()
  const nganSoTu = new Set()
  let dayTran = false

  for (const d of dong) {
    if (dai.size + ngan.size >= SO_BAM_TOI_DA) { dayTran = true; break }
    const tu = tachTu(d)
    if (tu.length >= SO_TU_CUM_DAI) {
      for (let i = 0; i + SO_TU_CUM_DAI <= tu.length; i += 1) {
        if (dai.size + ngan.size >= SO_BAM_TOI_DA) { dayTran = true; break }
        dai.add(_bam(muoi, tu.slice(i, i + SO_TU_CUM_DAI).join(' ')))
      }
    } else if (tu.length >= SO_TU_NGAN_MIN && tu.length <= SO_TU_NGAN_MAX) {
      ngan.add(_bam(muoi, `${tu.length}|${tu.join(' ')}`))
      nganSoTu.add(tu.length)
    }
    // Dòng 1 từ bị bỏ có chủ đích: một từ đơn trùng nhau là chuyện bình
    // thường của ngôn ngữ, không phải dấu hiệu sao chép.
  }

  if (!dai.size && !ngan.size) return null

  return {
    v: PHIEN_BAN,
    muoi,
    dai: [...dai],
    ngan: [...ngan],
    nganSoTu: [...nganSoTu].sort((a, b) => a - b),
    soDong: dong.length,
    dayTran,
  }
}

/**
 * Tìm cụm trong ``vanBan`` trùng với bằng chứng nguồn.
 *
 * Trả về ``cum`` là cụm trong VĂN BẢN MỚI (thứ ta có chữ, và cũng là thứ
 * người dùng cần sửa). Cụm tương ứng bên nguồn KHÔNG trả về được — xem phần
 * "Cái giá phải trả" ở đầu tệp.
 *
 * ``kiemDuoc: false`` nghĩa là **chưa kiểm được**, KHÁC HẲN "đã kiểm, không
 * trùng". Bên gọi phải phân biệt hai ca này: gộp chúng làm một là biến một
 * kịch bản chưa ai kiểm thành một kịch bản được coi là sạch.
 */
function timTrungLap(vanBan, dvt) {
  if (!dvt || dvt.v !== PHIEN_BAN || (!dvt.dai?.length && !dvt.ngan?.length)) {
    return { trung: false, cum: null, kieu: null, kiemDuoc: false }
  }
  const tu = tachTu(vanBan)
  if (!tu.length) return { trung: false, cum: null, kieu: null, kiemDuoc: true }

  const dai = new Set(dvt.dai || [])
  if (dai.size && tu.length >= SO_TU_CUM_DAI) {
    for (let i = 0; i + SO_TU_CUM_DAI <= tu.length; i += 1) {
      const cum = tu.slice(i, i + SO_TU_CUM_DAI).join(' ')
      if (dai.has(_bam(dvt.muoi, cum))) {
        return { trung: true, cum, kieu: 'cum_dai', kiemDuoc: true }
      }
    }
  }

  const ngan = new Set(dvt.ngan || [])
  if (ngan.size) {
    for (const k of dvt.nganSoTu || []) {
      if (!Number.isInteger(k) || k < SO_TU_NGAN_MIN || k > SO_TU_NGAN_MAX) continue
      for (let i = 0; i + k <= tu.length; i += 1) {
        const cum = tu.slice(i, i + k).join(' ')
        if (ngan.has(_bam(dvt.muoi, `${k}|${cum}`))) {
          return { trung: true, cum, kieu: 'dong_ngan', kiemDuoc: true }
        }
      }
    }
  }

  return { trung: false, cum: null, kieu: null, kiemDuoc: true }
}

/**
 * Lọc bằng chứng trước khi băm: chỉ giữ dòng ĐÃ XÁC NHẬN.
 *
 * Dòng OCR ``status: "unconfirmed"`` là chữ máy đọc mà chính nó không chắc —
 * băm vào rồi H3 sẽ chặn kịch bản vì trùng với một câu **có thể đọc sai**.
 * Transcript không mang ``status`` (ASR luôn được coi là dùng được, đúng như
 * client gửi lên ở `autodub/flow_blueprint.py`).
 *
 * Trả kèm ``soBoQua`` để bên gọi biết vùng phủ thiếu bao nhiêu.
 */
function locBangChungDaXacNhan(cacMuc) {
  const giu = []
  let soBoQua = 0
  for (const m of cacMuc || []) {
    const text = String(m?.text || '').trim()
    if (!text) continue
    const trangThai = String(m?.status || '').trim()
    if (trangThai && trangThai !== 'ok') { soBoQua += 1; continue }
    giu.push(text)
  }
  return { dong: giu, soBoQua }
}

module.exports = {
  PHIEN_BAN,
  SO_TU_CUM_DAI,
  SO_TU_NGAN_MIN,
  SO_TU_NGAN_MAX,
  SO_BAM_TOI_DA,
  DAI_BAM,
  chuanHoaSoKhop,
  tachTu,
  taoDauVanTay,
  timTrungLap,
  locBangChungDaXacNhan,
}
