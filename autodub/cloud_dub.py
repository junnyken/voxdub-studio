"""Máy khách gọi API lồng tiếng chạy trên máy chủ (mini-spec V51).

Vì sao tồn tại: audit V42 kết luận chạy song song nhiều video trên MỘT máy
là sai hướng — 4GB VRAM đã chạm 96% với đúng một workload (đo thật ở V32a),
song song thật chỉ đổi "chậm" lấy "CUDA OOM". Đường đúng để tăng thông lượng
là ``control_server/worker-dub`` (CPU-only, chạy được N bản sao, đã verify
atomic-safe từ V34a/V34b). V42 dừng ở kết luận đó và ghi lại: *"Chưa thiết
kế/xây cách app desktop hoặc quy trình vận hành đẩy batch job vào worker-dub
để scale thật"*. Module này chính là mảnh còn thiếu đó.

Đây là lớp identity THỨ HAI, song song `saas_client.py` chứ KHÔNG thay thế:

* ``saas_client.py`` — token thiết bị (machine fingerprint), dùng cho dịch/
  phân tích/nhạc AI. Ví Vox của thiết bị.
* module này — **API key** (``vx_live_…``, header ``Authorization: Bearer``),
  dùng cho lồng tiếng đầy đủ trên máy chủ. Quota tính bằng PHÚT video, sổ
  sách tách hẳn ví Vox (xem Constraint 2 của V34b).

Trộn hai thứ này là sai: chúng khác đơn vị tính tiền, khác vòng đời, và máy
chủ cũng tách hẳn hai middleware.

Hợp đồng dễ nhầm (đã cắn một lần, xem `control_server/src/utils/dub-langs.js`):
``source_lang`` nhận khoá ngắn HOẶC BCP-47 (``vi`` và ``vi-VN`` đều được),
còn ``target_lang`` CHỈ nhận khoá ngắn (``vi``). Hai tham số đứng cạnh nhau
nhưng khác định dạng.
"""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from autodub.saas_client import resolve_api_url
from autodub.utils import setup_logging

logger = setup_logging("autodub.cloud_dub")

ENV_API_KEY = "VOXDUB_API_KEY"

# Máy chủ chặn 5 lượt nộp/phút/key (rate limit của route). Client tự giữ
# nhịp thay vì cứ bắn rồi ăn 429 — 429 vẫn được xử lý, nhưng chủ động chậm
# lại thì log sạch hơn và không đốt hạn mức của chính mình.
SUBMIT_MIN_INTERVAL_S = 12.0


