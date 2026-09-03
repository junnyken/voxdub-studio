"""Worker diarization phải truyền access token đúng tên tham số của pyannote.

pyannote đổi tên tham số giữa 3.1.x (`use_auth_token`) và 4.x (`token`), và
không bản nào có `**kwargs`. Truyền nhầm là TypeError ngay lúc gọi, rồi bị
`except Exception` ở chỗ gọi biến thành "Không nạp được model diarization" —
đọc y như lỗi thiếu quyền truy cập, nên người gặp sẽ đi kiểm token và user
agreement, đúng hai thứ không hỏng.
"""
from __future__ import annotations

import json
import os
import subprocess

import pytest

from autodub.speech.diarize_worker import _token_kwarg

_WORKER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "autodub", "speech", "diarize_worker.py")


def test_chon_use_auth_token_cho_pyannote_31():
    def from_pretrained(checkpoint, hparams_file=None, use_auth_token=None):
        ...

    assert _token_kwarg(from_pretrained) == "use_auth_token"


def test_chon_token_cho_pyannote_4x():
    def from_pretrained(checkpoint, revision=None, hparams_file=None,
                        subfolder=None, token=None, cache_dir=None):
        ...

    assert _token_kwarg(from_pretrained) == "token"


def test_ham_khong_doc_duoc_chu_ky_thi_doan_theo_dong_moi():
    # Hàm dựng từ C (built-in) thường không lấy được signature — không được
    # để nguyên đó mà nổ, cứ đoán theo dòng phiên bản đang cài mới nhất.
    assert _token_kwarg(print) in ("token", "use_auth_token")


def test_ten_tham_so_chon_ra_goi_duoc_that():
    """Chốt bằng lời gọi thật, không chỉ so chuỗi.

    So chuỗi thôi thì vẫn lọt trường hợp tên đúng mà vị trí/cách truyền sai.
    """
    ghi_nhan = {}

    def from_pretrained(checkpoint, token=None):
        ghi_nhan["token"] = token
        return "pipeline"

    ket_qua = from_pretrained("pyannote/speaker-diarization-3.1",
                              **{_token_kwarg(from_pretrained): "hf_abc"})
    assert ket_qua == "pipeline"
    assert ghi_nhan["token"] == "hf_abc"


def _python_venv_diar() -> str | None:
    """Trình thông dịch của `.venv-diar`, hoặc None nếu chưa cài."""
    try:
        from autodub.config import Settings
        duong_dan = Settings.load().diarization_venv_python_path()
    except Exception:  # noqa: BLE001 — không đọc được cấu hình thì coi như chưa cài
        return None
    return duong_dan if os.path.isfile(duong_dan) else None


def test_ban_pyannote_dang_cai_thuc_su_nhan_ten_nay():
    """Regression thật, chạy TRONG `.venv-diar` — nơi pyannote thật sự nằm.

    C56: bản trước gọi `importorskip("pyannote.audio")`, tức hỏi VENV CHÍNH.
    Mà pyannote theo thiết kế CHỈ nằm trong `.venv-diar` (chính docstring cũ
    cũng viết vậy), nên test này **chưa từng chạy ở bất kỳ máy nào** — kể cả
    máy vừa cài xong diarization. Nó canh đúng ca đã CHẾT thật (pyannote 4.x
    đổi `use_auth_token` → `token`), mà lại canh trong một căn phòng trống.

    Nay chạy chính `_token_kwarg` của worker bên trong `.venv-diar` rồi đối
    chiếu với signature thật — đúng thứ xảy ra lúc chạy production. Worker chỉ
    import thư viện chuẩn ở tầng module nên nạp được bằng đường dẫn tệp, không
    cần cả gói `autodub` có mặt trong venv đó.
    """
    py = _python_venv_diar()
    if py is None:
        pytest.skip("chưa cài .venv-diar (scripts/setup_diarization.py)")

    ma = (
        "import importlib.util, inspect, json\n"
        f"spec = importlib.util.spec_from_file_location('dw', {_WORKER!r})\n"
        "dw = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(dw)\n"
        "from pyannote.audio import Pipeline\n"
        "ten = dw._token_kwarg(Pipeline.from_pretrained)\n"
        "print(json.dumps({'ten': ten, 'co_that': ten in "
        "inspect.signature(Pipeline.from_pretrained).parameters}))\n"
    )
    ra = subprocess.run([py, "-c", ma], capture_output=True, text=True,
                        timeout=300)
    if ra.returncode != 0:
        pytest.skip(f"không chạy được pyannote trong .venv-diar: "
                    f"{ra.stderr.strip()[-200:]}")
    data = json.loads(ra.stdout.strip().splitlines()[-1])
    assert data["co_that"], (
        f"worker sẽ truyền {data['ten']!r} nhưng pyannote đang cài KHÔNG có "
        "tham số đó — diarization sẽ chết ngay ở bước nạp model, và lời báo "
        "hiện ra là 'Không nạp được model' (đọc y như thiếu quyền truy cập)")
