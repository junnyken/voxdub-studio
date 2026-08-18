"""Chuyển giọng nói thành văn bản — mini-spec V71 (docs/PLAN.md, Phase H).

Nhận LIÊN KẾT (YouTube/Facebook/TikTok/Douyin…), file video, hoặc file âm
thanh; trả về văn bản kèm mốc thời gian.

**Lớp này CỐ Ý mỏng.** Mọi mảnh nặng đã tồn tại và đã chạy thật trong luồng
dub: `download_one` tải liên kết (V54/V67, đã verify với Facebook thật),
`extract_audio` bóc tiếng, `transcribe` chạy Whisper/Paraformer trong venv
riêng, `generate_srt` xuất phụ đề. Việc ở đây là nối chúng lại và xuất ra
đúng định dạng người dùng cần — KHÔNG dựng ASR mới.

Vì sao tách khỏi `pipeline.py`: luồng dub luôn chạy tiếp sang dịch + TTS +
ghép video. Ai chỉ cần bản chữ thì mọi bước sau ASR đều là thời gian và tiền
bỏ đi. Đây là đường đi RIÊNG dừng lại đúng chỗ, không phải một cờ `--skip-*`
cắm thêm vào pipeline (cắm cờ vào một luồng dài là cách sinh ra những nhánh
không ai test).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from autodub.utils import setup_logging

logger = setup_logging("autodub.transcribe")

#: Đuôi file coi là ÂM THANH — bỏ qua bước bóc tiếng khỏi video.
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}

#: Định dạng xuất. `txt` để đọc/soạn lại, `srt`/`vtt` để gắn vào video,
#: `json` giữ nguyên mốc thời gian từng câu cho ai muốn xử lý tiếp.
FORMATS = ("txt", "srt", "vtt", "json")


class TranscribeError(RuntimeError):
    """Lỗi có thể nói thẳng cho người dùng."""


@dataclass
class TranscribeResult:
    source: str
    audio_path: str
    segments: list[dict]
    outputs: dict[str, str] = field(default_factory=dict)
    title: str = ""

    @property
    def text(self) -> str:
        return "\n".join(str(s.get("text", "")).strip()
                         for s in self.segments if str(s.get("text", "")).strip())


def is_url(source: str) -> bool:
    return source.strip().lower().startswith(("http://", "https://"))


def is_audio_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_EXTS


def _vtt_timestamp(seconds: float) -> str:
    """VTT dùng DẤU CHẤM cho mili-giây, SRT dùng dấu phẩy — đổi nhầm là trình
    phát bỏ qua cả file mà không báo lỗi gì."""
    # Làm tròn về mili-giây TRƯỚC rồi mới tách giờ/phút/giây.
    #
    # Bản đầu tách trước rồi mới xử lý ca ms==1000 bằng cách `s += 1`, và test
    # bắt được ngay: 59.9999 ra `00:00:60.000` — trình phát từ chối cả file vì
    # không có giây thứ 60. Cộng bù ở một bậc thì phải cộng bù ở mọi bậc, nên
    # cách đúng là đừng để phát sinh bậc nào cần bù.
    tong_ms = int(round(max(0.0, float(seconds)) * 1000))
    ms = tong_ms % 1000
    tong_giay = tong_ms // 1000
    h, rem = divmod(tong_giay, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def write_vtt(segments: list[dict], output_path: str) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        lines.append(f"{_vtt_timestamp(seg.get('start', 0))} --> "
                     f"{_vtt_timestamp(seg.get('end', 0))}")
        lines.append(text)
        lines.append("")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path


def write_txt(segments: list[dict], output_path: str,
              with_timestamps: bool = False) -> str:
    lines = []
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        if with_timestamps:
            lines.append(f"[{_vtt_timestamp(seg.get('start', 0))}] {text}")
        else:
            lines.append(text)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    return output_path


def prepare_audio(source: str, work_dir: str, settings=None) -> tuple[str, str]:
    """Đưa mọi kiểu đầu vào về MỘT file WAV 16 kHz cho ASR.

    Trả ``(đường_dẫn_wav, tiêu_đề)``. Tiêu đề rỗng khi đầu vào là file trên máy
    — chỉ liên kết mới mang sẵn tiêu đề.

    File âm thanh vẫn phải đi qua ffmpeg chứ không dùng thẳng: ASR cần 16 kHz
    mono, mà mp3 tải trên mạng thường 44.1 kHz stereo.
    """
    os.makedirs(work_dir, exist_ok=True)
    title = ""

    if is_url(source):
        from autodub.media.downloader import download_one
        logger.info("Đang tải: %s", source)
        info = download_one(source, work_dir, settings=settings)
        media_path = info["filepath"]
        title = str(info.get("title") or "")
    else:
        media_path = source
        if not os.path.isfile(media_path):
            raise TranscribeError(f"Không tìm thấy file: {media_path}")

    audio_path = os.path.join(work_dir, "asr_16k.wav")
    from autodub.media.audio import extract_audio
    # `extract_audio` chạy được cho cả video lẫn file âm thanh thuần: ffmpeg
    # chỉ quan tâm có luồng audio hay không.
    extract_audio(media_path, audio_path)
    if not os.path.isfile(audio_path) or os.path.getsize(audio_path) == 0:
        raise TranscribeError(
            "Không bóc được tiếng từ file này — kiểm tra xem nó có tiếng không.")
    return audio_path, title


def transcribe_media(source: str, output_dir: str, settings,
                     language: str = "", formats=("txt", "srt"),
                     with_timestamps: bool = False,
                     progress=None) -> TranscribeResult:
    """Chuyển một liên kết/file thành văn bản.

    ``language``: mã ngôn ngữ NGUỒN (vd ``en``, ``vi``, ``zh``). Để trống thì
    dùng `settings.default_source_lang` — cùng quy ước với luồng dub, không
    đẻ ra mặc định thứ hai.
    """
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        raise TranscribeError(
            f"Định dạng không hỗ trợ: {', '.join(unknown)}. "
            f"Chọn trong: {', '.join(FORMATS)}.")

    def say(step: str, detail: str = "") -> None:
        logger.info("%s %s", step, detail)
        if progress:
            progress(step, detail)

    os.makedirs(output_dir, exist_ok=True)
    work_dir = os.path.join(output_dir, "_tam")

    say("download", "Đang chuẩn bị âm thanh…")
    audio_path, title = prepare_audio(source, work_dir, settings=settings)

    lang = (language or getattr(settings, "default_source_lang", "") or "").strip()
    say("asr", "Đang nghe và chép lời…")
    from autodub.speech.transcriber import transcribe as run_asr
    segments = run_asr(audio_path, lang, settings)
    if not segments:
        raise TranscribeError(
            "Không nghe được câu nào — file có thể không có tiếng nói, "
            "hoặc sai ngôn ngữ nguồn.")

    base = _output_basename(source, title)
    result = TranscribeResult(source=source, audio_path=audio_path,
                              segments=segments, title=title)

    say("export", f"Đang xuất {len(segments)} câu…")
    for fmt in formats:
        path = os.path.join(output_dir, f"{base}.{fmt}")
        if fmt == "txt":
            write_txt(segments, path, with_timestamps=with_timestamps)
        elif fmt == "vtt":
            write_vtt(segments, path)
        elif fmt == "srt":
            from autodub.text.srt import generate_srt
            generate_srt(segments, path)
        elif fmt == "json":
            from autodub.speech.transcriber import save_transcript
            save_transcript(segments, path)
        result.outputs[fmt] = path

    say("done", f"Xong: {len(segments)} câu")
    return result


def _output_basename(source: str, title: str) -> str:
    """Tên file kết quả — ưu tiên tiêu đề video, lùi về tên file gốc.

    Bỏ ký tự Windows cấm (`\\ / : * ? " < > |`); tên rỗng sau khi lọc thì dùng
    `ban_ghi` chứ không sinh ra file tên `.txt` không mở được.
    """
    raw = title.strip() if title.strip() else (
        "" if is_url(source) else os.path.splitext(os.path.basename(source))[0])
    sach = "".join("_" if c in '\\/:*?"<>|' else c for c in raw).strip()
    sach = " ".join(sach.split())[:80].strip(". ")
    # Tiêu đề toàn ký tự cấm sẽ thành một chuỗi gạch dưới — không rỗng nên lọt
    # qua phép kiểm `or`, mà cũng chẳng nói lên gì. Đòi có ít nhất một chữ
    # hoặc số thì mới coi là tên dùng được.
    if not any(c.isalnum() for c in sach):
        return "ban_ghi"
    return sach
