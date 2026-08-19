"""Tìm lại bộ máy nặng (Whisper/Paraformer/VieNeu) mà bản CŨ đã cài.

Vì sao cần (mini-spec V77): `.venv-whisper`, `.venv-asr`, `.venv-vieneu` và
`models/` nằm TRONG thư mục ứng dụng (``app_root()``). Nâng cấp = giải nén bản
mới ra thư mục khác, nên toàn bộ thứ đã cài "biến mất": app báo *chưa cài bộ
nghe* dù người dùng đã cài từ lâu, và cách chữa duy nhất là tải lại ~1,5 GB
model hoặc tự chép tay hai thư mục sang. Đây là lời than có thật, lặp lại ở
mọi lần lên phiên bản (xem docs/TEST_LOG.md V74).

Cách làm ở đây: khi thư mục mặc định KHÔNG có, dò các thư mục **nằm cạnh**
thư mục ứng dụng — chính là các bản cũ giải nén cạnh nhau — và dùng lại bộ đã
cài ở đó tại chỗ (không chép, không tải lại).

Ba ràng buộc cố ý:

1. Người dùng đặt đường dẫn thủ công trong Cài đặt thì KHÔNG bao giờ bị đè.
2. Chỉ nhận thư mục có ĐỦ cả trình thông dịch lẫn dấu ``installed_ok.json``
   — một bản cài dở dang còn tệ hơn là không tìm thấy gì.
3. Kết quả có nhớ đệm: ``whisper_venv_configured()`` bị gọi rất nhiều lần
   (mỗi lượt canh chữ, mỗi lần mở app, mỗi lượt nghe) — quét đĩa mỗi lần là
   tự tay làm app chậm đi.
"""
from __future__ import annotations

import os
import threading

from autodub.utils import app_root, setup_logging

logger = setup_logging("autodub.venv")

#: Số thư mục cạnh bên tối đa chịu ngó qua. Người dùng có thể giải nén app
#: vào Desktop hay Downloads — nơi có hàng trăm thư mục; quét vô hạn ở đó là
#: treo app lúc khởi động, mà bản cũ thì gần như luôn nằm ngay đầu danh sách.
_MAX_ANH_EM = 60

_cache: dict[tuple[str, str], tuple[str, str] | None] = {}
_lock = threading.Lock()


def _python_trong(venv_dir: str) -> str:
    exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return os.path.join(venv_dir, *exe.split("/"))


def tim_ban_cai_cu(ten_venv: str, ten_model: str) -> tuple[str, str] | None:
    """``(python, thư mục model)`` của một bản cài cũ cạnh bên, hoặc ``None``.

    ``ten_venv`` ví dụ ``".venv-whisper"``; ``ten_model`` ví dụ ``"whisper"``
    (thư mục con của ``models/``).
    """
    key = (ten_venv, ten_model)
    with _lock:
        if key in _cache:
            return _cache[key]

    ket_qua = None
    goc = app_root()
    cha = os.path.dirname(goc)
    try:
        anh_em = sorted(os.scandir(cha), key=lambda e: e.name)
    except OSError:
        anh_em = []

    ung_vien: list[tuple[float, str, str]] = []
    for i, entry in enumerate(anh_em):
        if i >= _MAX_ANH_EM:
            break
        try:
            if not entry.is_dir() or os.path.samefile(entry.path, goc):
                continue
        except OSError:
            continue
        py = _python_trong(os.path.join(entry.path, ten_venv))
        model_dir = os.path.join(entry.path, "models", ten_model)
        marker = os.path.join(model_dir, "installed_ok.json")
        if os.path.isfile(py) and os.path.isfile(marker):
            try:
                moi = os.path.getmtime(marker)
            except OSError:
                moi = 0.0
            ung_vien.append((moi, py, model_dir))

    if ung_vien:
        # Bản cài MỚI NHẤT — người dùng thường có vài bản cũ chồng nhau.
        _moi, py, model_dir = max(ung_vien, key=lambda x: x[0])
        ket_qua = (py, model_dir)
        # py = <thư mục bản cũ>/<venv>/{Scripts|bin}/python[.exe] — lùi BA
        # cấp mới ra tên thư mục bản cũ; lùi hai cấp chỉ ra tên venv.
        ten = os.path.basename(
            os.path.dirname(os.path.dirname(os.path.dirname(py))))
        logger.info(f"Dùng lại bộ đã cài của bản trước ở thư mục: {ten}")

    with _lock:
        _cache[key] = ket_qua
    return ket_qua


def quen_cache() -> None:
    """Xoá nhớ đệm — dùng trong test, và sau khi cài thêm bộ máy mới."""
    with _lock:
        _cache.clear()


def tim_thu_muc_bin_cu() -> str:
    """Thư mục ``bin/`` có ffmpeg của một bản cài cũ cạnh bên, hoặc "".

    Cùng cảnh ngộ với các venv (mini-spec V81): trình cài đặt tải ffmpeg về
    ``<thư mục app>/bin``, nên nâng cấp sang thư mục mới là app lại báo "máy
    chưa có FFmpeg" — dù người dùng đã cài rồi và tệp vẫn nằm ngay thư mục
    bên cạnh.
    """
    key = ("__bin__", "ffmpeg")
    with _lock:
        if key in _cache:
            return _cache[key] or ""

    ten = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    ket_qua = None
    goc = app_root()
    try:
        anh_em = sorted(os.scandir(os.path.dirname(goc)), key=lambda e: e.name)
    except OSError:
        anh_em = []
    for i, entry in enumerate(anh_em):
        if i >= _MAX_ANH_EM:
            break
        try:
            if not entry.is_dir() or os.path.samefile(entry.path, goc):
                continue
        except OSError:
            continue
        bin_dir = os.path.join(entry.path, "bin")
        if os.path.isfile(os.path.join(bin_dir, ten)):
            ket_qua = bin_dir
            logger.info(f"Dùng lại FFmpeg đã tải của bản trước ở thư mục: "
                        f"{os.path.basename(entry.path)}")
            break

    with _lock:
        _cache[key] = ket_qua
    return ket_qua or ""
