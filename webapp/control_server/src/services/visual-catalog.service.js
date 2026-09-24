'use strict'

/**
 * Từ điển chỉ đạo hình ảnh (Visual Direction Catalog) — MINI-SPEC I2.
 *
 * Đây là **vốn từ đóng, có số phiên bản**, không phải một tính năng dựng
 * video mới. Nó tồn tại để I3 (`scene_director`) có một danh sách hữu hạn để
 * chọn, thay vì để mô hình tự nghĩ ra thuật ngữ điện ảnh mà khâu ghép hình
 * của H4 không làm được.
 *
 * Ba luật sống còn, và cả ba đều được ép lúc DỰNG MÁY CHỦ: `build()`
 * nạp route `config`, route nạp tệp này, tệp này soi dữ liệu và NÉM nếu
 * sai — đo thật 22/09: thêm một mục `drone_shot` vào JSON thì máy chủ
 * không khởi động được, kèm câu nói rõ sai chỗ nào. Dữ liệu hỏng không
 * có đường nào lên tới người dùng:
 *
 *   1. **`supported` = H4 làm được THẬT.** Mục nào khai `supported` thì phải
 *      trỏ vào một hàm dựng hình CÓ THẬT trong `autodub/product_video.py` kèm
 *      tham số mà hàm đó nhận. Mục nào H4 không làm được thì là
 *      `advisory_only` — gợi ý cho người chọn ảnh, KHÔNG BAO GIỜ được gửi
 *      xuống như lệnh dựng (xem `kiemChon` với `mucDich: 'dung_hinh'`).
 *
 *   2. **Không mục nào được đụng vào thời lượng.** Thời lượng từng cảnh do D1
 *      suy từ giọng đọc thật (`autodub/du_an_tu_kich_ban.py::_moc_that`) và
 *      cảnh cuối phải phủ hết tệp tiếng. Một mục "nhịp dựng" mà rút được
 *      thời lượng là đúng cái lỗi "mấy giây cuối đứng hình" vừa sửa xong.
 *      Nên `THAM_SO_CAM` chặn thẳng mọi tham số mang nghĩa thời gian.
 *
 *   3. **Danh sách cấm là danh sách cấm.** Drone, dolly zoom, rack focus,
 *      whip pan, bám vật thể 3D, sinh video bằng AI — không có đường nào để
 *      chúng lọt vào tệp dữ liệu này mà không làm đỏ test.
 *
 * Tệp dữ liệu: `src/data/visual-direction-catalog.json` (nguồn DUY NHẤT —
 * cả máy chủ lẫn `tests/test_i2_catalog_khop_renderer.py` bên Python đọc
 * chính tệp này, không ai chép lại).
 */
const CATALOG_DU_LIEU = require('../data/visual-direction-catalog.json')
const { BEAT_TYPES } = require('../models/FlowBlueprint')

/**
 * Phiên bản catalog mà mã này hiểu, và phiên bản đang ship.
 *
 * Tách làm hai con số vì chúng trả lời hai câu khác nhau:
 *   - `PHIEN_BAN_HO_TRO` — bộ soi chấp nhận những số nào. Bản chỉ đạo đã lưu
 *     từ trước (I3) mang số cũ vẫn phải ĐỌC được, nếu không thì mỗi lần lên
 *     đời catalog là xoá sạch dữ liệu người dùng.
 *   - `PHIEN_BAN_HIEN_TAI` — số của tệp đang ship. Sửa nội dung mà quên nâng
 *     số là chuyện dễ xảy ra nhất, nên máy chủ tự chặn ngay lúc khởi động.
 *
 * v2 (22/09/2026): thêm ba kiểu chuyển cảnh trượt trái · trượt lên · mở vòng
 * — có sẵn trong `product_video.KIEU_CHUYEN` từ lâu, nay đã ĐO bằng ffmpeg
 * trên video 5 cảnh có giọng đọc thật trước khi cho vào (xem TEST_LOG).
 */
const PHIEN_BAN_HO_TRO = Object.freeze([1, 2])
const PHIEN_BAN_HIEN_TAI = 2

/** Sáu nhóm của catalog — đóng, đúng thứ tự mini-spec I2 §C2. */
const NHOM_V1 = Object.freeze([
  'shot', 'composition', 'motion', 'pacing', 'transition', 'lighting_color',
])

/** Trạng thái được phép NẰM TRONG dữ liệu chạy thật.
 *
 * `unavailable` cố ý KHÔNG có mặt: mini-spec I2 §C3 nói mục không dùng được
 * thì nằm ở tài liệu tồn đọng, không phải ở tệp dữ liệu ship ra. Để nó ở đây
 * là mở đường cho một mục chết nằm trong catalog rồi có ngày ai đó lọc thiếu.
 */
