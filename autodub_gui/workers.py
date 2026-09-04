"""Background workers: run the pipeline / batch / downloads off the UI thread.

Each worker is a QThread emitting Qt signals; ProgressEvent objects from the
core pipeline are forwarded as-is (they are plain dataclasses, safe across
threads via queued connections). A logging.Handler subclass forwards core log
records into the GUI log panel.
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QRunnable, QThread, Signal

from autodub.config import Settings
from autodub.pipeline import DubPipeline, DubRequest, DubResult
from autodub.progress import PipelineCancelled

from autodub.utils import setup_logging

logger = setup_logging("autodub_gui.workers")


# --- Lọc log cho người dùng --------------------------------------------------
# GuiLogHandler chỉ chuyển những gì người dùng cần thấy lên khung Nhật ký.
# Bảng thông báo soạn sẵn nằm trong log_text.py — chỉnh lời ở đó, không ở đây.
# Mọi log kỹ thuật (tên model, đường dẫn, tham số, id...) vẫn ra console và
# tệp log cho người phát triển, không bao giờ lên giao diện.


class GuiLogHandler(logging.Handler):
    """Chuyển log autodub.* lên signal Qt — chỉ những gì người dùng cần."""

    def __init__(self, signal):
        super().__init__()
        self._signal = signal

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from autodub_gui.log_text import notice_for
            import time as _time
            result = notice_for(record.getMessage(), record.levelno)
            if result is None:
                return
            text, level = result
            ts = _time.strftime("%H:%M", _time.localtime(record.created))
            self._signal.emit(f"{ts}  {text}", level)
        except RuntimeError:
            pass  # window closed while a worker was still logging


def attach_gui_logging(signal) -> GuiLogHandler:
    """Attach a GUI handler to the shared 'autodub' logger namespace."""
    handler = GuiLogHandler(signal)
    root = logging.getLogger("autodub")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return handler


def detach_gui_logging(handler: GuiLogHandler) -> None:
    logging.getLogger("autodub").removeHandler(handler)


class DubWorker(QThread):
    """Run one DubPipeline.run() in the background."""

    progress = Signal(object)          # ProgressEvent
    log = Signal(str, int)             # message, levelno
    finished_ok = Signal(object)       # DubResult
    failed = Signal(str)               # error message
    cancelled = Signal()

    def __init__(self, settings: Settings, request: DubRequest, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._request = request
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        handler = attach_gui_logging(self.log)
        try:
            pipeline = DubPipeline(
                self._settings,
                progress=self.progress.emit,
                cancel_event=self._cancel_event,
            )
            result: DubResult = pipeline.run(self._request)
            self.finished_ok.emit(result)
        except PipelineCancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001 — surfaced to the user verbatim
            self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class ExportWorker(QThread):
    """Chốt hold Vox rồi xuất video cho dự án đang chờ (luồng wizard).

    Gọi :func:`autodub.pipeline.export_committed_project`: commit hold (trừ
    Vox theo thực dùng, hoàn phần giữ chỗ thừa), giải mã file trung gian,
    rồi chạy phase Xuất video. Mất mạng ở bước commit → failed, Vox chưa
    trừ, bấm lại là chạy tiếp.
    """

    progress = Signal(object)          # ProgressEvent
    log = Signal(str, int)
    finished_ok = Signal(object)       # DubResult
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, settings: Settings, work_dir: str, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._work_dir = work_dir
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.pipeline import export_committed_project

        handler = attach_gui_logging(self.log)
        try:
            result: DubResult = export_committed_project(
                self._work_dir, self._settings,
                progress=self.progress.emit,
                cancel_event=self._cancel_event)
            self.finished_ok.emit(result)
        except PipelineCancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001 — surfaced to the user verbatim
            self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class SaveAllWorker(QThread):
    """Save every edited line, then re-run TTS for the ones that changed.

    One worker for the whole batch: the user edits freely, presses save once,
    and gets a single progress stream instead of per-row round trips.
    """

    log = Signal(str, int)
    seg_done = Signal(int, int, int)          # seg_id, index, total
    finished_ok = Signal(list)                # re-synthesized seg ids
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, settings: Settings, work_dir: str, edits: dict[int, str],
                 target_key: str, voice: str | None, parent=None,
                 force_all: bool = False,
                 force_ids: set[int] | None = None):
        super().__init__(parent)
        self._settings = settings
        self._work_dir = work_dir
        self._edits = edits
        self._target_key = target_key
        self._voice = voice
        self._force_all = force_all
        # Câu chỉ đổi giọng (không sửa chữ) vẫn phải đọc lại — text không đổi
        # nên save_segment_texts không trả về chúng; force_ids bù lại chỗ thiếu đó.
        self._force_ids: set[int] = set(force_ids or [])
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.editor import resynth_segments, save_segment_texts
        from autodub.progress import ProgressReporter

        handler = attach_gui_logging(self.log)
        reporter = ProgressReporter(lambda _e: None, self._cancel_event)
        try:
            changed = save_segment_texts(self._work_dir, self._edits, self._target_key)
            # Đổi giọng cho cả video: đọc lại mọi câu, kể cả câu không sửa chữ.
            if self._force_all:
                changed = sorted(self._edits.keys())
            # Câu chỉ đổi giọng mà không sửa chữ: bổ sung vào danh sách cần đọc lại.
            if self._force_ids:
                changed = sorted(set(changed) | self._force_ids)
            if not changed:
                self.finished_ok.emit([])
                return
            resynth_segments(
                self._work_dir, changed, self._settings,
                self._target_key, self._voice, reporter,
                on_progress=lambda done, total, sid:
                    self.seg_done.emit(sid, done, total))
            self.finished_ok.emit(changed)
        except PipelineCancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001 — surfaced to the user verbatim
            self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class RebuildWorker(QThread):
    """Rebuild the final audio + video from edited segments off the UI thread."""

    progress = Signal(object)          # ProgressEvent
    log = Signal(str, int)
    finished_ok = Signal(str)          # dubbed video path
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, settings: Settings, work_dir: str, target_key: str,
                 voice: str | None, bg_mode: str, bg_duck_db: float,
                 subtitle_mode: str | None, blur_regions: list[dict] | None,
                 subtitle_style: dict | None = None, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._work_dir = work_dir
        self._target_key = target_key
        self._voice = voice
        self._bg_mode = bg_mode
        self._bg_duck_db = bg_duck_db
        self._subtitle_mode = subtitle_mode
        self._blur_regions = blur_regions
        self._subtitle_style = subtitle_style
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.editor import rebuild_output
        from autodub.progress import ProgressReporter

        handler = attach_gui_logging(self.log)
        reporter = ProgressReporter(self.progress.emit, self._cancel_event)
        try:
            out = rebuild_output(
                self._work_dir, self._settings, self._target_key, self._voice,
                self._bg_mode, self._bg_duck_db,
                self._subtitle_mode, self._blur_regions,
                self._subtitle_style, reporter)
            self.finished_ok.emit(out)
        except PipelineCancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class SubtitleWorker(QThread):
    """Ghi lại phụ đề vào video mà không đụng tới giọng đọc.

    Đây là đường nhanh cho việc sửa chữ hoặc đổi kiểu chữ: chỉ vẽ lại chữ lên
    hình, dùng lại nguyên bản âm thanh của lần xuất trước.
    """

    progress = Signal(object)
    log = Signal(str, int)
    finished_ok = Signal(str)          # đường dẫn video kết quả
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, settings: Settings, work_dir: str, target_key: str,
                 subtitle_mode: str | None, blur_regions: list[dict] | None,
                 subtitle_style: dict | None = None, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._work_dir = work_dir
        self._target_key = target_key
        self._subtitle_mode = subtitle_mode
        self._blur_regions = blur_regions
        self._subtitle_style = subtitle_style
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.editor import rebuild_subtitles
        from autodub.progress import ProgressReporter

        handler = attach_gui_logging(self.log)
        reporter = ProgressReporter(self.progress.emit, self._cancel_event)
        try:
            out = rebuild_subtitles(
                self._work_dir, self._settings, self._target_key,
                self._subtitle_mode, self._blur_regions,
                self._subtitle_style, reporter)
            self.finished_ok.emit(out)
        except PipelineCancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class SegmentPreviewWorker(QThread):
    """Dựng đoạn xem thử ngắn quanh một câu, không đụng tới video kết quả.

    Chỉ mã hóa vài giây quanh câu đang chọn (ultrafast, 480p) — cho người
    dùng nghe thử giọng + nhạc nền + phụ đề đúng như bản xuất, trước khi
    tốn thời gian xuất cả phim.
    """

    log = Signal(str, int)
    finished_ok = Signal(str)          # đường dẫn mp4 xem thử
    failed = Signal(str)

    def __init__(self, settings: Settings, work_dir: str, seg_id: int,
                 target_key: str, bg_mode: str, bg_duck_db: float,
                 subtitle_mode: str | None, subtitle_style: dict | None = None,
                 parent=None):
        super().__init__(parent)
        self._settings = settings
        self._work_dir = work_dir
        self._seg_id = seg_id
        self._target_key = target_key
        self._bg_mode = bg_mode
        self._bg_duck_db = bg_duck_db
        self._subtitle_mode = subtitle_mode
        self._subtitle_style = subtitle_style
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.editor import render_segment_preview

        handler = attach_gui_logging(self.log)
        try:
            out = render_segment_preview(
                self._work_dir, self._settings, self._seg_id,
                self._target_key, self._bg_mode, self._bg_duck_db,
                self._subtitle_mode, self._subtitle_style)
            if not self._cancel_event.is_set():
                self.finished_ok.emit(out)
        except Exception as e:  # noqa: BLE001
            if not self._cancel_event.is_set():
                self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class BatchWorker(QThread):
    """Run a batch of pasted URLs (one per line) in the background."""

    progress = Signal(object)                    # ProgressEvent (current video)
    item_status = Signal(int, int, str, str, str)  # index, total, url, status, detail
    log = Signal(str, int)
    finished_ok = Signal(object)                 # BatchSummary
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, settings: Settings, req_template: DubRequest,
                 items: list, retry_done: bool = False, reuse_tts: bool = True,
                 parent=None):
        super().__init__(parent)
        self._settings = settings
        self._template = req_template
        self._items = items          # list[BatchItem] (or pasted text lines)
        self._retry_done = retry_done
        self._reuse_tts = reuse_tts
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.batch import run_batch

        handler = attach_gui_logging(self.log)

        def observer(i, total, item, status, detail):
            self.item_status.emit(i, total, item.key, status, detail)

        synth_cache = None
        demucs_cache = None
        whisper_cache = None
        try:
            if self._reuse_tts:
                from autodub.speech.tts import SynthCache
                synth_cache = SynthCache()
            if len(self._items) > 1:
                # Giữ worker Demucs sống giữa các video — CLI (run_batch) đã
                # làm vậy, nhánh GUI trước đây quên nên nạp lại model mỗi video.
                from autodub.media.vocal_separator import DemucsCache
                demucs_cache = DemucsCache()
                from autodub.speech.transcriber import WhisperCache
                whisper_cache = WhisperCache()
            pipeline = DubPipeline(
                self._settings,
                progress=self.progress.emit,
                cancel_event=self._cancel_event,
                synth_cache=synth_cache,
                demucs_cache=demucs_cache,
                whisper_cache=whisper_cache,
            )
            summary = run_batch(self._items, self._settings, self._template,
                                pipeline=pipeline, observer=observer,
                                retry_done=self._retry_done)
            self.finished_ok.emit(summary)
        except PipelineCancelled:
            self.cancelled.emit()
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
        finally:
            if synth_cache is not None:
                synth_cache.close()
            if demucs_cache is not None:
                demucs_cache.close()
            if whisper_cache is not None:
                whisper_cache.close()
            detach_gui_logging(handler)


class ProjectScanWorker(QThread):
    """Quét thư mục kết quả ở luồng nền.

    Việc này đọc rất nhiều tệp nhỏ và tính dung lượng cả cây thư mục, nên
    chạy trên luồng giao diện sẽ làm cửa sổ đứng vài giây khi có nhiều dự án.
    """

    ready = Signal(list)          # list[Project]
    failed = Signal(str)

    def __init__(self, output_dir: str, running_dir: str = "", parent=None):
        super().__init__(parent)
        self._output_dir = output_dir
        self._running_dir = running_dir

    def run(self) -> None:
        from autodub_gui.projects import scan

        try:
            self.ready.emit(scan(self._output_dir, self._running_dir))
        except Exception as e:  # noqa: BLE001 — hiện thành màn hình lỗi
            self.failed.emit(str(e))


class ThumbnailWorker(QRunnable):
    """Tạo một ảnh đại diện bằng ffmpeg, chạy trong nhóm luồng dùng chung."""

    class Signals(QObject):
        ready = Signal(str, str)      # khóa dự án, đường dẫn ảnh

    def __init__(self, project):
        super().__init__()
        self.signals = self.Signals()
        self._project = project
        self.setAutoDelete(True)

    def run(self) -> None:
        from autodub_gui.projects import ensure_thumbnail

        try:
            path = ensure_thumbnail(self._project)
        except Exception as e:  # noqa: BLE001 — thiếu ảnh thì dùng ô giữ chỗ
            logger.debug(f"Không tạo được ảnh đại diện dự án ({e})")
            path = ""
        if path:
            self.signals.ready.emit(self._project.key, path)


class WaveformWorker(QThread):
    """Tính dạng sóng ở luồng nền.

    Việc này quét cả tệp âm thanh, với video dài có thể mất vài giây, nên
    không được làm trên luồng giao diện.
    """

    ready = Signal(list)      # danh sách biên độ từ 0 tới 1

    def __init__(self, wav_path: str, buckets: int = 0, parent=None,
                 cache_name: str | None = None):
        super().__init__(parent)
        self._path = wav_path
        self._buckets = buckets
        self._cache_name = cache_name

    def run(self) -> None:
        from autodub_gui.waveform import DEFAULT_BUCKETS, peaks

        try:
            self.ready.emit(peaks(self._path, self._buckets or DEFAULT_BUCKETS,
                                  cache_name=self._cache_name))
        except Exception:  # noqa: BLE001 — không vẽ được thì hiện dải phẳng
            self.ready.emit([])


class PreflightWorker(QThread):
    """Chạy kiểm tra tiền chuyến bay (autodub.preflight) ở luồng nền.

    Kiểm tra chạm đĩa và gọi ffmpeg nên không được làm trên luồng giao diện.
    Kết quả là danh sách CheckResult (dataclass thuần, an toàn qua signal).
    """

    ready = Signal(list)      # list[autodub.preflight.CheckResult]

    def run(self) -> None:
        from autodub.preflight import run_preflight

        try:
            results = run_preflight(Settings.load(override=True))
        except Exception:  # noqa: BLE001 — không được làm sập giao diện
            # Nuốt im lặng ở đây là app KHÔNG hiện cảnh báo nào về máy thiếu
            # thành phần — người dùng tưởng mọi thứ ổn cho tới lúc chạy hỏng.
            # Đúng lớp lỗi V83, nên phải để lại dấu vết (V92).
            logger.exception("Kiểm tra điều kiện máy thất bại")
            results = []
        self.ready.emit(results)


class UpdateCheckWorker(QThread):
    """Hỏi GitHub xem có bản VoxDub mới không, chạy ở luồng nền.

    Gọi mạng nên không được chạy trên luồng giao diện. Không có mạng hay kho
    chưa có bản phát hành nào thì im lặng — kiểm tra nền không được làm phiền.
    """

    found = Signal(object)    # autodub.updates.UpdateInfo

    def __init__(self, repo: str, current_version: str, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._current = current_version

    def run(self) -> None:
        from autodub.updates import check_for_update

        try:
            info = check_for_update(self._repo, self._current)
        except Exception:  # noqa: BLE001 — lỗi mạng thì coi như không có bản mới
            return
        if info is not None:
            self.found.emit(info)


class SystemStatusWorker(QThread):
    """Đọc lại tệp cấu hình và kiểm tra ba thứ thiết yếu, chạy ở luồng nền.

    Kiểm tra giọng đọc, dịch tự động và FFmpeg. Việc này chạm vào ổ đĩa nên
    tuyệt đối không được làm trên luồng giao diện.
    """

    ready = Signal(dict)      # {"voice": (chữ, ổn), "translate": ..., "ffmpeg": ...}

    def run(self) -> None:
        import shutil

        result: dict[str, tuple[str, bool | None]] = {}
        try:
            settings = Settings.load(override=True)
            result["voice"] = self._voice_status(settings)
            result["translate"] = self._translate_status(settings)
            ok = bool(shutil.which("ffmpeg"))
            result["ffmpeg"] = ("sẵn sàng" if ok else "chưa cài", ok)
        except Exception as e:  # noqa: BLE001 — không được làm sập giao diện
            result = {"voice": ("không đọc được", False),
                      "translate": ("không đọc được", False),
                      "ffmpeg": (str(e)[:40], False)}
        self.ready.emit(result)

    @staticmethod
    def _voice_status(settings: Settings) -> tuple[str, bool | None]:
        """Có bao nhiêu giọng dùng được — kể cả khi chưa cài VieNeu."""
        try:
            from autodub.speech.tts.voices import catalog
            count = len(catalog(settings))
        except Exception:  # noqa: BLE001 — không được làm sập giao diện
            return ("không đọc được", False)
        if not count:
            return ("chưa có giọng nào", False)
        if not settings.vieneu_configured():
            return (f"{count} giọng CapCut (chưa cài VieNeu)", True)
        return (f"{count} giọng", True)

    @staticmethod
    def _translate_status(settings: Settings) -> tuple[str, bool | None]:
        """Kết nối tới máy chủ dịch, và số Vox còn lại.

        Chạy trong luồng nền của trang Trợ giúp nên được phép gọi mạng; mất
        mạng thì báo đúng như vậy chứ không treo giao diện.
        """
        if not settings.translate_enabled:
            return ("đang tắt", None)
        from autodub.saas_client import SaasError, get_client, is_configured

        if not is_configured():
            return ("chạy thuần trên máy — bước dịch làm tay", True)
        try:
            device = get_client().ensure_session()
        except SaasError as e:
            return (f"chưa kết nối được ({str(e)[:60]})", False)
        if not device.get("creditEnabled", True):
            return ("VoxDub Cloud (đang miễn phí)", True)
        balance = int(device.get("balance", 0))
        return (f"VoxDub Cloud — còn {balance:,} Vox", balance > 0)


class DownloadWorker(QThread):
    """Download a list of URLs (no dubbing)."""

    item_status = Signal(int, int, str, str, str)  # index, total, url, status, detail
    log = Signal(str, int)
    finished_ok = Signal(int, int)                 # success, failed
    failed = Signal(str)                           # whole-run error (e.g. bad output dir)
    cancelled = Signal()

    def __init__(self, urls: list[str], output_dir: str,
                 cookies_from_browser: str | None = None,
                 cookies_file: str | None = None, parent=None):
        super().__init__(parent)
        self._urls = urls
        self._output_dir = output_dir
        self._cookies_browser = cookies_from_browser or None
        self._cookies_file = cookies_file or None
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.media.downloader import download_one
        from autodub.utils import ensure_dir

        handler = attach_gui_logging(self.log)
        success = failed = 0
        try:
            ensure_dir(self._output_dir)
            total = len(self._urls)
            for i, url in enumerate(self._urls):
                if self._cancel_event.is_set():
                    self.cancelled.emit()
                    return
                self.item_status.emit(i, total, url, "start", "")
                try:
                    entry = download_one(url, self._output_dir,
                                         self._cookies_browser, self._cookies_file)
                    success += 1
                    self.item_status.emit(i, total, url, "success", entry["filepath"])
                except Exception as e:  # noqa: BLE001 — per-item failure
                    failed += 1
                    self.item_status.emit(i, total, url, "failed", str(e)[:200])
            self.finished_ok.emit(success, failed)
        except Exception as e:  # noqa: BLE001 — e.g. thư mục lưu không tạo được
            self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class TimelineThumbnailWorker(QThread):
    """Grab ~N khung nhỏ từ video bằng ffmpeg, lưu vào data/timeline_thumbs/.

    Trả về danh sách (timestamp_giây, đường_dẫn_ảnh) để TimelineCanvas vẽ.
    Không dùng QMediaPlayer — tránh giành surface phát.
    """

    ready = Signal(list)    # list[tuple[float, str]]
    failed = Signal(str)

    _THUMB_W = 90
    _THUMB_H = 51           # 16:9
    _N_FRAMES = 12
    _THUMB_DIR = "timeline_thumbs"

    def __init__(self, video_path: str, duration_s: float, work_dir: str,
                 parent=None):
        super().__init__(parent)
        self._video = video_path
        self._duration = duration_s
        self._work_dir = work_dir
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Bỏ dở phần khung còn lại — teardown không phải đợi hết 12 lệnh ffmpeg."""
        self._cancel_event.set()

    def run(self) -> None:
        import subprocess

        from autodub.workdir import data_path

        try:
            if not self._video or not __import__("os").path.isfile(self._video):
                return
            dur = max(1.0, self._duration)
            n = self._N_FRAMES
            thumbs_dir = data_path(
                self._work_dir, self._THUMB_DIR, create_dir=True)

            results: list[tuple[float, str]] = []
            for i in range(n):
                if self._cancel_event.is_set():
                    return
                t = dur * (i + 0.5) / n
                dst = __import__("os").path.join(thumbs_dir,
                                                 f"frame_{i:03d}.jpg")
                cmd = [
                    "ffmpeg", "-v", "error",
                    "-ss", f"{t:.3f}", "-i", self._video,
                    "-frames:v", "1", "-q:v", "5",
                    "-vf", f"scale={self._THUMB_W}:{self._THUMB_H}:force_original_aspect_ratio=decrease,"
                           f"pad={self._THUMB_W}:{self._THUMB_H}:(ow-iw)/2:(oh-ih)/2",
                    "-y", dst,
                ]
                flags = (subprocess.CREATE_NO_WINDOW
                         if __import__("os").name == "nt" else 0)
                subprocess.run(cmd, capture_output=True, timeout=10,
                               creationflags=flags)
                if __import__("os").path.isfile(dst):
                    results.append((t, dst))
            if results and not self._cancel_event.is_set():
                self.ready.emit(results)
        except Exception as e:  # noqa: BLE001
            if not self._cancel_event.is_set():
                self.failed.emit(str(e))


