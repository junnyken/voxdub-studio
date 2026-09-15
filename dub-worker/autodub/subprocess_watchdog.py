"""Watchdog cho subprocess worker dạng streaming (stdin/stdout, dài hạn) —
mini-spec V24 (docs/PLAN.md, Phase F).

Audit thật trước khi viết module này (xem "Audit" trong docs/TEST_LOG.md
mục V24) rà mọi điểm gọi subprocess trong autodub/speech/ + autodub/media/:

- Mọi lời gọi ``subprocess.run()`` một-lượt (ffmpeg/ffprobe...) ĐÃ có
  ``timeout=`` — không cần sửa.
- 2 kiểu đọc ``proc.stdout`` cho worker dài hạn (Popen + giao thức JSON qua
  dòng): kiểu ĐÃ ĐÚNG (``autodub/media/vocal_separator.py::_read_line`` —
  luồng nền bơm dòng vào hàng đợi, đọc CÓ TIMEOUT qua
  ``queue.Queue.get(timeout=...)``; ``autodub/speech/tts/vieneu_vi.py``
  cùng kiểu) và kiểu CHƯA ĐÚNG (``for line in proc.stdout:`` chặn VÔ THỜI
  HẠN nếu worker treo — thấy ở ``autodub/text/translate_local.py::
  run_local_worker()``, ``autodub/speech/transcriber.py``,
  ``autodub/speech/paraformer_transcriber.py``,
  ``autodub/speech/tts/voice_downloader.py``).

Module này TỔNG QUÁT HOÁ kiểu đã đúng thành 1 hàm dùng chung, áp dụng đầu
tiên cho ``run_local_worker()`` (V24 — nơi đã audit từ V21 và có bug thật
liên quan), rồi áp dụng nốt cho 3 điểm còn lại ở đợt kế tiếp:
``transcriber.py`` (worker Whisper, streaming theo dòng — dùng
``read_lines_with_timeout``), ``paraformer_transcriber.py`` (streaming
theo dòng, không có bước "ready" riêng — cùng hàm), và
``voice_downloader.py`` (đọc TOÀN BỘ stdout 1 lượt bằng ``.read()`` chứ
KHÔNG streaming theo dòng — dùng ``read_all_with_timeout`` riêng cho kiểu
này). Giá trị timeout mỗi nơi CHỦ ĐÍCH bảo thủ (mục tiêu: biến "treo vô
hạn" thành "treo có trần", không phải tối ưu tốc độ phát hiện), tham chiếu
theo timeout tổng đã có sẵn ở mỗi nơi (vd Whisper vốn đã có
``proc.wait(timeout=7200)`` — cho biết khối lượng việc dự kiến lớn tới
đâu) — CHƯA benchmark thật trên phần cứng thật, xem TEST_LOG mục V24 phần
Re-audit.
"""
from __future__ import annotations

import queue
import subprocess
import threading
from typing import Iterator


class SubprocessTimeoutError(Exception):
    """Subprocess worker không phản hồi dòng nào trong thời gian cho phép —
    coi như TREO. Caller nên ``proc.kill()`` ngay khi bắt lỗi này."""


class WatchedLineReader:
    """Đọc ``proc.stdout`` qua 1 luồng nền + hàng đợi — cho phép chờ CÓ
    TIMEOUT mỗi dòng, thay vì ``for line in proc.stdout:`` chặn vô thời hạn.

    Cùng kỹ thuật đã dùng đúng ở
    :func:`autodub.media.vocal_separator._DemucsWorker._read_line`, tổng
    quát hoá để dùng lại được ở nơi khác.
    """

    def __init__(self, proc: subprocess.Popen):
        self._proc = proc
        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        try:
            for line in self._proc.stdout:
                self._queue.put(line)
        except (OSError, ValueError):
            pass  # pipe đóng đột ngột (proc bị kill từ ngoài) — không giấu lỗi
        finally:
            self._queue.put(None)  # báo hết stdout (worker đã thoát)

    def readline(self, timeout: float) -> str:
        """1 dòng kế tiếp, hoặc ``""`` nếu stdout đã đóng (worker thoát sạch).

        Raise :class:`SubprocessTimeoutError` nếu không dòng nào tới trong
        ``timeout`` giây.
        """
        try:
            line = self._queue.get(timeout=timeout)
        except queue.Empty:
            raise SubprocessTimeoutError(
                f"Subprocess không phản hồi dòng nào trong {timeout:.0f}s "
                "— coi như treo.")
        return line if line is not None else ""


def read_lines_with_timeout(proc: subprocess.Popen, timeout: float) -> Iterator[str]:
    """Generator thay thế ``for line in proc.stdout:`` — cùng thứ tự dòng,
    dừng khi stdout đóng, nhưng KHÔNG chặn vô thời hạn: raise
    :class:`SubprocessTimeoutError` nếu 1 khoảng chờ giữa 2 dòng (hoặc dòng
    đầu) vượt ``timeout`` giây.
    """
    reader = WatchedLineReader(proc)
    while True:
        line = reader.readline(timeout)
        if not line:
            return
        yield line


def read_all_with_timeout(proc: subprocess.Popen, timeout: float) -> str:
    """Thay thế ``proc.stdout.read()`` (đọc TOÀN BỘ tới EOF, 1 lượt — dùng
    khi worker chỉ ghi đúng 1 khối kết quả rồi thoát, không phải giao thức
    theo dòng) — cùng lỗi cần tránh: ``.read()`` trần chặn vô thời hạn nếu
    worker treo mà không đóng stdout. Chạy `.read()` trong 1 luồng nền, chờ
    kết quả CÓ TIMEOUT qua hàng đợi.
    """
    result: "queue.Queue[str]" = queue.Queue()

    def _read() -> None:
        try:
            result.put(proc.stdout.read())
        except (OSError, ValueError):
            result.put("")

    threading.Thread(target=_read, daemon=True).start()
    try:
        return result.get(timeout=timeout)
    except queue.Empty:
        raise SubprocessTimeoutError(
            f"Subprocess không phản hồi trong {timeout:.0f}s — coi như treo.")
