"""Worker diarization phải truyền access token đúng tên tham số của pyannote.

pyannote đổi tên tham số giữa 3.1.x (`use_auth_token`) và 4.x (`token`), và
không bản nào có `**kwargs`. Truyền nhầm là TypeError ngay lúc gọi, rồi bị
`except Exception` ở chỗ gọi biến thành "Không nạp được model diarization" —
đọc y như lỗi thiếu quyền truy cập, nên người gặp sẽ đi kiểm token và user
agreement, đúng hai thứ không hỏng.
"""
from __future__ import annotations

import pytest

from autodub.speech.diarize_worker import _token_kwarg


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


def test_ban_pyannote_dang_cai_thuc_su_nhan_ten_nay():
    """Regression thật với pyannote đang cài (bỏ qua nếu chưa cài).

    Đây là ca đã CHẾT trước khi sửa: `.venv-diar` cài hôm nay ra 4.0.7, mà mã
    cũ truyền `use_auth_token=` nên diarization hỏng ngay từ bước nạp model.
    """
    Pipeline = pytest.importorskip(
        "pyannote.audio", reason="pyannote chỉ có trong .venv-diar").Pipeline

    ten = _token_kwarg(Pipeline.from_pretrained)
    import inspect
    assert ten in inspect.signature(Pipeline.from_pretrained).parameters
