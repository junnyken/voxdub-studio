"""Sinh tệp .srt, có ngắt dòng cho dễ đọc.

Phụ đề bám đúng mốc thời gian từng câu mà bước nghe-chép đã tách (khớp nhịp
video gốc). Phần lớn câu đều ngắn nên đi thẳng 1:1; câu nào quá dài mới bị
chia tiếp thành các dòng hiển thị ngắn (~42 ký tự mỗi hàng, tối đa 2 hàng),
thời gian chia theo số ký tự — đúng cách làm phụ đề chuyên nghiệp.

Chữ hiển thị lấy từ :func:`subtitle_text`: nếu câu có trường phụ đề riêng
(``sub_vi``) thì dùng nó, không thì dùng chính lời đọc. Nhờ vậy sửa một lỗi
chính tả trên phụ đề không bắt phải đọc lại giọng cho câu đó.
"""
from autodub.utils import format_timestamp, setup_logging

logger = setup_logging("autodub.srt_generator")

#: Trường chứa phụ đề riêng, khi người dùng muốn phụ đề khác lời đọc.
SUBTITLE_FIELD = "sub_vi"

# Giới hạn dễ đọc theo chuẩn phụ đề cho tiếng Việt.
MAX_LINE_CHARS = 42
MAX_LINES_PER_CUE = 2
MIN_CUE_SECONDS = 0.8

# mini-spec V19 — chữ CJK (Hán/Kana) render RỘNG hơn chữ Latin cùng cỡ chữ
# (quy ước "East Asian Width" của Unicode gọi đây là ký tự "Wide"/"Fullwidth"
# — chiếm khoảng gấp đôi bề ngang 1 ký tự Latin "Narrow"). Giữ nguyên
# MAX_LINE_CHARS=42 cho CJK sẽ tràn khung hình dù ĐÃ ngắt dòng đúng — hạ
# xuống ~20 ký tự/dòng để bề rộng thật trên màn hình gần khớp với 42 ký tự
# Latin (cũng khớp khuyến nghị phổ biến cho phụ đề tiếng Trung/Nhật trong
# ngành — thường 13-20 ký tự/dòng cho khung hình 16:9, không phải số tự bịa).
MAX_LINE_CHARS_CJK = 20

# mini-spec V19 (docs/PLAN.md, Phase E) — bug thật phát hiện khi audit: mọi
# logic ngắt dòng/ngắt mệnh đề dưới đây dựa vào ``text.split()`` (tách theo
# dấu CÁCH) và dấu câu theo sau có khoảng trắng — đúng cho tiếng Việt/Anh/
# các ngôn ngữ Latin khác (V17/V18), nhưng tiếng Trung/Nhật KHÔNG dùng dấu
# cách giữa chữ (cả câu bị coi là "1 từ" → không bao giờ ngắt dòng, phụ đề
# tràn khung hình) và tiếng Thái chỉ có dấu cách giữa CỤM (không phải từ) →
# ngắt thô. 3 ngôn ngữ này ngắt theo KÝ TỰ thay vì theo từ — đây CHÍNH LÀ
# cách ngắt dòng chuẩn của bản thân CJK (không cần giữ nguyên ranh giới từ
# khi xuống dòng, khác hẳn tiếng Latin), Thái là phương án tạm chấp nhận
# được (ngắt đúng ranh giới từ thật cần bộ tách từ tiếng Thái riêng, ngoài
# phạm vi mini-spec này — xem Remaining Limits trong TEST_LOG).
CHAR_WRAP_LANGS = frozenset({"ja", "zh", "th"})

#: Dấu câu CJK toàn độ rộng — không có khoảng trắng theo sau như tiếng Latin,
#: nên ranh giới mệnh đề (``re.split`` trong ``split_for_display``) phải nhận
#: cả dấu này, không chỉ dấu Latin + \s+.
_CJK_PUNCT = "，。！？；…"


def is_char_wrap_lang(lang_key: str | None) -> bool:
    """True khi ngôn ngữ này nên ngắt dòng phụ đề theo KÝ TỰ thay vì theo từ
    (CJK không có khoảng trắng giữa chữ; Thái chỉ có khoảng trắng giữa cụm,
    không phải giữa từ — cả hai đều làm ``text.split()`` mất tác dụng)."""
    return (lang_key or "").strip().lower() in CHAR_WRAP_LANGS


