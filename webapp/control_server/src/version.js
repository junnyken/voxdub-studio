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

/**
 * SHA nguồn nướng sẵn vào ảnh lúc dựng — D3 (14/09/2026).
 *
 * Vì sao cần: `version` lấy từ `package.json` nên KHÔNG đổi giữa các commit.
 * Đo thật 14/09: prod trả `"version":"3.17.16"` cả trước lẫn sau một lượt
 * deploy — tức đường này không trả lời được câu "prod đang chạy commit nào",
 * mà đó chính là câu D3 phải trả lời được.
 *
 * Biến môi trường vẫn được ƯU TIÊN (giữ nguyên hợp đồng cũ): nền tảng nào tự
 * truyền `APP_COMMIT` thì dùng của nó. Vibe Host không truyền, nên rơi xuống
 * tệp `control_server/SOURCE_SHA` do `scripts/gen_vays_control_server_branch.sh`
 * ghi vào thư mục build.
 *
 * Không có tệp là chuyện BÌNH THƯỜNG (chạy từ mã nguồn, chạy test) ⇒ im lặng.
 * Có tệp mà đọc không được thì KHÔNG im: đó là ảnh dựng hỏng, và nuốt nó đi
 * là để `/health` khai thiếu SHA mà không ai biết vì sao.
 */
function docShaTuTep() {
  const fs = require('fs')
  const path = require('path')
  const tep = path.join(__dirname, '..', 'SOURCE_SHA')
  try {
    return fs.readFileSync(tep, 'utf8').trim() || null
  } catch (err) {
    if (err.code !== 'ENOENT') {
      console.warn(`[version] không đọc được ${tep} (${err.code}) — `
        + '/health sẽ không khai được SHA nguồn')
    }
    return null
  }
}

const commit = process.env.APP_COMMIT || process.env.SOURCE_COMMIT
  || docShaTuTep() || null

module.exports = {
  version,
  commit: commit ? commit.slice(0, 12) : null,
}
