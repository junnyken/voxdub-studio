"""Video dubbing pipeline (Vietnamese).

GUI-ready core:
- no ``input()`` calls — voice must be resolved by the caller
- no ``sys.exit`` — errors raise, missing config raises :class:`ConfigError`
- progress observable via a callback (:class:`autodub.progress.ProgressEvent`)
- cancellable via ``threading.Event``
- the manual-translation stop is returned as data (``status="translate_pending"``),
  not an exception

Typical use::

    from autodub import DubRequest, DubPipeline, Settings

    settings = Settings.load()
    result = DubPipeline(settings).run(DubRequest(url="https://...", voice="male"))
    if result.status == "translate_pending":
        ...  # show TRANSLATE_PENDING.txt instructions, later re-run with resume_dir
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from autodub.config import Settings
from autodub.languages import TargetLang, get_target, resolve_source_lang
from autodub.progress import PipelineCancelled, ProgressFn, ProgressReporter
from autodub.utils import setup_logging, ensure_dir, seg_wav_path
from autodub.workdir import data_dir, data_path, youtube_dir

logger = setup_logging("autodub.pipeline")


class _PostTarget:
    """Nhãn dùng để tính job_id của bước đăng bài (không phải ngôn ngữ đích)."""

    text_field = "post"


_POST_TARGET = _PostTarget()


def source_video_path(work_dir: str) -> str | None:
    """External source video remembered for this work_dir, if still valid.

    Runs started from a local file outside work_dir record it in
    ``source_video.json`` so resumes (CLI and GUI) find the source without
    the user re-picking it.
    """
    marker = data_path(work_dir, "source_video.json")
    if not os.path.exists(marker):
        return None
    try:
        with open(marker, encoding="utf-8") as f:
            path = json.load(f).get("file_path")
    except (json.JSONDecodeError, OSError):
        return None
    if path and os.path.exists(path):
        return path
    return None


def _usage_snapshot() -> dict:
    """Số Vox đã tiêu cho video này (dịch + phân tích + rà soát + đăng bài).

    Token nằm phía máy chủ và người dùng không trả tiền theo token nữa, nên
    con số duy nhất có nghĩa với họ là số Vox — ghi vào quality_report.json
    để đối chiếu với lịch sử ví.
    """
    from autodub.text.translate_common import USAGE
    return USAGE.snapshot()


@dataclass
class DubRequest:
    """Everything needed for one dubbing run (Vietnamese)."""
    url: str | None = None
    file_path: str | None = None
    source_lang: str = "zh-CN"
    #: TÊN giọng đọc (xem autodub.speech.tts.voices). None → giọng mặc định
    #: trong cấu hình.
    voice: str | None = None
    bg_mode: str = "demucs"            # "demucs" | "duck" | "none"
    bg_duck_db: float = -12.0
    skip_video: bool = False
    output_dir: str | None = None      # default resolved from Settings
    resume_dir: str | None = None
    subtitle_mode: str = "none"        # "none" | "soft" | "burn"
    # Rectangles (normalized 0..1: x/y/w/h, optional t_start/t_end) blurred to
    # cover hardcoded source captions. Any region forces a video re-encode.
    blur_regions: list[dict] = field(default_factory=list)
    subtitle_style: dict | None = None  # libass styling; None → Settings default

    # Ngôn ngữ đích lồng tiếng — khoá ngắn khớp autodub.languages.TARGETS
    # ("vi"/"en"). Mặc định "vi" giữ hành vi trước mini-spec V8/V11.
    target: str = "vi"

    #: mini-spec V57 — tên hồ sơ nhân vật của series. Có hồ sơ thì nhân vật
    #: cũ nhận lại đúng giọng cũ ở tập mới. Rỗng = hành vi V36 như cũ.
    character_profile: str = ""

    #: mini-spec V56 — chỉ lồng tiếng N GIÂY ĐẦU để nghe thử trước khi cam
    #: kết chạy cả video. 0 = chạy bình thường (mặc định, 0 regression).
    preview_seconds: int = 0

    #: Luồng wizard: giữ chỗ Vox sau ASR, chạy tới hết ghép audio rồi DỪNG
    #: (``status="export_pending"``) — file trung gian trả phí nằm trên đĩa
    #: dưới dạng mã hóa cho tới khi người dùng bấm Xuất video (commit hold).
    #: Batch/legacy giữ False: trừ Vox theo từng lượt như cũ, không mã hóa.
    #: mini-spec V97 — người dùng đã xem giá và bấm chạy tiếp. Chỉ luồng
    #: wizard mới hỏi (batch/dòng lệnh không có ai ngồi đó để trả lời).
    chi_phi_da_duyet: bool = False
    defer_export: bool = False

    #: mini-spec V32b (docs/PLAN.md, Phase G) — "Đồng bộ khẩu hình" AI
    #: (MuseTalk), GPU-only, mặc định TẮT. Chỉ có hiệu lực khi
    #: ``skip_video=False`` VÀ ``Settings.lipsync_configured()``/
    #: ``lipsync_gpu_available()`` đều đúng — thiếu 1 trong 2 thì degrade
    #: trung thực (bỏ qua bước này, KHÔNG lỗi cả lượt chạy vì 1 tính năng
    #: tuỳ chọn chưa cài, xem Constraint 2 của V32b).
    lipsync: bool = False

    def __post_init__(self) -> None:
        # Chuẩn hoá NGAY tại cửa vào: `SOURCE_LANG_MAP` hỗ trợ chính thức cả
        # dạng ngắn ("vi", "en", "zh") lẫn BCP-47 đầy đủ, nhưng trước đây chỉ
        # bước ASR gọi `resolve_source_lang()` còn các bước sau vẫn đọc giá
        # trị THÔ. Hệ quả thật (bắt được lúc test e2e 2026-08-17): gửi "vi"
        # thì ASR chạy bình thường nhưng `translate_local.is_available()` tra
        # `flores_code("vi")` ra None → cả lượt âm thầm rẽ sang dịch tay
        # (`translate_pending`) sau khi đã tốn nguyên bước ASR. Chuẩn hoá một
        # lần ở đây thì mọi bước phía sau thấy cùng một giá trị; hàm này
        # idempotent ("vi-VN" → "vi-VN") nên chỗ gọi cũ không đổi hành vi.
        self.source_lang = resolve_source_lang(self.source_lang)


@dataclass
class DubResult:
    # "completed" | "translate_pending" | "export_pending" | "credit_blocked"
    # | "cost_pending" (V97 — chờ người dùng duyệt giá)
    status: str
    work_dir: str
    report: dict = field(default_factory=dict)


class DubPipeline:
    """Runs the full dub pipeline for a :class:`DubRequest`."""

    def __init__(
        self,
        settings: Settings,
        progress: ProgressFn | None = None,
        cancel_event: threading.Event | None = None,
        synth_cache=None,
        demucs_cache=None,
        whisper_cache=None,
    ):
        self.settings = settings
        # Telemetry tiến trình (mini-spec V13, docs/PLAN.md) — gắn THÊM 1
        # listener vào callback progress hiện có, độc lập với UI (Design
        # Choice của V13: tái dùng rep.emit(), không thêm hook mới trong
        # logic pipeline). run_id được gán mỗi lượt trong run() bên dưới.
        self._telemetry_run_id: str | None = None
        self._telemetry_last_stage: str = ""
        # mini-spec V29 (docs/PLAN.md, Phase G) — trace review dịch lượt
        # gần nhất, đọc lại bởi _build_quality_report(). Mặc định rỗng —
        # đường dịch TAY (không qua _auto_translate()) không bao giờ chạy
        # review, quality_report.json khi đó không có field review.
        self._last_review_trace: list[dict] = []
        # mini-spec V40 (docs/PLAN.md, Phase G) — tín hiệu chất lượng tách
        # nhạc nền lượt gần nhất, đọc lại bởi _build_quality_report(). Rỗng
        # khi bg_mode != "demucs" hoặc tách thất bại (không có file để đo).
        self._last_vocals_quality: dict = {}
        # mini-spec V32b (docs/PLAN.md, Phase G) — kết quả bước "Đồng bộ
        # khẩu hình" lượt gần nhất, đọc lại bởi _build_quality_report().
        # Rỗng khi DubRequest.lipsync=False (mặc định).
        self._last_lipsync_state: dict = {}
        from autodub import telemetry
        telemetry_listener = telemetry.make_progress_listener(self)

        def _progress_with_telemetry(event, _orig=progress, _tel=telemetry_listener):
            if _orig is not None:
                try:
                    _orig(event)
                except Exception:  # callback giao diện hỏng không được chặn telemetry
                    # Lỗi ở callback GUI không được chặn telemetry chạy
                    # tiếp — ProgressReporter.emit() cũng nuốt lỗi tương tự
                    # cho callback gốc, đây chỉ đảm bảo _tel() luôn tới lượt.
                    pass
            _tel(event)

        self._reporter = ProgressReporter(_progress_with_telemetry, cancel_event)
        # Giữ thẳng cờ Dừng: các bước chạy LÂU mà không phát progress (canh
        # chữ karaoke nghe lại từng clip) cần tự canh cờ, `rep.check_cancelled()`
        # giữa hai bước không cắt ngang được chúng (mini-spec V76).
        self._cancel_event = cancel_event
        # Vòng đời hold Vox của lượt chạy này — logic đầy đủ nằm ở
        # autodub/billing.py (mini-spec V2, xem docs/PLAN.md); các phương
        # thức _setup_hold/_stop_for_export/_settle_hold_inline/
        # _money_note_for_manual bên dưới chỉ còn delegate sang đây.
        from autodub.billing import HoldBillingAdapter
        self._billing = HoldBillingAdapter(self.settings, self._reporter)
        # Optional autodub.speech.tts.SynthCache — lets a batch run reuse one
        # warmed TTS model across videos. When set, the cache owns the
        # synthesizer lifecycle (this pipeline never closes it).
        self._synth_cache = synth_cache
        # Optional autodub.media.vocal_separator.DemucsCache — batch runs
        # reuse one loaded Demucs model across videos (caller owns lifecycle).
        self._demucs_cache = demucs_cache
        # Optional autodub.speech.transcriber.WhisperCache — batch runs reuse
        # one loaded Whisper model across videos (caller owns lifecycle).
        self._whisper_cache = whisper_cache
        # Work dir of the most recent run() call (set even when the run
        # fails mid-way) — batch uses it to resume the same folder later.
        self.last_work_dir = ""

    def _reset_per_run_state(self) -> None:
        """Xoá side-channel của lượt chạy TRƯỚC — bắt buộc gọi đầu mỗi
        ``_run_impl()``. Bug thật tìm được khi build V32b: ``pipeline`` là 1
        instance DÙNG CHUNG cho cả batch (xem ``batch.py::run_batch`` —
        không tạo mới mỗi video), nhưng 3 field dưới đây trước giờ chỉ khởi
        tạo MỘT LẦN trong ``__init__()`` — video B trong cùng batch không
        bật tính năng tương ứng vẫn thấy ``quality_report.json`` lộ dữ liệu
        CŨ của video A liền trước. Không giới hạn riêng cho V32b — sửa luôn
        2 field có sẵn từ V29/V40 cùng lỗi."""
        self._last_review_trace = []
        self._last_vocals_quality = {}
        self._last_lipsync_state = {}

    def _get_synth(self, target, voice):
        from autodub.speech.tts import get_synthesizer
        if self._synth_cache is not None:
            return self._synth_cache.get(target, self.settings, voice)
        return get_synthesizer(target, self.settings, voice)

    # ------------------------------------------------------------------ #

    def run(self, req: DubRequest) -> DubResult:
        """Run the pipeline; on error/cancel, release TTS workers + the
        background-separation future so a long-lived GUI process doesn't
        strand multi-GB worker subprocesses (VRAM) between runs."""
        self._active_synth = None
        self._active_bg_future = None
        self._bg_executor = None
        # Xoá dấu vết lượt trước — lỡ lượt này đổ TRƯỚC khi chọn xong thư mục
        # thì batch không nhầm sang thư mục của video trước đó.
        self.last_work_dir = ""
        # Telemetry (V13): 1 run_id MỚI mỗi lượt run() — pipeline dùng lại
        # cho cả batch (nhiều video/1 instance) nên phải reset ở đây, không
        # phải __init__. is_configured()==False thì listener là no-op nên
        # new_job_id() ở đây không lãng phí gì đáng kể (chuỗi UUID rẻ).
        from autodub.saas_client import new_job_id
        self._telemetry_run_id = new_job_id()
        self._telemetry_last_stage = ""
        try:
            return self._run_impl(req)
        except BaseException:
            from autodub import telemetry
            telemetry.note_failed(self)
            fut = self._active_bg_future
            if fut is not None:
                fut.cancel()
                # Observe the eventual result so a failure in the background
                # thread isn't reported as "exception was never retrieved".
                fut.add_done_callback(
                    lambda f: f.cancelled() or f.exception())
            synth = self._active_synth
            if (self._synth_cache is None and synth is not None
                    and hasattr(synth, "close")):
                try:
                    synth.close()
                except Exception as e:
                    logger.warning(f"Không đóng được TTS synth khi dọn dẹp: {e}")
            raise
        finally:
            # Executor được đóng ở đây, không phải ngay sau submit():
            # shutdown(wait=False) rồi bỏ tham chiếu để lại một luồng đang
            # chạy mà không ai giữ. Chỉ chờ khi việc nền đã xong — hủy giữa
            # lúc Demucs còn tách nhạc thì cancel() không cắt được nó, chờ ở
            # đây sẽ ghim nút Hủy cho tới khi Demucs chạy hết.
            bg_fut = self._active_bg_future
            executor = self._bg_executor
            self._active_synth = None
            self._active_bg_future = None
            self._bg_executor = None
            if executor is not None:
                executor.shutdown(wait=bg_fut is None or bg_fut.done())

    @staticmethod
    def _log_machine_info(settings: Settings) -> None:
        """Một dòng cấu hình máy đầu mỗi lượt chạy — để đọc log là biết ngay
        video chậm vì máy yếu hay vì lỗi, không phải hỏi lại người dùng."""
        from autodub.sysinfo import available_ram_gb, total_ram_gb
        from autodub.media.vocal_separator import gpu_venv_python
        from autodub.media.video import video_encoder_name

        total = total_ram_gb()
        avail = available_ram_gb()
        ram_txt = (f"RAM {avail:.1f}/{total:.1f} GB trống"
                   if total is not None and avail is not None else "RAM ?")
        gpu_txt = "có" if gpu_venv_python() else "không"
        logger.info(
            f"Máy: {os.cpu_count() or '?'} nhân, {ram_txt}, GPU (venv) {gpu_txt} — "
            f"TTS {settings.vieneu_max_workers} luồng, "
            f"parallel {settings.parallel_workers}")
        # Xuất video bằng card đồ họa nhanh gấp nhiều lần CPU. Ghi rõ ở đây để
        # người dùng máy yếu biết ngay mình đang chạy đường nào.
        try:
            logger.info(f"Xuất video bằng: {video_encoder_name()}")
        except Exception as exc:      # ffmpeg lạ — không đáng làm hỏng lượt chạy
            logger.debug(f"Không dò được encoder: {exc}")

    def _run_impl(self, req: DubRequest) -> DubResult:
        start_time = time.time()
        settings = self.settings
        rep = self._reporter
        # Ghi nhận thời gian từng bước để dễ phát hiện điểm nghẽn hiệu năng.
        stage_times: dict[str, float] = {}
        _stage_start: list[float] = [start_time]

        def _tick(name: str) -> None:
            now = time.time()
            stage_times[name] = round(now - _stage_start[0], 2)
            _stage_start[0] = now
            logger.info(f"  ⏱  {name}: {stage_times[name]:.1f}s")

        target = get_target(req.target)
        lang_code = resolve_source_lang(req.source_lang)
        logger.info(f"Source language: {lang_code} → {target.name}")
        self._log_machine_info(settings)
        self._reset_per_run_state()

        # Resume an existing work_dir or create a new timestamped one
        if req.resume_dir:
            if not os.path.isdir(req.resume_dir):
                raise FileNotFoundError(f"Resume directory not found: {req.resume_dir}")
            work_dir = req.resume_dir
            folder_name = os.path.basename(os.path.normpath(work_dir))
            logger.info(f"Resuming work directory: {work_dir}")
        else:
            output_dir = req.output_dir or self.default_output_dir(target)
            base_name = datetime.now().strftime("%Y%m%d%H%M%S") + target.folder_suffix
            # V56: hậu tố nằm NGAY TRONG tên thư mục — mở thư mục kết quả là
            # biết ngay cái nào chỉ là bản nghe thử. Đăng nhầm bản 30 giây lên
            # kênh là hỏng thật.
            from autodub.preview import apply_folder_suffix
            base_name = apply_folder_suffix(base_name, req.preview_seconds)
            folder_name = self._unique_new_folder_name(output_dir, base_name)
            work_dir = ensure_dir(os.path.join(output_dir, folder_name))
            logger.info(f"Output folder: {work_dir}")
        # Cho caller (batch) biết lượt chạy này nằm ở thư mục nào — kể cả khi
        # nó đổ giữa chừng, để lần chạy lại truyền resume_dir đúng chỗ.
        self.last_work_dir = work_dir

        # Bố cục thư mục: file kỹ thuật vào data/, kết quả nằm ở gốc.
        # Thư mục cũ (mọi thứ phẳng ở gốc) được data_path tự nhận và giữ nguyên.
        transcript_orig_path = data_path(work_dir, "transcript_original.json",
                                         create_dir=True)
        # mini-spec V40: marker giữ ngôn ngữ nguồn của transcript đã cache —
        # resume sau khi SỬA "Ngôn ngữ gốc" (vd job cũ dừng giữa chừng vì
        # chọn nhầm) phải nghe lại, không âm thầm dùng transcript sai ngôn
        # ngữ. Không tồn tại (thư mục từ trước V40) → coi là khớp, không ép
        # nghe lại oan cho dự án cũ.
        asr_lang_marker = data_path(work_dir, ".asr_lang")
        transcript_dub_path = data_path(work_dir, target.transcript_name)
        audio_path = data_path(work_dir, "original_audio.wav")

        # --- Step 1: Download or use local file ---
        rep.check_cancelled()
        # detail = work_dir: báo sớm cho GUI biết thư mục dự án của lượt chạy
        # này — lỡ có lỗi giữa chừng thì trang Tạo dự án còn biết chỗ mà mời
        # người dùng chạy tiếp (tránh tạo dự án mới, tránh trừ Vox hai lần).
        rep.emit("acquire", "start", detail=work_dir)
        logger.info("=" * 60)
        logger.info("STEP 1: Acquiring video")
        if req.url:
            logger.info("Đang tải video về máy...")
        video_path = self._resolve_video(work_dir, req.url, req.file_path)
        if req.preview_seconds > 0:
            # V56: cắt SAU khi đã có video thật trên đĩa — chỗ này phục vụ cả
            # link (đã tải xong ở trên) lẫn file local, nên chỉ cần một điểm
            # chèn duy nhất cho cả hai đường vào.
            from autodub.preview import make_preview_clip
            video_path = make_preview_clip(video_path, work_dir, req.preview_seconds)
            logger.info("Chế độ NGHE THỬ %ss — kết quả KHÔNG phải bản cuối",
                        req.preview_seconds)
        logger.info(f"Video: {video_path}")
        logger.info(f"Đã có video: {os.path.basename(video_path)}")
        rep.emit("acquire", "done", detail=video_path)
        _tick("acquire")

        # --- Step 2: Extract audio ---
        rep.check_cancelled()
        logger.info("=" * 60)
        # HQ extract for the background/mix path: 44.1 kHz stereo. The 16 kHz
        # mono file is what ASR wants, but running Demucs on it crushes the
        # soundtrack to phone-call bandwidth — the single biggest audio
        # quality loss of the old pipeline. Failure falls back to the ASR wav.
        hq_audio_path = data_path(work_dir, "original_audio_hq.wav")
        have_asr = (os.path.exists(audio_path)
                    and os.path.getsize(audio_path) > 0)
        have_hq = (os.path.exists(hq_audio_path)
                   and os.path.getsize(hq_audio_path) > 0)
        need_hq = settings.hq_background and not have_hq
        if have_asr:
            logger.info(f"STEP 2: Reusing existing extracted audio: {audio_path}")
            rep.emit("extract", "skip", detail=audio_path)
        else:
            logger.info("STEP 2: Extracting audio")
            rep.emit("extract", "start")
            from autodub.media.audio import extract_audio, extract_audio_dual
            if need_hq:
                # Cần cả hai bản — một lệnh ffmpeg, video giải mã một lần.
                try:
                    extract_audio_dual(video_path, audio_path, hq_audio_path,
                                       asr_rate=settings.audio_sample_rate)
                    need_hq = False
                except Exception as e:
                    logger.warning(f"Rút audio 1 lượt lỗi ({e}) — "
                                   "tách thành hai lệnh rời")
            if not (os.path.exists(audio_path)
                    and os.path.getsize(audio_path) > 0):
                extract_audio(video_path, audio_path,
                              sample_rate=settings.audio_sample_rate)
            rep.emit("extract", "done", detail=audio_path)
        if settings.hq_background:
            if need_hq:
                try:
                    from autodub.media.audio import extract_audio
                    extract_audio(video_path, hq_audio_path,
                                  sample_rate=44100, channels=2)
                except Exception as e:
                    logger.warning(f"Không rút được audio HQ ({e}) — "
                                   "nhạc nền dùng bản 16 kHz như cũ")
                    hq_audio_path = audio_path
        else:
            hq_audio_path = audio_path

        # --- Step 2.5: Background track — starts right after the audio
        # extract. The pipeline waits for it BEFORE ASR: Demucs and Whisper
        # sharing a 6 GB GPU slow each other down more than running back to
        # back, and each step alone peaks lower on RAM/VRAM.
        rep.check_cancelled()
        from concurrent.futures import ThreadPoolExecutor
        bg_executor = ThreadPoolExecutor(max_workers=1)
        bg_future = bg_executor.submit(
            self._resolve_background, req.bg_mode, req.bg_duck_db,
            hq_audio_path, work_dir,
        )
        # Giữ trên self, shutdown trong finally của run() — xem chú thích ở đó.
        self._bg_executor = bg_executor
        self._active_bg_future = bg_future

        tts_synth = None
        # Kiểu phụ đề chốt MỘT lần ở đây rồi dùng lại cho mọi bước sinh phụ
        # đề bên dưới — chữ trong tệp .srt và chữ ghi vào hình luôn khớp.
        from autodub.media.subtitle import normalize_style
        from autodub.text.subtitles import refresh_subtitles
        from autodub.text.translate_common import HOLD
        subtitle_style = normalize_style(req.subtitle_style
                                         or settings.subtitle_style())

        def _refresh_subs(*args, **kwargs):
            # Hold chưa chốt → không để phụ đề (bản dịch thuần chữ) nằm
            # thường trên đĩa. Phase Xuất video sinh lại đầy đủ SRT/ASS.
            if req.defer_export and HOLD.active:
                return None, None
            kwargs.setdefault("cancel_event", self._cancel_event)
            return refresh_subtitles(*args, **kwargs)

        # --- Step 3: Speech-to-Text (ASR) — GPU-exclusive ---
        rep.check_cancelled()
        logger.info("=" * 60)
        segments = self._load_cached_transcript(
            transcript_orig_path, asr_lang_marker, lang_code)
        if segments is not None:
            logger.info(f"STEP 3: Reusing existing transcript: {transcript_orig_path}")
            logger.info(f"Dùng lại lời thoại đã nghe từ lần chạy trước "
                        f"({len(segments)} câu) — đỡ chờ")
            rep.emit("asr", "skip", detail=f"{len(segments)} segments (cached)")
        if segments is None:
            # Demucs và ASR chỉ được chạy song song khi KHÔNG giành nhau
            # tài nguyên: Demucs trong tiến trình con GPU còn ASR chắc chắn
            # chạy CPU (Paraformer, hoặc Whisper không nạp được CUDA).
            # Còn lại giữ rào chắn cũ — hai việc nặng chen nhau trên cùng
            # GPU (hoặc cùng 4 nhân CPU) chậm hơn chạy lần lượt.
            from autodub.media.vocal_separator import gpu_venv_python
            from autodub.speech.transcriber import asr_will_use_gpu
            overlap_ok = (req.bg_mode == "demucs"
                          and bool(gpu_venv_python())
                          and not asr_will_use_gpu(settings, lang_code))
            if overlap_ok:
                logger.info("Demucs (GPU) và ASR (CPU) chạy song song — "
                            "tiết kiệm thời gian chờ")
            else:
                # Let the separation finish first so Whisper gets the GPU
                # alone (duck/none resolve instantly; a cached Demucs too).
                bg_future.result()
            logger.info("STEP 3: Transcribing audio (ASR)")
            logger.info("Đang nghe và ghi lại lời thoại trong video — "
                        "video dài thì bước này hơi lâu...")
            rep.emit("asr", "start")
            from autodub.speech.transcriber import transcribe, save_transcript
            from autodub.text.srt import generate_srt
            segments = transcribe(audio_path, lang_code, settings,
                                  whisper_cache=self._whisper_cache)
            save_transcript(segments, transcript_orig_path)
            with open(asr_lang_marker, "w", encoding="utf-8") as f:
                f.write(lang_code)
            generate_srt(segments, data_path(work_dir, "transcript_original.srt"),
                         text_field="text", lang_key=lang_code.split("-")[0].lower())
            logger.info(f"Nghe xong: video có {len(segments)} câu thoại")
            rep.emit("asr", "done", detail=f"{len(segments)} segments")
        logger.info(f"Transcribed {len(segments)} segments")
        if not segments:
            # Không có lời nói → dịch/TTS đều vô nghĩa; báo đúng nguyên nhân
            # thay vì để bước dịch fail với thông điệp gây hiểu nhầm.
            raise RuntimeError(
                "Không nhận dạng được lời nói nào trong video (video chỉ có "
                "nhạc, hoặc chọn sai ngôn ngữ gốc). Kiểm tra lại ngôn ngữ "
                "nguồn trong tab Lồng tiếng.")

        self._apply_diarization(segments, audio_path, target,
                                character_profile=req.character_profile)

        # --- Gộp mẩu vụn thành câu (mini-spec V97) ------------------------
        # PHẢI đứng ở đây: sau phân giọng (để biết ranh giới người nói mà
        # không gộp nhầm hai người) và TRƯỚC `annotate_slots` + `_setup_hold`
        # (giá được chốt theo số dòng, nên gộp sau khi giữ chỗ thì chẳng tiết
        # kiệm được đồng nào). Ghi lại bản chép lời và phụ đề gốc theo dòng đã
        # gộp để tệp trên đĩa khớp đúng thứ đem đi lồng tiếng.
        if settings.gop_cau_truoc_khi_dich and len(segments) > 1:
            from autodub.transcribe_tool import gop_de_dich

            truoc = len(segments)
            segments = gop_de_dich(segments)
            if len(segments) < truoc:
                logger.info(
                    f"Gộp câu: {truoc} mẩu → {len(segments)} dòng "
                    f"({len(segments) * 100 // truoc}%) — tiền tính theo dòng "
                    f"nên đây là phần không phải trả.")
                # Nạp tại chỗ: đường DÙNG LẠI bản chép lời cũ không đi qua
                # nhánh ASR nên hai tên này chưa có trong tầm nhìn.
                from autodub.speech.transcriber import save_transcript
                from autodub.text.srt import generate_srt

                save_transcript(segments, transcript_orig_path)
                generate_srt(segments,
                             data_path(work_dir, "transcript_original.srt"),
                             text_field="text",
                             lang_key=lang_code.split("-")[0].lower())
                rep.emit("asr", "done",
                         detail=f"{len(segments)} câu (gộp từ {truoc} mẩu)")

        # Real per-clip time window (until the next line starts) — drives the
        # translation character budget and the TTS target duration.
        from autodub.text.translate_hint import annotate_slots
        annotate_slots(segments)

        # --- Giữ chỗ Vox — sau ASR là lúc biết chính xác số câu và thời
        # lượng. MỌI lượt chạy đều giữ chỗ (wizard lẫn batch) nên giá luôn là
        # công thức đóng trên số segment. Thiếu Vox thì chặn NGAY TẠI ĐÂY,
        # trước khi máy chủ tốn một đồng phí AI nào. Khác biệt duy nhất giữa
        # hai luồng là THỜI ĐIỂM chốt: wizard dừng chờ bấm Xuất video, còn
        # batch/legacy chốt ngay sau khi xuất xong (xem cuối hàm).
        video_duration_s = max(float(s.get("end", 0) or 0) for s in segments)

        # Nguồn đã cùng ngôn ngữ với đích: KHÔNG có gì để dịch (mini-spec C23).
        #
        # Trước đây ba đường vào đều chặn thẳng, nhưng chặn là bỏ mất một việc
        # người dùng thật sự cần: đổi giọng cho video tiếng Việt sẵn có (giọng
        # gốc ồn, nói nhanh, hoặc muốn giọng khác). Việc đó chỉ cần
        # nghe-chép → tạo giọng → ghép, bỏ hẳn khâu dịch.
        #
        # Quan trọng về tiền: cờ này đi thẳng vào `create_hold(auto_translate=)`
        # nên máy chủ KHÔNG giữ chỗ tiền dịch. Với video 3-4 giờ, khoản đó là
        # hàng chục nghìn Vox.
        from autodub.languages import cung_ngon_ngu

        khong_can_dich = cung_ngon_ngu(req.source_lang or "", target.key)
        if khong_can_dich:
            logger.warning(
                f"Nguồn và đích đều là {target.name} — bỏ qua bước dịch, "
                "chỉ thay giọng đọc. Không tính Vox cho phần dịch.")

        # --- Xem trước chi phí (mini-spec V97) ----------------------------
        # Chỉ hỏi ở luồng wizard: batch và dòng lệnh không có ai ngồi trước
        # màn hình để bấm, dừng lại ở đó là treo cả mẻ.
        duyet_moc = data_path(work_dir, "chi_phi_da_duyet.json")
        da_duyet = req.chi_phi_da_duyet or os.path.isfile(duyet_moc)
        if req.chi_phi_da_duyet and not os.path.isfile(duyet_moc):
            # Ghi lại để lần chạy tiếp sau (kể cả sau khi mở lại app) không
            # hỏi lại một câu người dùng đã trả lời.
            try:
                with open(duyet_moc, "w", encoding="utf-8") as f:
                    json.dump({"sentences": len(segments)}, f)
            except OSError as e:
                logger.warning(f"Không ghi được dấu đã duyệt giá ({e}) — "
                               "lần chạy tiếp sẽ hỏi lại.")
        if req.defer_export:
            cho_duyet = self._billing.cong_xem_truoc(
                segments, work_dir, video_duration_s,
                khong_can_dich=khong_can_dich, da_duyet=da_duyet)
            if cho_duyet is not None:
                bg_future.result()   # kết quả đã cache — chạy tiếp dùng ngay
                return cho_duyet

        blocked = self._setup_hold(segments, target, work_dir,
                                   video_duration_s,
                                   khong_can_dich=khong_can_dich)
        if blocked is not None:
            bg_future.result()   # kết quả đã cache — lần chạy lại dùng ngay
            return blocked

        # Khởi động sớm bộ giọng: việc nạp model (vài giây trên CPU) nấp sau
        # bước dịch. VieNeu chạy CPU nên không tranh card đồ họa với bất cứ
        # thứ gì — lúc nào cũng khởi động sớm được. Ở đây chỉ NẠP model, còn
        # việc tạo giọng vẫn nằm nguyên trong Bước 5.
        try:
            tts_synth = self._get_synth(target, req.voice)
            self._active_synth = tts_synth
            warm = getattr(tts_synth, "warm_up_async", None)
            if warm is not None:
                # A3 fix: khởi động worker ngay lập tức thay vì chờ Demucs.
                # VieNeu chạy CPU-only — không tranh VRAM với Demucs (GPU),
                # nên có thể load song song và tiết kiệm 30-120s chờ đợi.
                warm()
        except Exception as e:
            logger.warning(f"Bỏ qua khởi động sớm bộ giọng ({e})")
            tts_synth = None
            self._active_synth = None

        # --- Step 4: Load translation (manual via skill or web AI) ---
        rep.check_cancelled()
        logger.info("=" * 60)
        logger.info(f"STEP 4: Loading {target.name} translation")
        if khong_can_dich:
            # Câu đích CHÍNH LÀ câu gốc. Vẫn ghi ra tệp bản dịch để các bước
            # sau (phụ đề, tạo giọng, xuất) không cần biết gì về ca này.
            for seg in segments:
                seg[target.text_field] = seg.get("text", "")
            _refresh_subs(segments, work_dir, target, subtitle_style)
            rep.emit("translate", "done",
                     detail=f"Không cần dịch — nguồn đã là {target.name}")
        elif os.path.exists(transcript_dub_path):
            logger.info(f"Reusing existing translation: {transcript_dub_path}")
            logger.info("Dùng lại bản dịch đã có — đỡ chờ")
            segments = self._load_translation(transcript_dub_path, segments, target)
            _refresh_subs(segments, work_dir, target, subtitle_style)
            # The hint file is no longer needed once the translation exists
            hint_leftover = os.path.join(work_dir, "TRANSLATE_PENDING.txt")
            if os.path.exists(hint_leftover):
                os.remove(hint_leftover)
            rep.emit("translate", "done", detail=transcript_dub_path)
        else:
            translated = self._auto_translate(segments, target,
                                              req.source_lang,
                                              work_dir=work_dir)
            if translated is None:
                # Rẽ sang dịch tay. Hold GIỮ NGUYÊN: giá đã chốt và trừ đủ từ
                # lúc giữ chỗ nên không có gì để hoàn, còn giữ hold thì lượt
                # chạy lại nhận lại đúng khóa để mở file đã mã hóa. Hướng dẫn
                # chỉ cần nói rõ là không phát sinh thêm Vox.
                refund_note = self._money_note_for_manual()
                from autodub.text.translate_hint import write_hint
                hint_path = write_hint(work_dir, target, req.source_lang,
                                       settings=self.settings,
                                       refund_note=refund_note)
                # Dòng info tiếng Anh cho console/dev; warning tiếng Việt là
                # dòng người dùng thấy trong Nhật ký.
                logger.info("Translation pending — see TRANSLATE_PENDING.txt in work dir")
                logger.warning("Video đang chờ bản dịch — xem hướng dẫn "
                               "3 bước hiện trên màn hình")
                rep.emit("translate", "start", detail=hint_path)
                # Let the background separation finish before stopping: the
                # result is cached on disk, so the resume run reuses it.
                bg_future.result()
                # Don't hold TTS resources while waiting for a manual
                # translation (cache-owned synths stay alive — the batch
                # owner closes them).
                if (self._synth_cache is None and tts_synth is not None
                        and hasattr(tts_synth, "close")):
                    tts_synth.close()
                return DubResult(status="translate_pending", work_dir=work_dir)

            # Persist before validating so the file is editable and the next
            # run hits the cached branch above (resume-safe, same as manual).
            from autodub.speech.transcriber import save_transcript
            save_transcript(translated, transcript_dub_path)
            if HOLD.active:
                # Bản dịch trả phí — mã hóa trên đĩa cho tới khi commit hold.
                from autodub import securestore
                securestore.encrypt_file(transcript_dub_path, HOLD.key)
                securestore.add_locked_file(work_dir, HOLD.hold_id,
                                            transcript_dub_path)
            segments = self._load_translation(transcript_dub_path, segments, target)
            _refresh_subs(segments, work_dir, target, subtitle_style)
            rep.emit("translate", "done", detail=transcript_dub_path)

        # --- Step 5: TTS ---
        # Strict 1:1 rendering: every translated segment becomes exactly one
        # spoken clip, placed at its original start time. Voice, subtitles,
        # translation and editor all share Whisper's per-fragment timeline —
        # nothing is grouped, so clips can never pile onto each other.
        rep.check_cancelled()
        logger.info("=" * 60)
        logger.info(f"STEP 5: Synthesizing {target.name} audio (TTS)")
        logger.info(f"Bắt đầu tạo giọng đọc cho {len(segments)} câu — "
                    "bước lâu nhất, tiến độ hiện ở khung bên trái...")
        seg_dir = ensure_dir(data_path(work_dir, "segments", create_dir=True))
        self._ensure_render_mode(work_dir, seg_dir, target, req.voice)
        self._apply_emotion_styles(segments, target, req.voice)
        tts_results = self._synthesize_segments(target, req.voice, segments,
                                                seg_dir, synth=tts_synth)
        # Free the TTS workers' VRAM before the NVENC video encode — unless a
        # batch cache owns them (the next video reuses the warm pool).
        if (self._synth_cache is None and tts_synth is not None
                and hasattr(tts_synth, "close")):
            tts_synth.close()

        # --- Step 5.5: Video speed (optional) — slow the WHOLE video by
        # VIDEO_SPEED (e.g. 0.82) so the naturally-longer dub simply fits.
        # One uniform factor: no per-segment fitting, no trimming ever.
        # Mutates segments onto the slowed timeline; on failure returns None
        # and the run continues on the original video.
        background_path, background_gain_db = bg_future.result()
        deferred_speed: tuple[float, str] | None = None
        if settings.video_speed < 0.999 and not req.skip_video:
            rep.check_cancelled()
            logger.info("=" * 60)
            logger.info(f"STEP 5.5: Slowing video ({settings.video_speed}x)")
            from autodub.media.retime import (apply_video_speed,
                                              defer_video_speed,
                                              rescale_blur_regions)
            # Video đằng nào cũng mã hóa lại ở bước ghép (phụ đề ghi vào
            # hình / che chữ) → gộp setpts vào lượt đó, đỡ nguyên một lần
            # encode toàn bộ video. Không mã hóa lại thì đi đường rời như cũ.
            deferred = None
            if req.subtitle_mode == "burn" or req.blur_regions:
                deferred = defer_video_speed(video_path, background_path,
                                             segments, work_dir, settings)
            if deferred is not None:
                if deferred[0] is not None:
                    background_path = deferred[0]
                deferred_speed = (float(settings.video_speed), deferred[2])
                if req.blur_regions:
                    req.blur_regions = rescale_blur_regions(
                        req.blur_regions, deferred[1])
                _refresh_subs(segments, work_dir, target, subtitle_style)
            else:
                slowed = apply_video_speed(video_path, background_path,
                                           segments, work_dir, settings)
                if slowed is not None:
                    video_path = slowed[0]
                    if slowed[1] is not None:
                        background_path = slowed[1]
                    # Blur windows + SRT follow the slowed timeline; the dub
                    # transcript keeps ORIGINAL timestamps on disk so a resume
                    # rescales from the same base (and reuses the cached encode).
                    if req.blur_regions:
                        req.blur_regions = rescale_blur_regions(
                            req.blur_regions, slowed[2])
                    _refresh_subs(segments, work_dir, target, subtitle_style)

        # --- Step 6: voice speed + merge audio ---
        rep.check_cancelled()
        logger.info("=" * 60)
        rep.emit("merge_audio", "start")
        total_duration = max(seg["end"] for seg in segments) + 1.0 if segments else 0

        # Hậu kỳ giọng: loudnorm + highpass + fade cho TỪNG clip — mọi giọng
        # ra cùng một mức âm lượng cảm nhận, hết click đầu
        # câu. VOICE_SPEED (atempo) gộp luôn vào cùng lệnh ffmpeg — mỗi câu
        # chỉ tốn MỘT tiến trình con thay vì hai.
        merge_src = seg_dir
        voice_speed = self.settings.voice_speed
        speed_in_post = (settings.voice_postprocess
                         and abs(voice_speed - 1.0) >= 0.005)
        if settings.voice_postprocess:
            logger.info("STEP 6a: Voice postprocess (loudnorm, fade, highpass)")
            logger.info("Đang cân chỉnh âm lượng các câu cho đều nhau...")
            from autodub.media.audio import postprocess_voice_clips
            # Tên thư mục mang hệ số tốc độ — đổi VOICE_SPEED giữa hai lần
            # chạy thì cache cũ tự bị bỏ qua (resume-safe).
            post_dir = ("segments_post" if not speed_in_post else
                        f"segments_post_speed{voice_speed:.2f}".replace(".", "_"))
            merge_src = postprocess_voice_clips(
                segments, seg_dir, data_path(work_dir, post_dir),
                target_lufs=settings.voice_target_lufs,
                max_workers=min(8, settings.parallel_workers),
                speed=voice_speed if speed_in_post else 1.0,
                on_done=lambda n, t: rep.emit("merge_audio", "progress",
                                              current=n, total=t))

        merge_dir = (merge_src if speed_in_post
                     else self._apply_voice_speed(segments, merge_src, work_dir))

        # Chống chồng tiếng mềm: đặt lại vị trí clip (ưu tiên DỒN TRỄ vào
        # khoảng lặng — tốc độ đọc mọi câu giữ nguyên; nén nhẹ chỉ khi bất
        # khả kháng, trần thấp). Chạy trên clip ĐÃ hậu kỳ + voice_speed để
        # số đo thời lượng là thật. Mutates segments → SRT làm lại bên dưới.
        timing_report = None
        if settings.soft_timing_fit:
            from autodub.media.timing import apply_soft_timing
            merge_dir, timing_report = apply_soft_timing(
                segments, merge_dir, data_path(work_dir, "segments_timed"),
                settings, max_workers=min(8, settings.parallel_workers))
            _refresh_subs(segments, work_dir, target, subtitle_style)

        # A long clip may run past the last segment's end — extend the mix
        # so the merge never cuts a clip at the timeline boundary.
        from autodub.media.audio import wav_duration_s
        for seg in segments:
            dur = wav_duration_s(seg_wav_path(merge_dir, seg["id"]))
            if dur:
                total_duration = max(total_duration, seg["start"] + dur + 0.5)

        logger.info("STEP 6: Merging audio segments")
        logger.info("Đang ghép giọng đọc với nhạc nền...")
        merged_audio_path = data_path(work_dir, target.audio_name)
        from autodub.media.audio import merge_segments
        merge_segments(
            segments, merge_dir, merged_audio_path, total_duration,
            background_path=background_path,
            background_gain_db=background_gain_db,
            duck_voice_db=settings.bg_duck_voice_db,
        )
        rep.emit("merge_audio", "done", detail=merged_audio_path)

        # Mọi thứ phase Xuất video cần, gói làm một: luồng batch/legacy dùng
        # ngay tại chỗ; luồng wizard ghi xuống đĩa (mã hóa) rồi DỪNG — bấm
        # Xuất video mới commit hold và chạy nốt.
        export_state = {
            "video_path": video_path,
            "merged_audio_path": merged_audio_path,
            "merge_dir": merge_dir,
            "deferred_speed": list(deferred_speed) if deferred_speed else None,
            "segments": segments,
            "tts_results": tts_results,
            "timing": (timing_report.to_dict()
                       if timing_report is not None else {}),
            "folder_name": folder_name,
            "lang_code": lang_code,
            "target": target.key,
            "audio_path": audio_path,
            "subtitle_style": subtitle_style,
            "url": req.url,
            "skip_video": req.skip_video,
            "subtitle_mode": req.subtitle_mode,
            "blur_regions": req.blur_regions,
            "voice": req.voice,
            "lipsync": req.lipsync,
            "elapsed_before": round(time.time() - start_time, 1),
        }

        if req.defer_export and HOLD.active:
            return self._stop_for_export(export_state, work_dir)

        # Batch/legacy không có nút Xuất video — chốt hold NGAY TẠI ĐÂY (trước
        # phase xuất, như thứ tự của luồng wizard): mở khóa file trung gian và
        # ghi tổng Vox vào sổ. HOLD giữ nguyên qua phase xuất để bước tạo nội
        # dung đăng bài trỏ đúng hold (gói +20 Vox đã nằm trong giá), rồi mới
        # xả — không rớt sang video kế tiếp của batch.
        self._settle_hold_inline(work_dir)
        try:
            return self._export_phase(export_state, work_dir, target)
        finally:
            HOLD.clear()

    def _stop_for_export(self, state: dict, work_dir: str) -> DubResult:
        """Dừng ở ranh giới Xuất video (luồng wizard, hold còn active).

        Logic đầy đủ: :meth:`autodub.billing.HoldBillingAdapter.stop_for_export`
        (mini-spec V2 — di chuyển nguyên văn, xem docs/PLAN.md).
        """
        return self._billing.stop_for_export(state, work_dir)

    def _settle_hold_inline(self, work_dir: str) -> None:
        """Chốt hold ngay trước phase xuất (luồng batch/legacy).

        Logic đầy đủ: :meth:`autodub.billing.HoldBillingAdapter.settle_hold_inline`
        (mini-spec V2 — di chuyển nguyên văn, xem docs/PLAN.md).
        """
        self._billing.settle_hold_inline(work_dir)

    def _export_phase(self, state: dict, work_dir: str,
                      target: TargetLang) -> DubResult:
        """Phase Xuất video: ghép video, nội dung đăng bài, báo cáo.

        Luồng batch/legacy chạy inline ngay sau ghép audio (hold được chốt
        ngay sau đó qua :meth:`_settle_hold_inline`); luồng wizard chạy qua
        :func:`export_committed_project` sau khi người dùng bấm Xuất video
        (hold đã commit, file đã giải mã).
        """
        settings, rep = self.settings, self._reporter
        phase_start = time.time()
        from autodub.text.subtitles import refresh_subtitles

        segments = state["segments"]
        merge_dir = state["merge_dir"]
        video_path = state["video_path"]
        merged_audio_path = state["merged_audio_path"]
        subtitle_style = state.get("subtitle_style") or {}
        deferred = state.get("deferred_speed")
        deferred_speed = ((float(deferred[0]), deferred[1])
                          if deferred else None)
        # DubRequest tối thiểu — _build_report chỉ đọc url/voice từ đây.
        req = DubRequest(url=state.get("url"), voice=state.get("voice"),
                         skip_video=bool(state.get("skip_video")),
                         subtitle_mode=state.get("subtitle_mode", "none"),
                         blur_regions=state.get("blur_regions") or [],
                         lipsync=bool(state.get("lipsync")))

        # --- Step 7: Merge video (optional) ---
        # Ghim tên giọng THẬT đã dùng (kể cả khi người dùng để mặc định),
        # để Trình chỉnh sửa hiện đúng giọng của video này thay vì đoán.
        # Ghim CẢ KHI bỏ qua bước ghép video, và GỘP vào render_opts thay vì
        # ghi đè — không xóa tùy chọn Trình chỉnh sửa đã lưu trước đó.
        from autodub.editor import load_render_opts, save_render_opts
        from autodub.speech.tts import voices as voice_catalog
        render_opts = load_render_opts(work_dir)
        render_opts["voice"] = voice_catalog.resolve(self.settings, req.voice,
                                                       target=target)
        dubbed_video_path = None
        if not req.skip_video:
            rep.check_cancelled()
            logger.info("=" * 60)
            logger.info("STEP 7: Creating dubbed video")
            logger.info("Đang xuất video hoàn chỉnh"
                        + (" (có ghi phụ đề/che chữ nên lâu hơn chút)"
                           if req.subtitle_mode == "burn" or req.blur_regions
                           else "") + "...")
            rep.emit("merge_video", "start")
            dubbed_video_path = os.path.join(work_dir, "dubbed_video.mp4")
            render_opts.update({
                "subtitle_mode": req.subtitle_mode,
                "blur_regions": req.blur_regions,
                "subtitle_style": subtitle_style,
            })
        else:
            # Chỉ xuất âm thanh: vẫn ghim kiểu phụ đề của LẦN CHẠY NÀY để
            # Trình chỉnh sửa mở lên thấy đúng lựa chọn, nhưng không đè
            # lên tùy chọn người dùng đã chỉnh trong Trình chỉnh sửa.
            render_opts.setdefault("subtitle_mode", req.subtitle_mode)
            render_opts.setdefault("blur_regions", req.blur_regions)
            render_opts.setdefault("subtitle_style", subtitle_style)
        save_render_opts(work_dir, render_opts)
        if not req.skip_video:
            # mini-spec V32b (docs/PLAN.md, Phase G) — "Đồng bộ khẩu hình"
            # AI, TUỲ CHỌN (mặc định TẮT). Chạy TRƯỚC bước mux hiện có: nhận
            # (video gốc, audio đã lồng tiếng) → trả video đã đồng bộ khẩu
            # hình để merge_video() dùng THAY video gốc — subtitle/blur/tốc
            # độ video vẫn xử lý y hệt như trước ở bước mux, không viết lại.
            lipsync_video_path = video_path
            if req.lipsync:
                rep.check_cancelled()
                lipsync_video_path, self._last_lipsync_state = self._apply_lipsync(
                    video_path, merged_audio_path, work_dir, settings)

            # Phụ đề ghi vào hình: cả câu (.srt) hay cụm chữ theo giọng đọc
            # (.ass) đều do refresh_subtitles quyết, dùng đúng bộ clip cuối
            # cùng nên chữ nhảy khớp giọng.
            _srt_path, burn_path = refresh_subtitles(
                segments, work_dir, target, subtitle_style,
                merge_dir=merge_dir, settings=settings,
                for_burn=req.subtitle_mode == "burn",
                cancel_event=self._cancel_event)
            from autodub.media.video import merge_video
            merge_video(
                lipsync_video_path, merged_audio_path, dubbed_video_path,
                srt_path=burn_path,
                subtitle_mode=req.subtitle_mode,
                blur_regions=req.blur_regions,
                subtitle_style=subtitle_style,
                subtitle_lang=target.iso639_2,
                speed=deferred_speed[0] if deferred_speed else None,
                fps=deferred_speed[1] if deferred_speed else None,
                cancel_event=self._cancel_event,
            )
            rep.emit("merge_video", "done", detail=dubbed_video_path)
        else:
            # Luồng wizard dừng trước khi sinh phụ đề — xuất chỉ-âm-thanh
            # vẫn phải có tệp .srt trong thư mục kết quả.
            refresh_subtitles(segments, work_dir, target, subtitle_style,
                              merge_dir=merge_dir, settings=settings,
                              cancel_event=self._cancel_event)

        # --- Step 8: Social post metadata ---
        content_result = self._generate_content(target, segments, req.url,
                                                work_dir, video_path)

        # --- Report + timing guide ---
        tts_results = state.get("tts_results") or []
        elapsed = (float(state.get("elapsed_before", 0))
                   + (time.time() - phase_start))
        report = self._build_report(
            target, state["folder_name"], req, state["lang_code"], segments,
            tts_results, work_dir, state["audio_path"], merged_audio_path,
            dubbed_video_path, content_result, elapsed,
        )

        report_path = data_path(work_dir, "report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # Quality report — người dùng thấy NGAY video này còn vấn đề gì và ở
        # câu nào (chồng tiếng còn lại, câu bị dồn trễ/nén, câu tràn budget)
        # trước khi quyết định đăng.
        quality = self._build_quality_report(target, segments,
                                             state.get("timing") or {},
                                             settings,
                                             review_trace=self._last_review_trace,
                                             vocals_quality=self._last_vocals_quality,
                                             lipsync_state=self._last_lipsync_state)
        quality_path = data_path(work_dir, "quality_report.json")
        with open(quality_path, "w", encoding="utf-8") as f:
            json.dump(quality, f, ensure_ascii=False, indent=2)
        # GUI shows this summary in the done-banner.
        report["quality"] = quality["summary"]
        s = quality["summary"]
        if s["segments_overlapped"]:
            logger.info(
                f"Kiểm tra chất lượng: {s['segments_ok']}/"
                f"{s['segments_total']} câu ổn — còn "
                f"{s['segments_overlapped']} câu chồng tiếng nhẹ. Nghe thử "
                "video; nếu khó chịu, giảm Tốc độ video trong Cài đặt rồi "
                "chạy lại (rất nhanh vì giọng đọc đã có sẵn).")
        elif len(quality["per_segment"]):
            logger.info(
                f"Kiểm tra chất lượng: {s['segments_ok']}/"
                f"{s['segments_total']} câu chuẩn, số còn lại chỉ lệch nhẹ "
                "— nghe thử để yên tâm.")
        else:
            logger.info("Kiểm tra chất lượng: tất cả các câu đều khớp đẹp")

        timing_guide = self._build_timing_guide(target, report, segments,
                                                tts_results)
        timing_path = data_path(work_dir, "timing_guide.json")
        with open(timing_path, "w", encoding="utf-8") as f:
            json.dump(timing_guide, f, ensure_ascii=False, indent=2)
        logger.info(f"Timing guide: {timing_path}")

        logger.info("=" * 60)
        logger.info(f"PIPELINE COMPLETE ({target.name})")
        logger.info(f"  Output:    {work_dir}")
        logger.info(f"  Segments:  {report['total_segments']}")
        logger.info(f"  Duration:  {report['total_original_duration']:.1f}s original, "
                    f"{report['total_tts_duration']:.1f}s dub audio")
        logger.info(f"  Adjusted:  {report['segments_speed_adjusted']} segments speed-adjusted")
        logger.info(f"  Time:      {elapsed:.1f}s")
        logger.info("=" * 60)
        mins, secs = divmod(int(elapsed), 60)
        logger.info(f"Hoàn tất! Lồng tiếng xong {report['total_segments']} "
                    f"câu trong {f'{mins} phút {secs} giây' if mins else f'{secs} giây'} "
                    "— video nằm trong thư mục kết quả.")

        # Tự dọn tệp trung gian nếu người dùng đã bật trong Cài đặt. Làm sau
        # cùng, khi mọi báo cáo đã ghi xong — video kết quả và phụ đề được
        # module diskspace giữ nguyên.
        if settings.auto_clean_intermediates:
            from autodub.diskspace import clean_project

            freed = clean_project(work_dir)
            if freed:
                logger.info(f"Đã tự dọn tệp trung gian, giải phóng "
                            f"{freed / (1024 ** 2):.0f} MB.")

        rep.emit("done", "done", detail=work_dir)
        return DubResult(status="completed", work_dir=work_dir, report=report)

    # ------------------------------------------------------------------ #

    def default_output_dir(self, target: TargetLang) -> str:
        """Thư mục kết quả mặc định — theo ngôn ngữ đích.

        target=vi (0 regression): y hệt trước V11 — ``vi_output_dir()``
        (tôn trọng ``VIETNAMESE_OUTPUT_DIR`` nếu người dùng đã đặt riêng).
        Target khác: KHÔNG dùng override đó (đặt để dời output tiếng Việt,
        không phải mọi ngôn ngữ) — về ``<output_dir>/<KEY>`` theo target,
        ví dụ ``output/EN`` cho tiếng Anh, tránh video tiếng Anh nằm lẫn
        trong thư mục "VN" như trước khi phát hiện ở live-verify V11.
        """
        if target.key == "vi":
            return self.settings.vi_output_dir()
        return os.path.join(self.settings.output_dir, target.key.upper())

    def _apply_diarization(self, segments: list[dict], audio_path: str,
                           target: TargetLang,
                           character_profile: str = "") -> None:
        """Tự tách giọng theo người nói + gán mỗi người 1 giọng TTS riêng —
        mini-spec V26 (docs/PLAN.md, Phase G). TUỲ CHỌN, mặc định TẮT (0
        regression khi không bật) — Design Choice: tái dùng cơ chế multi-
        voice per-segment (``seg["voice"]``) đã có sẵn từ trước V26, không
        viết lại tầng TTS.

        Degrade TRUNG THỰC nếu diarization chưa cài hoặc lỗi thật giữa
        chừng (Constraint 2) — không bao giờ để lỗi ở đây làm hỏng cả lượt
        dub, chỉ rơi về đúng hành vi 1-giọng-toàn-video như trước V26.
        """
        settings = self.settings
        if not settings.diarization_enabled:
            return
        if not settings.diarization_configured():
            logger.info(
                "Diarization đang bật nhưng chưa cài (.venv-diar) — dùng 1 "
                "giọng cho toàn video. Cài qua scripts/setup_diarization.py.")
            return

        from autodub.speech.diarization import (
            DiarizationError, assign_speakers, diarize,
        )
        from autodub.speech.tts import voices as voice_catalog
        from autodub.speech.tts.voice_assign import (
            apply_segment_voices, assign_voices_by_gender, assign_voices_round_robin,
        )

        try:
            self._reporter.emit("asr", "progress",
                                detail="Đang tách giọng theo người nói...")
            # V59: xin luôn embedding — pyannote đã tính sẵn khi gom nhóm
            # người nói, không tốn thêm thời gian xử lý nào.
            # V65b — gợi ý số người nói cho pyannote.
            #
            # Người dùng khai (`speaker_count`) THẮNG mọi suy đoán: họ xem
            # video rồi, ta thì không.
            #
            # Hồ sơ nhân vật CHỈ cấp cận TRÊN, cố ý không cấp cận dưới. Số
            # nhân vật của cả series là trần hợp lý cho một tập, nhưng làm
            # sàn thì sai: series 5 nhân vật mà tập này chỉ 2 người nói, ép
            # tối thiểu 5 là buộc pyannote xé một người thành nhiều — đổi lỗi
            # gộp lấy lỗi xé, không khá hơn. Cộng thêm 2 chỗ cho nhân vật mới
            # xuất hiện lần đầu ở tập này.
            so_nguoi_khai = max(0, int(getattr(settings, "speaker_count", 0) or 0))
            tran_tu_ho_so = self._profile_speaker_ceiling(
                character_profile, settings)
            diar_segments, speaker_embeddings = diarize(
                audio_path, settings, with_embeddings=True,
                num_speakers=so_nguoi_khai,
                max_speakers=0 if so_nguoi_khai else tran_tu_ho_so)
            assign_speakers(segments, diar_segments)
            speaker_labels = sorted({
                seg["speaker_label"] for seg in segments
                if seg.get("speaker_label")})
            if not speaker_labels:
                logger.info("Diarization: không tách được người nói nào "
                           "(video có thể chỉ 1 người nói) — giữ 1 giọng.")
                return
            available = [v.name for v in voice_catalog.catalog(settings, target)]

            # Mini-spec V36 (docs/PLAN.md, Phase G): ước lượng giới tính
            # từng người nói từ pitch (F0) để gán giọng phù hợp hơn round-
            # robin thuần — người nói ước lượng được rơi vào nhóm giới tính
            # đúng, người nói KHÔNG ước lượng được (âm thanh nhiễu/quá ngắn)
            # rơi về round-robin nguyên bản (Constraint 2/6, không đoán liều).
            from autodub.speech.diarization_voice_match import (
                estimate_speaker_genders, load_wav_mono,
            )

            genders: dict[str, str] = {}
            pitches: dict[str, float] = {}
            try:
                wav, sr = load_wav_mono(audio_path)
                from autodub.speech.diarization_voice_match import (
                    classify_gender, estimate_speaker_pitch,
                )
                # V57: tính F0 MỘT lần rồi suy ra cả giới tính (V36) lẫn khoá
                # nhận diện nhân vật — trước đây con số này bị dùng xong vứt.
                pitches = estimate_speaker_pitch(wav, sr, diar_segments)
                genders = {spk: classify_gender(f0) for spk, f0 in pitches.items()}
            except (OSError, EOFError) as e:
                logger.warning(
                    f"Không đọc được audio để ước lượng giới tính người nói "
                    f"({e}) — dùng round-robin cho toàn bộ.")

            catalog_full = voice_catalog.catalog(settings, target)
            voice_map = assign_voices_by_gender(
                speaker_labels, genders, catalog_full, fallback_names=available)

            # V57: hồ sơ nhân vật GHI ĐÈ lên gán tự động — nhân vật đã biết
            # phải giữ đúng giọng của tập trước, đó là toàn bộ mục đích.
            # V57: tên hồ sơ được TRUYỀN VÀO chứ không lấy từ `req` — hàm này
            # không thấy `req` (bug thật, test diarization bắt được ngay).
            profile_name = character_profile or ""
            if profile_name:
                voice_map = self._apply_character_profile(
                    profile_name, settings, pitches, genders, voice_map,
                    embeddings=speaker_embeddings)

            apply_segment_voices(segments, voice_map)
            gendered = sum(1 for lbl in speaker_labels if genders.get(lbl))
            logger.info(
                f"Diarization: {len(speaker_labels)} người nói phát hiện "
                f"được, {gendered} người gán giọng theo giới tính ước lượng, "
                f"{len(speaker_labels) - gendered} người dùng round-robin.")
        except DiarizationError as e:
            logger.warning(
                f"Diarization lỗi ({e}) — dùng 1 giọng cho toàn video như "
                "bình thường (không ảnh hưởng phần còn lại của lượt dub).")


    def _profile_speaker_ceiling(self, profile_name: str, settings) -> int:
        """Trần số người nói suy từ hồ sơ nhân vật — mini-spec V65b.

        Số nhân vật của cả series + 2 chỗ cho người mới xuất hiện lần đầu ở
        tập này. Trả ``0`` khi không có hồ sơ, hồ sơ rỗng, hoặc đọc lỗi —
        không có gợi ý thì pyannote tự đoán như trước, đúng đường lui của
        V26/V59.

        CHỈ trần, KHÔNG sàn: xem lý do ở chỗ gọi.
        """
        if not profile_name:
            return 0
        try:
            from autodub.character_profile import CharacterProfile
            profile = CharacterProfile.load(
                self._profiles_dir(settings), profile_name)
            so = len(profile.characters)
        except Exception as err:  # noqa: BLE001 — hồ sơ hỏng không được làm chết lượt dub
            logger.warning("Không đọc được hồ sơ «%s» để đoán số người nói "
                           "(%s) — để pyannote tự quyết.", profile_name, err)
            return 0
        return so + 2 if so else 0

    def _apply_character_profile(self, profile_name: str, settings,
                                 pitches: dict, genders: dict,
                                 voice_map: dict,
                                 embeddings: dict | None = None) -> dict:
        """Áp hồ sơ nhân vật của series lên bản đồ giọng (mini-spec V57).

        Nhân vật khớp được → dùng lại ĐÚNG giọng tập trước. Người nói lạ giữ
        nguyên giọng do V36 vừa gán, rồi được ghi vào hồ sơ thành nhân vật
        mới cho tập sau.

        Mọi lỗi ở đây đều KHÔNG được làm hỏng lượt dub: mất phần ghi nhớ thì
        tệ, nhưng mất cả tập vì một file hồ sơ thì tệ hơn nhiều.
        """
        try:
            from autodub.character_profile import CharacterProfile

            profiles_dir = self._profiles_dir(settings)
            profile = CharacterProfile.load(profiles_dir, profile_name)

            # V58: quy ước dịch của series đè cài đặt chung (chủ dự án chốt
            # 2026-08-18) — chỉ với những trường hồ sơ CÓ điền.
            from autodub.character_profile import apply_translation_context
            applied = apply_translation_context(profile, settings)
            if applied:
                logger.info("Hồ sơ «%s» áp quy ước riêng của series: %s",
                            profile_name, ", ".join(applied))

            embeddings = embeddings or {}
            matched = profile.match_speakers(pitches, embeddings)

            for speaker, character in matched.items():
                voice = profile.voice_for(character)
                if voice:
                    voice_map[speaker] = voice
            logger.info(
                "Hồ sơ nhân vật «%s»: nhận lại %d/%d người nói từ các tập "
                "trước (%d người mới), khớp bằng %s.",
                profile_name, len(matched), len(pitches),
                len(pitches) - len(matched),
                "embedding giọng" if embeddings else "cao độ giọng (F0)")

            # V61: ghi ĐIỂM SỐ THẬT ra log — đây là dữ liệu duy nhất để hiệu
            # chỉnh ngưỡng cosine cho đúng nội dung của người dùng, thay vì
            # giữ mãi một con số phỏng đoán.
            for line in profile.explain_matches():
                logger.info("Khớp nhân vật — %s", line)

            profile.remember(matched, pitches, voice_map, genders,
                             embeddings=embeddings)
            profile.save(profiles_dir)
        except Exception as err:      # noqa: BLE001 — xem docstring
            logger.warning(
                "Không dùng được hồ sơ nhân vật «%s» (%s) — lượt này gán "
                "giọng như bình thường.", profile_name, err)
        return voice_map

    @staticmethod
    def _profiles_dir(settings) -> str:
        """Nơi cất hồ sơ: cạnh thư mục kết quả, để người dùng tìm thấy."""
        import os as _os
        base = getattr(settings, "output_dir", "") or "output"
        return _os.path.join(base, "character_profiles")

    def _apply_lipsync(self, video_path: str, audio_path: str, work_dir: str,
                       settings) -> tuple[str, dict]:
        """Chạy bước "Đồng bộ khẩu hình" AI — mini-spec V32b (docs/PLAN.md,
        Phase G). TUỲ CHỌN, mặc định TẮT, GPU-only (NGOẠI LỆ kiến trúc đầu
        tiên so với "GPU-optional" của mọi tính năng khác — chốt chính sách
        2026-08-12).

        Trả về ``(video_path dùng cho bước mux, state để lộ ra
        quality_report.json)``. Degrade TRUNG THỰC (Constraint 2): chưa cài
        (.venv-lipsync/GPU)/consent-check chặn (Constraint 3, phạm vi CHỈ
        đúng những gì V32a đã benchmark thật)/lỗi thật đều KHÔNG làm hỏng cả
        lượt xuất video — rơi về dùng video gốc như trước V32b, nhưng LUÔN
        ghi rõ lý do vào state để người dùng biết chắc video này có thật sự
        được xử lý hay không, không phải lỗi mù mờ.
        """
        from autodub.media import lipsync as lipsync_module

        if not lipsync_module.available(settings):
            logger.info(
                "Đồng bộ khẩu hình đang bật nhưng chưa cài (.venv-lipsync/"
                "GPU không sẵn sàng) — xuất video như bình thường, không "
                "đồng bộ khẩu hình. Cài qua scripts/setup_lipsync.py trên "
                "máy có GPU NVIDIA thật.")
            return video_path, {"status": "unavailable"}

        from autodub.media.video import probe_duration_s
        duration_s = probe_duration_s(video_path)
        logger.info("=" * 60)
        logger.info("STEP 6.5: Đồng bộ khẩu hình AI")
        logger.info("Đang đồng bộ khẩu hình (GPU) — có thể mất nhiều phút, "
                    "không phải bị treo...")
        try:
            output_video = lipsync_module.run(
                video_path, audio_path, os.path.join(work_dir, "lipsync"),
                settings, video_duration_s=duration_s,
                cancel_event=self._cancel_event)
            return output_video, {"status": "applied"}
        except lipsync_module.LipsyncBlocked as e:
            logger.warning(
                f"Đồng bộ khẩu hình bị chặn ({e.reason}): {e} — xuất video "
                "như bình thường, không đồng bộ khẩu hình.")
            return video_path, {
                "status": "blocked", "reason": e.reason, "message": str(e),
            }
        except lipsync_module.LipsyncFailed as e:
            logger.warning(
                f"Đồng bộ khẩu hình lỗi: {e} — xuất video như bình thường, "
                "không đồng bộ khẩu hình.")
            return video_path, {"status": "failed", "message": str(e)}

    def _apply_emotion_styles(self, segments: list[dict], target: TargetLang,
                              run_voice: str | None) -> None:
        """Tự đổi giọng điệu đọc theo cảm xúc từng câu — mini-spec V28
        (docs/PLAN.md, Phase G). TUỲ CHỌN, mặc định TẮT (0 regression khi
        không bật).

        Hai nguồn tín hiệu (Design Choice của mini-spec — ưu tiên LLM khi
        có): nếu ``translate_saas.py`` đã gắn ``seg["tone"]`` từ lượt dịch
        SaaS (server bật ``emotionTone`` cùng cờ Cài đặt này), dùng THẲNG giá
        trị đó — chính xác hơn hẳn heuristic văn bản thuần vì LLM đọc hiểu cả
        câu. Câu nào KHÔNG có tín hiệu LLM (local-only, hoặc SaaS không trả
        được) rơi về heuristic văn bản cũ (dấu câu/từ khoá) — vẫn đúng
        Constraint 2 (2 đường xử lý RÕ RÀNG KHÁC NHAU, không giả vờ ngang
        hàng). Chỉ áp cho giọng VieNeu (Constraint 4) — giọng CapCut
        (``source == "capcut"``) bị bỏ qua, `capcut_vi.py::synthesize()`
        cũng tự bỏ qua tham số này nếu lỡ nhận được, đây là lớp phòng thủ
        THÊM để không tính toán tone vô ích.
        """
        settings = self.settings
        if not settings.emotion_voice_enabled:
            return

        from autodub.speech.tts import voices as voice_catalog
        from autodub.text.tone_heuristic import guess_tone, tone_to_vieneu_style

        catalog_by_name = {v.name: v for v in voice_catalog.catalog(settings, target)}
        text_field = target.text_field
        applied = 0
        from_llm = 0
        for seg in segments:
            voice_name = str(seg.get("voice") or run_voice or "").strip()
            entry = catalog_by_name.get(voice_name)
            # Giọng không rõ nguồn (không tìm thấy trong catalog) hoặc
            # nguồn CapCut -> bỏ qua, không suy đoán.
            if entry is not None and entry.source == "capcut":
                continue
            llm_tone = str(seg.get("tone") or "").strip()
            if llm_tone:
                tone = llm_tone
                from_llm += 1
            else:
                tone = guess_tone(str(seg.get(text_field, "")))
            seg["style"] = tone_to_vieneu_style(tone)
            applied += 1
        if applied:
            logger.info(
                f"Giọng điệu: đã tự gán style theo cảm xúc cho {applied}/"
                f"{len(segments)} câu ({from_llm} từ SaaS, "
                f"{applied - from_llm} từ heuristic văn bản, xem Cài đặt).")

    def _setup_hold(
        self, segments: list[dict], target: TargetLang, work_dir: str,
        video_duration_s: float, khong_can_dich: bool = False,
    ) -> DubResult | None:
        """Giữ chỗ Vox cho lượt chạy — gọi ngay sau ASR, mọi luồng.

        Logic đầy đủ: :meth:`autodub.billing.HoldBillingAdapter.setup_hold`
        (mini-spec V2 — di chuyển nguyên văn, xem docs/PLAN.md).
        """
        return self._billing.setup_hold(segments, target, work_dir,
                                        video_duration_s,
                                        khong_can_dich=khong_can_dich)

    def _money_note_for_manual(self) -> str:
        """Dòng trấn an về Vox để ghi vào hướng dẫn dịch tay.

        Logic đầy đủ:
        :meth:`autodub.billing.HoldBillingAdapter.money_note_for_manual`
        (mini-spec V2 — di chuyển nguyên văn, xem docs/PLAN.md).
        """
        return self._billing.money_note_for_manual()

    def _auto_translate(
        self, segments: list[dict], target: TargetLang,
        source_lang: str, work_dir: str | None = None,
    ) -> list[dict] | None:
        """Dịch qua máy chủ VoxDub, hoặc trả về None để chuyển sang dịch tay.

        Trả về None khi người dùng tắt dịch tự động, hoặc khi máy chủ không
        dịch được vì lý do không phải lỗi của người dùng. Hết Vox và thiết bị
        bị khóa thì NÉM lỗi lên trên: đó là những việc người dùng phải xử lý
        (nạp thêm, liên hệ hỗ trợ), lặng lẽ chuyển sang dịch tay chỉ khiến họ
        không hiểu chuyện gì vừa xảy ra.

        Dịch ba lượt: lượt 0 phân tích lời thoại rồi bơm ngữ cảnh (tóm tắt,
        xưng hô, thuật ngữ) vào lời nhắc của MỌI lô; lượt chính chia lô gửi
        lên máy chủ; lượt rà soát soát lại các câu nghi vấn. Cả ba đều có bộ
        nhớ đệm — chạy lại không tốn Vox cho phần đã xong.
        """
        settings, rep = self.settings, self._reporter
        if not settings.translate_enabled:
            return None

        from autodub.saas_client import is_configured
        if not is_configured():
            # Không có máy chủ — path C (mini-spec V6, docs/PLAN.md): dịch
            # local/offline nếu người dùng đã bật VÀ đã tải model. is_configured()
            # vẫn là cổng duy nhất phân biệt local/SaaS; path C là nhánh
            # con của "không SaaS", không phải cổng thứ hai.
            from autodub.text.translate_local import (
                LocalTranslateError, is_available, translate_segments_local)
            if settings.translate_local_enabled and is_available(settings, source_lang):
                try:
                    return translate_segments_local(
                        segments, target, source_lang, settings, rep,
                        cancel_event=self._cancel_event)
                except LocalTranslateError as e:
                    logger.warning(f"Dịch local lỗi ({e}) — chuyển sang dịch tay")
                    return None
            # Chạy thuần trên máy: không có máy chủ dịch nào được cấu hình.
            # Trả None để pipeline rẽ sang dịch tay (TRANSLATE_PENDING.txt).
            logger.info("Chưa cấu hình máy chủ dịch — chuyển sang dịch tay")
            return None

        from autodub.saas_client import (
            DeviceBlockedError, InsufficientCreditError, MaintenanceError,
            OfflineError, SaasError)
        from autodub.text.translate_common import USAGE
        from autodub.text.translate_saas import (
            analyze_transcript, apply_analysis, run_id_for, translate_segments)

        from autodub.media.audio import FALLBACKS

        USAGE.reset()      # đếm Vox của riêng video này, từ phân tích trở đi
        FALLBACKS.reset()  # các câu phải dùng bản dự phòng, cũng của riêng nó
        run_id = run_id_for(segments, target)

        # Tiêu đề gốc (downloader lưu lúc tải) — ngữ cảnh miễn phí cho cả
        # lượt phân tích lẫn prompt của mọi lô dịch.
        title = ""
        if work_dir:
            from autodub.workdir import load_video_meta
            title = str(load_video_meta(work_dir).get("title", "")).strip()

        rep.emit("translate", "start", detail="VoxDub Cloud")
        logger.info(f"Đang dịch {len(segments)} câu sang tiếng Việt...")

        try:
            # Lượt 0 — kết quả lưu trong thư mục dự án nên chạy tiếp không
            # tốn thêm Vox. Bản cấu hình hiệu dụng chỉ sống trong lượt này.
            effective = settings
            if settings.translate_analysis:
                cache = data_path(work_dir, "video_context.json") if work_dir else None
                analysis = analyze_transcript(segments, source_lang, target,
                                              video_title=title,
                                              cache_path=cache)
                effective = apply_analysis(settings, analysis)
            if title and not effective.translate_video_title:
                import dataclasses
                effective = dataclasses.replace(effective,
                                                translate_video_title=title)

            # Sổ tạm theo lô: rớt mạng ở lô 40/50 thì lần chạy lại chỉ gửi
            # nốt 10 lô cuối. Dịch trọn vẹn thì sổ tự xóa.
            ckpt = (data_path(work_dir, "translate_checkpoint.json")
                    if work_dir else None)
            result = translate_segments(segments, target, source_lang,
                                        effective, rep, checkpoint_path=ckpt)
        except PipelineCancelled:
            raise
        except (InsufficientCreditError, DeviceBlockedError, MaintenanceError):
            # Người dùng phải biết và phải hành động — không nuốt.
            rep.emit("translate", "error", detail="")
            raise
        except OfflineError as e:
            # Fail-closed: mất mạng thì dừng hẳn với lời báo rõ ràng. Sổ tạm
            # còn nguyên nên chạy lại chỉ dịch nốt phần chưa xong.
            logger.error(f"Không kết nối được máy chủ VoxDub: {e}")
            rep.emit("translate", "error", detail=str(e))
            raise
        except SaasError as e:
            logger.warning(f"Dịch tự động lỗi ({e}) — chuyển sang dịch tay")
            rep.emit("translate", "error", detail=str(e))
            return None
        except Exception as e:      # lỗi lạ: vẫn còn đường dịch tay
            logger.warning(f"Dịch tự động lỗi ({e}) — chuyển sang dịch tay")
            rep.emit("translate", "error", detail=str(e))
            return None

        # Lượt rà soát — soát câu tràn khung / lẫn chữ Hán / sót ý rồi dịch
        # lại đúng các câu đó. Hỏng thì giữ nguyên bản lượt đầu.
        try:
            from autodub.text.translate_review import review_translations
            # mini-spec V29 (docs/PLAN.md, Phase G) — trace được LỘ RA
            # (không đổi return type của review_translations(), chỉ THÊM
            # kênh phụ qua trace_out) rồi lưu vào self để
            # _build_quality_report() đọc lại — instance side-channel cùng
            # kiểu self.last_work_dir/self._telemetry_run_id đã dùng.
            trace: list[dict] = []
            result = review_translations(result, target, source_lang,
                                         effective, run_id=run_id,
                                         trace_out=trace)
            self._last_review_trace = trace
        except PipelineCancelled:
            raise
        except Exception as e:
            logger.warning(f"Rà soát bản dịch lỗi ({e}) — dùng bản lượt đầu")

        usage = _usage_snapshot()
        if usage["vox"]:
            logger.info(f"Lượt dịch này tốn {usage['vox']:,} Vox "
                        f"(còn lại {usage['balance_after']:,})")
        return result

    @staticmethod
    def _unique_new_folder_name(output_dir: str, base_name: str) -> str:
        """Đảm bảo tên thư mục cho 1 lượt chạy MỚI (không phải resume) không
        trùng thư mục đã tồn tại.

        mini-spec V42 (docs/PLAN.md, Phase G): ``base_name`` chỉ có độ phân
        giải tới GIÂY (``datetime.now().strftime("%Y%m%d%H%M%S")``) — 2 lượt
        chạy MỚI khởi động cùng 1 giây trước đây sẽ vô tình trùng tên,
        ``ensure_dir()`` (``exist_ok=True``) lặng lẽ tái dùng thư mục cũ như
        thể đang resume, khiến 2 video khác nhau đè file lên nhau. Vô hại
        hiện tại vì batch/watch chạy tuần tự thật (audit V42 xác nhận), vá
        phòng hờ trước khi có bất kỳ đường chạy song song nào (kể cả 2 tiến
        trình CLI độc lập người dùng tự khởi động cùng lúc).
        """
        folder_name = base_name
        suffix = 1
        while os.path.exists(os.path.join(output_dir, folder_name)):
            suffix += 1
            folder_name = f"{base_name}-{suffix}"
        return folder_name

    @staticmethod
    def _load_cached_transcript(
        transcript_path: str, lang_marker_path: str, lang_code: str
    ) -> list[dict] | None:
        """Resume-safe read of ``transcript_original.json`` — ``None`` means
        "nghe lại từ đầu" (file thiếu, hỏng, hoặc ngôn ngữ nguồn đã đổi kể
        từ lượt chạy sinh ra nó).

        mini-spec V40 (docs/PLAN.md, Phase G): trước đây CHỈ kiểm shape JSON
        khi resume — sửa lại "Ngôn ngữ gốc" sau khi job dừng giữa chừng (vd
        chọn nhầm ngôn ngữ) từng âm thầm dùng lại transcript nghe SAI ngôn
        ngữ, không có cảnh báo nào. ``lang_marker_path`` không tồn tại (thư
        mục từ trước V40) → coi là khớp, không ép nghe lại oan dự án cũ.
        """
        if not os.path.exists(transcript_path):
            return None
        try:
            with open(transcript_path, encoding="utf-8") as f:
                cached_segments = json.load(f)
            if not (isinstance(cached_segments, list)
                    and all(isinstance(s, dict) and "start" in s
                            and "end" in s and "text" in s
                            for s in cached_segments)):
                raise ValueError("transcript thiếu trường bắt buộc")
            cached_lang = None
            if os.path.exists(lang_marker_path):
                with open(lang_marker_path, encoding="utf-8") as f:
                    cached_lang = f.read().strip() or None
            if cached_lang is not None and cached_lang != lang_code:
                raise ValueError(
                    f"ngôn ngữ nguồn đã đổi ({cached_lang} → {lang_code})")
            return cached_segments
        except (ValueError, json.JSONDecodeError, OSError) as e:
            logger.warning(f"Transcript cũ hỏng hoặc không khớp ({e}) — nghe lại từ đầu")
            return None

    def _load_translation(
        self, path: str, original_segments: list[dict], target: TargetLang
    ) -> list[dict]:
        """Load and validate the manually-produced translated transcript.

        Guards against the most common hand-made mistakes (wrong root type,
        missing translated field, segment count mismatch) with actionable
        errors instead of a crash deep inside TTS.
        """
        try:
            # File có thể đang mã hóa (hold chưa chốt) — read_json_secure tự
            # nhận biết; file thường đọc như open() bình thường.
            from autodub import securestore
            from autodub.text.translate_common import HOLD
            segments = securestore.read_json_secure(path, HOLD.key)
        except securestore.SecureStoreError as e:
            # File thường mà JSON hỏng → lỗi sửa-tay quen thuộc; chỉ file
            # đang mã hóa mới là chuyện khóa giải mã.
            if not securestore.is_encrypted(path):
                raise ValueError(
                    f"Invalid JSON in {path}: {e}. "
                    "If the AI wrapped the output in ```json fences, "
                    "remove them and re-save."
                ) from e
            raise ValueError(
                f"Không giải mã được bản dịch {path}: {e}. Chạy lại video để "
                "nhận lại khóa từ máy chủ (phần đã dịch không tính phí lại)."
            ) from e

        if not isinstance(segments, list) or not segments:
            raise ValueError(f"{path} must be a non-empty JSON array of segments")

        # Timing fields are as essential as the text: a hand-made file
        # missing start/end/duration would otherwise crash with a bare
        # KeyError — possibly AFTER an expensive TTS pass already ran.
        bad_timing = [
            s.get("id", i + 1) for i, s in enumerate(segments)
            if not all(isinstance(s.get(k), (int, float))
                       for k in ("start", "end", "duration"))
        ]
        if bad_timing:
            raise ValueError(
                f"{path}: {len(bad_timing)} segment(s) missing numeric "
                f"start/end/duration (ids: {bad_timing[:10]}"
                f"{'...' if len(bad_timing) > 10 else ''}). "
                "Keep every field from transcript_original.json — only ADD "
                f"the '{target.text_field}' field."
            )

        missing = [s.get("id", i + 1) for i, s in enumerate(segments)
                   if not str(s.get(target.text_field, "")).strip()]
        if missing:
            raise ValueError(
                f"{path}: {len(missing)} segment(s) missing the '{target.text_field}' "
                f"field (ids: {missing[:10]}{'...' if len(missing) > 10 else ''})"
            )

        if len(segments) != len(original_segments):
            logger.warning(
                f"Translated transcript has {len(segments)} segments but the "
                f"original has {len(original_segments)} — using the translated file."
            )

        # Normalise for TTS (terminal punctuation, single spaces) — manual
        # translations and old transcripts bypass merge_translations, so the
        # guarantee is re-applied here for every path into the pipeline.
        # Slots too: hand-made files (and pre-slot work dirs) lack them.
        from autodub.text.translate_hint import annotate_slots, ensure_terminal_punct
        annotate_slots(segments)
        for seg in segments:
            seg[target.text_field] = ensure_terminal_punct(
                str(seg[target.text_field]))
        return segments

    def _resolve_video(self, work_dir: str, url: str | None, file_path: str | None) -> str:
        """Locate the source video for this work_dir.

        Resume-friendly: reuse a previously downloaded/copied video in work_dir
        instead of re-downloading. Files matching ``dubbed_video*.mp4`` are
        treated as pipeline output, not source. If ``file_path`` is passed it
        takes precedence — useful when the user keeps the source outside
        work_dir. External sources are remembered in ``source_video.json`` so
        a resume finds them without ``--file``.
        """
        marker = data_path(work_dir, "source_video.json", create_dir=True)

        def _remember(path: str) -> str:
            try:
                with open(marker, "w", encoding="utf-8") as f:
                    json.dump({"file_path": os.path.abspath(path)}, f,
                              ensure_ascii=False, indent=2)
            except OSError:
                pass  # marker is a convenience, never fail the run over it
            # File ngoài work_dir có thể mang kèm data/video_meta.json (title)
            # — batch prefetch tải vào thư mục riêng rồi đưa qua file_path.
            # Chép meta vào work_dir để bước dịch/metadata đọc được ngay.
            try:
                src_meta = os.path.join(os.path.dirname(os.path.abspath(path)),
                                        "data", "video_meta.json")
                dst_meta = data_path(work_dir, "video_meta.json")
                if os.path.isfile(src_meta) and not os.path.exists(dst_meta):
                    import shutil
                    shutil.copyfile(src_meta, dst_meta)
            except OSError:
                pass
            return path

        if file_path:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Video file not found: {file_path}")
            return _remember(file_path)

        video_exts = (".mp4", ".mkv", ".webm", ".mov", ".avi")
        output_prefixes = ("dubbed_video",)
        if os.path.isdir(work_dir):
            for f in sorted(os.listdir(work_dir)):
                lower = f.lower()
                if not lower.endswith(video_exts):
                    continue
                if any(lower.startswith(prefix) for prefix in output_prefixes):
                    continue
                cached = os.path.join(work_dir, f)
                logger.info(f"Reusing existing video: {cached}")
                return cached

        # Resume of a run whose source was an external local file.
        remembered = source_video_path(work_dir)
        if remembered:
            logger.info(f"Reusing remembered source video: {remembered}")
            return remembered

        if url:
            from autodub.media.downloader import download_video
            # V67 — cookie (nếu người dùng đã cấu hình) cho video giới hạn.
            return download_video(url, work_dir, settings=self.settings)

        raise RuntimeError(
            f"No source video found in {work_dir} and no --url/--file given. "
            "Pass --file <path> on resume if the original is outside work_dir."
        )

    def _resolve_background(
        self, bg_mode: str, bg_duck_db: float, audio_path: str, work_dir: str
    ) -> tuple[str | None, float]:
        """Resolve the background track for the dub merge (Step 2.5).

        ``audio_path`` is the HQ extract (44.1 kHz stereo) when
        ``hq_background`` is on — the stems keep that layout so the final mix
        retains the soundtrack's full bandwidth.
        """
        rep = self._reporter
        if bg_mode == "demucs":
            logger.info("=" * 60)
            logger.info("STEP 2.5: Separating vocals from original audio (Demucs)")
            logger.info("Đang tách giọng nói gốc ra khỏi nhạc nền — "
                        "mất vài phút với video dài...")
            rep.emit("separate", "start")
            # Keep the input's own layout: HQ path stays 44.1k stereo,
            # legacy path stays at the ASR rate (mono).
            import wave as _wave
            rate, ch = self.settings.audio_sample_rate, 1
            try:
                with _wave.open(audio_path, "rb") as w:
                    rate, ch = w.getframerate(), w.getnchannels()
            except (OSError, EOFError, _wave.Error):
                pass

            sep = None
            # Mini-spec V12 (docs/PLAN.md): tách nhạc trên cloud nếu người
            # dùng đã bật + có máy chủ cấu hình. Lỗi cloud (mạng, job hỏng,
            # quá hạn chờ) rơi về Demucs máy — cùng nguyên tắc "degrade
            # trung thực" đã có (vd Paraformer → Whisper), không im lặng
            # mất tính năng.
            from autodub import cloud_render
            from autodub.progress import PipelineCancelled
            if cloud_render.is_available(self.settings):
                try:
                    sep = cloud_render.separate_vocals_cloud(
                        audio_path, data_dir(work_dir, create=True),
                        sample_rate=rate, channels=ch, reporter=rep)
                except PipelineCancelled:
                    raise   # người dùng hủy — KHÔNG fallback, phải dừng thật
                except Exception as e:  # noqa: BLE001 — lỗi cloud khác đều fallback
                    logger.warning(f"Tách nhạc trên cloud lỗi ({e}) — "
                                   "chuyển sang tách trên máy")
                    sep = None
            if sep is None:
                from autodub.media.vocal_separator import separate_vocals
                sep = separate_vocals(audio_path, data_dir(work_dir, create=True),
                                      sample_rate=rate, channels=ch,
                                      demucs_cache=self._demucs_cache,
                                      cancel_event=self._cancel_event)
            background_path = sep.get("no_vocals")
            if background_path is None:
                logger.warning(
                    "Vocal separation unavailable — dubbed audio will use a silent base"
                )
                rep.emit("separate", "error", detail="separation failed, silent base")
            else:
                rep.emit("separate", "done", detail=background_path)
            # mini-spec V40: Demucs "chạy không lỗi" không có nghĩa là tách
            # SẠCH — file có thể gần như câm (giọng bị cuốn hết vào nhạc nền)
            # mà trước đây không có tín hiệu nào phát hiện. Tái dùng đúng
            # heuristic RMS/khoảng-lặng đã có ở V35 (voice cloning) áp lên
            # vocals.wav — CHỈ báo, KHÔNG chặn (video hoàn toàn không lời
            # thoại là hợp lệ, không phải lỗi tách).
            vocals_path = sep.get("vocals")
            if vocals_path:
                try:
                    import wave as _wave

                    import numpy as np

                    from autodub.speech.tts.audio_quality import analyze

                    # stdlib thay vì soundfile: vocals.wav luôn là PCM 16-bit
                    # do _normalize() ghi ra (pcm_s16le) — không cần kéo thêm
                    # dependency cho 1 phép đo phụ, không phải đường chính.
                    with _wave.open(vocals_path, "rb") as w:
                        raw = w.readframes(w.getnframes())
                        sr = w.getframerate()
                        n_channels = w.getnchannels()
                        sampwidth = w.getsampwidth()
                    if sampwidth != 2:
                        raise ValueError(f"unexpected sample width {sampwidth}")
                    wav = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    if n_channels > 1:
                        wav = wav.reshape(-1, n_channels).mean(axis=1)
                    quality = analyze(wav, sr)
                    self._last_vocals_quality = {
                        "level": quality.level,
                        "reasons": quality.reasons,
                    }
                    if quality.level != "ok":
                        logger.warning(
                            "Tách nhạc nền có thể chưa sạch: "
                            + "; ".join(quality.reasons))
                except Exception as exc:  # noqa: BLE001 — đo tín hiệu phụ, không được làm hỏng lượt tách đã thành công
                    logger.debug(f"Không đo được chất lượng tách nhạc: {exc}")
            return background_path, 0.0

        if bg_mode == "duck":
            logger.info("=" * 60)
            logger.info(
                f"STEP 2.5: Ducking original audio by {bg_duck_db:+.1f} dB "
                "(no vocal separation)"
            )
            rep.emit("separate", "done", detail=f"duck {bg_duck_db:+.1f} dB")
            return audio_path, bg_duck_db

        logger.info("STEP 2.5 skipped: --bg-mode=none, dubbed audio uses silent base")
        rep.emit("separate", "skip")
        return None, 0.0

    # Cached segment wavs are only reusable if they were rendered under the
    # same grouping scheme. Bump when the text-to-wav mapping changes.
    RENDER_MODE = "per_fragment_v1"

    def _ensure_render_mode(self, work_dir: str, seg_dir: str,
                             target: TargetLang, voice: str | None) -> None:
        """Invalidate segment wavs cached under an older render scheme OR a
        different resolved voice (mini-spec V40 — resume with the wizard's
        voice changed used to silently mix old-voice cached clips with
        new-voice fresh ones in the same output).

        Older runs grouped adjacent fragments into one wav keyed by the
        group's FIRST fragment id — reusing those files under the 1:1 scheme
        would play multi-line audio on a single line's slot (echoes and
        overlaps). A marker file records the scheme + resolved voice; on
        mismatch every derived wav is wiped so the run re-renders cleanly.
        """
        import shutil

        from autodub.speech.tts import voices as voice_catalog

        resolved_voice = voice_catalog.resolve(self.settings, voice, target=target)

        marker = os.path.join(seg_dir, ".render_mode")
        current_mode = None
        current_voice = None
        if os.path.exists(marker):
            try:
                with open(marker, encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except OSError:
                lines = []
            current_mode = lines[0].strip() if lines else None
            # Marker gốc (trước V40) chỉ có 1 dòng — current_voice ở lại
            # None nghĩa là "chưa biết", KHÔNG coi là đổi giọng để tránh xóa
            # oan cache của dự án tạo trước khi có field này.
            current_voice = lines[1].strip() if len(lines) > 1 else None

        mode_changed = current_mode != self.RENDER_MODE
        voice_changed = current_voice is not None and current_voice != resolved_voice
        has_wavs = any(f.endswith(".wav") for f in os.listdir(seg_dir))
        if has_wavs and (mode_changed or voice_changed):
            reason = (f"giọng đọc đổi ({current_voice} → {resolved_voice})"
                      if voice_changed else "cơ chế gộp câu cũ")
            logger.warning(
                f"Cache giọng đọc cũ không khớp lượt chạy này ({reason}) — "
                "xóa để tạo lại, tránh lẫn giọng/tiếng lặp trong cùng video."
            )
            for f in os.listdir(seg_dir):
                if f.endswith(".wav"):
                    os.remove(os.path.join(seg_dir, f))
            for d in os.listdir(data_dir(work_dir)):
                if d.startswith(("segments_fit", "segments_slow",
                                 "segments_speed", "segments_post",
                                 "segments_timed")):
                    shutil.rmtree(data_path(work_dir, d), ignore_errors=True)

        if mode_changed or current_voice != resolved_voice:
            with open(marker, "w", encoding="utf-8") as f:
                f.write(f"{self.RENDER_MODE}\n{resolved_voice}")

    def _synthesize_segments(
        self, target: TargetLang, voice: str | None,
        segments: list[dict], seg_dir: str, synth=None,
    ) -> list[dict]:
        """Step 5: per-segment TTS with caching (resume-safe), fanned out over
        one dispatch thread per live TTS worker (``recommended_threads``).

        ``synth`` reuses a pre-warmed synthesizer instance — creating a second
        one would load a second 5+ GB model and OOM a 6 GB card. Results keep
        segment order; cancellation propagates from any task.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from autodub.media.audio import wav_duration_s

        rep = self._reporter
        created_here = synth is None
        if synth is None:
            synth = self._get_synth(target, voice)
            # run()'s error path closes this if we die before the finally
            # below (e.g. an exception between here and the pool block).
            self._active_synth = synth
        text_field = target.text_field

        # Giọng phụ per-segment: câu nào mang khóa "voice" khác giọng chính
        # thì đọc bằng giọng đó. Mỗi giọng phụ chỉ mở MỘT tiến trình con —
        # vài câu lẻ không đáng nhân đôi RAM của cả nhóm worker.
        from autodub.speech.tts import voices as voice_catalog
        run_voice = voice_catalog.resolve(self.settings, voice, target=target)
        extra_synths: dict[str, object] = {}
        extra_lock = threading.Lock()

        def _synth_for(seg: dict):
            seg_voice = str(seg.get("voice", "")).strip()
            if not seg_voice:
                return synth
            name = voice_catalog.resolve(self.settings, seg_voice, target=target)
            if name == run_voice:
                return synth
            with extra_lock:
                if self._synth_cache is not None:
                    return self._synth_cache.get(target, self.settings, name)
                s = extra_synths.get(name)
                if s is None:
                    from autodub.speech.tts import get_synthesizer
                    s = get_synthesizer(target, self.settings, name,
                                        num_workers=1)
                    extra_synths[name] = s
                return s

        total = len(segments)
        # Mỗi câu một dòng nhật ký sẽ ngập giao diện khi video dài — lấy mẫu
        # để video 10 nghìn câu chỉ sinh khoảng 100 dòng tiến độ.
        log_every = 1 if total <= 60 else max(10, total // 100)
        # Số luồng gửi việc bám theo số tiến trình con đang sống thật (một
        # tiến trình chết giữa chừng sẽ bị loại khỏi nhóm).
        n_threads = max(1, getattr(
            synth, "recommended_threads",
            min(self.settings.parallel_workers,
                self.settings.vieneu_max_workers)))

        # Đếm trước phần việc thật: câu đã có clip từ lần chạy trước thì
        # không phải đọc lại. Người dùng cần thấy "còn phải đọc bao nhiêu",
        # không phải tổng số câu — nhất là khi chạy tiếp một dự án cũ.
        cached_n = sum(
            1 for seg in segments
            if os.path.exists(seg_wav_path(seg_dir, seg["id"]))
            and os.path.getsize(seg_wav_path(seg_dir, seg["id"])) > 0)
        seg_voices = {str(s.get("voice", "")).strip()
                      for s in segments if str(s.get("voice", "")).strip()}
        n_voices = len({run_voice} | {
            voice_catalog.resolve(self.settings, v, target=target)
            for v in seg_voices})
        logger.info(
            f"Giọng đọc: {run_voice}"
            + (f" + {n_voices - 1} giọng riêng cho một số câu"
               if n_voices > 1 else "")
            + f" — {total - cached_n}/{total} câu cần đọc"
            + (f" ({cached_n} câu dùng lại của lần chạy trước)"
               if cached_n else "")
            + f", chạy {n_threads} luồng song song")

        results: list[dict | None] = [None] * total
        count_lock = threading.Lock()
        done_count = 0

        def _one(seg: dict) -> dict:
            rep.check_cancelled()
            seg_path = seg_wav_path(seg_dir, seg["id"])
            if os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
                # Chỉ cần thời lượng: đọc header WAV, đừng nạp cả sóng âm —
                # resume video nghìn câu nhanh hơn hàng chục lần.
                return {
                    "path": seg_path,
                    "actual_duration": round(wav_duration_s(seg_path) or 0.0, 3),
                    "speed_adjusted": False,
                    "rate_applied": "cached",
                }
            return _synth_for(seg).synthesize(
                text=seg[text_field],
                output_path=seg_path,
                # Engines always render at natural pace now — timing is
                # handled globally by VIDEO_SPEED/VOICE_SPEED, never per clip.
                target_duration=None,
                # mini-spec V28 (docs/PLAN.md, Phase G) — style riêng cho
                # câu này nếu _apply_emotion_styles() đã gán; None (mặc
                # định) khi tính năng tắt hoặc engine không phải VieNeu —
                # mọi Synthesizer đều nhận tham số này (CapCut bỏ qua có
                # chủ đích, xem capcut_vi.py::synthesize).
                style=seg.get("style"),
            ).to_dict()

        try:
            with ThreadPoolExecutor(max_workers=n_threads) as pool:
                # Longest texts first: a 15 s segment picked up last would
                # leave the other workers idle at the tail of the run. Cached
                # segments cost nothing, so ordering by text length is fine.
                order = sorted(range(total),
                               key=lambda i: len(str(segments[i].get(text_field, ""))),
                               reverse=True)
                futures = {pool.submit(_one, segments[i]): i for i in order}
                try:
                    for fut in as_completed(futures):
                        i = futures[fut]
                        result = fut.result()  # re-raises errors / cancellation
                        results[i] = result
                        with count_lock:
                            done_count += 1
                            n = done_count
                        rep.emit("tts", "progress", current=n, total=total)
                        if (n % log_every == 0 or n == total
                                or result["speed_adjusted"]):
                            logger.info(
                                f"  Segment {segments[i]['id']}: "
                                f"{result['actual_duration']:.1f}s "
                                f"(target: {segments[i]['duration']:.1f}s, "
                                f"rate: {result['rate_applied']}) [{n}/{total}]"
                            )
                except BaseException:
                    # Unstarted tasks never run; in-flight renders (a few
                    # seconds each) finish as the pool context exits, then we
                    # re-raise.
                    for f in futures:
                        f.cancel()
                    raise
        finally:
            # Release worker subprocesses even on error/cancel — a leaked
            # pool pins GBs of VRAM in a long-lived GUI process.
            for extra in extra_synths.values():
                if hasattr(extra, "close"):
                    try:
                        extra.close()
                    except Exception as e:
                        logger.warning(
                            f"Không đóng được synth giọng phụ: {e}")
            if (created_here and self._synth_cache is None
                    and hasattr(synth, "close")):
                try:
                    synth.close()
                finally:
                    self._active_synth = None

        rep.emit("tts", "done", current=total, total=total)
        return results

    def _apply_voice_speed(self, segments: list[dict], seg_dir: str,
                           work_dir: str) -> str:
        """Apply the user's VOICE_SPEED uniformly to every clip.

        The ONLY voice-timing knob: no fitting, no trimming, no per-clip
        decisions. Overlaps are accepted — lower VIDEO_SPEED (or raise
        VOICE_SPEED) and re-run if lines collide. At 1.0 the raw renders
        are used as-is.
        """
        speed = self.settings.voice_speed
        if abs(speed - 1.0) < 0.005:
            return seg_dir
        logger.info(
            f"Chỉnh tốc độ giọng đọc {speed:.2f}x cho tất cả các câu "
            "(theo Cài đặt)"
        )
        from autodub.media.audio import slow_segments
        dst = data_path(work_dir, f"segments_speed{speed:.2f}".replace(".", "_"))
        return slow_segments(segments, seg_dir, dst, speed,
                             max_workers=min(8, self.settings.parallel_workers))

    def _generate_content(
        self, target: TargetLang, segments: list[dict],
        source_url: str | None, work_dir: str, video_path: str | None = None,
    ) -> dict:
        """Bước 8: tiêu đề, mô tả và hashtag cho mạng xã hội.

        Bước phụ — hỏng thì video vẫn xong. Riêng hết Vox thì ném lên trên để
        giao diện mời người dùng nạp thêm, vì đó không phải lỗi kỹ thuật.
        """
        del target, video_path
        rep = self._reporter
        settings = self.settings
        content_result: dict = {"metadata": {}}
        if not settings.generate_metadata:
            logger.info("Bỏ qua tạo tiêu đề và mô tả (đã tắt trong Cài đặt)")
            rep.emit("content", "skip")
            return content_result

        logger.info("=" * 60)
        logger.info("STEP 8: Generating social metadata")
        logger.info("Đang viết tiêu đề, mô tả và hashtag cho "
                    "YouTube/TikTok/Facebook...")
        rep.emit("content", "start")

        from autodub.saas_client import InsufficientCreditError

        try:
            from autodub.content.generator import generate_content
            from autodub.text.translate_saas import run_id_for
            from autodub.workdir import load_video_meta
            content_result = generate_content(
                segments=segments,
                source_url=source_url,
                output_dir=youtube_dir(work_dir, create=True),
                settings=settings,
                video_title=str(load_video_meta(work_dir).get("title", "")),
                # Cùng transcript ⇒ cùng job_id ⇒ chạy lại không tính phí lần hai.
                job_id=f"post-{run_id_for(segments, _POST_TARGET)}",
            )
            logger.info("Đã viết xong phần đăng bài "
                        "(xem thư mục youtube trong dự án)")
            rep.emit("content", "done")
        except InsufficientCreditError:
            rep.emit("content", "error", detail="Không đủ Vox")
            raise
        except Exception as e:
            logger.error(f"Tạo nội dung đăng bài lỗi (không ảnh hưởng video): {e}")
            rep.emit("content", "error", detail=str(e))
        return content_result

    def _build_report(
        self, target: TargetLang, folder_name: str, req: DubRequest,
        lang_code: str, segments: list[dict], tts_results: list[dict],
        work_dir: str, audio_path: str, merged_audio_path: str,
        dubbed_video_path: str | None, content_result: dict, elapsed: float,
    ) -> dict:
        from autodub.speech.tts import voices as voice_catalog
        return {
            "session_id": folder_name,
            "source_url": req.url,
            "source_language": lang_code,
            "target_language": target.code,
            # Tên giọng đã dùng thật (đã phân giải), để thẻ dự án hiện đúng.
            "voice": voice_catalog.resolve(self.settings, req.voice,
                                           target=target),
            "total_segments": len(segments),
            "total_original_duration": round(sum(s["duration"] for s in segments), 3),
            "total_tts_duration": round(sum(r["actual_duration"] for r in tts_results), 3),
            "segments_speed_adjusted": sum(1 for r in tts_results if r["speed_adjusted"]),
            "processing_time_seconds": round(elapsed, 1),
            "output_dir": work_dir,
            "files": {
                "original_audio": audio_path,
                "transcript_original_json": data_path(work_dir, "transcript_original.json"),
                "transcript_original_srt": data_path(work_dir, "transcript_original.srt"),
                "transcript_dub_json": data_path(work_dir, target.transcript_name),
                "transcript_dub_srt": os.path.join(work_dir, target.srt_name),
                "dub_audio": merged_audio_path,
                "dubbed_video": dubbed_video_path,
                "youtube_metadata": content_result.get("metadata_file"),
            },
        }

    @staticmethod
    def _build_quality_report(target: TargetLang, segments: list[dict],
                              timing_report, settings=None,
                              review_trace: list[dict] | None = None,
                              vocals_quality: dict | None = None,
                              lipsync_state: dict | None = None) -> dict:
        """quality_report.json — tổng hợp mọi vấn đề còn lại sau render.

        Nguồn: TimingReport của bước đặt timeline mềm + kiểm tra budget dịch.
        ``per_segment`` chỉ chứa các câu CÓ vấn đề (kèm text để tìm nhanh
        trong editor) — video sạch thì danh sách rỗng.

        ``review_trace`` (mini-spec V29, docs/PLAN.md Phase G — TUỲ CHỌN,
        ADDITIVE): trace của `translate_review.py::review_translations()`
        cho video này (rỗng nếu không chạy review, vd đường dịch tay) — lộ
        ra thành field `translate_review` cấp cao, KHÔNG đụng
        `summary`/`per_segment` đã có từ V23.

        ``vocals_quality`` (mini-spec V40, docs/PLAN.md Phase G — TUỲ CHỌN,
        ADDITIVE): tín hiệu RMS/khoảng-lặng đo trên ``vocals.wav`` sau khi
        Demucs tách xong (rỗng nếu bg_mode khác "demucs" hoặc tách thất
        bại) — lộ ra thành field `background_separation`, CHỈ báo, không
        chặn (không có cách nào biết chắc video có nên có lời thoại hay
        không mà không cần nghe thật).

        ``lipsync_state`` (mini-spec V32b, docs/PLAN.md Phase G — TUỲ CHỌN,
        ADDITIVE): kết quả bước "Đồng bộ khẩu hình" nếu ``DubRequest.
        lipsync=True`` (rỗng nếu không bật) — lộ ra thành field `lipsync`,
        gồm ``status`` (unavailable/blocked/failed/applied) để người dùng
        biết CHẮC video này có thật sự được xử lý hay đã tự động bỏ qua
        (Constraint 2: degrade trung thực, không phải lỗi mù mờ).
        """
        from autodub.media.audio import FALLBACKS
        from autodub.text.translate_hint import effective_cps, payload_segment

        # Câu phải dùng bản dự phòng (atempo/hậu kỳ ffmpeg trượt): clip vẫn
        # có nhưng sai tốc độ hoặc chưa chuẩn hóa âm lượng. Không làm hỏng
        # video nên không raise, song phải hiện ra đây — nghe thấy chất lượng
        # tệ mà không có dòng nào giải thích là điều tệ nhất.
        fallbacks = FALLBACKS.snapshot()
        speed_fallback = set(fallbacks.get("atempo_failed", ()))
        post_fallback = set(fallbacks.get("postprocess_failed", ()))

        # Budget theo tốc độ THẬT: giọng đã chỉnh voice_speed; segments lúc
        # này ĐÃ nằm trên timeline kéo dài (video chậm xong rồi) nên không
        # nhân thêm 1/video_speed — không thì câu vừa khít vẫn bị báo oan.
        cps = effective_cps(settings, video_slowdown_pending=False)
        # Nhận cả TimingReport lẫn dict (export_state lưu sẵn dạng dict).
        if timing_report is None:
            timing = {}
        elif isinstance(timing_report, dict):
            timing = timing_report
        else:
            timing = timing_report.to_dict()
        by_id = {d.get("id"): d for d in timing.get("details", [])}

        per_segment: list[dict] = []
        over_budget = 0
        for seg in segments:
            issues: dict = dict(by_id.get(seg.get("id"), {}))
            issues.pop("id", None)
            budget = payload_segment(seg, cps).get("max_chars")
            text = str(seg.get(target.text_field, ""))
            if budget and len(text) > budget * 1.25:
                issues["over_budget_chars"] = len(text) - budget
                over_budget += 1
            if seg.get("id") in speed_fallback:
                issues["speed_fallback"] = True
            if seg.get("id") in post_fallback:
                issues["postprocess_fallback"] = True
            if issues:
                per_segment.append({
                    "id": seg.get("id"),
                    "start": seg.get("start"),
                    "text": text[:120],
                    **issues,
                })

        return {
            "summary": {
                "segments_total": len(segments),
                "segments_ok": len(segments) - len(per_segment),
                "segments_shifted": timing.get("segments_shifted", 0),
                "max_shift_s": timing.get("max_shift_s", 0.0),
                "segments_compressed": timing.get("segments_compressed", 0),
                "segments_overlapped": timing.get("segments_overlapped", 0),
                "total_overlap_s": timing.get("total_overlap_s", 0.0),
                "segments_over_budget": over_budget,
                "segments_speed_fallback": len(speed_fallback),
                "segments_postprocess_fallback": len(post_fallback),
            },
            # Token đã tiêu cho video này (phân tích + dịch + rà soát) —
            # người dùng trả tiền theo con số này nhưng không thấy nó ở đâu
            # khác. Video dịch tay hoặc chạy lại từ cache thì toàn số 0.
            "translate_usage": _usage_snapshot(),
            "hint": ("Câu 'overlap_prev_s' là chồng tiếng còn lại — rút gọn "
                     "bản dịch câu đó trong tab Chỉnh sửa, hoặc hạ "
                     "VIDEO_SPEED rồi chạy lại. Câu 'over_budget_chars' nên "
                     "được rút gọn để đọc thong thả hơn."),
            "per_segment": per_segment,
            # mini-spec V29 (docs/PLAN.md, Phase G) — trace review dịch tự
            # động: câu nào bị nghi vấn, AI có sửa được không, before/after.
            # Rỗng nếu review không chạy (đường dịch tay) — không gây nhiễu.
            "translate_review": review_trace or [],
            # mini-spec V40 — xem docstring "vocals_quality" ở trên.
            "background_separation": vocals_quality or {},
            # mini-spec V32b — xem docstring "lipsync_state" ở trên.
            "lipsync": lipsync_state or {},
        }

    @staticmethod
    def _build_timing_guide(
        target: TargetLang, report: dict,
        segments: list[dict], tts_results: list[dict],
    ) -> dict:
        """Timing guide JSON showing per-segment original vs dub duration.

        Helps the user quickly identify which segments need manual adjustment
        in a video editor (e.g. CapCut).
        """
        lang = target.key  # "vi" — used in field names
        guide = {
            "session_id": report["session_id"],
            "source_url": report["source_url"],
            "target_language": target.code,
            "summary": {
                "total_segments": report["total_segments"],
                "original_duration": report["total_original_duration"],
                f"{lang}_duration": report["total_tts_duration"],
                "ratio": round(report["total_tts_duration"] / report["total_original_duration"], 2)
                         if report["total_original_duration"] > 0 else 0,
                "segments_need_edit": 0,
                "segments_ok": 0,
            },
            "segments": [],
        }

        need_edit = 0
        for seg, tts in zip(segments, tts_results):
            diff = round(tts["actual_duration"] - seg["duration"], 2)

            # OK if dub audio within ±30% of original duration
            if abs(diff) <= seg["duration"] * 0.3:
                status = "OK"
            elif diff > 0:
                status = "TOO_LONG"
                need_edit += 1
            else:
                status = "TOO_SHORT"
                need_edit += 1

            guide["segments"].append({
                "id": seg["id"],
                "text_original": seg.get("text", ""),
                target.text_field: seg.get(target.text_field, ""),
                "start": seg["start"],
                "end": seg["end"],
                "original_duration": seg["duration"],
                f"{lang}_duration": tts["actual_duration"],
                "diff_seconds": diff,
                "speed_adjusted": tts["speed_adjusted"],
                "rate_applied": tts.get("rate_applied", ""),
                "status": status,
                "edit_hint": f"{lang.upper()} {'dài' if diff > 0 else 'ngắn'} hơn {abs(diff):.1f}s"
                             if status != "OK" else "OK",
            })

        guide["summary"]["segments_need_edit"] = need_edit
        guide["summary"]["segments_ok"] = report["total_segments"] - need_edit

        return guide


def export_committed_project(
    work_dir: str,
    settings: Settings,
    progress: ProgressFn | None = None,
    cancel_event: threading.Event | None = None,
) -> DubResult:
    """Xuất video của một dự án đang chờ (``status="export_pending"``).

    Thứ tự làm — mỗi bước đều an toàn khi lặp lại:

    1. ``commit_hold`` — mở khóa dự án. Giá đã trừ đủ lúc giữ chỗ nên bước
       này KHÔNG động vào tiền. Idempotent: hold đã chốt (kể cả tự chốt sau
       48h) trả lại đúng kết quả cũ kèm khóa giải mã.
    2. Giải mã toàn bộ file trung gian theo marker ``voxdub_lock.json``.
    3. Chạy phase Xuất video: phụ đề, ghép MP4, nội dung đăng bài, báo cáo.

    Mất mạng ở bước 1 → ném :class:`OfflineError`, chưa mất gì — file còn mã
    hóa, bấm lại là chạy tiếp.
    """
    from autodub import securestore
    from autodub.saas_client import get_client
    from autodub.text.translate_common import HOLD, USAGE

    lock = securestore.read_lock(work_dir)
    if not lock:
        raise RuntimeError(
            f"Dự án không ở trạng thái chờ xuất (thiếu marker khóa): {work_dir}")
    hold_id = str(lock.get("hold_id") or "")
    if not hold_id:
        raise RuntimeError("Marker khóa hỏng (thiếu hold_id) — chạy lại video")

    # 1. Chốt hold — chỉ mở khóa, tiền đã trừ đủ từ lúc giữ chỗ.
    data = get_client().commit_hold(hold_id)
    key = str(data.get("encKeyHex") or "")
    if not key:
        raise RuntimeError("Máy chủ không trả khóa giải mã khi chốt hold — "
                           "liên hệ hỗ trợ")
    charged = int(data.get("chargedVox") or 0)
    balance = int(data.get("balance") or 0)
    if data.get("replayed"):
        logger.info(f"Video này đã tính {charged:,} Vox từ trước — chỉ xuất video")
    else:
        logger.info(f"Video này tốn {charged:,} Vox — ví còn {balance:,} Vox")

    # 2. Giải mã file trung gian — từ đây dữ liệu thuộc về người dùng.
    unlocked = securestore.unlock_all(work_dir, key)
    if unlocked:
        logger.info(f"Đã mở khóa {len(unlocked)} file dữ liệu của dự án")

    # 3. Đọc trạng thái xuất rồi chạy nốt phase cuối.
    state_path = data_path(work_dir, "export_state.json")
    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"Không đọc được trạng thái xuất ({e}) — chạy lại video để dựng "
            "lại (phần đã dịch không tính phí lần hai)") from e

    from autodub.media.audio import FALLBACKS

    # GIỮ hold_id qua phase cuối: bước tạo nội dung đăng bài chạy SAU commit,
    # nhưng +20 Vox của gói tiêu đề + mô tả đã nằm trong giá hold — server
    # nhận hold committed cho đúng một lượt generate_post, không trừ ví thêm.
    HOLD.set(hold_id, key)
    USAGE.reset()
    USAGE.add(charged, balance)  # thẻ tổng kết hiện đúng số Vox của video này
    FALLBACKS.reset()          # lượt dựng lại này tự đếm fallback của nó

    pipeline = DubPipeline(settings, progress=progress,
                           cancel_event=cancel_event)
    target = get_target(str(state.get("target") or "vi"))
    try:
        result = pipeline._export_phase(state, work_dir, target)
    finally:
        HOLD.clear()           # hold đã xong việc — không rớt sang lượt sau

    # Trạng thái xuất đã dùng xong — dọn để marker/resume không hiểu nhầm.
    try:
        os.remove(state_path)
    except OSError:
        pass
    return result
