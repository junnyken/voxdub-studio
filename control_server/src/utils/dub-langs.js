'use strict'

/**
 * Mã ngôn ngữ hợp lệ của API lồng tiếng — BẢN SAO CÓ CHỦ ĐÍCH của
 * `autodub/languages.py` (`SOURCE_LANG_MAP` và `TARGETS`).
 *
 * Vì sao phải nhân đôi danh sách: worker Python mới là nơi thực thi, nhưng
 * nó chỉ nhận job SAU khi server đã nhận file, giữ chỗ quota và worker đã
 * chạy xong bước ASR tốn tài nguyên. Không kiểm ở đây thì mã sai chỉ lộ ra
 * ở cuối bằng một lỗi mơ hồ (`translate_pending`) — người gọi API không
 * hiểu mình sai chỗ nào (bug thật, bắt được lúc test e2e 2026-08-17).
 *
 * Thêm ngôn ngữ mới thì sửa `autodub/languages.py` TRƯỚC rồi cập nhật ở
 * đây — `tests/dub-langs.test.js` đọc thẳng file Python để chặn 2 danh sách
 * trôi lệch nhau.
 *
 * Hai tham số dùng HAI định dạng khác nhau, rất dễ nhầm:
 *   - sourceLang: BCP-47 đầy đủ ("vi-VN") HOẶC dạng ngắn ("vi") — cả hai đều
 *     hợp lệ, pipeline tự chuẩn hoá qua `resolve_source_lang()`.
 *   - targetLang: CHỈ khoá ngắn của TARGETS ("vi", "en"…), không phải BCP-47.
 */

const SOURCE_LANGS = Object.freeze([
  'en', 'vi', 'zh', 'ko', 'ja', 'th', 'id',
  'en-US', 'vi-VN', 'zh-CN', 'zh-HK', 'zh-TW', 'ko-KR', 'ja-JP', 'th-TH', 'id-ID',
])

const TARGET_LANGS = Object.freeze([
  'vi', 'en', 'ja', 'zh', 'es', 'th', 'id', 'pt', 'fr', 'de',
])

function isValidSourceLang(lang) {
  return SOURCE_LANGS.includes(String(lang || '').trim())
}

function isValidTargetLang(lang) {
  return TARGET_LANGS.includes(String(lang || '').trim())
}

module.exports = { SOURCE_LANGS, TARGET_LANGS, isValidSourceLang, isValidTargetLang }