const TRANG_THAI = Object.freeze(['supported', 'advisory_only'])

/**
 * Hàm dựng hình CÓ THẬT mà mục `supported` được phép trỏ tới, kèm tham số
 * mà hàm đó thật sự nhận.
 *
 * Đây là bản khai phía máy chủ; `tests/test_i2_catalog_khop_renderer.py` đối
 * chiếu nó với chính mã Python (chữ ký hàm + `KIEU_CHUYEN`) nên hai bên
 * không trôi lệch nhau được.
 */
const CACH_DUNG = Object.freeze({
  'product_video.ghep_anh_nguoi_dung': Object.freeze(['kieu_chuyen']),
})

/**
 * Tham số CẤM trong mọi mapping — mọi thứ mang nghĩa thời gian.
 *
 * Catalog được phép nói "chuyển cảnh kiểu nào", không được phép nói "cảnh dài
 * bao nhiêu giây". Con số ấy chỉ có một nguồn: giọng đọc thật (D1).
 */
const THAM_SO_CAM = Object.freeze([
  'giay', 'giay_moi_anh', 'giay_chuyen', 'thoi_luong', 'dai_tieng',
  'duration', 'offset', 'start', 'end', 'speed', 'fps',
])

/** Khả năng bị cấm theo mini-spec I2 (guardrail 7) — chặn cả mã lẫn câu chữ. */
const KHA_NANG_BI_CAM = Object.freeze([
  'drone', 'flycam', 'dolly_zoom', 'dolly zoom', 'rack_focus', 'rack focus',
  'whip_pan', 'whip pan', 'motion_capture', 'motion capture', 'gimbal',
  'ai_video', 'ai video', 'sinh video', 'video ai', '3d_tracking',
  '3d tracking', 'optical flow', 'parallax',
])

const CHUOI_BAT_BUOC = Object.freeze([
  'label_vi', 'description_vi', 'prompt_hint_vi',
])
const MANG_BAT_BUOC = Object.freeze(['recommended_for', 'avoid_when'])

function laChuoiCoChu(x) { return typeof x === 'string' && x.trim().length > 0 }

function laMangChuoi(x) {
  return Array.isArray(x) && x.length > 0 && x.every(laChuoiCoChu)
}

/** Gom mọi chữ của một mục để soi từ cấm — id, nhãn, mô tả, gợi ý. */
function chuCuaMuc(muc) {
  return [
    muc.id, muc.label_vi, muc.description_vi, muc.prompt_hint_vi,
    muc.advisory_note_vi, ...(muc.recommended_for || []),
    ...(muc.avoid_when || []),
    muc.h4_mapping ? muc.h4_mapping.implementation : '',
    muc.h4_mapping ? muc.h4_mapping.ghi_chu_vi : '',
  ].filter(laChuoiCoChu).join(' \n ').toLowerCase()
}

/**
 * Soi một catalog. Trả về MẢNG LỖI (rỗng = đạt).
 *
 * Cố ý trả danh sách thay vì ném ở lỗi đầu tiên: sửa dữ liệu mà mỗi lần chỉ
 * biết một lỗi thì phải chạy lại chục lượt.
 */
