"""Cài FFmpeg cho VoxDub — tải bản đầy đủ về thư mục bin/ cạnh ứng dụng.

Chạy 1 lần:  py scripts/setup_ffmpeg.py   (hoặc đúp chuột tệp .bat cùng tên)

Vì sao có tệp này (mini-spec V82): FFmpeg là thành phần **bắt buộc** — thiếu
nó thì không đọc được video, không tải được YouTube, không chép lời được. Vậy
mà nó là thứ DUY NHẤT trong nhóm bắt buộc không có tệp .bat để đúp chuột,
trong khi Whisper/VieNeu/Paraformer/Douyin đều có. Người dùng mở thư mục ứng
dụng ra, thấy 4 tệp .bat, không tệp nào nói về FFmpeg — rồi phải tự đi tìm.

Bản tải về là "gpl" của BtbN: có sẵn libass, tức là ghi được phụ đề vào hình.
Bản "essentials" trên mạng thiếu libass, cài xong vẫn hỏng ở bước ghi phụ đề
mà không nói vì sao.
"""
import io
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(PROJECT_ROOT, "bin")

_URL = ("https://github.com/BtbN/ffmpeg-builds/releases/download/latest/"
        "ffmpeg-master-latest-win64-gpl.zip")
_CAN_CO = ("ffmpeg.exe", "ffprobe.exe") if os.name == "nt" else ("ffmpeg", "ffprobe")


def log(msg: str) -> None:
    print(f"[setup-ffmpeg] {msg}", flush=True)


def da_co() -> bool:
    return all(os.path.isfile(os.path.join(BIN_DIR, t)) for t in _CAN_CO)


def tren_may() -> bool:
    return all(shutil.which(t.replace(".exe", "")) for t in _CAN_CO)


def tai_ve() -> bytes:
    log(f"tải FFmpeg (~80 MB) từ {_URL.split('/')[2]} ...")
    req = urllib.request.Request(_URL, headers={"User-Agent": "VoxDub-Setup/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        tong = int(resp.headers.get("Content-Length", 0))
        buf = io.BytesIO()
        da_tai = 0
        moc = 0
        while True:
            khuc = resp.read(65536)
            if not khuc:
                break
            buf.write(khuc)
            da_tai += len(khuc)
            if tong:
                phan_tram = da_tai * 100 // tong
                if phan_tram >= moc + 10:
                    moc = phan_tram - phan_tram % 10
                    log(f"... {moc}%")
        return buf.getvalue()


def giai_nen(du_lieu: bytes) -> None:
    os.makedirs(BIN_DIR, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(du_lieu)) as z:
        for ten in z.namelist():
            co_ban = os.path.basename(ten)
            # Chỉ lấy đúng 2 tệp cần dùng: gói đầy đủ còn kèm ffplay và cả
            # thư mục doc/lib, chép hết là phình thư mục ứng dụng vô ích.
            if co_ban in _CAN_CO and "/bin/" in ten.replace("\\", "/"):
                log(f"chép {co_ban}")
                with z.open(ten) as src, \
                        open(os.path.join(BIN_DIR, co_ban), "wb") as dst:
                    shutil.copyfileobj(src, dst)
    for ten in _CAN_CO:
        duong = os.path.join(BIN_DIR, ten)
        if not os.path.isfile(duong):
            raise SystemExit(f"!! gói tải về thiếu {ten} — thử lại sau ít phút")
        if os.name != "nt":
            os.chmod(duong, 0o755)


def kiem_lai() -> None:
    """Có ghi được phụ đề vào hình không (libass) — bản rút gọn thì không."""
    ffmpeg = os.path.join(BIN_DIR, _CAN_CO[0])
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-filters"],
                             capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError) as e:
        raise SystemExit(f"!! không chạy được ffmpeg vừa tải: {e}")
    if " subtitles " not in out:
        log("!! bản vừa tải thiếu bộ ghi phụ đề (libass) — báo lại cho nhóm "
            "phát triển")
    else:
        log("kiểm tra: ghi được phụ đề vào hình (libass) — OK")


def main() -> None:
    log("Cài FFmpeg cho VoxDub — công cụ bắt buộc để đọc và cắt video")
    if da_co():
        log(f"đã có sẵn trong {BIN_DIR} — bỏ qua")
        kiem_lai()
        log("XONG — mở lại ứng dụng là dùng được.")
        return
    if tren_may():
        log("máy đã có FFmpeg trên đường dẫn hệ thống — không cần tải")
        log("XONG.")
        return
    giai_nen(tai_ve())
    kiem_lai()
    log(f"XONG — đã đặt vào {BIN_DIR}. Mở lại ứng dụng là dùng được.")


if __name__ == "__main__":
    main()
