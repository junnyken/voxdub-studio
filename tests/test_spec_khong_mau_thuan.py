"""V74 — `autodub.spec` không được vừa loại vừa gom cùng một gói.

Bug thật, tìm ra 2026-08-19 khi mở bản phát hành v3.4.1 ra đếm tệp:
`faster_whisper` và `ctranslate2` nằm ĐỒNG THỜI ở `collect_all(...)` và ở
`excludes`. Hai chỗ này không triệt tiêu nhau như người viết tưởng:

- `excludes` chặn ở **tầng import** (đồ thị module PyInstaller phân tích ra).
- `collect_all` nhét tệp vào qua **tầng datas**, mà datas được chép nguyên xi.

Nên mã Python của chúng vẫn nằm ở `_internal/` — thư mục có trên `sys.path`
của bản onedir — khiến `import faster_whisper` chạy được rồi chết ở `import
av`. Người dùng nhận `No module named 'av'`, một câu không thể suy ra được
là "chưa cài Whisper".

Bài test này đọc thẳng tệp spec vì không thể chạy PyInstaller cho Windows từ
Linux. Nó không chứng minh bundle sạch — nó chặn đúng cái mâu thuẫn đã sinh
ra bug, ngay tại chỗ dễ vô tình thêm lại nhất.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_SPEC = Path(__file__).parent.parent / "autodub.spec"


@pytest.fixture(scope="module")
def spec_src() -> str:
    return _SPEC.read_text(encoding="utf-8")


def _goi_duoc_collect(src: str) -> set[str]:
    """Các gói truyền cho `collect_all` qua vòng lặp `for pkg in (...)`."""
    m = re.search(r"for pkg in \(([^)]*)\):", src)
    assert m, "không tìm thấy vòng lặp collect_all trong spec"
    return {x.strip() for x in ast.literal_eval("(" + m.group(1) + ")")} \
        if m.group(1).strip() else set()


def _goi_bi_exclude(src: str) -> set[str]:
    m = re.search(r"excludes=\[(.*?)\n    \],", src, re.S)
    assert m, "không tìm thấy danh sách excludes trong spec"
    return set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', m.group(1)))


def test_khong_vua_loai_vua_gom(spec_src):
    chung = _goi_duoc_collect(spec_src) & _goi_bi_exclude(spec_src)
    assert not chung, (
        "gói vừa nằm trong collect_all vừa nằm trong excludes: "
        f"{sorted(chung)}. `excludes` chỉ chặn tầng import, `collect_all` vẫn "
        "nhét tệp vào qua tầng datas — gói sẽ CÓ MẶT trong bundle và import "
        "được nửa đường. Xem mini-spec V74.")


def test_van_con_gom_yt_dlp(spec_src):
    """yt-dlp nạp extractor động theo tên nên PyInstaller không thấy bằng
    phân tích import — bỏ nó khỏi collect_all là hỏng mọi lượt tải video."""
    assert "yt_dlp" in _goi_duoc_collect(spec_src)


@pytest.mark.parametrize("pkg", ["faster_whisper", "ctranslate2", "av",
                                 "onnxruntime"])
def test_engine_nang_van_bi_loai(spec_src, pkg):
    """Các engine chạy trong venv con phải nằm ngoài bundle — đó là điều làm
    bản phân phối nhẹ đi, và là giả định mà `preflight`/`transcribe` dựa vào
    sau V74."""
    assert pkg in _goi_bi_exclude(spec_src)
