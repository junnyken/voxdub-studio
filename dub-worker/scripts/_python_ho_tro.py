"""Chọn đúng phiên bản Python cho các script cài đặt (V80).

Người dùng báo (ảnh chụp màn hình 2026-08-19): cài giọng VieNeu chết ở
``failed-wheel-build-for-install ... kaldi-native-fbank``. Nhìn traceback thì
tiến trình đang chạy là **Python 3.14** — các gói ONNX/ASR chưa có wheel cho
3.14 nên pip quay ra build từ mã nguồn và gãy.

Tệp .bat ĐÃ thử ``py -3.12`` trước rồi mới tới ``py``, nhưng chuỗi đó không
đủ trong hai cảnh có thật:

1. Máy có 3.12 nhưng ``py -3.12`` không tìm ra (cài bằng Python Install
   Manager kiểu ``pythoncore-3.14-64``, hoặc cài sau khi đã chạy .bat lần
   đầu) → rơi xuống ``py`` = bản mới nhất.
2. Lần chạy trước đã tạo venv bằng 3.14. Lần sau dù chạy đúng 3.12 thì
   ``step_venv`` vẫn "venv đã có — bỏ qua" và tiếp tục cài vào venv hỏng.

Nên phần kiểm phải nằm trong CHÍNH script cài, không thể phó mặc cho .bat.
"""
import os
import shutil
import subprocess
import sys

#: Khoảng bản Python mà toàn bộ phụ thuộc (faster-whisper, vieneu,
#: funasr...) đều có wheel dựng sẵn. Ngoài khoảng này là pip đi build từ mã
#: nguồn — cần Visual C++ Build Tools, và gần như luôn gãy trên máy người
#: dùng cuối.
TOI_THIEU = (3, 10)
TOI_DA = (3, 12)


def _ban_nay_ok(major_minor=None) -> bool:
    v = major_minor or sys.version_info[:2]
    return TOI_THIEU <= tuple(v) <= TOI_DA


def _tim_python_khac() -> str:
    """Đường dẫn một Python được hỗ trợ trên máy, hoặc "" nếu không có."""
    ung_vien = []
    for minor in range(TOI_DA[1], TOI_THIEU[1] - 1, -1):
        nhan = f"3.{minor}"
        if os.name == "nt":
            ung_vien.append(["py", f"-{nhan}"])
        ung_vien.append([f"python{nhan}"])
    for cmd in ung_vien:
        exe = cmd[0] if os.path.isabs(cmd[0]) else shutil.which(cmd[0])
        if not exe:
            continue
        try:
            out = subprocess.run([*cmd, "-c",
                                  "import sys;print(sys.executable)"],
                                 capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        duong_dan = (out.stdout or "").strip().splitlines()
        if out.returncode == 0 and duong_dan and os.path.isfile(duong_dan[-1]):
            return duong_dan[-1]
    return ""


def bao_dam_python_ho_tro() -> None:
    """Đang chạy bản Python không hỗ trợ thì tự chạy lại bằng bản đúng.

    Không tìm được bản nào thì dừng với lời chỉ dẫn — dừng sớm ở đây tốt hơn
    nhiều so với chết giữa lúc pip build wheel (thông báo lỗi ở đó dài mấy
    chục dòng và không nói được người dùng phải làm gì).
    """
    if _ban_nay_ok():
        return

    dang = f"{sys.version_info[0]}.{sys.version_info[1]}"
    khac = _tim_python_khac()
    if khac:
        print(f"[setup] Python {dang} chưa có thư viện dựng sẵn — chạy lại "
              f"bằng {khac}", flush=True)
        ket_qua = subprocess.run([khac, os.path.abspath(sys.argv[0]),
                                  *sys.argv[1:]])
        raise SystemExit(ket_qua.returncode)

    raise SystemExit(
        f"!! Máy đang dùng Python {dang}, nhưng bộ cài cần Python "
        f"{TOI_THIEU[0]}.{TOI_THIEU[1]}–{TOI_DA[0]}.{TOI_DA[1]} (các thư "
        "viện chưa có bản dựng sẵn cho Python mới hơn, cài sẽ gãy giữa "
        "chừng).\n"
        "   Cách xử lý: cài Python 3.12 từ python.org (nhớ tick 'Add "
        "python.exe to PATH'), rồi đúp chuột lại tệp .bat này.")


def venv_dung_python_ho_tro(venv_python: str) -> bool:
    """venv đã có được tạo bằng bản Python hỗ trợ hay không.

    Venv tạo bằng 3.14 từ lần chạy trước là thứ làm mọi lần cài SAU đó cũng
    hỏng, dù người dùng đã cài thêm 3.12 — vì bước tạo venv thấy thư mục có
    sẵn nên bỏ qua.
    """
    if not os.path.isfile(venv_python):
        return False
    try:
        out = subprocess.run(
            [venv_python, "-c",
             "import sys;print(sys.version_info[0], sys.version_info[1])"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    if out.returncode != 0:
        return False
    try:
        major, minor = (int(x) for x in out.stdout.split()[:2])
    except (ValueError, IndexError):
        return False
    return _ban_nay_ok((major, minor))
