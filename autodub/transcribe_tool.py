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


#: Câu phải nằm TRỌN trong vùng im, trừ ra ngần này giây ở hai đầu.
#: Mốc của bộ nghe và mốc của bộ dò âm lượng không khớp tuyệt đối.
_LE_VUNG_IM = 0.3


def loc_cau_trong_vung_im(segments: list[dict],
                          vung_im: list[tuple[float, float]]
                          ) -> tuple[list[dict], int]:
    """Bỏ những câu nằm TRỌN trong một vùng im (mini-spec C29).

    Vì sao cần, dù đã có `loc_lap_lai`: bộ lọc kia chỉ bắt được câu bịa LẶP
    LẠI. Một câu bịa đứng lẻ giữa quãng im thì lọt. Mà chỗ im thì theo định
    nghĩa **không có gì để chép** — câu nào hiện ra ở đó đều là bịa.

    Chỉ bỏ khi câu nằm TRỌN trong vùng im, có trừ lề: câu bắt đầu trong chỗ im
    rồi kéo sang chỗ có tiếng là câu thật bị dò lệch mốc, không được đụng tới.
    """
    if not vung_im:
        return segments, 0
    ra: list[dict] = []
    bo = 0
    for seg in segments:
        dau = float(seg.get("start", 0) or 0)
        cuoi = float(seg.get("end", 0) or 0)
        trong_im = any(v_dau - _LE_VUNG_IM <= dau and cuoi <= v_cuoi + _LE_VUNG_IM
                       for v_dau, v_cuoi in vung_im)
        if trong_im:
            bo += 1
            logger.warning(
                f"Bỏ câu ở {dau:.0f}s — nằm trọn trong chỗ im: "
                f"«{str(seg.get('text', ''))[:60]}»")
        else:
            ra.append(seg)
    return ra, bo


def _chuan_hoa_so_sanh(chu: str) -> str:
    """Bỏ dấu câu và chữ hoa để so hai câu có PHẢI CÙNG MỘT CÂU không."""
    import re

    return re.sub(r"[^\w\s]", "", str(chu or "")).lower().strip()


def loc_lap_lai(segments: list[dict], toi_thieu: int = 3) -> tuple[list[dict], int]:
    """Bỏ những câu lặp lại liên tiếp do mô hình BỊA (mini-spec C28).

    Whisper học từ hàng triệu phụ đề YouTube, nên gặp quãng im nó lấp chỗ
    trống bằng đúng những câu quen thuộc nhất: "các bạn hãy đăng ký kênh",
    "hãy subscribe"… Chạy thật trên bài giảng 3 giờ 43: từ phút 33 tới 37 in
    ra một dòng như thế mỗi 40 giây, trong khi không ai nói câu nào.

    **Chỉ gộp khi lặp từ `toi_thieu` lần liên tiếp trở lên.** Người nói lặp
    hai lần là chuyện thật ("Không. Không."); lặp bốn năm lần y hệt thì gần
    như chắc chắn là máy bịa. Giữ MỘT bản, bỏ phần thừa.

    Trả `(danh sách đã lọc, số câu đã bỏ)` — số đó phải nói ra, vì im lặng
    xoá chữ của người dùng là điều tệ nhất một công cụ chép lời có thể làm.
    """
    ra: list[dict] = []
    bo = 0
    i = 0
    while i < len(segments):
        chu = _chuan_hoa_so_sanh(segments[i].get("text", ""))
        j = i + 1
        while (j < len(segments)
               and chu
               and _chuan_hoa_so_sanh(segments[j].get("text", "")) == chu):
            j += 1
        dai = j - i
        if dai >= toi_thieu:
            ra.append(segments[i])
            bo += dai - 1
        else:
            ra.extend(segments[i:j])
        i = j
    return ra, bo


#: Gộp câu cho bản .txt (mini-spec C27).
#:
#: Bộ nghe bật lọc khoảng lặng ngưỡng 0,5 giây, nên người nói chậm — giảng
#: bài, đọc chậm — bị cắt câu ở MỌI nhịp ngắt. Kết quả: mỗi dòng 1-2 chữ.
#: Với tệp 3 giờ 43 là khoảng tám nghìn dòng, đúng chữ nhưng không đọc nổi.
#:
#: Gộp ở khâu GHI .txt chứ không ở khâu nghe: phụ đề (.srt/.vtt) CẦN từng
#: mẩu ngắn để hiện kịp trên màn hình, gộp ở đó là làm hỏng phụ đề.
_GOP_TOI_DA_GIAY = 14.0
_GOP_TOI_DA_CHU = 220
_KHOANG_NGHI_TACH_DOAN = 1.2
_DAU_KET_CAU = ".!?…"


