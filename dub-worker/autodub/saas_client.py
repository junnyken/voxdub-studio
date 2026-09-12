"""Kết nối tới máy chủ dịch tùy chọn (backend trong ``control_server/``).

Máy chủ này là TÙY CHỌN. Không cấu hình ``VOXDUB_API_URL`` thì app chạy hoàn
toàn trên máy: nghe-chép bằng Whisper, đọc bằng VieNeu, còn bước dịch chuyển
sang dịch tay (app ghi sẵn lời nhắc ra ``TRANSLATE_PENDING.txt``).

Ai muốn dịch tự động thì tự dựng backend (xem ``control_server/README.md``)
rồi trỏ ``VOXDUB_API_URL`` về đó. Khi đã có máy chủ:

- App đăng ký thiết bị một lần để lấy token (``ensure_session``). Token cất
  trong kho khóa của hệ điều hành, hết hạn thì tự đăng ký lại.
- Mỗi lô mang ``job_id`` ổn định. Rớt mạng giữa chừng, app không biết request
  đã tới nơi hay chưa — gửi lại đúng ``job_id`` đó thì máy chủ trả kết quả cũ
  và KHÔNG trừ credit lần hai.

Nguyên tắc fail-closed: đã cấu hình máy chủ mà gọi không được thì dừng bước
dịch với lời báo rõ ràng, không âm thầm bỏ qua.
"""
from __future__ import annotations

import os
import threading
import uuid

from autodub.device_id import get_device_name, get_fingerprint
from autodub.utils import setup_logging

logger = setup_logging("autodub.saas")

ENV_KEY = "VOXDUB_API_URL"
#: Tên mục trong kho khóa hệ điều hành, nơi cất token thiết bị.
TOKEN_KEY = "VOXDUB_DEVICE_TOKEN"

_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 300.0     # một lô dịch lớn có thể mất vài phút


