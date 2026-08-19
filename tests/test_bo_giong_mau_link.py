"""V84 — link tải bộ giọng mẫu trỏ sang một kho KHÔNG TỒN TẠI.

`voice_downloader.VOICES_RELEASE_URL` ghim `ttthanh2044/voxdub`, trong khi bản
phát hành thật nằm ở `junnyken/voxdub-studio`. Đo thẳng bằng HTTP:

    URL cũ  -> 404
    URL mới -> 302 (tải được)

Nghĩa là tính năng "Nạp bộ giọng đọc mẫu" (120 giọng) **chưa bao giờ tải được**
trên bản đóng gói — cùng lớp lỗi với V80 (`asr_whisper_worker.py` không được
đóng gói) và V83 (`icons.brand_logo` không tồn tại): thứ được gọi tới thì có,
thứ ở đầu bên kia thì không.

Chữa bằng cách bỏ hằng số ghim tay: đọc kho phát hành từ `Settings.update_repo`
— cùng nguồn sự thật với việc kiểm tra bản cập nhật.
"""
from __future__ import annotations

import os
import re

from autodub.config import Settings
from autodub.speech.tts.voice_downloader import voices_release_url

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_lay_kho_phat_hanh_tu_cau_hinh():
    st = Settings()
    st.update_repo = "junnyken/voxdub-studio"
    url = voices_release_url(st)
    assert url.startswith("https://github.com/junnyken/voxdub-studio/releases/")
    assert url.endswith("preset_voices_vn.zip")


def test_doi_kho_phat_hanh_thi_link_di_theo():
    """Một nguồn sự thật: đổi ở Cài đặt là mọi thứ đi theo, không còn hằng số
    nào âm thầm trỏ về kho cũ."""
    st = Settings()
    st.update_repo = "ai-do/kho-rieng"
    assert "ai-do/kho-rieng" in voices_release_url(st)


def test_cau_hinh_hong_thi_ve_kho_mac_dinh():
    st = Settings()
    for xau in ("", "   ", "khong-co-dau-gach-cheo"):
        st.update_repo = xau
        assert "junnyken/voxdub-studio" in voices_release_url(st)


def test_khong_con_kho_chet_nao_trong_ma_nguon():
    """Kho `ttthanh2044/voxdub` không tồn tại — còn sót ở đâu là còn một
    đường tải chết ở đó."""
    sot = []
    for goc, _dirs, files in os.walk(REPO):
        if any(x in goc for x in (".git", "node_modules", ".venv", "dist",
                                  "build", "__pycache__")):
            continue
        for f in files:
            if not f.endswith((".py", ".md", ".bat", ".spec")):
                continue
            duong = os.path.join(goc, f)
            try:
                noi_dung = open(duong, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            # Tệp CỐ Ý nhắc tên kho cũ để giải thích lỗi (test này, ghi chú
            # trong mã, nhật ký kỹ thuật) thì không tính.
            if os.path.basename(duong) in ("test_bo_giong_mau_link.py",
                                           "voice_downloader.py",
                                           "TEST_LOG.md", "PLAN.md"):
                continue
            for dong in re.findall(r".*ttthanh2044/voxdub.*", noi_dung):
                sot.append(f"{os.path.relpath(duong, REPO)}: {dong.strip()[:70]}")
    assert not sot, f"còn trỏ về kho không tồn tại: {sot}"


def test_env_mau_ghi_dung_kho():
    """`.env.example` là thứ người dùng chép thành `.env` — ghi sai ở đây là
    mọi thứ đi theo hướng sai."""
    noi_dung = open(os.path.join(REPO, ".env.example"), encoding="utf-8").read()
    assert "UPDATE_REPO=junnyken/voxdub-studio" in noi_dung


def test_loi_tiktok_chan_duoc_dich_thanh_cach_chua_co_that():
    """V85 — yt-dlp bảo người dùng đi báo lỗi trên GitHub; app phải nói cách
    chữa có thật: mượn cookie trình duyệt (đã có sẵn trong Cài đặt)."""
    from autodub_gui.dub_constants import friendly_error

    that = ("ERROR: [TikTok] 7508664773936991495: Unexpected response from "
            "webpage request; please report this issue on "
            "https://github.com/yt-dlp/yt-dlp/issues?q=")
    soan = friendly_error(that)
    assert soan is not None
    _tieu_de, cach_chua = soan
    assert "Cookie" in cach_chua or "cookie" in cach_chua
    assert "Tải tệp lên" in cach_chua
