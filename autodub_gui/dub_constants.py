"""Hằng số dùng chung cho luồng lồng tiếng.

Gom về một chỗ để trang Tạo dự án, trang Xử lý hàng loạt và trang Trợ giúp
đều đọc cùng một nguồn, không ai chép lại của ai.
"""
from __future__ import annotations

#: Mini-spec V4 (docs/PLAN.md) — mở rộng danh sách nguồn Whisper hỗ trợ sẵn.
#: 4 ngôn ngữ cuối (Hàn/Nhật/Thái/Indonesia) đã live-verify chất lượng ASR
#: (2026-08-11, xem docs/TEST_LOG.md mục V4 — TTS thật + Whisper thật, khớp
#: gần như tuyệt đối cả 4 ngôn ngữ). Giới hạn còn lại: verify dùng giọng đọc
#: TTS rõ ràng, chưa thử video thật có nhạc nền/giọng vùng miền.
SOURCE_LANGS: list[tuple[str, str]] = [
    ("Tiếng Trung (zh-CN)", "zh-CN"),
    ("Tiếng Anh (en-US)", "en-US"),
    ("Tiếng Trung - Hồng Kông (zh-HK)", "zh-HK"),
    ("Tiếng Trung - Đài Loan (zh-TW)", "zh-TW"),
    ("Tiếng Hàn (ko-KR)", "ko-KR"),
    ("Tiếng Nhật (ja-JP)", "ja-JP"),
    ("Tiếng Thái (th-TH)", "th-TH"),
    ("Tiếng Indonesia (id-ID)", "id-ID"),
    # Thêm 22/8/2026 theo yêu cầu người dùng thật. Whisper nghe được tiếng
    # Việt sẵn — KHÔNG cần cài thêm bộ nhận dạng nào (Paraformer chỉ dành cho
    # tiếng Trung). Bộ dịch ngoại tuyến cũng đã biết tiếng Việt từ trước
    # (`translate_local.py`: "vi-VN" → "vie_Latn"), nên đây thuần là thêm một
    # dòng vào danh sách chọn.
    #
    # Có nghĩa khi ĐÍCH khác tiếng Việt (video tiếng Việt → lồng tiếng Anh,
    # Nhật…). Nguồn và đích cùng tiếng Việt thì không có gì để dịch — xem
    # `cung_ngon_ngu()`.
    ("Tiếng Việt (vi-VN)", "vi-VN"),
]

#: Mã nguồn (BCP-47) → khoá đích tương ứng, để biết nguồn và đích có trùng
#: ngôn ngữ không.
_NGUON_SANG_DICH = {
    "vi-VN": "vi", "en-US": "en", "ja-JP": "ja", "th-TH": "th",
    "id-ID": "id", "ko-KR": "ko",
    "zh-CN": "zh", "zh-HK": "zh", "zh-TW": "zh",
}


def cung_ngon_ngu(source_lang: str, target_key: str) -> bool:
    """Nguồn và đích có cùng một ngôn ngữ không.

    Dịch tiếng Việt sang tiếng Việt thì không có gì để dịch: người dùng mất
    tiền cho một lượt gọi mô hình chỉ để nhận lại gần đúng câu cũ. Chặn sớm
    và chỉ sang trang Chép lời — đó mới là thứ họ đang cần.
    """
    if not source_lang or not target_key:
        return False
    return _NGUON_SANG_DICH.get(source_lang, "") == target_key

#: Paraformer (autodub/speech/paraformer_transcriber.py) chỉ hỗ trợ tiếng
#: Trung — dùng để cảnh báo trong GUI khi chọn kèm ngôn ngữ khác (backend đã
#: tự fallback về Whisper an toàn, xem transcriber.transcribe(); đây chỉ là
#: cảnh báo sớm, tránh người dùng ngỡ ngàng vì tưởng đang dùng Paraformer).
PARAFORMER_SOURCE_PREFIX = "zh"


def paraformer_language_mismatch(asr_engine: str, source_lang: str) -> bool:
    """True khi đã chọn Paraformer nhưng ngôn ngữ nguồn không phải tiếng Trung."""
    return (asr_engine == "paraformer"
            and not (source_lang or "").lower().startswith(PARAFORMER_SOURCE_PREFIX))

