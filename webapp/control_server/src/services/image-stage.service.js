'use strict'

/**
 * Chốt chuyển pha cho tính năng dựng ảnh sản phẩm (mini-spec C2).
 *
 * Vì sao tách hẳn ra một tệp: quyết định "máy này có được gọi không, và lượt
 * này ghi sổ là hiệu chỉnh hay chạy thật" phải TEST ĐƯỢC mà không cần cơ sở
 * dữ liệu. Nhét thẳng vào route thì chỉ kiểm được bằng cách dựng cả máy chủ,
 * và đúng lớp lỗi nguy hiểm nhất ở đây — mở nhầm cho người bán thật — là lớp
 * không kêu tiếng nào khi sai.
 *
 * Ba nấc, xem `config.service.js` khoá `image.scene.stage`.
 */

/** Tách danh sách vân tay máy: chấp nhận dấu phẩy, xuống dòng và khoảng trắng. */
function danhSachMay(raw) {
  return String(raw || '')
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

/**
 * Máy này được gọi cửa dựng ảnh không, và lượt này ghi sổ ở chế độ nào.
 *
 * Trả `{ choPhep, runMode, code, message }`. `runMode` LUÔN do đây quyết
 * định, không bao giờ lấy từ thân yêu cầu: client tự khai "tôi đang chạy
 * production" thì báo cáo hiệu chỉnh thành vô nghĩa.
 *
 * Nấc lạ (gõ sai trong trang quản trị, hoặc khoá bị xoá) rơi về ĐÓNG. Đây là
 * lựa chọn có chủ đích: một lỗi chính tả không được phép mở cửa.
 */
function quyetDinh({ stage, devices, fingerprint }) {
  const nac = String(stage || '').trim()

  if (nac === 'production') {
    return { choPhep: true, runMode: 'production' }
  }

  if (nac === 'calibration') {
    const duocPhep = danhSachMay(devices)
    if (duocPhep.includes(String(fingerprint || ''))) {
      return { choPhep: true, runMode: 'calibration' }
    }
    return {
      choPhep: false,
      code: 'IMAGE_STAGE_CALIBRATION',
      message: 'Tính năng dựng ảnh sản phẩm đang trong giai đoạn hiệu chỉnh, '
        + 'chưa mở cho máy này.',
    }
  }

  return {
    choPhep: false,
    code: 'IMAGE_STAGE_OFF',
    message: 'Tính năng dựng ảnh sản phẩm đang tắt.',
  }
}

module.exports = { quyetDinh, danhSachMay }
