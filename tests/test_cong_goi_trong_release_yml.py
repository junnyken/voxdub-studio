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