def gop_cau(segments: list[dict]) -> list[dict]:
    """Nối các mẩu ngắn liền nhau thành câu đọc được.

    Ba lý do để CẮT sang dòng mới, theo thứ tự ưu tiên:

    1. Mẩu trước kết thúc bằng dấu chấm câu — đó là ranh giới thật.
    2. Người nói nghỉ hơn `_KHOANG_NGHI_TACH_DOAN` giây — nghỉ dài thường là
       hết ý, kể cả khi bộ nghe không đánh dấu chấm.
    3. Dòng đã quá dài (theo thời lượng hoặc số chữ) — không có ranh giới nào
       thì vẫn phải xuống dòng, chứ không để một dòng dài vô tận.

    Mốc thời gian của dòng gộp là mốc của mẩu ĐẦU TIÊN: người đọc tua tới đó
    để nghe lại thì phải rơi vào đầu câu, không phải giữa câu.
    """
    ra: list[dict] = []
    for seg in segments:
        chu = str(seg.get("text", "")).strip()
        if not chu:
            continue
        dau = float(seg.get("start", 0) or 0)
        cuoi = float(seg.get("end", 0) or 0)

        if ra:
            truoc_do = ra[-1]
            het_cau = truoc_do["text"].rstrip().endswith(tuple(_DAU_KET_CAU))
            nghi = dau - float(truoc_do["end"])
            qua_dai = (cuoi - float(truoc_do["start"]) > _GOP_TOI_DA_GIAY
                       or len(truoc_do["text"]) + len(chu) > _GOP_TOI_DA_CHU)
            if not (het_cau or nghi > _KHOANG_NGHI_TACH_DOAN or qua_dai):
                truoc_do["text"] = f"{truoc_do['text']} {chu}".strip()
                truoc_do["end"] = cuoi
                continue

        ra.append({"start": dau, "end": cuoi, "text": chu})
    return ra


def doc_txt_co_moc(duong_dan: str) -> list[dict]:
    """Đọc ngược một bản chép lời `.txt` có mốc thời gian thành danh sách câu.

    Dùng để GỘP LẠI một tệp đã xuất bằng bản cũ (mini-spec C27) — người dùng
    chạy mất vài giờ rồi mới có bản vá thì không thể bảo họ chạy lại.

    Dòng không đúng khuôn `[mm:ss] chữ` được nối vào câu ngay trước: bản chép
    lời có thể có dòng chú thích đầu tệp, và vứt đi là mất chữ.
    """
    import re

    cau: list[dict] = []
    with open(duong_dan, encoding="utf-8") as f:
        for dong in f:
            dong = dong.rstrip("\n")
            if not dong.strip() or dong.lstrip().startswith("#"):
                continue
            m = re.match(r"\s*\[(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)\]\s*(.*)", dong)
            if not m:
                if cau:
                    cau[-1]["text"] = f"{cau[-1]['text']} {dong.strip()}".strip()
                continue
            gio = int(m.group(1) or 0)
            giay = gio * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            cau.append({"start": giay, "end": giay, "text": m.group(4).strip()})

    # Mỗi câu kết thúc ở lúc câu sau bắt đầu — tệp .txt không ghi mốc kết
    # thúc, mà `gop_cau` cần nó để biết người nói nghỉ bao lâu.
    for i, c in enumerate(cau[:-1]):
        c["end"] = cau[i + 1]["start"]
    return cau


def gop_tep_txt(duong_dan: str, duong_ra: str = "") -> str:
    """Gộp câu cho một tệp `.txt` đã xuất sẵn. Trả về đường dẫn tệp mới.

    KHÔNG ghi đè tệp gốc: bản vụn vẫn là dữ liệu thật của người dùng, và gộp
    sai thì họ còn đường quay lại.
    """
    cau = doc_txt_co_moc(duong_dan)
    if not cau:
        raise ValueError(
            "Tệp này không có dòng nào dạng [phút:giây] chữ — có thể không "
            "phải bản chép lời có mốc thời gian.")
    # Tệp xuất bằng bản cũ còn nguyên các câu bịa lặp lại (mini-spec C28) —
    # lọc luôn ở đây, vì đó chính là tệp cần cứu.
    cau, so_bo = loc_lap_lai(cau)
    if so_bo:
        logger.warning(f"Đã bỏ {so_bo} câu lặp lại liên tiếp.")
    goc, duoi = os.path.splitext(duong_dan)
    duong_ra = duong_ra or f"{goc}_da_gop{duoi or '.txt'}"
    write_txt(cau, duong_ra, with_timestamps=True, gop=True)
    logger.info(f"Gộp {len(cau)} mẩu thành bản dễ đọc: «{duong_ra}»")
    return duong_ra