class CloudDubError(Exception):
    """Lỗi từ phía máy chủ lồng tiếng, kèm mã máy đọc được."""

    def __init__(self, message: str, code: str = "", status: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class QuotaExceededError(CloudDubError):
    """Hết quota phút lồng tiếng — nộp thêm cũng vô ích cho tới khi được cấp."""


class ResultLostError(CloudDubError):
    """Máy chủ mất kết quả trước khi kịp giao; phí ĐÃ được hoàn.

    Tách riêng vì đây KHÔNG phải lỗi của video hay của người dùng: gửi lại
    đúng file đó là xong. Gộp chung vào lỗi thường sẽ khiến người vận hành
    tưởng video hỏng và bỏ đi.
    """

    def __init__(self, message: str, minutes_refunded: int = 0) -> None:
        super().__init__(message, code="RESULT_LOST_REFUNDED", status=410)
        self.minutes_refunded = minutes_refunded


@dataclass
class Quota:
    org_name: str
    minutes_quota: int
    minutes_used: int
    minutes_reserved: int
    minutes_remaining: int


def resolve_api_key() -> str:
    """API key lồng tiếng, hoặc chuỗi rỗng nếu chưa cấu hình."""
    return os.environ.get(ENV_API_KEY, "").strip()


def is_configured() -> bool:
    """True khi có ĐỦ cả địa chỉ máy chủ lẫn API key.

    Thiếu một trong hai là chưa dùng được — báo thẳng chứ không im lặng rơi
    về chạy máy (nguyên tắc degrade trung thực của dự án: người dùng phải
    biết mình đang ở chế độ nào).
    """
    return bool(resolve_api_url() and resolve_api_key())


class CloudDubClient:
    """Gọi ``/api/v1/dub*``. An toàn khi dùng từ nhiều luồng."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 timeout: float = 60.0) -> None:
        self.base_url = (base_url or resolve_api_url()).rstrip("/")
        self.api_key = api_key if api_key is not None else resolve_api_key()
        self.timeout = timeout
        if not self.base_url:
            raise CloudDubError(
                "Chưa cấu hình địa chỉ máy chủ (VOXDUB_API_URL).", code="NO_SERVER")
        if not self.api_key:
            raise CloudDubError(
                f"Chưa cấu hình API key lồng tiếng ({ENV_API_KEY}). "
                "Xin key từ quản trị rồi đặt vào biến môi trường đó.",
                code="NO_API_KEY")
        self._last_submit_at = 0.0

    # ------------------------------------------------------------ nội bộ --

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _raise_for_payload(self, resp: requests.Response) -> dict:
        """Đọc JSON lỗi của máy chủ, giữ nguyên mã lỗi để nơi gọi phân nhánh."""
        try:
            data = resp.json()
        except ValueError:
            data = {}
        code = str(data.get("code") or "")
        message = str(data.get("message") or f"Máy chủ trả lỗi {resp.status_code}.")
        if resp.status_code == 402 or code == "DUB_QUOTA_EXCEEDED":
            raise QuotaExceededError(message, code=code or "DUB_QUOTA_EXCEEDED",
                                     status=resp.status_code)
        if code == "RESULT_LOST_REFUNDED":
            raise ResultLostError(message, int(data.get("minutesRefunded") or 0))
        raise CloudDubError(message, code=code, status=resp.status_code)

    # -------------------------------------------------------------- công --

    def quota(self) -> Quota:
        resp = requests.get(f"{self.base_url}/api/v1/me",
                            headers=self._headers, timeout=self.timeout)
        if resp.status_code != 200:
            self._raise_for_payload(resp)
        data = resp.json()
        return Quota(
            org_name=str(data.get("orgName") or ""),
            minutes_quota=int(data.get("dubMinutesQuota") or 0),
            minutes_used=int(data.get("dubMinutesUsed") or 0),
            minutes_reserved=int(data.get("dubMinutesReserved") or 0),
            minutes_remaining=int(data.get("dubMinutesRemaining") or 0),
        )

    def submit(self, video_path: Path, *, source_lang: str, target_lang: str,
               voice: str = "", bg_mode: str = "none",
               estimated_minutes: int = 0) -> str:
        """Gửi 1 video, trả về ``jobId``. Đọc file THEO DÒNG, không nạp vào RAM."""
        self._respect_submit_pace()
        params = {
            "sourceLang": source_lang,
            "targetLang": target_lang,
            "bgMode": bg_mode,
        }
        if voice:
            params["voice"] = voice
        if estimated_minutes > 0:
            params["estimatedMinutes"] = str(int(estimated_minutes))

        with open(video_path, "rb") as fh:
            resp = requests.post(
                f"{self.base_url}/api/v1/dub",
                headers=self._headers,
                params=params,
                files={"file": (video_path.name, fh, "video/mp4")},
                timeout=self.timeout,
            )
        self._last_submit_at = time.time()
        if resp.status_code != 200:
            self._raise_for_payload(resp)
        return str(resp.json()["jobId"])

    def status(self, job_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/api/v1/dub/{job_id}",
                            headers=self._headers, timeout=self.timeout)
        if resp.status_code != 200:
            self._raise_for_payload(resp)
        return resp.json()

    def download(self, job_id: str, dest: Path) -> int:
        """Tải kết quả về ``dest``, trả về số byte. Ghi qua file tạm rồi mới đổi tên.

        Máy chủ XOÁ kết quả ngay sau lượt tải đầu tiên (chính sách dữ liệu
        V9) — nên một file tải dở mà mang đúng tên thật là mất hàng: lượt sau
        nhìn thấy file "đã có" và bỏ qua, trong khi bên máy chủ không còn gì
        để tải lại. Vì vậy ghi ``.part`` rồi ``replace()`` (đổi tên là thao
        tác nguyên tử trên cùng ổ đĩa).
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with requests.get(f"{self.base_url}/api/v1/dub/{job_id}/result",
                          headers=self._headers, stream=True,
                          timeout=self.timeout) as resp:
            if resp.status_code != 200:
                self._raise_for_payload(resp)
            expected = int(resp.headers.get("content-length") or 0)
            written = 0
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)
                        written += len(chunk)

        if written == 0:
            tmp.unlink(missing_ok=True)
            raise CloudDubError("Máy chủ trả về file rỗng.", code="EMPTY_RESULT")
        if expected and written != expected:
            # Đứt giữa chừng: KHÔNG được để lại file mang tên thật, vì lượt
            # chạy sau sẽ tưởng đã tải xong (mà máy chủ thì đã xoá bản gốc).
            tmp.unlink(missing_ok=True)
            raise CloudDubError(
                f"Tải thiếu: nhận {written}/{expected} byte.", code="TRUNCATED")

        tmp.replace(dest)
        return written

    # ------------------------------------------------------------- nhịp --

    def _respect_submit_pace(self) -> None:
        """Giữ khoảng cách giữa 2 lượt nộp cho khớp rate limit của máy chủ."""
        gap = time.time() - self._last_submit_at
        if self._last_submit_at and gap < SUBMIT_MIN_INTERVAL_S:
            wait = SUBMIT_MIN_INTERVAL_S - gap
            logger.info("Chờ %.1fs cho khớp hạn mức nộp của máy chủ", wait)
            time.sleep(wait)


def estimate_minutes(video_path: Path) -> int:
    """Ước lượng thời lượng (phút, làm tròn LÊN) bằng ffprobe nếu có.

    Chỉ dùng để khai ``estimatedMinutes`` — con số này KHÔNG quyết định tiền;
    máy chủ luôn tính lại theo thời lượng thật worker đo được. Không có
    ffprobe thì trả 0 và để máy chủ dùng mặc định, không chặn việc nộp.
    """
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0
    import subprocess

    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(video_path)],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
        seconds = float(out)
    except (subprocess.SubprocessError, ValueError, OSError):
        return 0
    if seconds <= 0:
        return 0
    return max(1, int(seconds // 60) + (1 if seconds % 60 else 0))