class ExportAudioWorker(QThread):
    """Chuyển audio_vi_full.wav thành MP3 bằng ffmpeg rồi lưu ra đường dẫn đã chọn."""

    log = Signal(str, int)
    finished_ok = Signal(str)   # đường dẫn MP3 kết quả
    failed = Signal(str)

    def __init__(self, work_dir: str, output_path: str,
                 bitrate: str = "192k", parent=None):
        super().__init__(parent)
        self._work_dir = work_dir
        self._output_path = output_path
        self._bitrate = bitrate
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        import subprocess

        from autodub.media.audio import wav_duration_s
        from autodub.utils import ffmpeg_timeout_s
        from autodub.workdir import data_path

        handler = attach_gui_logging(self.log)
        try:
            src = data_path(self._work_dir, "audio_vi_full.wav")
            if not __import__("os").path.isfile(src):
                self.failed.emit(
                    "Chưa có tệp audio_vi_full.wav — hãy xuất video ít nhất "
                    "một lần trước khi tải âm thanh riêng.")
                return
            cmd = [
                "ffmpeg", "-y", "-i", src,
                "-b:a", self._bitrate,
                "-map_metadata", "-1",
                self._output_path,
            ]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    timeout=ffmpeg_timeout_s(wav_duration_s(src)))
            except subprocess.TimeoutExpired:
                if not self._cancel_event.is_set():
                    self.failed.emit(
                        "ffmpeg treo quá lâu khi chuyển sang MP3 — hãy thử lại.")
                return
            if self._cancel_event.is_set():
                return
            if result.returncode != 0:
                self.failed.emit(
                    f"ffmpeg trả về lỗi:\n{result.stderr[-800:]}")
                return
            self.finished_ok.emit(self._output_path)
        except Exception as e:  # noqa: BLE001
            if not self._cancel_event.is_set():
                self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class PrefetchWorker(QThread):
    """Tải trước một URL về thư mục tạm trong khi người dùng cấu hình các bước 2–4.

    Khi người dùng bấm Tiếp tục ở bước 1 (nguồn URL), worker này tải video về
    ngầm. Đến bước 5 (Phụ đề) file đã sẵn sàng nên StyleDialog lấy được frame
    để xem trước ngay, không phải đợi pipeline chạy.
    """

    finished_ok = Signal(str)   # đường dẫn file vừa tải về
    failed = Signal(str)        # lý do thất bại

    def __init__(self, url: str, output_dir: str, parent=None):
        super().__init__(parent)
        self._url = url
        self._output_dir = output_dir
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.media.downloader import download_video
        from autodub.utils import ensure_dir

        try:
            ensure_dir(self._output_dir)
            path = download_video(self._url, self._output_dir)
            if not self._cancel_event.is_set():
                self.finished_ok.emit(path)
        except Exception as e:  # noqa: BLE001
            if not self._cancel_event.is_set():
                self.failed.emit(str(e))