ASR_ENGINES: list[tuple[str, str]] = [
    ("Whisper — nghe được mọi ngôn ngữ", "whisper"),
    ("Paraformer — chuyên tiếng Trung", "paraformer"),
]

WHISPER_MODELS: list[tuple[str, str]] = [
    ("Tự chọn (khuyên dùng)", "auto"),
    ("Nhanh nhất (tiny)", "tiny"),
    ("Nhanh (base)", "base"),
    ("Khá (small)", "small"),
    ("Chính xác (medium)", "medium"),
    ("Chính xác nhất (large-v3)", "large-v3"),
]

BG_MODES: list[tuple[str, str]] = [
    ("Tách giọng gốc, giữ nguyên nhạc nền", "demucs"),
    ("Giảm nhỏ tiếng gốc khi có lời thoại", "duck"),
    ("Bỏ hết âm thanh gốc", "none"),
    # Mini-spec V37 (docs/PLAN.md, Phase G) — nhạc nền do AI sinh
    # (ElevenLabs), sinh qua khối "Nhạc nền & hiệu ứng AI" ở Trình chỉnh
    # sửa (data/ai_music.wav) — chọn mục này KHÔNG tự sinh nhạc, chỉ dùng
    # bản đã sinh sẵn (chưa sinh -> im lặng, giống các chế độ khác khi
    # thiếu file nguồn, xem `editor.resolve_existing_background()`).
    ("Nhạc nền AI (ElevenLabs)", "ai_music"),
]

SUBTITLE_MODES: list[tuple[str, str]] = [
    ("Không gắn phụ đề", "none"),
    ("Phụ đề rời, người xem tự bật", "soft"),
    ("Ghi thẳng vào hình", "burn"),
]

# Ngôn ngữ đích khi lồng tiếng (mini-spec V11, xem docs/PLAN.md). Nhãn hiển
# thị lấy tay ở đây (tiếng Việt, cho người dùng) — khoá "vi"/"en" khớp với
# autodub.languages.TARGETS (nguồn thật cho lõi xử lý). Tiếng Anh đánh dấu
# thử nghiệm: engine giọng đọc chỉ có CapCut (qua mạng), chưa có giọng
# offline như VieNeu cho tiếng Việt.
#: Mini-spec V17 (docs/PLAN.md, Phase E) — mở rộng đích theo catalog giọng
#: CapCut thật (autodub/speech/tts/capcut_api/Voice.json). Tất cả (trừ vi)
#: đánh dấu "thử nghiệm" — chỉ tiếng Nhật đã live-verify (xem TEST_LOG mục
#: V17); 7 ngôn ngữ còn lại code đúng/giọng có thật nhưng CHƯA chạy pipeline
#: thật (đúng nguyên tắc V4/V11: mở rộng có kiểm chứng, không giả vờ).
DUB_TARGETS: list[tuple[str, str]] = [
    ("Tiếng Việt", "vi"),
    ("Tiếng Anh (thử nghiệm, cần mạng cho giọng đọc)", "en"),
    ("Tiếng Nhật (thử nghiệm, cần mạng cho giọng đọc)", "ja"),
    ("Tiếng Trung (thử nghiệm, cần mạng cho giọng đọc)", "zh"),
    ("Tiếng Tây Ban Nha (thử nghiệm, cần mạng, chưa kiểm chứng ASR/dịch thật)", "es"),
    ("Tiếng Thái (thử nghiệm, cần mạng, chưa kiểm chứng ASR/dịch thật)", "th"),
    ("Tiếng Indonesia (thử nghiệm, cần mạng, chưa kiểm chứng ASR/dịch thật)", "id"),
    ("Tiếng Bồ Đào Nha (thử nghiệm, cần mạng, chưa kiểm chứng ASR/dịch thật)", "pt"),
    ("Tiếng Pháp (thử nghiệm, cần mạng, chưa kiểm chứng ASR/dịch thật)", "fr"),
    ("Tiếng Đức (thử nghiệm, cần mạng, chưa kiểm chứng ASR/dịch thật)", "de"),
]