def subtitle_text(seg: dict, text_field: str = "text_vi") -> str:
    """Chữ sẽ hiện trên phụ đề của một câu.

    Ưu tiên phụ đề riêng ``sub_vi``; trống thì dùng chính lời đọc. Đây là
    hàm DUY NHẤT mọi nơi sinh phụ đề được phép dùng, để phụ đề trong video,
    tệp .srt và bản xem trước không bao giờ lệch nhau.
    """
    override = str(seg.get(SUBTITLE_FIELD, "") or "").strip()
    return override or str(seg.get(text_field, "") or "").strip()


def has_subtitle_override(seg: dict, text_field: str = "text_vi") -> bool:
    """Câu này có phụ đề viết riêng, khác với lời đọc, hay không."""
    override = str(seg.get(SUBTITLE_FIELD, "") or "").strip()
    return bool(override) and override != str(seg.get(text_field, "") or "").strip()


def _wrap_lines(text: str, width: int = MAX_LINE_CHARS,
                line_words: int = 0, char_wrap: bool = False) -> list[str]:
    """Ngắt dòng: theo SỐ CHỮ mỗi hàng khi ``line_words`` > 0, không thì gói
    tham lam theo bề rộng ký tự (chuẩn 42) — không bao giờ cắt giữa một chữ.

    ``char_wrap=True`` (CJK/Thái, xem :func:`is_char_wrap_lang`): ``text``
    không có ranh giới từ đáng tin (không dấu cách hoặc chỉ dấu cách giữa
    cụm) — ngắt thẳng theo KÝ TỰ, bỏ qua ``line_words`` (khái niệm "số chữ
    mỗi hàng" không có nghĩa cho các ngôn ngữ này).
    """
    if char_wrap:
        text = text.strip()
        return [text[i:i + width] for i in range(0, len(text), width)] or []
    if line_words > 0:
        words = text.split()
        return [" ".join(words[i:i + line_words])
                for i in range(0, len(words), line_words)] or []
    lines: list[str] = []
    cur = ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if len(cand) <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def split_for_display(seg: dict, text_field: str, line_words: int = 0,
                      max_lines: int = MAX_LINES_PER_CUE,
                      all_caps: bool = False, lang_key: str | None = None) -> list[dict]:
    """Chia một câu (có thể dài) thành các dòng hiển thị ngắn.

    Ranh giới ưu tiên dấu câu; thời gian chia đều cho các mảnh theo số ký tự.
    Câu đã vừa một dòng hiển thị (trường hợp phổ biến) đi thẳng, không đổi.

    ``line_words`` > 0: người dùng chốt số chữ mỗi hàng — sức chứa một dòng
    hiển thị tính theo CHỮ (line_words × số hàng) thay vì theo ký tự.

    ``lang_key``: mã ngôn ngữ đích (``TargetLang.key``, vd "ja"/"zh"/"th") —
    quyết định ngắt theo từ (mặc định) hay theo ký tự (:func:`is_char_wrap_lang`).
    """
    import re

    text = subtitle_text(seg, text_field)
    if not text:
        return []
    if all_caps:
        text = text.upper()

    max_lines = max(1, int(max_lines or MAX_LINES_PER_CUE))
    char_wrap = is_char_wrap_lang(lang_key)
    # Chữ CJK render rộng hơn Latin cùng cỡ chữ — dùng ngưỡng ký tự/dòng
    # riêng, thấp hơn, để bề rộng thật trên khung hình tương đương nhau.
    line_width = MAX_LINE_CHARS_CJK if char_wrap else MAX_LINE_CHARS

    # Đơn vị đo theo chế độ: chữ (khi chỉnh tay, CHỈ áp dụng cho ngôn ngữ
    # ngắt theo từ) hoặc ký tự (mặc định, và LUÔN LUÔN cho char_wrap).
    if line_words > 0 and not char_wrap:
        def measure(s: str) -> int:
            return len(s.split())
        max_cue = line_words * max_lines
    else:
        measure = len
        max_cue = line_width * max_lines

    def _wrapped(chunk: str) -> str:
        return "\n".join(_wrap_lines(chunk, width=line_width,
                                     line_words=line_words, char_wrap=char_wrap))

    if measure(text) <= max_cue:
        return [{"start": seg["start"], "end": seg["end"],
                 "text": _wrapped(text)}]

    # Cắt ở dấu ngắt mệnh đề trước, rồi dồn thành các mảnh vừa một dòng hiện.
    # \s* (không phải \s+): dấu câu CJK toàn độ rộng không có khoảng trắng
    # theo sau (vd "你好，很vui。") — \s+ sẽ khiến regex này KHÔNG khớp gì cả
    # cho văn bản CJK, cả câu rơi lại thành 1 "mệnh đề" duy nhất.
    parts = [p.strip() for p in
             re.split(rf"(?<=[,.!?;…{_CJK_PUNCT}])\s*", text) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for part in parts:
        # Một mệnh đề dài hơn cả một dòng hiển thị thì phải cắt tiếp.
        while measure(part) > max_cue:
            if char_wrap:
                head = part[:max_cue]
            elif line_words > 0:
                head = " ".join(part.split()[:max_cue])
            else:
                head = " ".join(_wrap_lines(part, max_cue)[:1])
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(head)
            part = part[len(head):].strip()
        # CJK không cần khoảng trắng nối mệnh đề (không tự nhiên trong văn
        # bản Trung/Nhật thật); ngôn ngữ ngắt theo từ vẫn cần khoảng trắng.
        cand = (f"{cur}{part}" if char_wrap else f"{cur} {part}").strip()
        if measure(cand) <= max_cue or not cur:
            cur = cand
        else:
            chunks.append(cur)
            cur = part
    if cur:
        chunks.append(cur)

    # Chia thời gian của câu cho các mảnh theo số ký tự.
    total_chars = sum(len(c) for c in chunks) or 1
    duration = seg["end"] - seg["start"]
    cues = []
    t = seg["start"]
    for i, chunk in enumerate(chunks):
        share = duration * len(chunk) / total_chars
        share = max(share, MIN_CUE_SECONDS
                    if duration >= MIN_CUE_SECONDS * len(chunks) else share)
        end = seg["end"] if i == len(chunks) - 1 else min(t + share, seg["end"])
        cues.append({"start": round(t, 3), "end": round(end, 3),
                     "text": _wrapped(chunk)})
        t = end
    return cues


def generate_srt(segments: list[dict], output_path: str,
                 text_field: str = "text", line_words: int = 0,
                 max_lines: int = MAX_LINES_PER_CUE,
                 all_caps: bool = False, lang_key: str | None = None) -> str:
    lines = []
    n = 0
    for seg in segments:
        for cue in split_for_display(seg, text_field, line_words=line_words,
                                     max_lines=max_lines, all_caps=all_caps,
                                     lang_key=lang_key):
            n += 1
            start_ts = format_timestamp(cue["start"])
            end_ts = format_timestamp(cue["end"])
            lines.append(f"{n}\n{start_ts} --> {end_ts}\n{cue['text']}\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Đã ghi phụ đề: {output_path} ({n} dòng hiện từ "
                f"{len(segments)} câu)")
    return output_path


def generate_srt_styled(segments: list[dict], output_path: str,
                        text_field: str, style: dict | None,
                        lang_key: str | None = None) -> str:
    """Sinh .srt theo đúng kiểu phụ đề người dùng đã chọn.

    Gói lại ba tùy chọn ảnh hưởng tới NỘI DUNG dòng phụ đề (số chữ mỗi hàng,
    số hàng, viết hoa toàn bộ) để pipeline và trình chỉnh sửa không phải bóc
    tay từ dict kiểu — và không nơi nào quên mất một tùy chọn.

    ``lang_key`` (mini-spec V19): mã ngôn ngữ đích — quyết định ngắt dòng
    theo từ hay theo ký tự (xem :func:`is_char_wrap_lang`).
    """
    from autodub.media.subtitle import normalize_style

    s = normalize_style(style)
    return generate_srt(segments, output_path, text_field=text_field,
                        line_words=int(s["line_words"]),
                        max_lines=int(s["max_lines"]),
                        all_caps=bool(s["all_caps"]), lang_key=lang_key)
