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
    #: File WAV đã đưa cho ASR. Đã bị `_don_tam` xoá lúc xuất xong — giữ lại
    #: đường dẫn để đọc nhật ký, không phải để mở ra dùng.
    audio_path: str
    segments: list[dict]
    outputs: dict[str, str] = field(default_factory=dict)
    title: str = ""

    @property
    def text(self) -> str:
        return "\n".join(str(s.get("text", "")).strip()
                         for s in self.segments if str(s.get("text", "")).strip())


def is_url(source: str) -> bool:
    """Đầu vào này là địa chỉ web hay đường dẫn file?

    Nhận cả dạng THIẾU `https://` (`www.youtube.com/watch?v=…`): yt-dlp vốn
    tải được, chỗ từ chối là ứng dụng — người gõ tay sẽ nhận thông báo "không
    tìm thấy file", đúng kỹ thuật nhưng vô nghĩa với họ. `looks_like_bare_url`
    cố tình hẹp để không bao giờ coi một đường dẫn file là địa chỉ web.
    Lược đồ được `downloader.normalize_url` thêm vào trước khi tải.
    """
    from autodub.utils import looks_like_bare_url

    text = source.strip()
    return (text.lower().startswith(("http://", "https://"))
            or looks_like_bare_url(text))


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


def prepare_audio(source: str, work_dir: str,
                  settings=None) -> tuple[str, str, str]:
    """Đưa mọi kiểu đầu vào về MỘT file WAV 16 kHz cho ASR.

    Trả ``(đường_dẫn_wav, tiêu_đề, đường_dẫn_media)``. Tiêu đề rỗng khi đầu vào
    là file trên máy — chỉ liên kết mới mang sẵn tiêu đề.

    ``đường_dẫn_media`` là file nguồn đã dùng: với liên kết thì đó là video vừa
    TẢI VỀ nằm trong ``work_dir`` (dọn được), với file trên máy thì đó chính là
    file CỦA NGƯỜI DÙNG (tuyệt đối không được đụng vào) — xem `_don_tam`.

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
    return audio_path, title, media_path


def _don_tam(work_dir: str, *duong_dan: str) -> None:
    """Xoá file trung gian sau khi đã xuất xong — mini-spec V73.

    Chép lời từ LIÊN KẾT tải nguyên video về rồi chỉ dùng phần tiếng. Tên file
    đặt theo `<extractor>_<id>` nên mỗi video là một file mới: không dọn thì
    chép lời 20 video YouTube là giữ lại 20 video đầy đủ (hàng GB) mà người
    dùng không hề xin — họ vào đây để lấy CHỮ. Và code không hề dùng lại file
    cũ (luôn tải mới), nên giữ lại không đổi lấy được gì.

    **Chỉ xoá thứ NẰM TRONG ``work_dir``.** Khi đầu vào là file trên máy thì
    `prepare_audio` trả về chính đường dẫn của NGƯỜI DÙNG — xoá nhầm là phá dữ
    liệu gốc của họ, hỏng nặng hơn mọi thứ hàm này định sửa. Nên phép kiểm là
    bắt buộc, không phải cho chắc.

    Chỉ gọi khi đã xuất xong: mục HỎNG thì giữ lại file để còn dò nguyên nhân.
    """
    goc = os.path.realpath(work_dir)
    for duong in duong_dan:
        if not duong:
            continue
        try:
            that = os.path.realpath(duong)
            # commonpath ném ValueError khi hai đường ở hai ổ đĩa khác nhau
            # (Windows) — nghĩa là chắc chắn nằm ngoài work_dir.
            if os.path.commonpath([that, goc]) != goc:
                continue
            os.remove(that)
        except (OSError, ValueError):
            pass        # dọn dẹp không được phép làm hỏng một lượt đã thành công


def _kiem_huy(cancel_event) -> None:
    """Ném `TranscribeCancelled` nếu người dùng đã bấm Dừng — mini-spec V72.

    Gọi ở RANH GIỚI từng bước (sau tải, sau bóc tiếng, trước khi xuất). Bên
    trong bước ASR còn một lớp kiểm nữa ở `transcriber` — bước đó dài nhất nên
    chỉ chặn ở ranh giới thì người dùng vẫn phải chờ hết cả video.
    """
    if cancel_event is not None and cancel_event.is_set():
        from autodub.speech.transcriber import TranscribeCancelled
        raise TranscribeCancelled("Đã dừng theo yêu cầu.")


def transcribe_media(source: str, output_dir: str, settings,
                     language: str = "", formats=("txt", "srt"),
                     with_timestamps: bool = False,
                     progress=None, cancel_event=None,
                     output_name: str = "", taken_names=None) -> TranscribeResult:
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

    # Thiếu FFmpeg thì mọi đường đều gãy, nhưng mỗi đường gãy một kiểu khó
    # hiểu: file trên máy cho `[WinError 2] The system cannot find the file
    # specified`, còn liên kết YouTube cho lỗi của yt-dlp. Nói thẳng ở đây
    # (mini-spec V82).
    from autodub.ffmpeg_deps import bao_dam_co_ffmpeg
    bao_dam_co_ffmpeg(TranscribeError)

    os.makedirs(output_dir, exist_ok=True)
    work_dir = os.path.join(output_dir, "_tam")

    _kiem_huy(cancel_event)
    say("download", "Đang chuẩn bị âm thanh…")
    audio_path, title, media_path = prepare_audio(source, work_dir,
                                                  settings=settings)

    _kiem_huy(cancel_event)

    lang = (language or getattr(settings, "default_source_lang", "") or "").strip()
    say("asr", "Đang nghe và chép lời…")
    from autodub.speech.transcriber import transcribe as run_asr
    segments = run_asr(audio_path, lang, settings, cancel_event=cancel_event)
    if not segments:
        raise TranscribeError(
            "Không nghe được câu nào — file có thể không có tiếng nói, "
            "hoặc sai ngôn ngữ nguồn.")

    # `output_name` do lượt hàng loạt truyền vào để tránh hai nguồn cùng tên
    # ghi đè kết quả của nhau — xem `transcribe_many`.
    #
    # Với LIÊN KẾT thì tên chỉ biết được SAU khi tải xong (lấy từ tiêu đề
    # video), nên việc chống trùng phải làm ở đây chứ không làm trước được:
    # hai tập cùng tên «Tập 1» của hai kênh khác nhau là chuyện thường.
    base = output_name or _du_phong_ten(_output_basename(source, title), taken_names)
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
    _don_tam(work_dir, audio_path, media_path)
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


@dataclass
class BatchItem:
    """Một mục trong lượt chép lời hàng loạt."""
    source: str
    status: str = "cho"          # cho | xong | hong | huy
    result: "TranscribeResult | None" = None
    error: str = ""


def expand_sources(inputs) -> list[str]:
    """Bung danh sách đầu vào — mini-spec V72.

    Nhận lẫn lộn liên kết, file, và THƯ MỤC. Thư mục được duyệt lấy mọi file
    video/âm thanh bên trong (không đệ quy: thư mục con thường là bản nháp,
    file tạm — quét vào là chép lời cả rác).

    Giữ NGUYÊN thứ tự người dùng đưa, và bỏ trùng: dán nhầm hai lần cùng một
    liên kết thì chỉ chạy một lần, không tính tiền/thời gian hai lần.
    """
    VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v"}
    ra: list[str] = []
    da_co: set[str] = set()

    def them(x: str) -> None:
        if x and x not in da_co:
            da_co.add(x)
            ra.append(x)

    for raw in inputs:
        muc = str(raw).strip()
        if not muc:
            continue
        if is_url(muc):
            them(muc)
        elif os.path.isdir(muc):
            for ten in sorted(os.listdir(muc)):
                duong = os.path.join(muc, ten)
                if not os.path.isfile(duong):
                    continue
                if os.path.splitext(ten)[1].lower() in (VIDEO_EXTS | AUDIO_EXTS):
                    them(duong)
        else:
            them(muc)
    return ra


def transcribe_many(sources, output_dir: str, settings, *,
                    language: str = "", formats=("txt", "srt"),
                    with_timestamps: bool = False,
                    on_item=None, cancel_event=None) -> list[BatchItem]:
    """Chép lời nhiều mục, tuần tự — mini-spec V72.

    **Một mục hỏng KHÔNG làm hỏng cả lượt**: nó được đánh dấu `hong` kèm lý do
    và lượt chạy đi tiếp. Dừng cả mẻ vì một liên kết chết là bắt người dùng
    làm lại từ đầu những mục đã tốn thời gian chạy xong.

    Chạy TUẦN TỰ chứ không song song: ASR ăn trọn CPU/GPU, chạy hai lượt cùng
    lúc trên cùng một máy chỉ làm cả hai chậm đi (cùng kết luận với V42 cho
    luồng dub).

    Huỷ giữa chừng: mục đang chạy dừng theo cờ, mọi mục còn lại đánh dấu `huy`
    — kết quả của các mục đã xong vẫn giữ nguyên trên đĩa.
    """
    from autodub.speech.transcriber import TranscribeCancelled

    muc_list = [BatchItem(source=s) for s in expand_sources(sources)]
    ten_da_dung: set[str] = set()
    for i, muc in enumerate(muc_list):
        if cancel_event is not None and cancel_event.is_set():
            for con_lai in muc_list[i:]:
                con_lai.status = "huy"
            break
        try:
            muc.result = transcribe_media(
                muc.source, output_dir, settings, language=language,
                formats=formats, with_timestamps=with_timestamps,
                cancel_event=cancel_event,
                output_name=_ten_khong_trung(muc.source, ten_da_dung),
                taken_names=ten_da_dung)
            muc.status = "xong"
        except TranscribeCancelled:
            for con_lai in muc_list[i:]:
                con_lai.status = "huy"
            if on_item:
                on_item(i, len(muc_list), muc)
            break
        except Exception as e:  # noqa: BLE001 — hỏng 1 mục, không hỏng cả mẻ
            muc.status = "hong"
            muc.error = str(e)
            logger.warning("Chép lời hỏng «%s»: %s", muc.source, e)
        if on_item:
            on_item(i, len(muc_list), muc)
    return muc_list


def _ten_khong_trung(source: str, da_dung: set[str]) -> str:
    """Tên file kết quả KHÔNG đụng tên đã dùng trong cùng lượt — mini-spec V72.

    Hai file cùng tên ở hai thư mục khác nhau (`Tap1/video.mp4` và
    `Tap2/video.mp4`) là chuyện thường. Không xử lý thì file sau ghi đè file
    trước, âm thầm, và người dùng chỉ phát hiện khi mở ra thấy thiếu.

    Tên trùng thì thêm hậu tố `_2`, `_3`… chứ không thêm dấu thời gian: người
    dùng còn phải tìm lại file theo tên, dấu thời gian làm việc đó khó hơn.

    Lưu ý: tên cho LIÊN KẾT vẫn phải chờ tải xong mới biết tiêu đề, nên ở đây
    trả về rỗng để `transcribe_media` tự đặt như thường — chống trùng cho liên
    kết là việc của đợt sau, và ghi rõ ở TEST_LOG chứ không lặng lẽ bỏ qua.
    """
    if is_url(source):
        return ""
    goc = _output_basename(source, "")
    ten = goc
    lan = 2
    while ten in da_dung:
        ten = f"{goc}_{lan}"
        lan += 1
    da_dung.add(ten)
    return ten


def _du_phong_ten(base: str, taken_names) -> str:
    """Thêm hậu tố nếu tên đã bị dùng trong cùng lượt — mini-spec V72b.

    Dùng cho LIÊN KẾT, vì tên của liên kết lấy từ tiêu đề video nên chỉ biết
    sau khi tải xong. Hai tập cùng tên «Tập 1» của hai kênh khác nhau là
    chuyện thường; không xử lý thì file sau ghi đè file trước, âm thầm.

    `taken_names` là ``None`` khi chạy lẻ một mục — không có gì để đụng độ.
    """
    if taken_names is None:
        return base
    ten = base
    lan = 2
    while ten in taken_names:
        ten = f"{base}_{lan}"
        lan += 1
    taken_names.add(ten)
    return ten