# Sáu phong cách dịch. Chuỗi ghi chú được nối thêm vào phần hướng dẫn dịch
# mà lõi xử lý đã đọc sẵn, nên không phải sửa gì trong lõi.
TRANSLATE_STYLES: list[tuple[str, str, str]] = [
    ("Tự nhiên, gần gũi (mặc định)", "natural", ""),
    ("Trang trọng", "formal",
     "Dịch trang trọng, lịch sự, dùng từ chuẩn mực; tránh tiếng lóng."),
    ("Sát nghĩa", "literal",
     "Bám sát nghĩa gốc, giữ nguyên cấu trúc câu khi tiếng Việt vẫn xuôi."),
    ("Sáng tạo", "creative",
     "Dịch thoáng, ưu tiên câu chữ mượt và hấp dẫn hơn là bám từng chữ."),
    ("Hài hước", "humorous",
     "Giữ giọng vui, dí dỏm; dùng cách nói đời thường của giới trẻ Việt."),
    ("Hợp mạng xã hội", "social",
     "Câu ngắn, nhịp nhanh, dễ nghe khi lướt; tránh câu dài lê thê."),
]

# Dung lượng thật của từng phần cần tải thêm, hiện trong Cài đặt và Trợ giúp.
MODEL_SIZES: dict[str, str] = {
    "tiny": "khoảng 75 MB",
    "base": "khoảng 145 MB",
    "small": "khoảng 480 MB",
    "medium": "khoảng 1.5 GB",
    "large-v3": "khoảng 3.1 GB",
    "paraformer": "khoảng 1.2 GB",
    "vieneu": "khoảng 0.9 GB",
}

# Bảng dịch lỗi kỹ thuật sang lời khuyên cho người dùng.
# Mỗi mục gồm: chuỗi nhận dạng, tiêu đề ngắn, việc cần làm.
FRIENDLY_ERRORS: list[tuple[str, str, str]] = [
    ("Thiếu cấu hình bắt buộc", "Thiếu cấu hình",
     "Mở trang Cài đặt và điền các mục còn trống, rồi chạy lại."),
    ("Không đủ Vox", "Hết Vox",
     "Mở trang Tài khoản để nạp thêm, rồi chạy tiếp thư mục dự án đang dở. "
     "Phần đã dịch xong vẫn được giữ nguyên, không phải trả tiền lần nữa."),
    ("Không kết nối được máy chủ", "Mất kết nối máy chủ",
     "Kiểm tra mạng rồi chạy tiếp thư mục dự án đang dở. Phần đã dịch xong "
     "vẫn được giữ nguyên."),
    ("đang bảo trì", "Máy chủ đang bảo trì",
     "Thử lại sau ít phút. Các bước chạy trên máy (nghe chép, giọng đọc, "
     "xuất video) vẫn dùng bình thường."),
    ("Thiết bị này đã bị khóa", "Thiết bị bị khóa",
     "Liên hệ hỗ trợ kèm mã máy hiện ở trang Tài khoản."),
    ("Máy chủ đang bận", "Máy chủ đang quá tải",
     "Chờ một chút rồi chạy tiếp thư mục dự án đang dở."),
    ("CUDA out of memory", "Card đồ họa không đủ bộ nhớ",
     "Đóng bớt ứng dụng đang dùng card đồ họa như trò chơi hoặc trình duyệt "
     "mở nhiều video, hoặc đổi Nhạc nền sang Giảm nhỏ tiếng gốc cho nhẹ hơn, "
     "rồi chạy tiếp thư mục dự án đang dở."),
    # V82 — hai dòng lỗi người dùng thật sự gặp đều KHÔNG có chữ nào gợi ý
    # FFmpeg với người không rành: mã lỗi của Windows khi không tìm thấy
    # chương trình, và lời than của yt-dlp. Bắt cả hai.
    # V85 — TikTok (và đôi khi Facebook/Instagram) chặn máy tải ẩn danh:
    # yt-dlp báo "Unexpected response from webpage request", không gợi ý gì.
    # Cách chữa CÓ THẬT trong app là mượn cookie trình duyệt (COOKIES_FROM_
    # BROWSER trong Cài đặt) — nói thẳng ra thay vì để người dùng đi báo lỗi
    # cho yt-dlp như thông báo gốc bảo.
    ("unexpected response from webpage request", "Trang video chặn lượt tải",
     "Trang này (thường là TikTok) đòi trình duyệt đã đăng nhập. Mở Cài đặt "
     "→ thẻ Nâng cao → mục \"Tải video khó\", chọn trình duyệt bạn hay dùng "
     "rồi thử lại. Hoặc tải video về máy bằng trình duyệt rồi dùng nút Tải "
     "tệp lên."),
    ("ffmpeg", "Máy chưa có FFmpeg",
     "Mở lại ứng dụng rồi bấm \"Tải giúp tôi\" ở hộp thoại hiện ra — ứng "
     "dụng tự tải giúp (~80 MB). Hoặc chép ffmpeg.exe và ffprobe.exe vào "
     "thư mục bin nằm cạnh ứng dụng."),
    ("the system cannot find the file specified", "Máy chưa có FFmpeg",
     "Windows không tìm thấy chương trình phụ trợ (thường là FFmpeg). Mở lại "
     "ứng dụng rồi bấm \"Tải giúp tôi\" ở hộp thoại hiện ra, hoặc chép "
     "ffmpeg.exe và ffprobe.exe vào thư mục bin nằm cạnh ứng dụng."),
    ("winerror 2", "Máy chưa có FFmpeg",
     "Windows không tìm thấy chương trình phụ trợ (thường là FFmpeg). Mở lại "
     "ứng dụng rồi bấm \"Tải giúp tôi\" ở hộp thoại hiện ra, hoặc chép "
     "ffmpeg.exe và ffprobe.exe vào thư mục bin nằm cạnh ứng dụng."),
    ("VieNeu worker", "Bộ giọng đọc gặp sự cố",
     "Chọn chạy tiếp thư mục dự án đang dở để tiếp tục từ chỗ dừng. Nếu vẫn "
     "lỗi, cài lại một lần: py scripts/setup_vieneu.py"),
    ("Chưa cài bộ giọng VieNeu", "Chưa cài bộ giọng",
     "Chạy một lần: py scripts/setup_vieneu.py — sau đó mở lại ứng dụng."),
    ("Không tìm thấy video gốc", "Không tìm thấy video gốc",
     "Thư mục này không còn video gốc, có thể video nằm ở nơi khác hoặc đã bị "
     "xóa. Chọn lại tệp video rồi bấm chạy — ứng dụng sẽ tiếp tục từ chỗ dừng "
     "và ghi nhớ vị trí video cho lần sau."),
    ("chưa có bản âm thanh đã ghép", "Chưa xuất video lần nào",
     "Bấm Xuất video một lần để tạo bản âm thanh, sau đó mới ghi riêng phụ "
     "đề được."),
]


