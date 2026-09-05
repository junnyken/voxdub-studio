'use strict'

/**
 * Phiên bản máy chủ — MỘT nguồn duy nhất.
 *
 * C54: trước đây con số này được gõ tay ở ba chỗ (`/health`, `/v1/config`,
 * `/v1/admin/whoami`) và đứng yên ở '3.0.0' suốt 48 lượt deploy, trong khi
 * ứng dụng đã đi tới 3.16.x. Ai đi kiểm "máy chủ đang chạy bản nào" đều bị
 * con số đó dẫn sai đường — tệ hơn là không hiển thị gì.
 *
 * `commit` chỉ có khi nền tảng hosting truyền vào; không có thì bỏ hẳn field
 * chứ không đoán.
 */
const { version } = require('../package.json')

const commit = process.env.APP_COMMIT || process.env.SOURCE_COMMIT || null

module.exports = {
  version,
  commit: commit ? commit.slice(0, 12) : null,
}