class SaasError(Exception):
    """Máy chủ không trả về kết quả dùng được."""

    def __init__(self, message: str, code: str = "", status: int = 0,
                 retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        #: Giây máy chủ yêu cầu chờ trước khi thử lại (header ``Retry-After``),
        #: 0 nếu máy chủ không nói gì. Bước dịch dùng để giãn nhịp retry.
        self.retry_after = retry_after


class OfflineError(SaasError):
    """Không kết nối được máy chủ (mất mạng, máy chủ sập, sai địa chỉ)."""


class InsufficientCreditError(SaasError):
    """Hết Vox — người dùng cần nạp thêm trước khi chạy tiếp."""

    def __init__(self, message: str, balance: int = 0, required: int = 0) -> None:
        super().__init__(message, code="INSUFFICIENT_CREDIT", status=402)
        self.balance = balance
        self.required = required


class DeviceBlockedError(SaasError):
    """Thiết bị bị khóa từ phía quản trị."""


class MaintenanceError(SaasError):
    """Hệ thống đang bảo trì."""


def resolve_api_url() -> str:
    """Địa chỉ máy chủ dịch, hoặc chuỗi rỗng khi chạy thuần trên máy.

    Thứ tự: giá trị nhúng lúc build exe → biến môi trường ``VOXDUB_API_URL``
    (chỉ khi chạy từ mã nguồn). Rỗng = không có máy chủ, bước dịch tự chuyển
    sang dịch tay.

    Bug thật tìm+sửa (mini-spec V34a, xem docs/TEST_LOG.md): import
    ``autodub_gui._embedded`` từng KHÔNG có try/except — mâu thuẫn trực
    tiếp với cam kết của ``autodub/cli.py`` (docstring + test cách ly
    ``test_importing_cli_does_not_pull_in_gui_or_qt``) rằng CLI headless
    không phụ thuộc ``autodub_gui``. Mọi máy dev/CI trước giờ đều có sẵn
    ``autodub_gui/`` cạnh ``autodub/`` nên lỗi này chưa từng lộ ra — chỉ vỡ
    thật khi chạy trong môi trường server KHÔNG cài GUI (tái hiện thật lúc
    dựng container ``control_server/worker-dub/``). Giá trị nhúng chỉ có ý
    nghĩa cho bản .exe đóng gói (PyInstaller) — thiếu package đó ở môi
    trường khác là bình thường, không phải lỗi cấu hình.
    """
    import sys

    # Chạy thử tự động lúc dựng bản (AUTODUB_SMOKE=1) KHÔNG được chạm máy
    # chủ thật. Bỏ qua điều này thì mỗi lần CI dựng bản là một thiết bị mới
    # đăng ký và một suất Vox dùng thử bị tiêu — đã xảy ra thật ngày
    # 22/8/2026, ngay lượt build đầu sau khi nhúng được địa chỉ máy chủ:
    # máy chủ mọc ra một máy tên `runnervm…` mang 500 Vox.
    #
    # Chốt đặt ở ĐÂY chứ không ở từng trang: đây là cửa duy nhất mọi lượt
    # gọi phải đi qua, nên không có đường vòng nào sót lại.
    if os.environ.get("AUTODUB_SMOKE") == "1":
        return ""

    try:
        from autodub_gui._embedded import VOXDUB_API_URL as embedded
    except ImportError:
        embedded = ""

    url = (embedded or "").strip()
    if not getattr(sys, "frozen", False):
        url = os.environ.get(ENV_KEY, "").strip() or url
    return url.rstrip("/")


def is_configured() -> bool:
    """True khi có máy chủ dịch để gọi."""
    return bool(resolve_api_url())


def new_job_id() -> str:
    """Khóa idempotency cho một lượt gọi."""
    return str(uuid.uuid4())


def _la_thanh_cong(ma: int) -> bool:
    """Mọi mã 2xx đều là THÀNH CÔNG, không riêng 200.

    Lỗi thật chủ dự án gặp ngày 10/09/2026: lưu hồ sơ brand đầu tiên báo
    "Lỗi máy chủ (HTTP 201)". `201 Created` là mã ĐÚNG CHUẨN cho việc tạo mới
    và máy chủ dùng nó ở ba cửa — hồ sơ brand (H1), Flow Blueprint (H2),
    BrandScript (H3) — nhưng máy khách chỉ chấp nhận đúng `200`.

    Hậu quả không dừng ở một câu báo sai: hồ sơ ĐÃ được tạo trên máy chủ mà
    người dùng thấy lỗi, nên bấm lưu lại là sinh bản trùng. Với H2/H3 thì nặng
    hơn — hai cửa đó **đã trừ Vox** rồi mới trả 201, tức là trừ tiền xong báo
    hỏng, đúng lớp lỗi đã phải bịt hai lần ở H3.

    Vì sao test không bắt được: test máy chủ kiểm `201`, test máy khách dựng
    response giả `200`. Hai bên đều xanh, còn ĐƯỜNG NỐI giữa chúng thì chưa
    ai đi qua. `tests/test_ma_thanh_cong_khop_may_chu.py` quét mã route để
    chốt lại chỗ nối đó.
    """
    return 200 <= ma < 300


def _doc_than(resp) -> dict:
    """Đọc thân JSON của một lượt gọi thành công.

    `204 No Content` (và mọi thân rỗng) là thành công HỢP LỆ, không phải dữ
    liệu hỏng — trả dict rỗng thay vì ném lỗi.
    """
    if resp.status_code == 204 or not (resp.content or b"").strip():
        return {}
    try:
        return resp.json()
    except ValueError as e:
        raise SaasError("Máy chủ trả về dữ liệu không đọc được.") from e


class SaasClient:
    """Máy khách HTTP tới máy chủ VoxDub. An toàn khi dùng từ nhiều luồng.

    Token được chia sẻ giữa các luồng nên mọi thao tác đọc/ghi token đều nằm
    trong khóa: hai luồng cùng gặp 401 chỉ được đăng ký lại MỘT lần, không
    phải hai (đăng ký lại hai lần sẽ cấp hai token và luồng kia dùng token đã
    bị thay).
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or resolve_api_url()).rstrip("/")
        self._token: str | None = None
        self._lock = threading.RLock()
        self._local = threading.local()
        self._device: dict = {}
        self._config: dict = {}

    # ------------------------------------------------------------ phiên --

    def _http(self):
        """Phiên requests RIÊNG cho từng luồng (giữ kết nối, đỡ bắt tay TLS).

        Bước dịch chạy tới 4 luồng trên cùng một client. ``requests.Session``
        không hứa an toàn nhiều luồng (pool kết nối và hộp cookie đều là state
        chung), mà bọc khóa quanh mỗi request thì 4 lô dịch thành tuần tự —
        mất đúng phần song song. Một session mỗi luồng chỉ tốn thêm một lần
        bắt tay TLS cho mỗi luồng trong cả lượt chạy.
        """
        session = getattr(self._local, "session", None)
        if session is None:
            import requests

            session = requests.Session()
            session.headers["User-Agent"] = f"VoxDub/{_app_version()} (Windows)"
            self._local.session = session
        return session

    def _load_token(self) -> str:
        """Token đã cất trong kho khóa hệ điều hành, hoặc chuỗi rỗng."""
        if self._token is not None:
            return self._token
        from autodub import keystore

        self._token = keystore.get_secret(TOKEN_KEY) or ""
        return self._token

    def _store_token(self, token: str) -> None:
        from autodub import keystore

        self._token = token
        # Kho khóa không dùng được (máy thiếu gói keyring) thì token chỉ sống
        # trong phiên này — mỗi lần mở app đăng ký lại, vẫn chạy đúng.
        keystore.set_secret(TOKEN_KEY, token)

    def forget_token(self) -> None:
        """Quên token hiện tại (dùng khi máy chủ báo token đã bị thu hồi)."""
        from autodub import keystore

        with self._lock:
            self._token = ""
            keystore.delete_secret(TOKEN_KEY)

    # ------------------------------------------------------- gọi HTTP ----

    def _request(self, method: str, path: str, *, json_body: dict | None = None,
                 auth: bool = True, timeout: float = _READ_TIMEOUT,
                 _retry_auth: bool = True) -> dict:
        """Một lượt gọi API. Ném :class:`SaasError` cho mọi lỗi.

        Gặp 401 thì đăng ký lại thiết bị đúng một lần rồi thử lại — token hết
        hạn là chuyện bình thường sau vài tuần, người dùng không cần biết.
        """
        if not self.base_url:
            raise OfflineError("Chưa cấu hình địa chỉ máy chủ VoxDub.")

        import requests

        headers = {}
        if auth:
            token = self._load_token() or self._register_device()
            headers["Authorization"] = f"Bearer {token}"

        url = f"{self.base_url}{path}"
        try:
            resp = self._http().request(
                method, url, json=json_body, headers=headers,
                timeout=(_CONNECT_TIMEOUT, timeout))
        except requests.exceptions.RequestException as e:
            raise OfflineError(
                "Không kết nối được máy chủ VoxDub. Kiểm tra mạng rồi thử lại."
            ) from e

        if _la_thanh_cong(resp.status_code):
            return _doc_than(resp)

        try:
            data = resp.json()
        except ValueError:
            data = {}
        code = str(data.get("code") or "")
        message = str(data.get("message") or f"Lỗi máy chủ (HTTP {resp.status_code})")

        if resp.status_code == 401 and auth and _retry_auth:
            # Token hết hạn hoặc bị thu hồi — đăng ký lại rồi thử lại đúng một lần.
            self.forget_token()
            return self._request(method, path, json_body=json_body, auth=auth,
                                 timeout=timeout, _retry_auth=False)
        if resp.status_code == 402:
            raise InsufficientCreditError(
                message, balance=int(data.get("balance") or 0),
                required=int(data.get("required") or 0))
        if code == "DEVICE_BLOCKED":
            raise DeviceBlockedError(message, code=code, status=resp.status_code)
        if code == "MAINTENANCE":
            raise MaintenanceError(message, code=code, status=resp.status_code)
        if resp.status_code == 429:
            # GIỮ nguyên mã và câu của máy chủ khi nó có nói.
            #
            # Bản trước vứt cả `code` lẫn `message` rồi thay bằng "Máy chủ
            # đang bận… Chờ một chút rồi thử lại" cho MỌI lượt 429. Nhưng 429
            # có hai nghĩa hoàn toàn khác nhau:
            #
            #   RATE_LIMITED — bấm dồn dập; chờ vài giây là xong
            #   DAILY_LIMIT  — hết hạn mức NGÀY; máy chủ nói rõ "Thử lại vào
            #                  ngày mai"
            #
            # Trộn hai ca lại nghĩa là người hết hạn mức ngày đọc được "chờ
            # một chút" rồi bấm lại cả buổi. Cùng lớp với lỗi 201: hợp đồng
            # máy chủ bị máy khách viết đè.
            # Hỏi thẳng `data`, KHÔNG dùng `message`: biến đó đã có sẵn câu dự
            # phòng "Lỗi máy chủ (HTTP 429)" nên không bao giờ rỗng, và dùng
            # nó là đổi một câu khó hiểu lấy một câu sai — tệ cả hai đường.
            cau_may_chu = str(data.get("message") or "").strip()
            raise SaasError(
                cau_may_chu or "Máy chủ đang bận (quá nhiều yêu cầu). Chờ "
                               "một chút rồi thử lại.",
                code=code or "RATE_LIMITED", status=429,
                retry_after=_retry_after_s(resp))
        raise SaasError(message, code=code, status=resp.status_code,
                        retry_after=_retry_after_s(resp))

    # ---------------------------------------------------------- thiết bị --

    def _register_device(self) -> str:
        """Đăng ký máy này và cất token. Trả về token."""
        with self._lock:
            # Một luồng khác có thể vừa đăng ký xong trong lúc ta chờ khóa.
            if self._token:
                return self._token
            data = self._request(
                "POST", "/v1/device/register", auth=False, timeout=30.0,
                json_body={
                    "fingerprint": get_fingerprint(),
                    "name": get_device_name(),
                    "appVersion": _app_version(),
                })
            self._store_token(str(data["token"]))
            self._device = data.get("device") or {}
            return self._token

    def ensure_session(self) -> dict:
        """Bảo đảm có token dùng được; trả về thông tin thiết bị + số dư.

        Gọi lúc khởi động app. Ném :class:`OfflineError` khi không kết nối
        được — người gọi quyết định hiện cảnh báo hay chặn hẳn.
        """
        if not self._load_token():
            self._register_device()
        data = self._request("GET", "/v1/device/me", timeout=30.0)
        self._device = data.get("device") or {}
        self._device["creditEnabled"] = bool(data.get("creditEnabled", True))
        return self._device

    @property
    def device(self) -> dict:
        """Thông tin thiết bị đã đọc gần nhất (có thể rỗng nếu chưa gọi)."""
        return dict(self._device)

    def balance(self) -> int:
        data = self._request("GET", "/v1/device/balance", timeout=30.0)
        balance = int(data.get("balance") or 0)
        self._device["balance"] = balance
        return balance

    def activate_key(self, code: str) -> dict:
        """Kích hoạt một mã. Trả về ``{vox, balanceAfter, alreadyActivated}``."""
        data = self._request("POST", "/v1/device/activate", timeout=30.0,
                             json_body={"code": str(code).strip()})
        self._device["balance"] = int(data.get("balanceAfter") or 0)
        return data

    def credit_history(self, page: int = 1, limit: int = 20) -> dict:
        return self._request(
            "GET", f"/v1/device/history?page={page}&limit={limit}", timeout=30.0)

    def estimate(self, sentences: int, *, auto_translate: bool = False,
                 metadata: bool = False) -> dict:
        """Giá của một video ``sentences`` segment, hỏi trước khi chạy.

        Cùng công thức với lúc tạo hold nên con số hiện cho người dùng ở bước
        xem trước khớp đúng số bị trừ. Trả về ``{"estimated", "balance",
        "enough"}`` — máy chủ không trả bảng chi tiết theo bước xử lý.
        """
        return self._request("POST", "/v1/device/estimate", timeout=30.0, json_body={
            "sentences": int(sentences),
            "autoTranslate": bool(auto_translate),
            "metadata": bool(metadata),
        })

    # ------------------------------------------------------ cấu hình app --

    def app_config(self, force: bool = False) -> dict:
        """Cấu hình máy chủ (bảo trì, phiên bản tối thiểu, bảng giá).

        Gọi lúc khởi động. Không kết nối được thì trả về dict rỗng — app vẫn
        mở lên được, chỉ dừng ở bước dịch (fail-closed đúng chỗ cần).
        """
        if self._config and not force:
            return self._config
        try:
            config = self._request("GET", "/v1/config/app", auth=False,
                                   timeout=15.0)
        except SaasError:
            config = {}
        with self._lock:
            self._config = config
        return config

    # ------------------------------------------ cloud rendering (V12) ----
    #
    # Mini-spec V9 → V12 (docs/PLAN.md) — POC hẹp: CHỈ stage Demucs. Job xử
    # lý BẤT ĐỒNG BỘ (V12): nộp -> nhận jobId ngay -> tự poll -> tải kết
    # quả. Không dùng ``_request`` (chỉ JSON) — nộp job là multipart, tải
    # kết quả là stream nhị phân.

    def submit_demucs_job(self, audio_path: str) -> dict:
        """Nộp 1 file audio để tách nhạc trên cloud. Trả về ngay
        ``{"jobId", "status": "queued", "async": true, "balanceAfter"}`` —
        KHÔNG đợi xử lý xong (V12, khác V9 cũ). Thiếu Vox ->
        :class:`InsufficientCreditError`.
        """
        import requests

        if not self.base_url:
            raise OfflineError("Chưa cấu hình địa chỉ máy chủ VoxDub.")
        token = self._load_token() or self._register_device()
        url = f"{self.base_url}/v1/jobs/demucs"
        try:
            with open(audio_path, "rb") as f:
                resp = self._http().post(
                    url, files={"file": (os.path.basename(audio_path), f, "audio/wav")},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=(_CONNECT_TIMEOUT, 60.0))
        except requests.exceptions.RequestException as e:
            raise OfflineError(
                "Không kết nối được máy chủ VoxDub. Kiểm tra mạng rồi thử lại."
            ) from e
        return self._parse_response(resp)

    def job_status(self, job_id: str) -> dict:
        """Trạng thái job — gọi lặp lại (poll) tới khi ``status`` là
        ``"done"``/``"failed"``. Trả về ``{"jobId", "stage", "status",
        "error", "creditCharged", "expiresAt"}``."""
        return self._request("GET", f"/v1/jobs/{job_id}", timeout=30.0)

    def download_job_result(self, job_id: str, stem: str, dest_path: str) -> None:
        """Tải 1 stem kết quả (``"vocals"``/``"no_vocals"``) về ``dest_path``.

        Máy chủ XOÁ file NGAY sau khi cả 2 stem đã tải (chính sách dữ liệu
        đã chủ dự án duyệt, xem docs/TEST_LOG.md mục V9) — gọi lại lần 2
        cho stem đã tải trước đó sẽ nhận SaasError (file không còn).
        """
        import requests

        if not self.base_url:
            raise OfflineError("Chưa cấu hình địa chỉ máy chủ VoxDub.")
        token = self._load_token() or self._register_device()
        url = f"{self.base_url}/v1/jobs/{job_id}/result/{stem}"
        try:
            resp = self._http().get(
                url, headers={"Authorization": f"Bearer {token}"},
                timeout=(_CONNECT_TIMEOUT, 120.0), stream=True)
        except requests.exceptions.RequestException as e:
            raise OfflineError(
                "Không kết nối được máy chủ VoxDub. Kiểm tra mạng rồi thử lại."
            ) from e
        if not _la_thanh_cong(resp.status_code):
            # Dùng `_raise_saas_error` chứ KHÔNG phải `_parse_response`:
            # `_parse_response` nay trả về dict cho mọi mã 2xx thay vì luôn
            # ném, nên nhánh này sẽ rơi xuống `return` và **lặng lẽ không tải
            # gì** — đúng lớp hỏng không kêu tiếng nào. `_raise_saas_error`
            # thì không có đường nào trả về.
            self._raise_saas_error(resp)
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)

    def _parse_response(self, resp) -> dict:
        """Diễn giải 1 response HTTP thô thành dict hoặc ném SaasError —
        cùng luật mã lỗi với ``_request`` (402/DEVICE_BLOCKED/MAINTENANCE/
        429), tách riêng vì multipart/stream không đi qua ``_request``."""
        if _la_thanh_cong(resp.status_code):
            return _doc_than(resp)
        self._raise_saas_error(resp)

    def _raise_saas_error(self, resp) -> None:
        """Ném đúng loại SaasError theo mã lỗi HTTP — dùng chung cho response
        JSON (``_parse_response``) VÀ response nhị phân (mini-spec V37:
        ``generate_sound_effect()``/``generate_music()`` — 200 là audio,
        không phải JSON, nên không đi qua ``_parse_response`` được)."""
        try:
            data = resp.json()
        except ValueError:
            data = {}
        code = str(data.get("code") or "")
        message = str(data.get("message") or f"Lỗi máy chủ (HTTP {resp.status_code})")
        if resp.status_code == 402:
            raise InsufficientCreditError(
                message, balance=int(data.get("balance") or 0),
                required=int(data.get("required") or 0))
        if code == "DEVICE_BLOCKED":
            raise DeviceBlockedError(message, code=code, status=resp.status_code)
        if code == "MAINTENANCE":
            raise MaintenanceError(message, code=code, status=resp.status_code)
        raise SaasError(message, code=code, status=resp.status_code,
                        retry_after=_retry_after_s(resp))

    def _note_usage(self, data: dict) -> None:
        """Ghi số Vox vừa tiêu vào sổ chung của lượt dịch, và cập nhật số dư.

        Gọi sau MỌI lượt gọi AI thành công — báo cáo chất lượng cuối video
        lấy con số từ đây, và thanh Vox trên đầu app đọc ``device["balance"]``.
        Bước dịch gọi hàm này từ nhiều luồng nên phần ghi ``_device`` nằm trong
        khóa; ``USAGE.add`` đã tự khóa.
        """
        from autodub.text.translate_common import USAGE

        balance = int(data.get("balanceAfter") or 0)
        with self._lock:
            self._device["balance"] = balance
        USAGE.add(int(data.get("creditCharged") or 0), balance)

    # ------------------------------------------------------ hold (giữ chỗ) --

    def create_hold(self, hold_id: str, sentences: int,
                    video_duration_s: float = 0.0,
                    auto_translate: bool = True,
                    metadata: bool = True) -> dict:
        """Giữ chỗ Vox cho một lượt lồng tiếng — TRỪ ĐỦ GIÁ ngay tại đây.

        ``hold_id`` = run_id (hash nội dung transcript) nên gọi lại cùng
        video là idempotent — nhận về đúng hold cũ kèm khóa giải mã.

        Giá chốt từ số segment: ``auto_translate`` cộng thêm mỗi segment,
        ``metadata`` (tiêu đề + mô tả) là phụ phí trọn gói một lần. Sau bước
        này giá không đổi nữa, dùng nhiều hay ít lượt AI cũng vậy.
        Trả về ``{"hold": {..., "encKeyHex"}, "balance", "created"}``.
        Thiếu Vox → :class:`InsufficientCreditError`.
        """
        data = self._request("POST", "/v1/holds", timeout=30.0, json_body={
            "holdId": str(hold_id),
            "sentences": int(sentences),
            "videoDurationS": float(video_duration_s),
            "autoTranslate": bool(auto_translate),
            "metadata": bool(metadata),
        })
        self._device["balance"] = int(data.get("balance") or 0)
        return data

    def get_hold(self, hold_id: str) -> dict:
        """Trạng thái hold + khóa giải mã (khi còn active hoặc đã committed).

        Trả về ``{"hold": {...}, "balance"}``. Không tìm thấy → SaasError 404.
        """
        data = self._request("GET", f"/v1/holds/{hold_id}", timeout=30.0)
        self._device["balance"] = int(data.get("balance") or 0)
        return data

    def commit_hold(self, hold_id: str) -> dict:
        """Chốt hold lúc xuất video — mở khóa, KHÔNG động vào tiền.

        Giá đã trừ đủ lúc tạo hold nên bước này không hoàn cũng không truy
        thu. Idempotent — gọi lại trả kết quả cũ kèm ``encKeyHex``. Trả về
        ``{"committed", "usedVox", "chargedVox", "balance", "encKeyHex"}``.
        """
        data = self._request("POST", f"/v1/holds/{hold_id}/commit", timeout=60.0)
        balance = int(data.get("balance") or 0)
        self._device["balance"] = balance
        from autodub.text.translate_common import USAGE

        # Đồng bộ số dư lên thanh Vox (không cộng thêm usage — đã tích lũy
        # từng lượt trong lúc chạy rồi).
        USAGE.add(0, balance)
        return data

    # -------------------------------------------------------------- AI ---

    def translate(self, segments: list[dict], *, job_id: str, source_lang: str,
                  target_lang: str = "vi",
                  context: dict | None = None, cps_budget: float = 12.5,
                  prev_context: list[dict] | None = None,
                  hold_id: str | None = None,
                  emotion_tone: bool = False) -> dict:
        """Dịch một lô câu.

        ``segments``: ``[{"id", "text", "duration", "max_chars"}]``.
        ``target_lang``: khoá ngắn ngôn ngữ đích (``autodub.languages.TargetLang.key``,
        vd "vi"/"en") — mini-spec V15 (docs/PLAN.md): TRƯỚC ĐÂY thiếu tham số
        này, máy chủ luôn dịch sang tiếng Việt bất kể đang lồng tiếng ngôn
        ngữ nào (bug thật, xem docs/TEST_LOG.md).
        ``emotion_tone`` (mini-spec V28, Phase G): bật thì mỗi câu trả về
        thêm ``"tone"`` (đọc để chọn style VieNeu per-segment) — mặc định
        TẮT, giữ nguyên contract cũ cho mọi lượt gọi khác.
        Trả về ``{"segments": [{"id", "text_<target_lang>"[, "tone"]}], "creditCharged", "balanceAfter"}``.
        """
        payload = {
            "jobId": job_id,
            "sourceLang": source_lang,
            "targetLang": target_lang,
            "cpsBudget": float(cps_budget),
            "segments": segments,
        }
        if context:
            payload["context"] = context
        if prev_context:
            payload["prevContext"] = prev_context
        if hold_id:
            payload["holdId"] = hold_id
        if emotion_tone:
            payload["emotionTone"] = True
        data = self._request("POST", "/v1/ai/translate", json_body=payload)
        self._note_usage(data)
        return data

    def analyze(self, lines: list[str], *, job_id: str, source_lang: str,
                target_lang: str = "vi",
                video_title: str = "", hold_id: str | None = None) -> dict | None:
        """Phân tích ngữ cảnh video (lượt 0). Trả về dict hoặc None."""
        payload = {
            "jobId": job_id,
            "sourceLang": source_lang,
            "targetLang": target_lang,
            "videoTitle": video_title[:300],
            "lines": lines,
        }
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request("POST", "/v1/ai/analyze", timeout=120.0,
                             json_body=payload)
        self._note_usage(data)
        return data.get("analysis")

    def review(self, items: list[dict], *, job_id: str, source_lang: str,
               target_lang: str = "vi",
               context: dict | None = None, cps_budget: float = 12.5,
               hold_id: str | None = None) -> list[dict]:
        """Rà soát các câu nghi vấn. Trả về danh sách câu ĐÃ SỬA (có thể rỗng)."""
        payload = {
            "jobId": job_id,
            "sourceLang": source_lang,
            "targetLang": target_lang,
            "cpsBudget": float(cps_budget),
            "items": items,
        }
        if context:
            payload["context"] = context
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request("POST", "/v1/ai/review", json_body=payload)
        self._note_usage(data)
        return data.get("segments") or []

    def translate_subtitle(self, items: list[dict], *, job_id: str,
                           source_flores: str, target_flores: str,
                           source_name: str | None = None,
                           target_name: str | None = None,
                           hold_id: str | None = None) -> dict:
        """Dịch phụ đề rời (mini-spec V14, docs/PLAN.md) — TÁCH KHỎI
        :meth:`translate` (dùng cho pipeline dub, gắn ``duration``/
        ``max_chars``/``cpsBudget`` không áp dụng cho phụ đề thuần).

        ``items``: ``[{"id", "text"}]``. ``source_flores``/``target_flores``
        là mã FLORES-200 (vd ``"vie_Latn"``) — KHÔNG phải BCP-47/khoá ngắn
        như :meth:`translate`, xem Constraint 1 của V14.
        Trả về ``{"segments": [{"id", "text"}], "creditCharged", "balanceAfter"}``.
        """
        payload = {
            "jobId": job_id,
            "sourceFlores": source_flores,
            "targetFlores": target_flores,
            "items": items,
        }
        if source_name:
            payload["sourceName"] = source_name
        if target_name:
            payload["targetName"] = target_name
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request("POST", "/v1/ai/translate-subtitle", json_body=payload)
        self._note_usage(data)
        return data

    def scene_stage(self, timeout: float = 20.0) -> dict:
        """Nấc tính năng ảnh cho ĐÚNG MÁY NÀY — mini-spec C18.

        Khác `app_config()`: cửa đó không đăng nhập nên máy chủ không biết
        đang trả lời cho máy nào, mà nấc hiệu chỉnh mở theo từng máy.
        """
        return self._request("GET", "/v1/ai/scene-stage", timeout=timeout)

    def image_providers(self, timeout: float = 20.0) -> list[dict]:
        """Các nơi gọi mô hình ảnh người dùng được chọn — mini-spec C17.

        Hỏng thì trả danh sách rỗng: không chọn được nơi gọi chỉ mất một tiện
        nghi, còn chặn cả trang vì không hỏi được danh sách là mất cả tính
        năng. Đường "Tự động" luôn còn đó.
        """
        try:
            data = self._request("GET", "/v1/ai/image-providers", timeout=timeout)
        except SaasError as e:
            logger.warning(f"Không lấy được danh sách nơi gọi ảnh ({e})")
            return []
        muc = data.get("items")
        return muc if isinstance(muc, list) else []

    def product_scene(self, image: dict, scene: str, *, job_id: str,
                      mode: str = "SAFE", note: str = "",
                      hold_id: str | None = None, provider: str = "",
                      timeout: float = 120.0) -> dict:
        """Dựng lại ảnh sản phẩm trong một bối cảnh khác — mini-spec C1.

        ``image`` là ``{"mimeType": ..., "data": <base64>}``. Trả về dict có
        ``image`` (cùng dạng) kèm ``mode`` và số Vox đã trừ.

        ``mode="SAFE"`` giữ nguyên bao bì, chỉ đổi bối cảnh — đây là mặc định
        và là thứ dùng được cho video bán hàng. ``"CONCEPT"`` cho phép mô hình
        vẽ lại bao bì; ảnh đó CHỈ để tham khảo ý tưởng.
        """
        payload = {"jobId": job_id, "scene": scene, "mode": mode,
                   "image": image}
        if provider:
            payload["provider"] = provider
        if note:
            payload["note"] = note[:300]
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request("POST", "/v1/ai/product-scene", timeout=timeout,
                             json_body=payload)
        self._note_usage(data)
        return data

    def story_image(self, brief: str, *, job_id: str,
                    hold_id: str | None = None, provider: str = "",
                    timeout: float = 120.0) -> dict:
        """Vẽ ảnh minh hoạ cho một đoạn kịch bản — mini-spec H4d.

        Khác ``product_scene`` ở chỗ KHÔNG có ảnh gốc: mô hình vẽ từ chữ.
        Cũng vì thế không có ``mode`` — SAFE/CONCEPT là câu hỏi "có được đổi
        bao bì sản phẩm thật không", mà ở đây không có sản phẩm thật nào.

        Ảnh trả về **chưa qua kiểm** (``daKiem`` luôn là False). Nơi dùng phải
        cho nó qua ``kiem_anh_minh_hoa`` rồi đóng nhãn AI-generated — xem
        ``autodub/story_image.py``.
        """
        payload = {"jobId": job_id, "brief": brief[:400]}
        if provider:
            payload["provider"] = provider
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request("POST", "/v1/ai/story-image", timeout=timeout,
                             json_body=payload)
        self._note_usage(data)
        return data

    def assist_day_du(self, task: str, input_data: dict, **kw) -> dict:
        """Như ``assist()`` nhưng trả NGUYÊN gói, kể cả ``creditCharged``.

        Vì sao cần (mini-spec H4d-0): ``assist()`` vứt ``creditCharged`` vào
        sổ dùng chung rồi chỉ trả ``results``. Với đường vẽ ảnh minh hoạ, mỗi
        tấm là HAI lượt tính tiền — vẽ (30 Vox) và kiểm (3 Vox) — nên nơi gọi
        không có cách nào nói cho người dùng biết họ vừa mất bao nhiêu khi
        lượt kiểm hỏng giữa chừng. Đoán bằng hằng số ở máy khách là đúng lớp
        lỗi "giá hiện ra khác giá bị trừ" vừa phải sửa.
        """
        return self._assist_goi(task, input_data, **kw)

    def assist(self, task: str, input_data: dict, *, job_id: str,
               images: list[dict] | None = None,
               hold_id: str | None = None, timeout: float = 45.0) -> list[dict]:
        """Chạy một tác vụ trợ lý — mini-spec V89.

        Trả về danh sách ``[{"value": ..., "reason": ...}]``. Mỗi kết quả LUÔN
        kèm lý do: giao diện hiện lý do đó cho người dùng, và người dùng cần
        biết vì sao máy đề xuất như vậy thay vì tin một cái nhãn.

        App chỉ gửi TÊN tác vụ và dữ liệu; toàn bộ câu chữ hướng dẫn mô hình
        nằm ở máy chủ, nên sửa chúng không cần phát hành lại bản .exe.

        Ném :class:`SaasError` khi hỏng — mọi nơi gọi hàm này đều phải có
        đường lui chạy trên máy (xem `music_suggest.goi_y_nhac`).
        """
        data = self._assist_goi(task, input_data, job_id=job_id, images=images,
                                hold_id=hold_id, timeout=timeout)
        ket_qua = data.get("results")
        return ket_qua if isinstance(ket_qua, list) else []

    def _assist_goi(self, task: str, input_data: dict, *, job_id: str,
                    images: list[dict] | None = None,
                    hold_id: str | None = None, timeout: float = 45.0) -> dict:
        payload = {"jobId": job_id, "task": task, "input": input_data or {}}
        if images:
            payload["images"] = images
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request("POST", "/v1/ai/assist", timeout=timeout,
                             json_body=payload)
        self._note_usage(data)
        return data

    def generate_post(self, script_original: str, script_vi: str, *,
                      job_id: str, video_title: str = "",
                      hold_id: str | None = None) -> dict:
        """Viết tiêu đề, mô tả và hashtag. Trả về dict metadata."""
        payload = {
            "jobId": job_id,
            "scriptOriginal": script_original[:20000],
            "scriptVi": script_vi[:20000],
            "videoTitle": video_title[:300],
        }
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request("POST", "/v1/ai/generate-post", timeout=180.0,
                             json_body=payload)
        self._note_usage(data)
        return data.get("metadata") or {}

    # ---------------------------------- nhạc nền/SFX AI (mini-spec V37) --
    #
    # Response 200 là AUDIO NHỊ PHÂN (không phải JSON) — không đi qua
    # ``_request()`` được (nó luôn ``resp.json()`` lúc 200), cùng lý do
    # ``submit_demucs_job()``/``download_job_result()`` tự gọi HTTP trực
    # tiếp rồi tự diễn giải response.

    def generate_sound_effect(self, text: str, dest_path: str, *,
                              duration_seconds: float | None = None,
                              job_id: str | None = None) -> dict:
        """Sinh 1 hiệu ứng âm thanh từ mô tả, ghi ra ``dest_path`` (MP3).

        Trả về ``{"creditCharged", "balanceAfter"}`` (đọc từ header response
        — server không gói billing vào JSON vì response CHÍNH LÀ audio).
        Thiếu Vox -> :class:`InsufficientCreditError`. Tính năng đang tắt ở
        server (opt-in, mini-spec V37 Constraint 2) -> :class:`SaasError`
        với ``code="MUSIC_MATCH_DISABLED"``.
        """
        import requests

        if not self.base_url:
            raise OfflineError("Chưa cấu hình địa chỉ máy chủ VoxDub.")
        token = self._load_token() or self._register_device()
        payload = {"text": text[:500]}
        if duration_seconds:
            payload["durationSeconds"] = float(duration_seconds)
        if job_id:
            payload["jobId"] = job_id
        try:
            resp = self._http().post(
                f"{self.base_url}/v1/ai/sound-effect", json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=(_CONNECT_TIMEOUT, 60.0))
        except requests.exceptions.RequestException as e:
            raise OfflineError(
                "Không kết nối được máy chủ VoxDub. Kiểm tra mạng rồi thử lại."
            ) from e
        return self._save_audio_response(resp, dest_path)

    def generate_music(self, prompt: str, dest_path: str, *,
                       music_length_ms: int | None = None,
                       job_id: str | None = None) -> dict:
        """Sinh 1 đoạn nhạc nền từ mô tả tâm trạng, ghi ra ``dest_path``
        (MP3). Cùng hợp đồng lỗi/billing với :meth:`generate_sound_effect`."""
        import requests

        if not self.base_url:
            raise OfflineError("Chưa cấu hình địa chỉ máy chủ VoxDub.")
        token = self._load_token() or self._register_device()
        payload = {"prompt": prompt[:2000]}
        if music_length_ms:
            payload["musicLengthMs"] = int(music_length_ms)
        if job_id:
            payload["jobId"] = job_id
        try:
            resp = self._http().post(
                f"{self.base_url}/v1/ai/music", json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=(_CONNECT_TIMEOUT, 180.0))
        except requests.exceptions.RequestException as e:
            raise OfflineError(
                "Không kết nối được máy chủ VoxDub. Kiểm tra mạng rồi thử lại."
            ) from e
        return self._save_audio_response(resp, dest_path)

    def _save_audio_response(self, resp, dest_path: str) -> dict:
        if not _la_thanh_cong(resp.status_code):
            self._raise_saas_error(resp)
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(resp.content)
        data = {
            "creditCharged": int(resp.headers.get("X-Credit-Charged") or 0),
            "balanceAfter": int(resp.headers.get("X-Balance-After") or 0),
        }
        # Billing của 2 endpoint này nằm ở header (response là audio nhị
        # phân), không phải JSON — nhưng vẫn phải cập nhật sổ Vox chung
        # (thanh Vox đầu app) giống MỌI lượt gọi AI khác, xem `_note_usage`.
        self._note_usage(data)
        return data

    # -------------------------------------------- telemetry (V13) --------

    # ------------------------------------------------- hồ sơ brand (H1) --
    # Mini-spec H1 (docs/PLAN.md, Phase H) — nền tảng cho H3 (viết lại kịch
    # bản)/H4 (dựng video). "owner_account_id" của đặc tả CHÍNH LÀ thiết bị
    # này (máy chủ tự suy ra từ token, xem control_server/src/routes/
    # brand-profiles.js) — không có khái niệm tài khoản riêng để gõ vào đây.

    def list_brand_profiles(self, timeout: float = 20.0) -> list[dict]:
        """Danh sách hồ sơ brand của máy này. Trả rỗng khi lỗi mạng — thiếu
        danh sách chỉ chặn trang này, không chặn việc khác đang chạy."""
        try:
            data = self._request("GET", "/v1/brand-profiles/", timeout=timeout)
        except SaasError as e:
            logger.warning(f"Không lấy được danh sách hồ sơ brand ({e})")
            return []
        muc = data.get("data")
        return muc if isinstance(muc, list) else []

    def create_brand_profile(
        self, ten_brand: str, *, mo_ta_san_pham: str = "",
        doi_tuong_khach: str = "", tone_giong: str = "", usp: str = "",
        rang_buoc_khong_duoc_noi: list[str] | None = None,
        timeout: float = 20.0,
    ) -> dict:
        """Tạo hồ sơ brand mới. ``rang_buoc_khong_duoc_noi`` BẮT BUỘC có mặt
        (mảng, có thể rỗng) — Constraint 2 của H1: người dùng phải đi qua
        bước hỏi ràng buộc trước khi lưu, không được lặng lẽ bỏ qua."""
        payload = {
            "tenBrand": ten_brand, "moTaSanPham": mo_ta_san_pham,
            "doiTuongKhach": doi_tuong_khach, "toneGiong": tone_giong,
            "usp": usp,
            "rangBuocKhongDuocNoi": list(rang_buoc_khong_duoc_noi or []),
        }
        return self._request("POST", "/v1/brand-profiles/", timeout=timeout,
                             json_body=payload)

    def update_brand_profile(
        self, profile_id: str, *, ten_brand: str, mo_ta_san_pham: str = "",
        doi_tuong_khach: str = "", tone_giong: str = "", usp: str = "",
        rang_buoc_khong_duoc_noi: list[str] | None = None,
        timeout: float = 20.0,
    ) -> dict:
        """Sửa một hồ sơ brand của chính máy này. `404 KHONG_THAY_HO_SO` nếu
        hồ sơ không tồn tại hoặc không thuộc máy này — hai ca đó máy chủ cố
        ý trả về giống hệt nhau, không tiết lộ hồ sơ của máy khác có tồn tại
        hay không."""
        payload = {
            "tenBrand": ten_brand, "moTaSanPham": mo_ta_san_pham,
            "doiTuongKhach": doi_tuong_khach, "toneGiong": tone_giong,
            "usp": usp,
            "rangBuocKhongDuocNoi": list(rang_buoc_khong_duoc_noi or []),
        }
        return self._request("PUT", f"/v1/brand-profiles/{profile_id}",
                             timeout=timeout, json_body=payload)

    def delete_brand_profile(self, profile_id: str, timeout: float = 20.0) -> None:
        """Xoá một hồ sơ brand của chính máy này."""
        self._request("DELETE", f"/v1/brand-profiles/{profile_id}", timeout=timeout)

    # -------------------------------------- flow blueprint (H2, Phase H) --
    # Mini-spec H2 (docs/PLAN.md, Phase H) — bằng chứng ASR/OCR trích ở máy
    # người dùng (``autodub.flow_blueprint.trich_bang_chung``), gửi LÊN đây
    # để máy chủ gọi mô hình phân tích cấu trúc rồi lưu kết quả. Một lượt
    # tổng hợp (không phải job nền) — không có xử lý nặng phía server.

    def list_flow_blueprints(self, timeout: float = 20.0) -> list[dict]:
        """Danh sách Flow Blueprint của máy này. Trả rỗng khi lỗi mạng —
        cùng lý do `list_brand_profiles`."""
        try:
            data = self._request("GET", "/v1/flow-blueprints/", timeout=timeout)
        except SaasError as e:
            logger.warning(f"Không lấy được danh sách Flow Blueprint ({e})")
            return []
        muc = data.get("data")
        return muc if isinstance(muc, list) else []

    def get_flow_blueprint(self, blueprint_id: str, timeout: float = 20.0) -> dict:
        """Một Flow Blueprint của chính máy này. `404 KHONG_THAY_BLUEPRINT`
        nếu không tồn tại hoặc không thuộc máy này."""
        return self._request("GET", f"/v1/flow-blueprints/{blueprint_id}",
                             timeout=timeout)

    def delete_flow_blueprint(self, blueprint_id: str, timeout: float = 20.0) -> None:
        """Xoá một Flow Blueprint của chính máy này."""
        self._request("DELETE", f"/v1/flow-blueprints/{blueprint_id}", timeout=timeout)

    def create_flow_blueprint(
        self, bang_chung, *, job_id: str, hold_id: str | None = None,
        timeout: float = 120.0,
    ) -> dict:
        """Gửi bằng chứng ASR/OCR đã trích để máy chủ phân tích cấu trúc và
        lưu lại một Flow Blueprint mới.

        ``bang_chung``: :class:`autodub.flow_blueprint.BangChungFlowBlueprint`
        (hoặc bất kỳ object nào có cùng thuộc tính) — TRƯỜNG ``title`` không
        gửi lên (entity server không có field này, chỉ dùng hiển thị cục bộ).
        ``job_id`` idempotent theo hash bằng chứng, giống mọi lượt gọi AI
        khác trong file này.
        Trả về Flow Blueprint đã lưu kèm ``creditCharged``/``balanceAfter``.
        Thiếu Vox -> :class:`InsufficientCreditError`.
        """
        payload = {
            "jobId": job_id,
            "sourceType": bang_chung.source_type,
            "sourceReference": bang_chung.source_reference,
            "languageSourceDetected": bang_chung.language_source_detected,
            "samplingPolicyUsed": bang_chung.sampling_policy_used,
            "evidenceSummary": bang_chung.evidence_summary,
            "transcript": bang_chung.transcript,
            "ocrEvidence": bang_chung.ocr_evidence,
        }
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request("POST", "/v1/flow-blueprints/", timeout=timeout,
                             json_body=payload)
        self._note_usage(data)
        return data

    # --------------------------------------- brand script (H3, Phase H) --
    # Mini-spec H3 — viết lại kịch bản cho brand từ nhịp kể chuyện của một
    # Flow Blueprint. Máy chủ giữ TOÀN BỘ phần quyết định: sinh kịch bản, hai
    # lớp kiểm (tuân thủ + nguyên gốc), và tính trạng thái. App KHÔNG được
    # đặt trạng thái, cũng không có đường nào bỏ qua bước kiểm — nếu app tự
    # quyết được thì mọi guardrail của H3 chỉ còn là trang trí.

    def list_brand_scripts(self, timeout: float = 20.0) -> list[dict]:
        """Danh sách kịch bản của máy này. Trả rỗng khi lỗi mạng — thiếu danh
        sách chỉ chặn trang này, không chặn việc khác đang chạy."""
        try:
            data = self._request("GET", "/v1/brand-scripts/", timeout=timeout)
        except SaasError as e:
            logger.warning(f"Không lấy được danh sách kịch bản brand ({e})")
            return []
        muc = data.get("data")
        return muc if isinstance(muc, list) else []

    def get_brand_script(self, script_id: str, timeout: float = 20.0) -> dict:
        """Một kịch bản của chính máy này. `404 KHONG_THAY_KICH_BAN` nếu
        không tồn tại hoặc thuộc máy khác."""
        return self._request("GET", f"/v1/brand-scripts/{script_id}",
                             timeout=timeout)

    def delete_brand_script(self, script_id: str, timeout: float = 20.0) -> None:
        """Xoá một kịch bản của chính máy này."""
        self._request("DELETE", f"/v1/brand-scripts/{script_id}", timeout=timeout)

    def create_brand_script(
        self, flow_blueprint_id: str, brand_profile_id: str, *, job_id: str,
        hold_id: str | None = None, timeout: float = 180.0,
    ) -> dict:
        """Sinh kịch bản mới từ một Flow Blueprint + một hồ sơ brand.

        Cả hai id phải thuộc CHÍNH máy này (máy chủ kiểm chéo, trả `404` nếu
        không). Hồ sơ brand thiếu trường bắt buộc -> `400 HO_SO_BRAND_THIEU`
        kèm danh sách `thieu` — máy chủ cố ý KHÔNG tự bịa nội dung còn thiếu.
        Trả về kịch bản đã lưu kèm ``creditCharged``/``balanceAfter``.
        """
        payload = {
            "jobId": job_id,
            "flowBlueprintId": flow_blueprint_id,
            "brandProfileId": brand_profile_id,
        }
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request("POST", "/v1/brand-scripts/", timeout=timeout,
                             json_body=payload)
        self._note_usage(data)
        return data

    def regenerate_brand_script_beat(
        self, script_id: str, beat_index: int, *, job_id: str,
        hold_id: str | None = None, timeout: float = 180.0,
    ) -> dict:
        """Viết lại MỘT đoạn của kịch bản.

        Máy chủ chạy lại cả hai lớp kiểm cho TOÀN BỘ kịch bản, không chỉ đoạn
        vừa sửa — nên trạng thái trả về có thể đổi ở đoạn khác. Nguồn (Flow
        Blueprint hoặc hồ sơ brand) đã bị xoá -> `409 NGUON_DA_MAT` và kịch
        bản bị hạ về "chưa kiểm được".
        """
        payload = {"jobId": job_id, "beatIndex": int(beat_index)}
        if hold_id:
            payload["holdId"] = hold_id
        data = self._request(
            "POST", f"/v1/brand-scripts/{script_id}/regenerate-beat",
            timeout=timeout, json_body=payload)
        self._note_usage(data)
        return data

    def send_pipeline_event(self, run_id: str, status: str, stage: str,
                            error_stage: str = "") -> None:
        """Báo trạng thái tiến trình 1 lượt dubbing (mini-spec V13, xem
        docs/PLAN.md). CHỈ (runId, status, stage, errorStage?) — không bao
        giờ nội dung, máy chủ tự chặn field lạ (guardrail 2).

        Không tự bọc try/except ở đây — bên gọi (``autodub.telemetry``)
        chạy hàm này trong luồng nền riêng và nuốt mọi lỗi (guardrail 3:
        best-effort, không được làm chậm/hỏng pipeline chính).
        """
        payload = {"runId": run_id, "status": status, "stage": stage}
        if error_stage:
            payload["errorStage"] = error_stage
        self._request("POST", "/v1/telemetry/pipeline-event", timeout=10.0,
                      json_body=payload)


def _retry_after_s(resp) -> float:
    """Header ``Retry-After`` dạng số giây, 0 nếu thiếu hoặc là mốc HTTP-date.

    Máy chủ VoxDub chỉ gửi dạng số giây; dạng ngày tháng bỏ qua cho gọn — bên
    gọi đã có giãn cách mặc định của riêng nó.
    """
    try:
        value = float((resp.headers.get("Retry-After") or "").strip())
    except (AttributeError, TypeError, ValueError):
        return 0.0
    return max(0.0, min(60.0, value))


def _app_version() -> str:
    try:
        from autodub_gui.app import APP_VERSION

        return APP_VERSION
    except Exception:  # noqa: BLE001 — dùng từ CLI, không có GUI
        return "3.0.0"


# Máy khách dùng chung cho cả tiến trình: token, phiên HTTP và cấu hình chỉ
# nên tồn tại một bản. Dựng lười để nạp module không tốn gì.
_client: SaasClient | None = None
_client_lock = threading.Lock()


def get_client() -> SaasClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = SaasClient()
        return _client


def reset_client() -> None:
    """Vứt máy khách hiện tại (dùng sau khi đổi địa chỉ máy chủ trong dev)."""
    global _client
    with _client_lock:
        _client = None
