'use strict'

/**
 * Thống kê cổng trợ lý (mini-spec V89, giai đoạn 3).
 *
 * Tách khỏi route để phần dựng truy vấn TEST ĐƯỢC mà không cần cơ sở dữ liệu
 * — `control_server` cố ý chỉ có test thuần, và một truy vấn gộp sai thì im
 * lặng cho ra số đẹp chứ không kêu lên.
 *
 * Câu hỏi trang này phải trả lời được, đúng ba câu đã hứa trong bản kế hoạch:
 * tuần rồi tốn bao nhiêu, việc nào tốn nhất, và mô hình nào hay hỏng.
 */

/** Mốc bắt đầu của khoảng thống kê.
 *
 * Số hợp lệ thì kẹp vào [1, 90]; không phải số thì dùng mặc định 7 ngày.
 * Viết `Number(days) || 7` là sai: `days=0` rơi vào nhánh mặc định thành 7
 * ngày, trong khi dòng `Math.max(1, ...)` ngay dưới nói rằng nó kẹp về 1 —
 * mã và ý định lệch nhau, test bắt được.
 */
function since(days, now = new Date()) {
  const n = Number(days)
  const d = Number.isFinite(n) ? Math.min(90, Math.max(1, n)) : 7
  return new Date(now.getTime() - d * 24 * 3600_000)
}

/**
 * Gộp theo TỪNG TÁC VỤ.
 *
 * Đếm cả lượt hỏng: tỷ lệ hỏng chính là thứ báo mô hình đang xuống cấp, mà
 * truy vấn chỉ lấy lượt thành công thì con số đó vĩnh viễn bằng 0.
 */
function theoTacVu(days, now = new Date()) {
  return [
    { $match: { action: 'assist', createdAt: { $gte: since(days, now) } } },
    {
      $group: {
        _id: '$assistTask',
        luot: { $sum: 1 },
        hong: { $sum: { $cond: [{ $eq: ['$status', 'error'] }, 1, 0] } },
        // Lượt dùng lại kết quả cũ: 0 đồng, nhưng phải thấy được — tỷ lệ này
        // cao nghĩa là người dùng đang bấm đi bấm lại cùng một thứ.
        dungLai: { $sum: { $cond: ['$fromCache', 1, 0] } },
        vox: { $sum: '$creditCharged' },
        tokenVao: { $sum: '$promptTokens' },
        tokenRa: { $sum: '$completionTokens' },
        thoiGian: { $avg: '$durationMs' },
        soMay: { $addToSet: '$fingerprint' },
      },
    },
    {
      $project: {
        _id: 0,
        task: '$_id',
        luot: 1, hong: 1, dungLai: 1, vox: 1, tokenVao: 1, tokenRa: 1,
        thoiGianMs: { $round: ['$thoiGian', 0] },
        soMay: { $size: '$soMay' },
      },
    },
    { $sort: { vox: -1, luot: -1 } },
  ]
}

/** Gộp theo mô hình — để thấy nhà nào hay hỏng trước khi người dùng thấy. */
function theoMoHinh(days, now = new Date()) {
  return [
    { $match: { action: 'assist', createdAt: { $gte: since(days, now) } } },
    {
      $group: {
        _id: { provider: '$aiProvider', model: '$aiModel' },
        luot: { $sum: 1 },
        hong: { $sum: { $cond: [{ $eq: ['$status', 'error'] }, 1, 0] } },
        tokenVao: { $sum: '$promptTokens' },
        tokenRa: { $sum: '$completionTokens' },
      },
    },
    {
      $project: {
        _id: 0,
        provider: '$_id.provider',
        model: '$_id.model',
        luot: 1, hong: 1, tokenVao: 1, tokenRa: 1,
      },
    },
    { $sort: { luot: -1 } },
  ]
}

/**
 * Đang chạy bằng vai trò nào.
 *
 * Chưa cấu hình nơi gọi mô hình cho vai `assist` thì hệ thống dùng chung vai
 * `translate` — vẫn chạy, nhưng đắt hơn hàng chục lần. Không nhìn thấy được
 * thì cứ tưởng đang tiết kiệm.
 */
function theoVaiTro(days, now = new Date()) {
  return [
    {
      $match: {
        action: 'assist', status: 'success',
        createdAt: { $gte: since(days, now) },
      },
    },
    { $group: { _id: '$assistRole', luot: { $sum: 1 } } },
    { $project: { _id: 0, vai: '$_id', luot: 1 } },
    { $sort: { luot: -1 } },
  ]
}

/** Mã lỗi hay gặp nhất — đọc là biết nên sửa prompt hay đổi nhà cung cấp. */
function theoMaLoi(days, now = new Date()) {
  return [
    {
      $match: {
        action: 'assist', status: 'error',
        createdAt: { $gte: since(days, now) },
      },
    },
    { $group: { _id: '$errorCode', luot: { $sum: 1 } } },
    { $project: { _id: 0, ma: '$_id', luot: 1 } },
    { $sort: { luot: -1 } },
    { $limit: 10 },
  ]
}

/**
 * Cộng các dòng đã gộp thành phần tóm tắt.
 *
 * Hàm thuần để test được đúng chỗ dễ sai nhất: chia cho 0 khi chưa có lượt
 * nào, và tỷ lệ hỏng phải tính trên TỔNG lượt chứ không phải trên số dòng.
 */
function tomTat(dongTacVu, voxToVnd = 10) {
  const luot = dongTacVu.reduce((t, d) => t + (d.luot || 0), 0)
  const hong = dongTacVu.reduce((t, d) => t + (d.hong || 0), 0)
  const vox = dongTacVu.reduce((t, d) => t + (d.vox || 0), 0)
  const tokenVao = dongTacVu.reduce((t, d) => t + (d.tokenVao || 0), 0)
  const tokenRa = dongTacVu.reduce((t, d) => t + (d.tokenRa || 0), 0)
  const dungLai = dongTacVu.reduce((t, d) => t + (d.dungLai || 0), 0)
  const tonNhat = dongTacVu.reduce(
    (max, d) => ((d.vox || 0) > (max?.vox || -1) ? d : max), null)
  return {
    luot,
    hong,
    tyLeHong: luot ? Math.round((hong / luot) * 1000) / 10 : 0,
    vox,
    vnd: vox * (Number(voxToVnd) || 0),
    tokenVao,
    tokenRa,
    dungLai,
    tacVuTonNhat: tonNhat ? tonNhat.task : '',
  }
}

module.exports = {
  since, theoTacVu, theoMoHinh, theoVaiTro, theoMaLoi, tomTat,
}
