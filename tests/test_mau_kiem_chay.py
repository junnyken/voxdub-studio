"""Video mẫu của hai cổng kiểm chạy thật — quyền sở hữu VÀ khả năng chứng minh.

Giới hạn (1) của `docs/TEST_LOG.md` mục I0-FDE(e): `tap01_clip.mp4` không tra
được nguồn gốc, trong khi guardrail 11 của mini-spec I0-FDE đòi video mẫu bắt
buộc phải là *project-owned or explicitly permitted*. Nay mẫu do chính dự án
dựng (`scripts/tao_mau_kiem_chay.py`).

Nhưng "sạch bản quyền" chỉ là MỘT nửa. Nửa còn lại, và là nửa dễ mất hơn: mẫu
mới phải giữ đúng những tính chất khiến các chốt của hai cổng còn **phân biệt
được đạt/hỏng**. Một mẫu 2 giây, hoặc một mẫu nói tiếng Việt, vẫn cho cổng màu
xanh — trong khi ngưỡng câm, ngưỡng lệch thời lượng và cả đường dịch tay đều
đã thành trang trí. Những phép kiểm dưới đây khoá đúng bốn tính chất đó, cộng
chốt "hai cổng thật sự dùng mẫu này".
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAU = os.path.join(GOC, "mau_kiem_chay.mp4")
MANIFEST = os.path.join(GOC, "mau_kiem_chay.json")

#: Sàn thời lượng. Dưới mức này thì ngưỡng lệch 35% chỉ còn vài giây — mà
#: chính giọng đọc tiếng Việt thay vào đã lệch hơn thế, nên chốt sẽ kêu oan
#: thay vì bắt lỗi.
GIAY_TOI_THIEU = 30.0

#: Sàn số câu. Bản chép lời một câu thì phần đóng vai dịch tay (xoay vòng ba
#: câu mẫu) và chốt "nghe được N câu" đều mất ý nghĩa.
SO_CAU_TOI_THIEU = 5


def _doc(ten: str) -> str:
    with open(os.path.join(GOC, ten), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def ho_so() -> dict:
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def _ffprobe(*args: str) -> str:
    return subprocess.run(["ffprobe", "-v", "error", *args],
                          capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


# ------------------------------------------------------- quyền sở hữu ------

def test_mau_va_manifest_deu_co_trong_repo():
    assert os.path.isfile(MAU), (
        "thiếu video mẫu — cả hai cổng chạy thật sẽ dừng ở mã 2")
    assert os.path.isfile(MANIFEST), (
        "thiếu manifest thì không ai trả lời được 'mẫu này của ai'")


def test_manifest_noi_ro_ai_so_huu_va_co_so_phap_ly(ho_so):
    assert "VoxDub Studio" in ho_so["so_huu"]
    phap_ly = ho_so["co_so_phap_ly"]
    for phan in ("loi_thoai", "tieng", "hinh"):
        assert phap_ly[phan].strip(), f"thiếu cơ sở pháp lý cho phần {phan}"
    assert ho_so["dung_bang"].endswith("tao_mau_kiem_chay.py"), (
        "phải chỉ đúng script dựng — 'tự dựng' mà không ai dựng lại được thì "
        "cũng chỉ là một lời khai")


def test_sha256_trong_manifest_khop_tep_that(ho_so):
    """Đổi tệp mà quên chạy lại script dựng là manifest nói dối."""
    h = hashlib.sha256()
    with open(MAU, "rb") as f:
        for khoi in iter(lambda: f.read(1 << 20), b""):
            h.update(khoi)
    assert ho_so["sha256"] == h.hexdigest()
    assert ho_so["byte"] == os.path.getsize(MAU)


# -------------------------------- bốn tính chất giữ cho cổng còn NGHĨA -----

def test_mau_du_dai_de_hai_nguong_con_phan_biet_duoc(ho_so):
    assert ho_so["giay"] >= GIAY_TOI_THIEU, (
        f"mẫu {ho_so['giay']}s là quá ngắn: ngưỡng lệch thời lượng 35% của "
        "cổng sẽ nhỏ hơn cả phần lệch bình thường của giọng đọc tiếng Việt")


def test_mau_co_NHIEU_cau_khong_phai_mot(ho_so):
    assert len(ho_so["loi_thoai"]) >= SO_CAU_TOI_THIEU
    do = ho_so.get("do_bang_whisper_tiny") or {}
    assert do.get("da_do"), (
        "manifest phải ghi lượt ĐO THẬT bằng chính bộ nghe của CI, không chỉ "
        "ghi ý định thiết kế")
    assert do["so_cau"] >= SO_CAU_TOI_THIEU, (
        f"bộ nghe chỉ ra {do['so_cau']} câu — phần đóng vai dịch tay và chốt "
        "'nghe được N câu' mất ý nghĩa")


def test_tieng_trong_mau_KHONG_phai_tieng_viet(ho_so):
    """Mẫu tiếng Việt làm pipeline BỎ HẲN khâu dịch → cổng kiểm nhầm đường.

    `pipeline.py` đặt `khong_can_dich = cung_ngon_ngu(lang_code, target.key)`
    và chỉ giữ lại khâu dịch khi độ tin cậy < 0,85. Mẫu tiếng Việt nghe rõ sẽ
    không đi qua `TRANSLATE_PENDING.txt` — thứ mà cả hai cổng đều đòi.
    """
    do = ho_so.get("do_bang_whisper_tiny") or {}
    ngon_ngu = str(do.get("ngon_ngu", "")).lower()
    assert ngon_ngu and not ngon_ngu.startswith("vi"), (
        f"bộ nghe nhận ra {ngon_ngu!r} — trùng ngôn ngữ đích thì lượt chạy bỏ "
        "qua đường dịch tay và cổng không còn kiểm đúng thứ nó tưởng")
    assert do.get("do_tin_cay", 0) > 0


def test_mau_co_khoang_lang_giua_cac_cau(ho_so):
    """Nói liên tục không khoảng nghỉ thì giọng đọc tiếng Việt không có chỗ
    dồn phần trễ, và chốt lệch thời lượng 35% sẽ kêu oan."""
    moc = ho_so["loi_thoai"]
    khoang = [sau["bat_dau"] - truoc["ket_thuc"]
              for truoc, sau in zip(moc, moc[1:])]
    assert khoang and min(khoang) >= 0.5, (
        f"khoảng lặng nhỏ nhất {min(khoang) if khoang else 0}s")


def test_mau_dung_dinh_dang_nhu_tep_nguoi_dung_dua_vao():
    """h264 + aac: mẫu phải đi đúng đường giải mã mà người dùng thật đi."""
    if not os.path.isfile(MAU):
        pytest.skip("không có mẫu")
    video = _ffprobe("-select_streams", "v", "-show_entries",
                     "stream=codec_name", "-of", "default=nw=1:nk=1", MAU)
    tieng = _ffprobe("-select_streams", "a", "-show_entries",
                     "stream=codec_name", "-of", "default=nw=1:nk=1", MAU)
    assert video == "h264" and tieng == "aac", (video, tieng)


# ----------------------------------- hai cổng phải THẬT SỰ dùng mẫu này ----

def test_hai_cong_lay_mau_nay_lam_mac_dinh():
    assert 'default="mau_kiem_chay.mp4"' in _doc("scripts/kiem_chay_that.py")
    assert 'GOC_REPO / "mau_kiem_chay.mp4"' in _doc(
        "scripts/kiem_goi_phat_hanh.py")


@pytest.mark.parametrize("wf", ["release.yml", "test.yml"])
def test_CI_chay_cong_bang_mau_cua_du_an(wf):
    """Đổi cờ `--video` trong YAML về mẫu cũ là quay lại đúng câu hỏi bản
    quyền mà bản vá này vừa đóng."""
    chu = _doc(os.path.join(".github", "workflows", wf))
    assert "--video mau_kiem_chay.mp4" in chu
    assert "--video tap01_clip.mp4" not in chu