def write_txt(segments: list[dict], output_path: str,
              with_timestamps: bool = False, gop: bool = True) -> str:
    """Ghi bản chép lời ra .txt.

    `gop=True` (mặc định) nối các mẩu ngắn thành câu — xem `gop_cau`.
    """
    if gop:
        segments = gop_cau(segments)
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

    # Ghi DẦN từng câu ra một tệp tạm (mini-spec C24).
    #
    # Trước đây kết quả chỉ ghi ra đĩa khi xong hết. Với file vài giờ, hỏng ở
    # phút thứ 200 là mất sạch — và người dùng không có gì trong tay để biết
    # nó đã nghe được tới đâu. Nay mỗi câu nghe được là ghi thêm một dòng,
    # nối đuôi nên không tốn công ghi lại từ đầu.
    ten_tam = f"{output_name or 'chep_loi'}{DUOI_DANG_CHAY}"
    duong_tam = os.path.join(output_dir, ten_tam)
    os.makedirs(output_dir, exist_ok=True)
    ghi_dan = _GhiDan(duong_tam)
    try:
        segments = _chep_mot_hoac_nhieu_doan(
            audio_path, lang, settings, run_asr,
            cancel_event=cancel_event, ghi_dan=ghi_dan, say=say)
    except BaseException:
        # Giữ NGUYÊN tệp dở và nói chỗ của nó. Hỏng giữa chừng mà xoá luôn
        # phần đã nghe được là lấy đi thứ duy nhất còn cứu được.
        ghi_dan.dong()
        if ghi_dan.so_cau:
            logger.warning(
                f"Dừng giữa chừng — {ghi_dan.so_cau} câu đã nghe được vẫn "
                f"nằm ở «{duong_tam}».")
        raise
    ghi_dan.dong()

    # Bỏ những câu lặp do mô hình bịa (mini-spec C28). Lọc ở ĐÂY chứ không ở
    # khâu ghi .txt: câu bịa là dữ liệu SAI, nên phụ đề và .json cũng không
    # được có nó — khác hẳn chuyện gộp câu, vốn chỉ là cách trình bày.
    segments, so_bo = loc_lap_lai(segments)
    if so_bo:
        say("asr", f"Đã bỏ {so_bo} câu lặp lại liên tiếp — nhiều khả năng là "
                   "chỗ im lặng bị nghe nhầm.")

        # Đã thấy dấu hiệu bịa thì soi tiếp bằng ÂM LƯỢNG (mini-spec C29):
        # câu nào nằm trọn trong chỗ im thì bỏ, kể cả câu đứng lẻ mà bộ lọc
        # lặp không bắt được. Chỉ chạy khi đã có dấu hiệu — dò âm lượng tốn
        # một lượt quét cả tệp, không đáng làm cho mọi lượt chép lời.
        from autodub.media.cat_tep import tim_vung_lang

        segments, bo_im = loc_cau_trong_vung_im(
            segments, tim_vung_lang(audio_path))
        if bo_im:
            say("asr", f"Đã bỏ thêm {bo_im} câu nằm trong chỗ im.")
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

    # Xuất xong rồi thì tệp dở hết việc — bỏ đi để thư mục không lẫn hai
    # bản của cùng một nội dung.
    ghi_dan.xoa()
    say("done", f"Xong: {len(segments)} câu")
    _don_tam(work_dir, audio_path, media_path)
    return result


#: Dài hơn ngần này thì tự cắt ra rồi nghe từng đoạn (mini-spec C26).
#:
#: 45 phút: dưới mức đó thì một lượt chạy liền mạch vừa đơn giản vừa không có
#: ranh giới nào để làm hỏng câu. Trên mức đó thì lợi ích của việc chia nhỏ
#: (thấy tiến độ, hỏng một đoạn không mất cả buổi) vượt cái giá của ranh giới.
PHUT_TU_CAT = 45


