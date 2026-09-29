"""Định danh máy — mã thiết bị dùng để gắn ví Vox.

Không có tài khoản người dùng: chính chiếc máy này LÀ danh tính. Mã thiết bị
được băm từ ba thứ gắn với phần cứng và hệ điều hành, không phải từ thứ gì
người dùng đặt được:

- ``MachineGuid`` trong registry — Windows sinh lúc cài đặt, không đổi qua
  các lần cập nhật, và không có giao diện nào cho phép sửa.
- Tên máy và mã bộ xử lý — hai lớp phụ, giúp phân biệt hai máy nhân bản từ
  cùng một ảnh đĩa (trường hợp GUID trùng nhau).

Kết quả là chuỗi SHA-256 64 ký tự. Cài lại ứng dụng, xóa ``.env``, đổi thư
mục — mã vẫn thế, nên credit đã mua không mất. Cài lại Windows thì GUID mới,
mã mới: trường hợp đó người dùng liên hệ hỗ trợ để chuyển credit sang máy.

**Máy không phải Windows và không có địa chỉ MAC thật** (container, một số
máy ảo): ``uuid.getnode()`` không tìm được phần cứng nào thì nó **bịa một số
ngẫu nhiên MỚI mỗi tiến trình** (RFC 4122, có bật bit multicast để báo điều
đó). Bản đầu dùng thẳng số ấy, nên mỗi lần mở ứng dụng là một MÁY MỚI: ví
mới, và một suất dùng thử mới. Đo thật trên workspace Linux ngày 22/8/2026:
**25 thiết bị từ đúng một máy**, vài cái mang 500 Vox dùng thử. Đó vừa là lỗ
cấp phát tiền, vừa làm danh sách máy hiệu chỉnh không thể dùng được.

Nay số ngẫu nhiên đó được **ghi xuống đĩa một lần rồi dùng lại**. Đường
Windows không đổi một dòng nào.
"""
from __future__ import annotations

import hashlib
import os
import platform
import uuid

from autodub.utils import setup_logging

logger = setup_logging("autodub.device_id")

#: Nơi giữ mã dự phòng cho máy không có MAC thật. Để ở thư mục nhà chứ không
#: cạnh mã nguồn: gỡ và cài lại ứng dụng thì mã vẫn còn, đúng như lời hứa
#: "credit đã mua không mất" ở trên.
TEP_MA_DU_PHONG = os.path.join(os.path.expanduser("~"), ".voxdub_device_id")

_cached_fingerprint: str | None = None


def _machine_guid() -> str:
    """MachineGuid của Windows; địa chỉ MAC là phương án dự phòng."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            # Bắt buộc đọc nhánh 64-bit: tiến trình 32-bit bị chuyển hướng
            # sang Wow6432Node và đọc ra GUID KHÁC — mã thiết bị sẽ đổi chỉ
            # vì đổi kiến trúc bản đóng gói.
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        try:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(guid).strip()
        finally:
            winreg.CloseKey(key)
    except (ImportError, OSError):
        # Không phải Windows, hoặc registry không đọc được: dùng địa chỉ MAC.
        # Kém ổn định hơn (card mạng ảo có thể đổi) nhưng còn hơn không có gì.
        node = uuid.getnode()
        # Bit multicast bật = Python KHÔNG tìm được MAC nào và đã bịa một số
        # ngẫu nhiên cho lần chạy này. Dùng thẳng nó là mỗi lần mở ứng dụng
        # một máy mới — xem docstring đầu tệp.
        if (node >> 40) & 1:
            return _ma_du_phong_on_dinh()
        return f"mac-{node:012x}"


def _ma_du_phong_on_dinh() -> str:
    """Mã ngẫu nhiên nhưng CHỈ SINH MỘT LẦN, giữ lại trên đĩa."""
    try:
        with open(TEP_MA_DU_PHONG, encoding="utf-8") as f:
            ma = f.read().strip()
        if ma:
            return ma
    except OSError:
        pass  # chưa có tệp là chuyện thường ở lần chạy đầu

    ma = f"rand-{uuid.uuid4().hex}"
    try:
        with open(TEP_MA_DU_PHONG, "w", encoding="utf-8") as f:
            f.write(ma)
    except OSError as e:
        # Không ghi được thì mã chỉ ổn định trong phiên này — tức là quay về
        # đúng hành vi cũ. Phải KÊU LÊN, vì hậu quả (ví mới mỗi lần chạy)
        # nhìn từ phía người dùng là "tự dưng mất tiền".
        logger.warning(
            f"Không ghi được mã thiết bị vào «{TEP_MA_DU_PHONG}» ({e}) — "
            "máy này sẽ được coi là máy mới ở lần chạy sau")
    return ma


def get_fingerprint() -> str:
    """Mã thiết bị (SHA-256 hex, 64 ký tự). Tính một lần mỗi phiên."""
    global _cached_fingerprint
    if _cached_fingerprint is not None:
        return _cached_fingerprint

    raw = "|".join((
        _machine_guid(),
        platform.node(),
        platform.machine(),
    ))
    _cached_fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return _cached_fingerprint


def get_device_name() -> str:
    """Tên máy hiển thị trong trang quản trị, vd "DESKTOP-ABC (Windows 10.0.26200)"."""
    node = platform.node() or "Máy không tên"
    system = platform.system() or "?"
    release = platform.version() or platform.release() or ""
    return f"{node} ({system} {release})".strip()


def short_id() -> str:
    """8 ký tự đầu của mã thiết bị — đủ để đọc cho bộ phận hỗ trợ."""
    return get_fingerprint()[:8].upper()
