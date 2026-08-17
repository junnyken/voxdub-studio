"""Đẩy hàng loạt video lên máy chủ lồng tiếng (mini-spec V51).

Đóng đúng gap mà V42 để lại: batch trên MÁY phải tuần tự (GPU 4GB đã chạm
96% với một workload — song song thật là CUDA OOM chứ không phải "chậm hơn"),
còn ``worker-dub`` trên máy chủ là CPU-only và chạy được nhiều bản sao. Thiếu
mảnh nối giữa hai bên nên throughput thật vẫn kẹt ở 1 video/lượt.

Nguyên tắc thiết kế (đều rút từ những chỗ đã cắn trong dự án này):

* **Resume-safe** — trạng thái ghi ra đĩa sau MỖI thay đổi, giống
  ``batch.py``. Ngắt giữa chừng rồi chạy lại phải bỏ qua video đã xong,
  không nộp lại (nộp lại = trả tiền lần hai).
* **Hết quota thì DỪNG nộp**, không cắm đầu bắn tiếp để ăn 402 hàng loạt —
  nhưng vẫn theo dõi nốt job đang chạy dở, vì tiền cho những job đó đã tiêu.
* **Mất kết quả ≠ video hỏng** — máy chủ có thể mất file trước khi giao và tự
  hoàn phí (V44/V45). Ca đó phải được đánh dấu RIÊNG là "gửi lại được", nếu
  gộp vào ``failed`` thì người vận hành tưởng video lỗi và bỏ đi.
* **Không bao giờ xoá/sửa file nguồn.**
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from autodub.cloud_dub import (
    CloudDubClient,
    CloudDubError,
    QuotaExceededError,
    ResultLostError,
    estimate_minutes,
)
from autodub.utils import save_json_atomic, setup_logging

logger = setup_logging("autodub.cloud_batch")

STATE_FILENAME = "cloud_batch_state.json"

VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".ts"}

# Trạng thái mỗi mục. `refunded` tách khỏi `failed` có chủ đích — xem docstring.
STATUS_PENDING = "pending"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_REFUNDED = "refunded"


@dataclass
class ItemResult:
    path: Path
    status: str = STATUS_PENDING
    job_id: str = ""
    output: str = ""
    bytes_written: int = 0
    error: str = ""
    minutes_refunded: int = 0


@dataclass
class BatchReport:
    items: list[ItemResult] = field(default_factory=list)
    stopped_early: str = ""

    @property
    def succeeded(self) -> list[ItemResult]:
        return [i for i in self.items if i.status == STATUS_SUCCESS]

    @property
    def failed(self) -> list[ItemResult]:
        return [i for i in self.items if i.status == STATUS_FAILED]

    @property
    def refunded(self) -> list[ItemResult]:
        return [i for i in self.items if i.status == STATUS_REFUNDED]

    @property
    def skipped(self) -> list[ItemResult]:
        return [i for i in self.items if i.status == STATUS_PENDING]


def collect_videos(source: Path) -> list[Path]:
    """1 file, hoặc mọi video trong 1 thư mục (sắp xếp ổn định để resume đoán được)."""
    if source.is_file():
        return [source]
    return sorted(
        p for p in source.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES
    )


def _load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        import json
        return json.loads(state_path.read_text(encoding="utf-8")).get("items", {})
    except (OSError, ValueError):
        # Trạng thái hỏng thì coi như chưa có — thà làm lại còn hơn từ chối
        # chạy. Không nộp trùng vì bước dưới còn kiểm file kết quả trên đĩa.
        logger.warning("Không đọc được %s, bỏ qua trạng thái cũ", state_path)
        return {}


def _save_state(state_path: Path, items: dict) -> None:
    # Chú ý thứ tự tham số: (data, path) — không phải (path, data).
    save_json_atomic({"items": items}, str(state_path))


def run_cloud_batch(
    source: Path,
    output_dir: Path,
    *,
    source_lang: str,
    target_lang: str,
    voice: str = "",
    bg_mode: str = "none",
    client: CloudDubClient | None = None,
    poll_interval: float = 5.0,
    job_timeout_s: float = 3600.0,
    retry_done: bool = False,
    queue_ahead: int = 2,
    on_progress: Callable[[str], None] | None = None,
) -> BatchReport:
    """Nộp lần lượt từng video, chờ xong, tải kết quả về ``output_dir``.

    Tuần tự có chủ đích ở phía client: máy chủ chặn 5 lượt nộp/phút/key và
    hiện chỉ có 1 worker, nên bắn song song chỉ đổi thời gian chờ từ chỗ này
    sang chỗ khác mà thêm rủi ro rối trạng thái. Chỗ đáng song song là SỐ
    BẢN SAO worker trên máy chủ — quyết định hạ tầng, không phải việc của
    client này.
    """
    client = client or CloudDubClient()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / STATE_FILENAME
    state = _load_state(state_path)

    def say(msg: str) -> None:
        logger.info(msg)
        if on_progress:
            on_progress(msg)

    videos = collect_videos(source)
    report = BatchReport(items=[ItemResult(path=p) for p in videos])
    if not videos:
        say(f"Không tìm thấy video nào trong {source}")
        return report

    quota = client.quota()
    say(f"Quota còn {quota.minutes_remaining} phút "
        f"(hạn mức {quota.minutes_quota}, đang giữ chỗ {quota.minutes_reserved})")
    if quota.minutes_remaining <= 0:
        report.stopped_early = "Hết quota phút lồng tiếng trước khi bắt đầu."
        say(report.stopped_early)
        return report

    # --- Vòng chạy ĐƯỜNG ỐNG (mini-spec V52) ---------------------------
    #
    # V51 chạy thuần tuần tự: nộp → chờ xong → tải → mới nộp video kế tiếp.
    # Hệ quả là worker trên máy chủ NẰM KHÔNG suốt thời gian upload video sau
    # — với file vài trăm MB qua đường truyền nhà thì đó là phần lớn thời
    # gian. Mà mục tiêu gốc của V42 chính là thông lượng.
    #
    # V52 giữ trước một hàng đợi ngắn: trong lúc job N đang chạy trên máy
    # chủ thì job N+1 đã nộp xong và đứng chờ sẵn, nên worker không có
    # khoảng trống giữa 2 video. Vẫn KHÔNG chạy song song phía máy chủ —
    # worker vẫn xử lý từng job một; thứ được cắt bỏ là thời gian chết.
    #
    # Giữ hàng đợi NGẮN có chủ đích: mỗi job đứng chờ đã giữ chỗ quota (V43),
    # nộp trước quá nhiều là tự khoá quota của chính mình cho những video có
    # thể chẳng bao giờ tới lượt.
    pending = [it for it in report.items]
    inflight: list[ItemResult] = []
    next_index = 0
    stop_submitting = False

    def _skip_if_done(item: ItemResult) -> bool:
        key = item.path.name
        dest = output_dir / f"{item.path.stem}_dubbed.mp4"
        prev = state.get(key, {})
        if not retry_done and prev.get("status") == STATUS_SUCCESS and dest.exists():
            item.status = STATUS_SUCCESS
            item.output = str(dest)
            item.bytes_written = int(prev.get("bytes") or 0)
            say(f"Bỏ qua (đã xong): {key}")
            return True
        return False

    def _try_submit(item: ItemResult) -> str:
        """Trả về: 'submitted' | 'failed' | 'quota'."""
        key = item.path.name
        try:
            minutes = estimate_minutes(item.path)
            item.job_id = client.submit(
                item.path, source_lang=source_lang, target_lang=target_lang,
                voice=voice, bg_mode=bg_mode, estimated_minutes=minutes,
            )
            say(f"Đã nộp {key} → job {item.job_id}")
            return "submitted"
        except QuotaExceededError as err:
            # KHÔNG đánh dấu video này hỏng: nó chưa được thử thật sự, chỉ là
            # chưa còn chỗ. Để nguyên `pending` để báo cáo nói đúng "chưa chạy".
            say(f"Hết quota khi nộp {key}: {err}")
            report.stopped_early = f"Hết quota khi đang nộp: {err}"
            return "quota"
        except (CloudDubError, OSError) as err:
            item.status = STATUS_FAILED
            item.error = str(err)
            say(f"Nộp hỏng {key}: {err}")
            state[key] = {"status": item.status, "error": item.error}
            _save_state(state_path, state)
            return "failed"

    def _fill_queue() -> None:
        """Nộp thêm cho đủ `queue_ahead` job đang chờ trên máy chủ."""
        nonlocal next_index, stop_submitting
        while (not stop_submitting and len(inflight) < max(1, queue_ahead)
               and next_index < len(pending)):
            item = pending[next_index]
            next_index += 1
            if _skip_if_done(item):
                continue
            outcome = _try_submit(item)
            if outcome == "submitted":
                inflight.append(item)
            elif outcome == "quota":
                # Trả lại chỗ trong hàng đợi để lượt sau (khi quota được giải
                # phóng lúc job xong) còn thử lại được chính video này.
                next_index -= 1
                stop_submitting = True

    def _drain_one() -> None:
        """Chờ job cũ nhất xong rồi tải kết quả về."""
        nonlocal stop_submitting
        item = inflight.pop(0)
        key = item.path.name
        dest = output_dir / f"{item.path.stem}_dubbed.mp4"

        try:
            final = _wait_for_job(client, item.job_id, poll_interval, job_timeout_s, say)
        except CloudDubError as err:
            item.status = STATUS_FAILED
            item.error = str(err)
            state[key] = {"status": item.status, "jobId": item.job_id, "error": item.error}
            _save_state(state_path, state)
            return

        if final.get("status") != "done":
            item.status = STATUS_FAILED
            item.error = str(final.get("error")
                             or f"Job kết thúc ở trạng thái {final.get('status')}")
            say(f"Job hỏng {key}: {item.error}")
            state[key] = {"status": item.status, "jobId": item.job_id, "error": item.error}
            _save_state(state_path, state)
            return

        try:
            item.bytes_written = client.download(item.job_id, dest)
            item.status = STATUS_SUCCESS
            item.output = str(dest)
            say(f"Xong {key} → {dest.name} ({item.bytes_written} byte)")
            state[key] = {
                "status": STATUS_SUCCESS, "jobId": item.job_id,
                "output": str(dest), "bytes": item.bytes_written,
            }
        except ResultLostError as err:
            item.status = STATUS_REFUNDED
            item.minutes_refunded = err.minutes_refunded
            item.error = str(err)
            say(f"Máy chủ mất kết quả {key}, đã hoàn {err.minutes_refunded} phút — gửi lại được")
            state[key] = {"status": STATUS_REFUNDED, "jobId": item.job_id,
                          "minutesRefunded": err.minutes_refunded}
        except CloudDubError as err:
            item.status = STATUS_FAILED
            item.error = str(err)
            say(f"Tải kết quả hỏng {key}: {err}")
            state[key] = {"status": item.status, "jobId": item.job_id, "error": item.error}
        _save_state(state_path, state)

        # Job vừa xong đã trả lại chỗ quota nó giữ (V43) — mở lại đường nộp
        # cho video bị 402 chặn ở lượt trước, thay vì bỏ luôn.
        if stop_submitting and next_index < len(pending):
            stop_submitting = False
            report.stopped_early = ""

    _fill_queue()
    while inflight:
        _drain_one()
        _fill_queue()

    return report


def _wait_for_job(client: CloudDubClient, job_id: str, poll_interval: float,
                  timeout_s: float, say: Callable[[str], None]) -> dict:
    """Chờ job chạy xong. Lỗi mạng lẻ tẻ KHÔNG được giết vòng chờ."""
    deadline = time.time() + timeout_s
    last_status = ""
    while time.time() < deadline:
        try:
            data = client.status(job_id)
        except CloudDubError as err:
            # Job vẫn đang chạy trên máy chủ; một lượt hỏi hụt không có nghĩa
            # là hỏng. Chỉ ném ra khi hết hạn chờ.
            say(f"Hỏi trạng thái job {job_id} hụt ({err}), thử lại sau")
            time.sleep(poll_interval)
            continue

        status = str(data.get("status") or "")
        if status != last_status:
            say(f"Job {job_id}: {status}")
            last_status = status
        if status in ("done", "failed"):
            return data
        time.sleep(poll_interval)

    raise CloudDubError(
        f"Quá {int(timeout_s)}s mà job {job_id} chưa xong.", code="TIMEOUT")


def format_report(report: BatchReport) -> str:
    """Tóm tắt cho người đọc — nói thẳng cả phần chưa chạy."""
    lines = [
        f"Xong: {len(report.succeeded)}",
        f"Hỏng: {len(report.failed)}",
        f"Máy chủ mất kết quả (đã hoàn phí, gửi lại được): {len(report.refunded)}",
        f"Chưa chạy: {len(report.skipped)}",
    ]
    if report.stopped_early:
        lines.append(f"DỪNG SỚM: {report.stopped_early}")
    for item in report.failed:
        lines.append(f"  - {item.path.name}: {item.error}")
    return "\n".join(lines)