def style_note(key: str) -> str:
    """Ghi chú phong cách dịch ứng với một mã, không có thì trả về chuỗi rỗng."""
    for _label, style_key, note in TRANSLATE_STYLES:
        if style_key == key:
            return note
    return ""


def friendly_error(message: str) -> tuple[str, str] | None:
    """Đổi thông báo lỗi kỹ thuật thành cặp (tiêu đề, việc cần làm)."""
    lowered = (message or "").lower()
    for needle, title, advice in FRIENDLY_ERRORS:
        if needle.lower() in lowered:
            return title, advice
    return None


def friendly_assist_error(message: str) -> str:
    """Lỗi của cổng trợ lý, nói bằng tiếng người (mini-spec V89).

    Trợ lý là lớp BỒI THÊM: hỏng thì người dùng vẫn làm việc bình thường
    được. Nên lời báo phải ngắn, nói rõ còn dùng được gì, và tuyệt đối không
    dựng lên như một sự cố nghiêm trọng.
    """
    thap = (message or "").lower()
    if "tài khoản" in thap or "chưa cấu hình" in thap:
        return "Tính năng này cần tài khoản VoxDub — mở Cài đặt để kết nối."
    if "insufficient" in thap or "không đủ vox" in thap:
        return "Không đủ Vox cho lượt này. Mọi thứ khác vẫn dùng bình thường."
    if "daily_limit" in thap or "hết" in thap and "lượt" in thap:
        return "Hôm nay đã dùng hết lượt trợ lý. Thử lại vào ngày mai."
    if "timeout" in thap or "timed out" in thap or "mạng" in thap:
        return "Trợ lý phản hồi chậm — thử lại sau ít phút."
    return "Trợ lý chưa trả lời được. Bạn vẫn làm tiếp bình thường được."
