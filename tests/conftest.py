"""Rào an toàn cho toàn bộ test suite.

**Bug thật, tìm ra 2026-08-17 khi cài đủ dependency để chạy suite tại chỗ.**

`.env` của người phát triển (chính README hướng dẫn tạo) chứa
``VOXDUB_API_URL`` trỏ về máy chủ THẬT. `Settings.load()` gọi `load_dotenv()`,
mà `load_dotenv` bơm thẳng vào ``os.environ`` của cả tiến trình. Nên chỉ cần
MỘT test bất kỳ gọi `Settings.load()` là từ đó trở đi mọi test khác đều thấy
biến môi trường đó — kể cả những test cố tình dựng `SaasClient(base_url="")`
để kiểm nhánh offline: chúng rơi về `resolve_api_url()` và **gọi mạng thật**.

Bằng chứng nó đã xảy ra thật chứ không phải lo xa: test
`test_generate_music_offline_raises_when_no_base_url` fail với
``resp = <Response [402]>`` — tức suite đã đăng ký một thiết bị trên máy chủ
production và thử một thao tác TÍNH PHÍ. CI không bao giờ lộ ra vì CI không
có `.env`.

Vì vậy: xoá sạch mọi biến trỏ ra mạng TRƯỚC mỗi test. Test nào cần địa chỉ
máy chủ thì tự đặt bằng `monkeypatch.setenv` — tường minh, và tự dọn sau khi
xong.
"""
import os

import pytest

# Biến khiến mã nguồn tự tìm đường ra một máy chủ thật.
NETWORK_ENV_VARS = ("VOXDUB_API_URL", "VOXDUB_API_KEY")


@pytest.fixture(autouse=True)
def _no_accidental_network(monkeypatch):
    for name in NETWORK_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    yield


def pytest_configure(config):
    """Dọn ngay lúc khởi động, trước cả khi import test module.

    Fixture ở trên chỉ chạy quanh từng test; nhưng có module đọc biến môi
    trường ngay lúc import (hằng số ở tầng module). Xoá sớm là chặn được cả
    đường đó.
    """
    for name in NETWORK_ENV_VARS:
        os.environ.pop(name, None)