function kiemTraCatalog(data) {
  const loi = []
  if (!data || typeof data !== 'object') return ['catalog không phải đối tượng']

  if (!PHIEN_BAN_HO_TRO.includes(data.catalog_version)) {
    loi.push('catalog_version phải là một trong các số '
      + `${PHIEN_BAN_HO_TRO.join(', ')} (đang là ${JSON.stringify(data.catalog_version)})`)
  }
  if (!Array.isArray(data.groups)) return [...loi, 'thiếu mảng groups']

  const tenNhom = data.groups.map((g) => g && g.id)
  if (JSON.stringify(tenNhom) !== JSON.stringify([...NHOM_V1])) {
    loi.push(`groups phải đúng sáu nhóm theo thứ tự ${NHOM_V1.join(', ')} `
      + `(đang là ${tenNhom.join(', ')})`)
  }

  const daThayId = new Set()
  for (const nhom of data.groups) {
    if (!nhom || !laChuoiCoChu(nhom.id)) { loi.push('có nhóm thiếu id'); continue }
    if (!laChuoiCoChu(nhom.label_vi)) loi.push(`nhóm ${nhom.id} thiếu label_vi`)
    if (!laChuoiCoChu(nhom.description_vi)) loi.push(`nhóm ${nhom.id} thiếu description_vi`)
    if (!Array.isArray(nhom.values) || !nhom.values.length) {
      loi.push(`nhóm ${nhom.id} không có mục nào`)
      continue
    }

    for (const muc of nhom.values) {
      const ten = `${nhom.id}.${muc && muc.id ? muc.id : '?'}`
      if (!muc || !laChuoiCoChu(muc.id)) { loi.push(`${ten}: thiếu id`); continue }
      if (!/^[a-z][a-z0-9_]*$/.test(muc.id)) {
        loi.push(`${ten}: id chỉ được gồm chữ thường, số và gạch dưới`)
      }
      if (daThayId.has(muc.id)) loi.push(`${ten}: id trùng với mục khác`)
      daThayId.add(muc.id)

      for (const truong of CHUOI_BAT_BUOC) {
        if (!laChuoiCoChu(muc[truong])) loi.push(`${ten}: thiếu ${truong}`)
      }
      for (const truong of MANG_BAT_BUOC) {
        if (!laMangChuoi(muc[truong])) {
          loi.push(`${ten}: ${truong} phải là mảng chuỗi không rỗng`)
        }
      }
      const beatLa = (muc.recommended_for || []).filter(
        (b) => !BEAT_TYPES.includes(b) || b === 'unknown')
      if (beatLa.length) {
        loi.push(`${ten}: recommended_for có vai lạ (${beatLa.join(', ')}) — `
          + 'chỉ được dùng beatType có thật của H2/H3')
      }

      if (!TRANG_THAI.includes(muc.render_mode)) {
        loi.push(`${ten}: render_mode phải là ${TRANG_THAI.join(' hoặc ')} `
          + `(đang là ${JSON.stringify(muc.render_mode)})`)
        continue
      }

      if (muc.render_mode === 'supported') {
        const map = muc.h4_mapping
        if (!map || typeof map !== 'object') {
          loi.push(`${ten}: khai supported thì bắt buộc có h4_mapping`)
        } else if (!Object.prototype.hasOwnProperty.call(CACH_DUNG, map.implementation)) {
          loi.push(`${ten}: implementation "${map.implementation}" không có `
            + 'trong danh sách hàm dựng hình có thật')
        } else if (!map.parameters || typeof map.parameters !== 'object'
            || Array.isArray(map.parameters)) {
          loi.push(`${ten}: h4_mapping.parameters phải là đối tượng (rỗng cũng được)`)
        } else {
          const nhan = CACH_DUNG[map.implementation]
          for (const k of Object.keys(map.parameters)) {
            if (THAM_SO_CAM.includes(k)) {
              loi.push(`${ten}: tham số "${k}" mang nghĩa thời gian — catalog `
                + 'không được đổi thời lượng do giọng đọc thật quyết định (D1)')
            } else if (!nhan.includes(k)) {
              loi.push(`${ten}: "${map.implementation}" không nhận tham số "${k}"`)
            }
          }
        }
      } else {
        if (muc.h4_mapping !== null && muc.h4_mapping !== undefined) {
          loi.push(`${ten}: advisory_only thì h4_mapping phải là null — có `
            + 'mapping nghĩa là có đường thực thi, tức nói sai sự thật')
        }
        if (!laChuoiCoChu(muc.advisory_note_vi)) {
          loi.push(`${ten}: advisory_only thì phải nói rõ vì sao chưa tự làm được `
            + '(advisory_note_vi)')
        }
      }

      if (nhom.id === 'pacing') {
        if (muc.render_mode !== 'advisory_only') {
          loi.push(`${ten}: nhóm pacing chỉ được advisory_only — nhịp dựng `
            + 'không được trở thành lệnh đổi thời lượng')
        }
        if (muc.nguon_thoi_luong !== 'd1_audio') {
          loi.push(`${ten}: nhóm pacing phải khai nguon_thoi_luong="d1_audio"`)
        }
      }

      const chu = chuCuaMuc(muc)
      const cam = KHA_NANG_BI_CAM.filter((t) => chu.includes(t))
      if (cam.length) {
        loi.push(`${ten}: chạm khả năng bị cấm (${cam.join(', ')}) — H4 không `
          + 'làm được những thứ này, đưa vào catalog là hứa sai')
      }
    }
  }
  return loi
}

/** Nạp + soi ngay lúc require: dữ liệu hỏng thì máy chủ không được khởi động. */
function _napCatalog() {
  const loi = kiemTraCatalog(CATALOG_DU_LIEU)
  // Tệp ĐANG SHIP thì phải mang đúng số phiên bản hiện tại. Bộ soi ở trên
  // chấp nhận cả số cũ (để đọc dữ liệu đã lưu), nên thiếu phép kiểm này thì
  // sửa nội dung mà quên nâng số sẽ trôi lọt — và mọi bản chỉ đạo cũ bỗng
  // trông như vẫn khớp catalog mới.
  if (CATALOG_DU_LIEU.catalog_version !== PHIEN_BAN_HIEN_TAI) {
    loi.push(`tệp đang ship khai catalog_version `
      + `${JSON.stringify(CATALOG_DU_LIEU.catalog_version)} nhưng mã này ship `
      + `bản ${PHIEN_BAN_HIEN_TAI} — nâng số hoặc sửa mã, đừng để lệch`)
  }
  if (loi.length) {
    throw new Error('Từ điển chỉ đạo hình ảnh không hợp lệ:\n- '
      + loi.join('\n- '))
  }
  return Object.freeze(CATALOG_DU_LIEU)
}