class ExportSubsFileWorker(QThread):
    """Xuất phụ đề ra tệp SRT hoặc ASS độc lập (không ghép vào video)."""

    log = Signal(str, int)
    finished_ok = Signal(str)   # đường dẫn tệp kết quả
    failed = Signal(str)

    def __init__(self, segments: list[dict], work_dir: str,
                 output_path: str, text_field: str,
                 subtitle_style: dict | None,
                 subs_format: str = "srt",   # "srt" | "ass"
                 merge_dir: str | None = None,
                 parent=None):
        super().__init__(parent)
        self._segments = segments
        self._work_dir = work_dir
        self._output_path = output_path
        self._text_field = text_field
        self._style = subtitle_style
        self._format = subs_format
        self._merge_dir = merge_dir
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        handler = attach_gui_logging(self.log)
        try:
            if self._format == "ass":
                from autodub.text.ass_karaoke import build_karaoke_ass
                from autodub.workdir import data_path

                merge_dir = self._merge_dir or data_path(
                    self._work_dir, "segments")
                # Cờ Dừng phải đi TỚI bước canh chữ: đây là bước lâu nhất
                # của việc ghi phụ đề, mà trước V76 `cancel()` chỉ có tác
                # dụng SAU khi nó chạy xong — bấm Dừng rồi vẫn phải ngồi chờ.
                build_karaoke_ass(
                    self._segments, merge_dir, self._output_path,
                    self._style, text_field=self._text_field,
                    cache_path=data_path(self._work_dir, "align_cache.json"),
                    cancel_event=self._cancel_event)
            else:
                from autodub.text.srt import generate_srt_styled

                generate_srt_styled(self._segments, self._output_path,
                                    self._text_field, self._style)
            if not self._cancel_event.is_set():
                self.finished_ok.emit(self._output_path)
        except Exception as e:  # noqa: BLE001
            if not self._cancel_event.is_set():
                self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class SubtitleTranslateWorker(QThread):
    """Dịch 1 file phụ đề rời (mini-spec V14, docs/PLAN.md) — KHÔNG liên quan
    tới `SubtitleWorker` ở trên (cái đó ghi phụ đề vào video của lượt dub
    hiện có; cái này dịch 1 file `.srt`/`.vtt` độc lập, không cần dự án nào).
    """

    log = Signal(str, int)
    finished_ok = Signal(object)   # SubtitleTranslateResult
    failed = Signal(str)

    def __init__(self, input_path: str, source_flores: str, target_flores: str,
                 mode: str, settings: Settings, parent=None):
        super().__init__(parent)
        self._input_path = input_path
        self._source_flores = source_flores
        self._target_flores = target_flores
        self._mode = mode   # "local" | "saas"
        self._settings = settings

    def run(self) -> None:
        from autodub.text.subtitle_translate import (
            translate_subtitle_file_local, translate_subtitle_file_saas,
        )

        handler = attach_gui_logging(self.log)
        try:
            if self._mode == "saas":
                import uuid
                result = translate_subtitle_file_saas(
                    self._input_path, self._source_flores, self._target_flores,
                    job_id=f"sub-{uuid.uuid4().hex}")
            else:
                result = translate_subtitle_file_local(
                    self._input_path, self._source_flores, self._target_flores,
                    self._settings)
            self.finished_ok.emit(result)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class TranscribeWorker(QThread):
    """Chép lời một liên kết/file — mini-spec V71.

    Chạy trong luồng riêng vì ASR mất từ vài chục giây tới vài phút; để ở
    luồng giao diện là app đứng hình và người dùng tưởng hỏng.
    """

    log = Signal(str, int)
    progress = Signal(str, str)      # bước, mô tả
    # Kèm LÝ DO hỏng như `DownloadWorker`/`BatchWorker` — báo "HỎNG" trống
    # không thì người dùng không biết là sai liên kết, mất mạng hay video có khoá.
    item_status = Signal(int, int, str, str, str)  # thứ tự, tổng, nguồn, trạng thái, lý do
    finished_ok = Signal(list)       # list[BatchItem]
    failed = Signal(str)

    def __init__(self, sources, output_dir: str, settings: Settings, *,
                 language: str = "", formats=("txt", "srt"),
                 with_timestamps: bool = False, parent=None):
        super().__init__(parent)
        # Luôn giữ dạng DANH SÁCH kể cả khi chỉ có một mục: một đường đi duy
        # nhất cho cả lẻ lẫn hàng loạt thì không có nhánh nào bị bỏ quên test.
        self._sources = [sources] if isinstance(sources, str) else list(sources)
        self._output_dir = output_dir
        self._settings = settings
        self._language = language
        self._formats = tuple(formats)
        self._with_timestamps = with_timestamps
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Dừng: mục đang chạy dừng ở câu kế tiếp, mục còn lại không chạy nữa."""
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.transcribe_tool import transcribe_many

        handler = attach_gui_logging(self.log)
        try:
            ket_qua = transcribe_many(
                self._sources, self._output_dir, self._settings,
                language=self._language, formats=self._formats,
                with_timestamps=self._with_timestamps,
                cancel_event=self._cancel_event,
                on_item=lambda i, tong, muc: self.item_status.emit(
                    i, tong, muc.source, muc.status, muc.error))
            self.finished_ok.emit(ket_qua)
        except Exception as e:  # noqa: BLE001 — lỗi tải/ASR thật, báo nguyên văn
            self.failed.emit(str(e))
        finally:
            detach_gui_logging(handler)


class AssistWorker(QThread):
    """Chạy MỘT tác vụ trợ lý ngoài luồng giao diện — mini-spec V89.

    Một lớp cho mọi tác vụ vì hình dạng giống hệt nhau: gửi tên tác vụ + dữ
    liệu, nhận về danh sách ``{value, reason}``. Nơi gọi tự quyết hiển thị.

    Chưa cấu hình máy chủ thì báo `failed` NGAY, không thử gọi — chạy thuần
    trên máy là không bao giờ gọi ra ngoài (nguyên tắc xuyên suốt dự án).
    """

    finished_ok = Signal(list)   # [{"value":…, "reason":…}]
    failed = Signal(str)

    def __init__(self, task: str, input_data: dict, parent=None):
        super().__init__(parent)
        self._task = task
        self._input = input_data or {}

    def run(self) -> None:
        try:
            from autodub.saas_client import get_client, is_configured, new_job_id

            if not is_configured():
                self.failed.emit(
                    "Tính năng này cần tài khoản VoxDub — mở Cài đặt để kết nối.")
                return
            ket = get_client().assist(self._task, self._input,
                                      job_id=new_job_id(), timeout=60.0)
        except Exception as e:  # noqa: BLE001 — nơi gọi hiện lời thân thiện
            self.failed.emit(str(e))
            return
        if not ket:
            self.failed.emit("Trợ lý chưa trả lời được. Thử lại sau ít phút.")
            return
        self.finished_ok.emit(list(ket))


#: Luồng nền đang chạy mà KHÔNG có cha — xem `giu_song`.
_DANG_CHAY: set = set()


def giu_song(worker: QThread) -> None:
    """Giữ tham chiếu tới một QThread cho tới khi nó chạy xong.

    C60 — bug thật: một luồng gọi máy chủ (hạn 30 giây) được gắn `parent=` là
    trang giao diện. Người dùng đóng trang hoặc thoát app trước khi lượt gọi
    xong thì Qt huỷ QThread lúc nó CÒN ĐANG CHẠY và gọi `abort()`:
    "QThread: Destroyed while thread is still running" — app chết ngay sau một
    thông báo lỗi, đúng lúc người dùng đang bực nhất.

    Đã sập thật trong bộ test 04-09 (cả tiến trình pytest bị abort). Cách chữa
    KHÔNG phải là `wait()` lúc đóng — đó là treo giao diện tới 30 giây. Giữ
    tham chiếu ở tầng module để luồng sống lâu hơn trang, rồi tự dọn khi xong.
    """
    _DANG_CHAY.add(worker)
    worker.finished.connect(lambda: _DANG_CHAY.discard(worker))


class ExplainErrorWorker(QThread):
    """Nhờ trợ lý dịch một dòng lỗi kỹ thuật sang việc người dùng làm được.

    Mini-spec V89. Đây là lớp BỒI THÊM cho bảng lời soạn tay: chỉ chạy khi
    bảng đó không có câu nào khớp. Hỏng thì im lặng — người dùng đã có dòng
    lỗi gốc, thêm một thông báo "không giải thích được lỗi" chỉ làm rối lúc
    họ đang bực.

    Miễn phí (0 Vox) và chạy cả khi hết Vox: người đang gặp lỗi mà còn bị
    chặn vì hết tiền là lúc tệ nhất để thu phí.
    """

    finished_ok = Signal(str, str)   # việc cần làm, chuyện đã xảy ra

    def __init__(self, message: str, step: str = "", parent=None):
        super().__init__(parent)
        self._message = message
        self._step = step

    def run(self) -> None:
        try:
            from autodub.saas_client import get_client, is_configured, new_job_id

            if not is_configured():
                return
            ket = get_client().assist(
                "explain_error",
                {"message": self._message[:2000], "step": self._step[:100]},
                job_id=new_job_id(), timeout=30.0)
        except Exception:  # noqa: BLE001 — im lặng có chủ đích, xem docstring
            return
        if ket:
            dau = ket[0]
            viec = str(dau.get("value", "")).strip()
            chuyen = str(dau.get("reason", "")).strip()
            if viec:
                self.finished_ok.emit(viec, chuyen)


class MusicSuggestWorker(QThread):
    """Gợi ý mô tả nhạc nền — mini-spec V89.

    Tách khỏi luồng giao diện vì đường qua máy chủ có thể mất vài giây; đường
    luật thì tức thì nhưng không đáng tách hai lối gọi khác nhau ở nơi dùng.
    Không có tín hiệu `failed`: hàm bên dưới LUÔN trả về được — hỏng máy chủ
    thì rơi về đo trên máy, đó chính là điểm của thiết kế hai tầng.
    """

    finished_ok = Signal(list, str)   # danh sách GoiYNhac, nguồn ("may_chu"|"luat")

    def __init__(self, segments: list, text_field: str = "",
                 video_title: str = "", parent=None):
        super().__init__(parent)
        self._segments = segments
        self._text_field = text_field
        self._video_title = video_title

    def run(self) -> None:
        from autodub.media.music_suggest import goi_y_nhac_thong_minh

        try:
            ra, nguon = goi_y_nhac_thong_minh(
                self._segments, self._text_field, self._video_title)
        except Exception:  # noqa: BLE001 — gợi ý hỏng không được giết Editor
            ra, nguon = [], "luat"
        self.finished_ok.emit(list(ra), nguon)


class MusicSfxWorker(QThread):
    """Nhạc nền/hiệu ứng âm thanh AI — mini-spec V37, docs/PLAN.md Phase G.

    3 hành động dùng chung 1 lớp (``kind``) vì cùng hình dạng: gọi 1 hàm của
    ``autodub.media.music_match`` (đã tự bọc lỗi rõ ràng), báo kết quả qua
    Qt signal — không có logic khác biệt đáng tách lớp riêng.
    """

    finished_ok = Signal(str, dict)   # đường dẫn file kết quả, {creditCharged, balanceAfter}
    failed = Signal(str)

    def __init__(self, kind: str, work_dir: str, *,
                 description: str = "", name: str = "",
                 timestamp_s: float = 0.0, sfx_wav_path: str = "",
                 parent=None):
        super().__init__(parent)
        self._kind = kind   # "music" | "sfx_preview" | "sfx_apply"
        self._work_dir = work_dir
        self._description = description
        self._name = name
        self._timestamp_s = timestamp_s
        self._sfx_wav_path = sfx_wav_path

    def run(self) -> None:
        from autodub.media import music_match

        try:
            if self._kind == "music":
                billing = music_match.generate_and_save_music(
                    self._work_dir, self._description)
                from autodub.workdir import data_path
                self.finished_ok.emit(data_path(self._work_dir, "ai_music.wav"), billing)
            elif self._kind == "sfx_preview":
                path, billing = music_match.generate_sound_effect_preview(
                    self._work_dir, self._description, self._name)
                self.finished_ok.emit(path, billing)
            elif self._kind == "sfx_apply":
                path = music_match.insert_sfx_and_replace_video(
                    self._work_dir, self._sfx_wav_path, self._timestamp_s)
                self.finished_ok.emit(path, {})
            else:  # pragma: no cover - lỗi lập trình, không phải người dùng
                self.failed.emit(f"Loại thao tác không hợp lệ: {self._kind}")
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class CloudBatchWorker(QThread):
    """Đẩy cả loạt video lên MÁY CHỦ xử lý (mini-spec V53, dùng V51/V52).

    Khác `BatchWorker` ở chỗ căn bản: không có pipeline nào chạy trên máy này
    — chỉ upload, chờ, tải kết quả. Nên không có `ProgressEvent` theo giai
    đoạn (tách nhạc/nghe chép/…) mà chỉ có dòng nhật ký từ máy chủ; giả vờ
    hiện thanh tiến trình theo giai đoạn ở đây sẽ là bịa.
    """

    log = Signal(str, int)
    finished_ok = Signal(object)      # BatchReport
    failed = Signal(str)

    def __init__(self, source_dir, output_dir, *, source_lang: str,
                 target_lang: str, voice: str = "", bg_mode: str = "none",
                 retry_done: bool = False, queue_ahead: int = 2, parent=None):
        self._cancel_event = threading.Event()
        super().__init__(parent)
        self._source = source_dir
        self._output = output_dir
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._voice = voice
        self._bg_mode = bg_mode
        self._retry_done = retry_done
        self._queue_ahead = queue_ahead

    def cancel(self) -> None:
        """Yêu cầu dừng — runner sẽ huỷ THẬT các job trên máy chủ (V55)."""
        self._cancel_event.set()

    def run(self) -> None:
        from autodub.cloud_batch import run_cloud_batch
        from autodub.cloud_dub import CloudDubError

        try:
            report = run_cloud_batch(
                self._source, self._output,
                source_lang=self._source_lang,
                target_lang=self._target_lang,
                voice=self._voice,
                bg_mode=self._bg_mode,
                retry_done=self._retry_done,
                queue_ahead=self._queue_ahead,
                cancel_event=self._cancel_event,
                on_progress=lambda msg: self.log.emit(msg, 20),
            )
        except CloudDubError as err:
            self.failed.emit(str(err))
            return
        except Exception as err:  # noqa: BLE001 — luồng nền không được chết câm
            self.failed.emit(f"Lỗi không lường trước: {err}")
            return
        self.finished_ok.emit(report)


class ProductSceneWorker(QThread):
    """Dựng ảnh sản phẩm theo bối cảnh — mini-spec C1.

    Mỗi bối cảnh là một lượt gọi máy chủ mất vài giây, nên chạy nền và bắn
    tín hiệu từng ảnh một: người dùng thấy ảnh đầu tiên trong lúc ảnh thứ tư
    còn đang dựng.

    Không có nút Dừng: mỗi ảnh đã tính tiền ngay khi máy chủ dựng xong, dừng
    giữa chừng cũng không hoàn lại được lượt đang chạy. Thay vào đó giới hạn
    số bối cảnh chọn được mỗi lượt ở phía giao diện.
    """

    tien_trinh = Signal(str)        # dòng trạng thái
    xong = Signal(object)           # product_scene.Phien
    hong = Signal(str)

    def __init__(self, anh_goc: str, boi_canh: list[str], thu_muc: str,
                 che_do: str = "SAFE", ghi_chu: str = "", noi_goi: str = "",
                 parent=None):
        super().__init__(parent)
        self._anh_goc = anh_goc
        self._boi_canh = list(boi_canh)
        self._thu_muc = thu_muc
        self._che_do = che_do
        self._ghi_chu = ghi_chu
        self._noi_goi = noi_goi

    def run(self) -> None:
        try:
            from autodub import product_scene

            self.tien_trinh.emit(
                f"Đang dựng {len(self._boi_canh)} bối cảnh…")
            phien = product_scene.dung_boi_canh(
                self._anh_goc, self._boi_canh, self._thu_muc,
                che_do=self._che_do, ghi_chu=self._ghi_chu,
                noi_goi=self._noi_goi)
        except Exception as e:  # noqa: BLE001 — lỗi phải lên tới người dùng
            logger.warning(f"Dựng bối cảnh hỏng: {e}")
            self.hong.emit(str(e))
            return
        self.xong.emit(phien)


class ImageProvidersWorker(QThread):
    """Hỏi máy chủ có những nơi gọi mô hình ảnh nào — mini-spec C17.

    Một lượt gọi mạng nhỏ nhưng vẫn là gọi mạng: đặt trên luồng giao diện là
    đúng lỗi đã mắc ở C7 (cửa sổ đứng hình ngay lúc mở trang).
    """

    xong = Signal(object)   # list[(tên, nhãn)]

    def run(self) -> None:
        from autodub import product_scene

        try:
            self.xong.emit(product_scene.danh_sach_noi_goi())
        except Exception as e:  # noqa: BLE001 — mất tiện nghi, không mất trang
            logger.warning(f"Không lấy được danh sách nơi gọi ảnh: {e}")
            self.xong.emit([])


class ProductVideoWorker(QThread):
    """Ghép ảnh sản phẩm đã duyệt thành video ngắn — mini-spec C6.

    Chạy nền vì ffmpeg mã hoá vài giây tới vài chục giây tuỳ số ảnh. Không có
    nút Dừng: mẻ ngắn, và dừng giữa chừng chỉ để lại một tệp video hỏng.
    """

    xong = Signal(str)      # đường dẫn video
    hong = Signal(str)
    canh_bao = Signal(str)  # các cảnh chưa liền mạch — KHÔNG chặn ghép

    def __init__(self, anh, duong_ra: str, giay_moi_anh: float = 2.5,
                 kieu_chuyen: str = "mo_chong", parent=None):
        super().__init__(parent)
        self._anh = list(anh)
        self._duong_ra = duong_ra
        self._giay = giay_moi_anh
        self._kieu_chuyen = kieu_chuyen

    def run(self) -> None:
        from autodub import product_video

        # Kiểm liên tục nằm TRONG luồng nền cùng với việc ghép: nó gọi mạng
        # (tới 60 giây) và thu nhỏ tới sáu ảnh bằng ffmpeg. Gọi thẳng từ chỗ
        # bấm nút là treo cả cửa sổ — kể cả dòng "Đang ghép…" cũng không kịp
        # hiện ra. Đây là lý do trang nào cũng có worker.
        try:
            lien_tuc = product_video.kiem_lien_tuc(self._anh)
            if lien_tuc.da_kiem and not lien_tuc.muot:
                self.canh_bao.emit(lien_tuc.ly_do)
        except Exception as e:  # noqa: BLE001 — cảnh báo hỏng thì bỏ qua
            logger.warning(f"Không kiểm được liên tục: {e}")

        try:
            duong = product_video.dung_video(
                self._anh, self._duong_ra, giay_moi_anh=self._giay,
                kieu_chuyen=self._kieu_chuyen)
        except Exception as e:  # noqa: BLE001 — lý do phải tới người dùng
            logger.warning(f"Ghép video sản phẩm hỏng: {e}")
            self.hong.emit(str(e))
            return
        self.xong.emit(duong)


class SceneScriptWorker(QThread):
    """Xin gợi ý câu dẫn cho từng cảnh — mini-spec C7.

    Cũng gọi mạng (tới 45 giây) nên phải nằm ngoài luồng giao diện. Hỏng thì
    trả danh sách rỗng: đây là tiện ích, mất nó không chặn ai làm gì.
    """

    xong = Signal(list)     # [(câu dẫn, gợi ý nhịp)]

    def __init__(self, anh, san_pham: str = "", xem_anh: bool = False,
                 parent=None):
        super().__init__(parent)
        self._anh = list(anh)
        self._san_pham = san_pham
        self._xem_anh = xem_anh

    def run(self) -> None:
        try:
            from autodub import product_video

            goi_y = product_video.goi_y_kich_ban(
                self._anh, san_pham=self._san_pham, xem_anh=self._xem_anh)
        except Exception as e:  # noqa: BLE001 — tiện ích hỏng thì thôi
            logger.warning(f"Không lấy được gợi ý kịch bản: {e}")
            goi_y = []
        self.xong.emit(goi_y)


class CatTepWorker(QThread):
    """Cắt một tệp dài thành nhiều đoạn — mini-spec C25.

    Chạy nền dù chép luồng rất nhanh: với tệp vài GB trên ổ chậm, "rất nhanh"
    vẫn có thể là chục giây, và đóng băng cửa sổ mười giây là đủ để người dùng
    tưởng app treo.
    """

    xong = Signal(list)     # danh sách đường dẫn các đoạn
    hong = Signal(str)

    def __init__(self, duong_dan: str, phut: int = 30, parent=None):
        super().__init__(parent)
        self._duong_dan = duong_dan
        self._phut = phut

    def run(self) -> None:
        try:
            from autodub.media.cat_tep import cat_deu

            phan = cat_deu(self._duong_dan, phut=self._phut)
        except Exception as e:  # noqa: BLE001 — lý do phải tới người dùng
            logger.warning(f"Cắt tệp hỏng: {e}")
            self.hong.emit(str(e))
            return
        self.xong.emit(phan)