def _chep_mot_hoac_nhieu_doan(audio_path, lang, settings, run_asr, *,
                              cancel_event, ghi_dan, say):
    """Nghe cả tệp một lượt, hoặc tự cắt ra nghe từng đoạn rồi GHÉP LẠI.

    Người dùng không phải quyết định gì: tệp ngắn thì chạy như cũ, tệp dài
    thì tự chia. Và dù chia hay không, **kết quả trả về là MỘT mạch duy nhất**
    với mốc thời gian liên tục từ đầu tới cuối — chia nhỏ là chuyện nội bộ,
    không phải chuyện người dùng phải đi ghép tay tám tệp lại.

    Mốc cắt nắn về khoảng lặng (xem `media/cat_tep.py`) nên ranh giới rơi vào
    chỗ im, không rơi giữa câu.
    """
    from autodub.media.cat_tep import cat_deu, do_dai_giay

    tong = do_dai_giay(audio_path)
    if not tong or tong <= PHUT_TU_CAT * 60:
        return run_asr(audio_path, lang, settings, cancel_event=cancel_event,
                       on_segment=ghi_dan.them)

    thu_muc_doan = os.path.join(os.path.dirname(audio_path), "doan_tam")
    doan = cat_deu(audio_path, thu_muc_doan, phut=PHUT_TU_CAT)
    if len(doan) <= 1:
        return run_asr(audio_path, lang, settings, cancel_event=cancel_event,
                       on_segment=ghi_dan.them)

    say("asr", f"Tệp dài {tong / 60:.0f} phút — chia làm {len(doan)} đoạn để "
               "nghe cho chắc.")
    tat_ca: list[dict] = []
    moc = 0.0
    for i, tep in enumerate(doan, 1):
        _kiem_huy(cancel_event)
        say("asr", f"Đang nghe đoạn {i}/{len(doan)}…")
        cau = run_asr(tep, lang, settings, cancel_event=cancel_event,
                      on_segment=ghi_dan.them)
        # Dời mốc về THỜI GIAN THẬT trong tệp gốc. Không dời thì tám đoạn đều
        # bắt đầu từ 00:00 và bản chép lời ghép lại thành vô nghĩa.
        for c in cau:
            c["start"] = round(float(c.get("start", 0) or 0) + moc, 3)
            c["end"] = round(float(c.get("end", 0) or 0) + moc, 3)
            c["id"] = len(tat_ca) + 1
            tat_ca.append(c)
        moc += do_dai_giay(tep) or 0.0
    _don_tam(thu_muc_doan, *doan)
    return tat_ca


#: Đuôi tệp ghi dở. Đặt rõ ràng để người dùng nhìn là biết đây là bản chưa
#: xong, và để lượt chạy sau không nhầm nó với kết quả thật.
DUOI_DANG_CHAY = ".dang_chay.txt"


class _GhiDan:
    """Ghi từng câu ra đĩa ngay khi nghe được (mini-spec C24).

    NỐI ĐUÔI chứ không ghi lại cả tệp: với vài nghìn câu, ghi lại từ đầu mỗi
    lần là công việc bình phương theo số câu. Nối đuôi thì mỗi câu tốn đúng
    một lần ghi, và tệp vẫn đọc được ngay cả khi tiến trình bị giết đột ngột.
    """

    def __init__(self, duong_dan: str) -> None:
        self.duong_dan = duong_dan
        self.so_cau = 0
        self._f = None

    def them(self, seg: dict) -> None:
        if self._f is None:
            self._f = open(self.duong_dan, "w", encoding="utf-8")
            self._f.write("# Bản chép lời đang chạy — chưa xong.\n\n")
        moc = _mmss(float(seg.get("start", 0) or 0))
        self._f.write(f"[{moc}] {str(seg.get('text', '')).strip()}\n")
        # Xả ngay: đệm nằm trong bộ nhớ thì mất khi tiến trình bị giết, mà đó
        # đúng là ca tệp này sinh ra để cứu.
        self._f.flush()
        self.so_cau += 1

    def dong(self) -> None:
        if self._f is not None:
            try:
                self._f.close()
            finally:
                self._f = None

    def xoa(self) -> None:
        self.dong()
        try:
            if os.path.exists(self.duong_dan):
                os.remove(self.duong_dan)
        except OSError as e:
            logger.warning(f"Không xoá được tệp dở «{self.duong_dan}» ({e})")


def _mmss(giay: float) -> str:
    phut, gy = divmod(int(giay), 60)
    gio, phut = divmod(phut, 60)
    return f"{gio:02d}:{phut:02d}:{gy:02d}" if gio else f"{phut:02d}:{gy:02d}"


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
