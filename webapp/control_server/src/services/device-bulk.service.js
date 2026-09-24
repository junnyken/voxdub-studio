'use strict'

/**
 * Xử lý hàng loạt thiết bị (mini-spec C21).
 *
 * Vì sao tách khỏi route: đây là thao tác **không lùi được** trên dữ liệu
 * thật (xoá máy là xoá luôn ví Vox của máy đó), nên phần quyết định "được
 * làm gì với máy nào" phải TEST ĐƯỢC mà không cần dựng cơ sở dữ liệu —
 * `control_server` cố ý chỉ có test thuần.
 *
 * Ba chốt, theo thứ tự:
 *
 * 1. **Trần số máy mỗi lượt.** Không phải để chống lạm dụng — để chống một
 *    cú bấm "chọn tất cả" trên bộ lọc rộng hơn người bấm tưởng.
 * 2. **Máy còn số dư phải được kể tên.** Xoá một ví còn tiền là huỷ tiền,
 *    và người bấm cần thấy điều đó TRƯỚC khi bấm, không phải sau.
 * 3. **Không có đường "xoá tất cả".** Danh sách vân tay phải được gửi lên
 *    tường minh; không nhận bộ lọc để tự quét.
 */

const TRAN_MOI_LUOT = 200
const VIEC = new Set(['block', 'unblock', 'delete'])

/**
 * Xét một yêu cầu xử lý hàng loạt.
 *
 * Trả `{ loi }` nếu không làm được, hoặc `{ fingerprints, viec }` nếu hợp lệ.
 * KHÔNG tự đọc cơ sở dữ liệu — nơi gọi làm việc đó.
 */
function xetYeuCau({ fingerprints, action }) {
  if (!VIEC.has(String(action || ''))) {
    return { loi: `Không có việc "${action}". Chỉ nhận: ${[...VIEC].join(', ')}.` }
  }
  const ds = [...new Set((fingerprints || [])
    .map((f) => String(f || '').trim())
    .filter(Boolean))]
  if (!ds.length) return { loi: 'Chưa chọn máy nào.' }
  if (ds.length > TRAN_MOI_LUOT) {
    return {
      loi: `Mỗi lượt tối đa ${TRAN_MOI_LUOT} máy, đang chọn ${ds.length}. `
        + 'Chia nhỏ ra để còn nhìn được mình đang làm gì.',
    }
  }
  return { fingerprints: ds, viec: String(action) }
}

/**
 * Những máy sẽ MẤT TIỀN nếu xoá.
 *
 * Trả về danh sách để nơi gọi kể tên trong lời cảnh báo, thay vì chỉ nói
 * "một vài máy còn số dư".
 */
function mayConTien(danhSach) {
  return (danhSach || [])
    .filter((d) => Number(d.creditBalance || 0) > 0)
    .map((d) => ({
      fingerprint: d.fingerprint,
      name: d.name || '',
      creditBalance: Number(d.creditBalance || 0),
    }))
}

/**
 * Máy xin xử lý mà không tìm thấy trong cơ sở dữ liệu.
 *
 * Báo ra chứ không im lặng bỏ qua: người bấm chọn 25 máy mà chỉ 23 máy đổi
 * trạng thái thì họ phải biết hai máy kia đi đâu.
 */
function mayKhongThay(xin, timDuoc) {
  const co = new Set((timDuoc || []).map((d) => d.fingerprint))
  return (xin || []).filter((f) => !co.has(f))
}

module.exports = { xetYeuCau, mayConTien, mayKhongThay, TRAN_MOI_LUOT, VIEC }