const CATALOG = _napCatalog()

/** Bản catalog đã soi — đọc được, không sửa được. */
function docCatalog() { return CATALOG }

/** Tra một mục theo nhóm. Không thấy thì `null` (không đoán). */
function timMuc(nhomId, mucId) {
  const nhom = CATALOG.groups.find((g) => g.id === nhomId)
  if (!nhom) return null
  return nhom.values.find((v) => v.id === mucId) || null
}

/**
 * Cổng kiểm cho bên tiêu thụ sau này (I3 `scene_director`, I4 lưu lựa chọn).
 *
 * `chon`: `{ catalog_version, nhom: giá_trị, ... }` ví dụ
 *         `{ catalog_version: 2, shot: 'can_canh', transition: 'fade_nhe' }`.
 * `mucDich`:
 *   - `'goi_y'`    — nhận cả `supported` lẫn `advisory_only` (để hiện cho người dùng);
 *   - `'dung_hinh'` — CHỈ nhận `supported`. Đây là chỗ chặn một mục gợi ý bị
 *     mang đi dựng hình như thể máy làm được.
 *
 * Trả `{ ok, loi: [...] }`. Không ném: bên gọi là route, cần mã lỗi chứ không
 * cần stack.
 */
function kiemChon(chon, { mucDich = 'goi_y' } = {}) {
  const loi = []
  if (!chon || typeof chon !== 'object' || Array.isArray(chon)) {
    return { ok: false, loi: ['lựa chọn phải là một đối tượng'] }
  }
  if (!['goi_y', 'dung_hinh'].includes(mucDich)) {
    return { ok: false, loi: [`mục đích không hợp lệ: ${mucDich}`] }
  }
  if (chon.catalog_version !== CATALOG.catalog_version) {
    loi.push(`catalog_version ${JSON.stringify(chon.catalog_version)} không `
      + `khớp bản đang chạy (${CATALOG.catalog_version})`)
  }
  const khoa = Object.keys(chon).filter((k) => k !== 'catalog_version')
  if (!khoa.length) loi.push('chưa chọn nhóm nào')
  for (const k of khoa) {
    if (!NHOM_V1.includes(k)) { loi.push(`không có nhóm "${k}"`); continue }
    const muc = timMuc(k, chon[k])
    if (!muc) { loi.push(`nhóm "${k}" không có mục "${chon[k]}"`); continue }
    if (mucDich === 'dung_hinh' && muc.render_mode !== 'supported') {
      loi.push(`"${k}.${muc.id}" chỉ là gợi ý (advisory_only) — không gửi `
        + 'xuống khâu dựng hình được')
    }
  }
  return { ok: loi.length === 0, loi }
}

/**
 * Cách dựng THẬT của một mục — chỉ trả khi mục đó `supported`.
 *
 * Vì sao tính lúc ĐỌC chứ không lưu vào bản chỉ đạo: bản chỉ đạo lưu MÃ,
 * còn cách dựng là chuyện của catalog. Tính lúc đọc thì sửa ánh xạ một chỗ
 * là mọi bản đã lưu khớp theo ngay — không phải di trú dữ liệu, và không
 * bao giờ có hai nguồn sự thật để trôi lệch nhau.
 *
 * Mục `advisory_only` trả `null` chứ không trả bảng tham số rỗng: rỗng sẽ
 * khiến bên gọi tưởng dựng được mà chẳng có gì để làm.
 */
function cachDungCua(nhomId, mucId) {
  const muc = timMuc(nhomId, mucId)
  if (!muc || muc.render_mode !== 'supported') return null
  const anh_xa = muc.h4_mapping
  if (!anh_xa || !anh_xa.implementation) return null
  return {
    implementation: anh_xa.implementation,
    parameters: { ...(anh_xa.parameters || {}) },
  }
}

module.exports = {
  PHIEN_BAN_HO_TRO,
  PHIEN_BAN_HIEN_TAI,
  NHOM_V1,
  TRANG_THAI,
  CACH_DUNG,
  THAM_SO_CAM,
  KHA_NANG_BI_CAM,
  kiemTraCatalog,
  docCatalog,
  timMuc,
  cachDungCua,
  kiemChon,
}
