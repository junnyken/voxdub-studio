"""Không worker nào được chết vì một tham số nó chưa biết (mini-spec C53).

Lỗi thật, chủ dự án gặp ngày 28/08 khi chạy v3.16.0: tiến trình cha gửi
`--ram-trong-gb 1.77` xuống một `asr_whisper_worker.py` bản CŨ; argparse gặp
tham số lạ liền `sys.exit(2)`, và **cả lượt lồng tiếng chết** — vì một tính
năng chỉ để chọn model cho khéo.

Cả hai gói phát hành đều chứa worker mới nên KHÔNG tái hiện được vì sao máy đó
chạy bản cũ. Nhưng cách chữa đúng không phải truy cho ra, mà là làm cho hợp
đồng cha–con không thể gãy kiểu đó nữa. Toàn bộ 9 worker của dự án đều dùng
`parse_args()`, tức đều có sẵn cùng một quả mìn.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORKERS = [
    "autodub/speech/asr_whisper_worker.py",
    "autodub/speech/asr_paraformer_worker.py",
    "autodub/speech/align_whisper_worker.py",
    "autodub/speech/diarize_worker.py",
    "autodub/speech/tts/vieneu_worker.py",
    "autodub/media/text_regions_worker.py",
    "autodub/media/demucs_worker.py",
    "autodub/media/lipsync_worker.py",
    "autodub/text/translate_local_worker.py",
]


@pytest.mark.parametrize("duong_dan", WORKERS)
def test_worker_khong_dung_parse_args_tran(duong_dan):
    src = open(os.path.join(GOC, duong_dan), encoding="utf-8").read()
    assert "parser.parse_args()" not in src, (
        f"{duong_dan} còn dùng parse_args() — cha bản mới hơn gửi một tham số "
        "lạ là worker này chết, kéo theo cả lượt chạy")
    assert "parse_known_args" in src


@pytest.mark.parametrize("duong_dan", WORKERS)
def test_bo_qua_thi_phai_NOI_RA(duong_dan):
    """Bỏ qua im lặng là lớp lỗi #1 của dự án (except rỗng sống nhiều tháng)."""
    src = open(os.path.join(GOC, duong_dan), encoding="utf-8").read()
    assert "Bỏ qua tham số không nhận ra" in src


def test_chay_that_worker_voi_tham_so_la_KHONG_thoat_ma_2():
    """Chạy thật: tham số lạ không được làm worker thoát bằng mã lỗi argparse."""
    kq = subprocess.run(
        [sys.executable, os.path.join(GOC, "autodub/speech/asr_whisper_worker.py"),
         "--audio", "khong-co.wav", "--tham-so-chua-ton-tai", "9"],
        capture_output=True, text=True, timeout=120, errors="replace")
    duoi = kq.stdout + kq.stderr
    assert "unrecognized arguments" not in duoi
    assert kq.returncode != 2, "vẫn thoát bằng mã lỗi của argparse"
    assert "Bỏ qua tham số không nhận ra" in duoi


def test_ram_doc_duoc_tu_bien_moi_truong():
    """Đường mới: cha gửi RAM qua biến môi trường, worker cũ bỏ qua trong im
    lặng nên không bao giờ gãy vì chuyện này nữa."""
    src = open(os.path.join(GOC, "autodub/speech/asr_whisper_worker.py"),
               encoding="utf-8").read()
    assert 'os.environ.get("VOXDUB_RAM_TRONG_GB"' in src
    cha = open(os.path.join(GOC, "autodub/speech/transcriber.py"),
               encoding="utf-8").read()
    assert 'moi_truong["VOXDUB_RAM_TRONG_GB"]' in cha
