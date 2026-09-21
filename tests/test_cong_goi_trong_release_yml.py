"""I0-FDE §F — cổng kiểm bản đóng gói phải nằm ĐÚNG CHỖ trong release.yml.

Một cổng kiểm đặt sai chỗ thì vô dụng: chạy SAU bước phát hành thì bản hỏng
đã lên GitHub Release rồi (app có trình kiểm bản mới đọc đúng nguồn đó, nên
người dùng thật sẽ được mời cập nhật). Đặt `continue-on-error` thì nó đỏ mà
không chặn được gì.

Cả hai đều là kiểu hỏng KHÔNG lộ ra trong bất kỳ lượt chạy xanh nào — chỉ lộ
ra đúng lần đầu tiên có sự cố thật. Nên khoá bằng test.
"""
from __future__ import annotations

import os

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUONG = os.path.join(REPO, ".github", "workflows", "release.yml")

#: Bước chạy bộ lái cổng kiểm bản đóng gói (một bước cho mỗi chế độ).
BO_LAI = "scripts/kiem_goi_phat_hanh.py"


def _cac_buoc() -> list[dict]:
    with open(DUONG, encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    return wf["jobs"]["build-windows"]["steps"]


def _chi_so(dieu_kien) -> list[int]:
    return [i for i, b in enumerate(_cac_buoc()) if dieu_kien(b)]


def _chay(b: dict) -> str:
    return str(b.get("run") or "")


def test_co_du_ba_che_do_cong_goi():
    che_do = {c for b in _cac_buoc() if BO_LAI in _chay(b)
              for c in ("sach", "nang-cap", "am-tinh")
              if f"--che-do {c}" in _chay(b)}
    assert che_do == {"sach", "nang-cap", "am-tinh"}, (
        "thiếu chế độ nào thì phần đó của I0-D/E/F không được chứng minh, "
        f"đang có: {sorted(che_do)}")


def test_cong_goi_chay_sau_cong_ma_nguon_va_TRUOC_khi_phat_hanh():
    buoc = _cac_buoc()
    dung = _chi_so(lambda b: BO_LAI in _chay(b))
    nguon = _chi_so(lambda b: "kiem_chay_that.py" in _chay(b))
    phat_hanh = _chi_so(lambda b: "action-gh-release" in str(b.get("uses", "")))
    assert dung and nguon and phat_hanh
    assert max(nguon) < min(dung), (
        "cổng gói phải chạy SAU cổng dub từ mã nguồn — hỏng ở tầng dưới thì "
        "chẩn tầng trên chỉ tốn thời gian")
    assert max(dung) < min(phat_hanh), (
        "cổng gói phải chạy TRƯỚC bước phát hành, không thì bản hỏng đã lên "
        f"GitHub Release (đang là {dung} vs {phat_hanh}, {len(buoc)} bước)")


def test_cong_goi_khong_duoc_gan_dieu_kien_hay_bo_qua_loi():
    for b in _cac_buoc():
        if BO_LAI not in _chay(b) or "--chi-in-bang" in _chay(b):
            continue
        assert "if" not in b, (
            f"bước {b.get('name')!r} có điều kiện — một cổng có thể bị bỏ qua "
            "thì nó không còn là cổng")
        assert not b.get("continue-on-error"), (
            f"bước {b.get('name')!r} bỏ qua lỗi: đỏ mà vẫn phát hành")


def test_buoc_phat_hanh_van_chi_chay_voi_tag():
    """Giữ nguyên chốt dry-run đã có (commit 06dbfd3) — không nới ra."""
    phat_hanh = [b for b in _cac_buoc()
                 if "action-gh-release" in str(b.get("uses", ""))]
    assert len(phat_hanh) == 1
    assert "refs/tags/v" in str(phat_hanh[0].get("if", "")), (
        "bỏ điều kiện tag là mọi lượt kích hoạt tay đều tạo GitHub Release "
        "công khai")


def test_bang_chung_duoc_giu_lai_ke_ca_khi_do():
    tai_len = [b for b in _cac_buoc()
               if "upload-artifact" in str(b.get("uses", ""))]
    assert tai_len, "không giữ bằng chứng thì mỗi lần hỏng lại phải đoán"
    assert any(str(b.get("if", "")).strip() == "always()" for b in tai_len), (
        "bằng chứng cần nhất đúng lúc ĐỎ — `if: always()`")


def test_bang_tom_tat_doc_tu_tep_bang_chung():
    """Bảng kết quả phải sinh từ tệp, không phải do người viết YAML gõ tay."""
    tom = [b for b in _cac_buoc() if "--chi-in-bang" in _chay(b)]
    assert len(tom) == 1
    assert "GITHUB_STEP_SUMMARY" in _chay(tom[0])
    assert str(tom[0].get("if", "")).strip() == "always()"


# ----------------------------------- NÂNG CẤP LIÊN PHIÊN BẢN (giới hạn (2)) --
#
# Bản cũ của cổng I0-E nay dựng từ một GÓI PHÁT HÀNH THẬT tải trên GitHub
# Releases. Ba thứ dưới đây nếu tuột ra thì cổng vẫn xanh mà không còn kiểm
# nâng cấp liên phiên bản nữa — đúng kiểu hỏng không lộ ra ở lượt chạy nào.

#: Bước tải gói phát hành cũ.
BO_TAI = "scripts/tai_goi_phat_hanh_cu.py"


def test_co_buoc_tai_goi_phat_hanh_cu_va_chay_TRUOC_cong_nang_cap():
    tai = _chi_so(lambda b: BO_TAI in _chay(b))
    nang = _chi_so(lambda b: "--che-do nang-cap" in _chay(b))
    assert len(tai) == 1, (
        "bước tải phải ĐỨNG RIÊNG: gộp vào cổng nâng cấp thì mạng hỏng cũng "
        "trông y như sản phẩm hỏng")
    assert tai[0] < min(nang), "tải xong mới có gì để dựng bản cũ"


def test_buoc_tai_khong_duoc_bo_qua_loi():
    """Tải hỏng mà vẫn đi tiếp = cổng nâng cấp chạy với bản cũ sai/thiếu."""
    for b in _cac_buoc():
        if BO_TAI not in _chay(b):
            continue
        assert "if" not in b
        assert not b.get("continue-on-error")


def test_ca_hai_cong_I0E_deu_nhan_goi_ban_cu():
    for che_do in ("nang-cap", "am-tinh"):
        buoc = [b for b in _cac_buoc() if f"--che-do {che_do}" in _chay(b)]
        assert len(buoc) == 1, che_do
        assert "--zip-ban-cu" in _chay(buoc[0]), (
            f"cổng {che_do} không nhận gói bản cũ thì nó lại dựng bản cũ từ "
            "chính gói ứng viên — đúng giới hạn (2) vừa đóng")
        assert "--nguon-ban-cu" in _chay(buoc[0]), (
            f"cổng {che_do} thiếu bằng chứng nguồn gốc bản cũ")


def test_cong_cai_moi_KHONG_duoc_nhan_goi_ban_cu():
    """I0-D phải là máy trắng: có bản cũ cạnh bên là hỏng cả định nghĩa."""
    for b in _cac_buoc():
        if "--che-do sach" in _chay(b):
            assert "--zip-ban-cu" not in _chay(b)


def test_ban_cu_ghim_TAG_CO_DINH_khong_phai_latest():
    """`latest` sẽ tự trỏ vào chính bản vừa phát hành — kiểm bản với chính nó."""
    tai = [b for b in _cac_buoc() if BO_TAI in _chay(b)]
    assert tai
    lenh = _chay(tai[0])
    import re
    m = re.search(r"--tag\s+(\S+)", lenh)
    assert m, "bước tải phải ghi rõ --tag"
    assert re.fullmatch(r"v\d+(\.\d+)+", m.group(1)), (
        f"tag bản cũ phải là một mốc cố định, đang là {m.group(1)!r}")
