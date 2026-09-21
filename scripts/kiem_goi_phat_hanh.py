"""Cổng kiểm BẢN ĐÓNG GÓI: chạy dub thật bằng chính `VoxDub.exe` đã đóng gói.

Mini-spec I0-FDE (I0-D cài mới · I0-E nâng cấp cạnh bên · I0-F dub bằng gói).

Khác `scripts/kiem_chay_that.py` ở đúng MỘT điểm, và đó là cả lý do tồn tại:
bộ canh cũ chạy `python -m autodub.cli` — tức là **mã nguồn**. Nó không chạm
tới những thứ chỉ bản đóng gói mới có:

* tệp worker có thật sự nằm trong gói không (V80: `asr_whisper_worker.py`
  thiếu khỏi `datas` qua HÀNG CHỤC bản phát hành mà mọi cổng kiểm đều xanh);
* `sys._MEIPASS` có trỏ đúng không;
* bản cài mới có mượn nhầm tệp của cây mã nguồn / bản cũ / cache của runner
  không (một lượt "xanh" nhờ mượn không chứng minh gì cho người tải bản zip);
* nâng cấp cạnh bên có dùng lại được `.venv-*`/`models/` của bản cũ không, và
  có làm hỏng bản cũ không.

Ba chế độ::

    python scripts/kiem_goi_phat_hanh.py --che-do sach     --zip … --goc-thu …
    python scripts/kiem_goi_phat_hanh.py --che-do nang-cap --zip … --goc-thu …
    python scripts/kiem_goi_phat_hanh.py --che-do am-tinh  --zip … --goc-thu …

Mã thoát: 0 đạt · 1 HỎNG · 2 BỊ CHẶN (thiếu điều kiện để kết luận — vẫn là
đỏ, không được đọc thành xanh).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

GOC_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC_REPO))
sys.path.insert(0, str(GOC_REPO / "scripts"))

# DÙNG LẠI bộ soi của cổng kiểm mã nguồn — không viết định nghĩa "câm" hay
# "lệch thời lượng" lần thứ hai. Hai định nghĩa khác nhau cho cùng một câu
# hỏi là cách chắc chắn nhất để một ngày nào đó chúng nói ngược nhau.
from kiem_chay_that import (  # noqa: E402
    CAU_DICH_TAY, _ffprobe, _muc_am_trung_binh, _thoi_luong,
    _viet_ban_dich_tay,
)

from autodub.bang_chung import (  # noqa: E402
    bam_tep, che_bi_mat, duong_ngoai_vung, manifest_thu_muc, so_sanh_manifest,
    trong_vung,
)

for _luong in (sys.stdout, sys.stderr):
    try:
        _luong.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


#: Token GIẢ của hộp thử nâng cấp. Phải là chuỗi không thể trùng ngẫu nhiên:
#: cuối lượt kiểm sẽ quét TOÀN BỘ tệp bằng chứng tìm đúng chuỗi này, thấy là
#: hỏng (bằng chứng tải lên CI là artifact ai cũng tải được).
TOKEN_GIA = "vox_token_gia_I0E_KHONG_DUOC_LO_9f3c1d"


#: Cờ dòng lệnh của `--tu-kiem-goi` mà giá trị là ĐƯỜNG DẪN. Đưa cho exe
#: dạng tương đối là mất bằng chứng (xem chốt trong :func:`chay_exe`).
CO_MANG_DUONG_DAN = ("--bang-chung", "--video", "--thu-muc-ra", "--resume-dir")


class Hong(Exception):
    """Một mục kiểm không đạt."""


class BiChan(Exception):
    """Không đủ điều kiện để KẾT LUẬN — không phải đạt, cũng không phải hỏng."""


def log(msg: str) -> None:
    print(f"[goi] {msg}", flush=True)


# --------------------------------------------------------------- hộp cát --

def giai_nen(tep_zip: Path, dich: Path) -> Path:
    """Giải nén gói phát hành vào ``dich`` và trả về thư mục chứa VoxDub.exe.

    Hai dạng zip cùng tồn tại trong dự án và chúng KHÁC nhau ở gốc:

    * `VoxDub-Studio-<ref>-win64.zip` (release.yml, `Compress-Archive
      dist/VoxDub/*`) — tệp nằm ngay gốc zip. **Đây là bản người dùng tải.**
    * `dist/VoxDub-Studio-v<ver>.zip` (build_exe.py) — bọc trong thư mục
      `VoxDub Studio/`.

    Nhận cả hai, rồi tự tìm `VoxDub.exe`: đoán sai gốc zip là kiểm nhầm một
    thư mục rỗng mà vẫn báo xanh.
    """
    dich.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(tep_zip) as zf:
        zf.extractall(dich)
    ung_vien = [p for p in dich.rglob("VoxDub.exe")]
    if not ung_vien:
        raise Hong(f"Giải nén {tep_zip.name} xong nhưng KHÔNG có VoxDub.exe "
                   f"ở đâu dưới {dich} — gói phát hành không dùng được.")
    return min(ung_vien, key=lambda p: len(p.parts)).parent


def chup_moi_truong(thu_muc_cai: Path) -> dict:
    """Ảnh chụp môi trường chạy — che mọi biến mang tên bí mật."""
    return che_bi_mat({
        "he_dieu_hanh": f"{os.name} · {sys.platform}",
        "python_lai": sys.version.split()[0],
        "thu_muc_cai": str(thu_muc_cai),
        "thu_muc_cha": str(thu_muc_cai.parent),
        "anh_em_cua_thu_muc_cai": sorted(
            p.name for p in thu_muc_cai.parent.iterdir() if p.is_dir()),
        "ffmpeg_he_thong": shutil.which("ffmpeg") or "",
        "ffprobe_he_thong": shutil.which("ffprobe") or "",
        "bien_moi_truong": {k: v for k, v in sorted(os.environ.items())
                            if k.upper().startswith(
                                ("VOXDUB", "AUTODUB", "TRANSLATE", "WHISPER",
                                 "ASR_", "VIENEU", "HF_", "PYTHON"))},
        "goc_repo": str(GOC_REPO),
    })


def kiem_hop_cat_sach(thu_muc_cai: Path) -> list[str]:
    """Chứng minh hộp cát cài mới KHÔNG có gì để mượn (I0-D).

    Trả về danh sách dòng báo cáo; ném :class:`Hong` khi còn đường mượn.
    """
    bao_cao = []
    cha = thu_muc_cai.parent
    anh_em = [p for p in cha.iterdir() if p.is_dir() and p != thu_muc_cai]
    if anh_em:
        raise Hong(f"Thư mục cha {cha} còn {len(anh_em)} thư mục cạnh bên "
                   f"({[p.name for p in anh_em][:5]}) — bản 'cài mới' có thể "
                   "dùng lại bộ máy của chúng, nên lượt kiểm này không chứng "
                   "minh được gì về máy người dùng mới.")
    bao_cao.append(f"thư mục cha {cha.name}: không có bản cài nào cạnh bên")

    for ten in (".venv-whisper", ".venv-vieneu", ".venv-asr", ".venv-gpu"):
        if (thu_muc_cai / ten).exists():
            raise Hong(f"Gói phát hành chứa sẵn {ten} — bản tải về của người "
                       "dùng không có thứ đó.")
    if trong_vung(str(thu_muc_cai), str(GOC_REPO)):
        raise Hong(f"Hộp cát {thu_muc_cai} nằm TRONG cây mã nguồn "
                   f"{GOC_REPO} — mọi kết luận sẽ bị nhiễm bởi tệp mã nguồn.")
    bao_cao.append("hộp cát nằm ngoài cây mã nguồn, không có .venv-* sẵn")
    return bao_cao


# ------------------------------------------------------------ cài bộ máy --

#: Bộ máy cần cho đường kiểm tối thiểu: nghe (Whisper) + giọng đọc (VieNeu).
#: Demucs/OCR/lipsync KHÔNG cần — `bg_mode=none`, `subtitle_mode=none`.
BO_MAY_CAN = (
    ("whisper", "Cai dat Whisper ASR.bat", "setup_whisper.py",
     ".venv-whisper", "models/whisper/installed_ok.json"),
    ("vieneu", "Cai dat giong VieNeu.bat", "setup_vieneu.py",
     ".venv-vieneu", "models/vieneu/installed_ok.json"),
)


def cai_bo_may(thu_muc_cai: Path, cach: str, timeout_s: int) -> list[str]:
    """Cài Whisper + VieNeu vào ĐÚNG thư mục cài, theo đường người dùng đi.

    ``cach="bat"`` chạy chính tệp `.bat` được đóng gói (đường thật của người
    dùng: đúp chuột). Lưu ý đã đo: tệp `.bat` kết thúc bằng `pause` và KHÔNG
    trả mã lỗi ra ngoài — nên ở đây bắt buộc phải tự kiểm dấu `installed_ok`
    sau khi chạy, không được tin mã thoát.
    """
    bao_cao = []
    for ten, bat, script, venv, dau in BO_MAY_CAN:
        dich_dau = thu_muc_cai / dau
        if dich_dau.is_file():
            bao_cao.append(f"{ten}: đã có sẵn ({dau})")
            continue
        bat_dau = time.time()
        if cach == "bat":
            tep_bat = thu_muc_cai / bat
            if not tep_bat.is_file():
                raise Hong(f"Gói phát hành THIẾU '{bat}' — người dùng không "
                           f"có cách nào cài {ten} bằng đúp chuột.")
            lenh = ["cmd", "/c", str(tep_bat)]
        else:
            tep_py = thu_muc_cai / "scripts" / script
            if not tep_py.is_file():
                raise Hong(f"Gói phát hành THIẾU scripts/{script}.")
            lenh = [sys.executable, str(tep_py)]
        log(f"cài {ten} bằng {'tệp .bat' if cach == 'bat' else script} …")
        with open(os.devnull) as nul:   # `pause` trong .bat: stdin rỗng = qua
            kq = subprocess.run(lenh, cwd=str(thu_muc_cai), stdin=nul,
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=timeout_s)
        giay = time.time() - bat_dau
        if not dich_dau.is_file():
            duoi = ((kq.stdout or "") + (kq.stderr or ""))[-1500:]
            raise Hong(
                f"Cài {ten} xong nhưng KHÔNG có {dau} trong {thu_muc_cai} — "
                f"trên máy người dùng mới đây chính là ca 'cài mãi không "
                f"xong'. Mã thoát {kq.returncode}, 1500 ký tự cuối:\n{duoi}")
        if not (thu_muc_cai / venv).is_dir():
            raise Hong(f"Có dấu {dau} nhưng KHÔNG có {venv} — bộ máy được ghi "
                       "nhận là cài xong trong khi môi trường chạy không tồn "
                       "tại.")
        bao_cao.append(f"{ten}: cài xong trong thư mục cài ({giay:.0f}s)")
    return bao_cao


# ------------------------------------------------------------- chạy .exe --

def chay_exe(exe: Path, tham_so: list[str], bang_chung: Path,
             timeout_s: int, moi_truong: dict | None = None) -> tuple:
    """Chạy `VoxDub.exe` và trả ``(CompletedProcess, result.json đã đọc)``.

    Bản `.exe` dựng `console=False` nên KHÔNG có stdout/stderr thật — mọi kết
    luận phải đọc từ `result.json` mà chính exe ghi ra. Vẫn hứng ống ra tệp
    để khi exe chết trước lúc ghi được gì thì còn dấu vết.
    """
    # CHỐT ĐƯỜNG CHẠY. Cả lý do tồn tại của cổng này là "chạy bản đóng gói,
    # không chạy mã nguồn" — nên nếu một ngày nào đó ai đó tiện tay đổi sang
    # `python -m autodub.cli` cho nhanh thì phải ĐỎ ngay tại đây, chứ không
    # phải xanh êm rồi phát hành một bản chưa ai chạy thử.
    if exe.name.lower() != "voxdub.exe":
        raise Hong(f"Cổng kiểm bản đóng gói chỉ được chạy VoxDub.exe, "
                   f"nhận được {exe.name!r}.")
    if trong_vung(str(exe), str(GOC_REPO)):
        raise Hong(f"{exe} nằm trong cây mã nguồn {GOC_REPO} — đó là bản "
                   "dựng tại chỗ, không phải gói người dùng tải về.")
    if not exe.is_file():
        raise Hong(f"Không có {exe} — gói phát hành thiếu tệp chạy.")

    # CHỐT ĐƯỜNG DẪN TUYỆT ĐỐI. Bộ lái chạy ở gốc repo, còn `.exe` được chạy
    # với `cwd` = thư mục cài trong hộp cát — hai thư mục làm việc KHÁC nhau.
    # Đưa đường dẫn tương đối qua ranh giới đó thì exe vẫn chạy đúng, vẫn trả
    # đúng mã thoát, nhưng ghi bằng chứng vào TRONG HỘP CÁT rồi biến mất cùng
    # runner — và bộ lái đọc phải thư mục rỗng nên kết luận sai hẳn về sản
    # phẩm. Đã xảy ra thật: run 35614850573, bước I0-D đỏ với câu "bản đóng
    # gói KHÔNG báo thiếu" trong khi nó báo thiếu hoàn toàn đúng.
    if not bang_chung.is_absolute():
        raise Hong(f"Thư mục bằng chứng phải là đường dẫn tuyệt đối, nhận "
                   f"được {bang_chung!s}.")
    for i, t in enumerate(tham_so):
        if t in CO_MANG_DUONG_DAN:
            gia_tri = tham_so[i + 1] if i + 1 < len(tham_so) else ""
            if not os.path.isabs(gia_tri):
                raise Hong(
                    f"Tham số {t} đưa cho VoxDub.exe là đường dẫn TƯƠNG ĐỐI "
                    f"({gia_tri!r}). exe chạy ở {exe.parent} chứ không phải "
                    f"{os.getcwd()}, nên nó sẽ hiểu ra một chỗ khác — và bằng "
                    "chứng sẽ biến mất không một tiếng động.")

    bang_chung.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    # Tiến trình con ghi nhật ký tiếng Việt ra ỐNG (không phải console) nên
    # Python rơi về bảng mã của máy (cp1252 trên Windows) rồi bộ lái giải mã
    # bằng UTF-8 → chữ vỡ. Cùng gốc với D1f; đặt trước khi exe khởi động mới
    # có tác dụng.
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.update(moi_truong or {})
    bat_dau = time.time()
    try:
        kq = subprocess.run([str(exe), *tham_so], cwd=str(exe.parent), env=env,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise Hong(f"Quá {timeout_s}s mà VoxDub.exe chưa xong "
                   f"({' '.join(tham_so[:4])}…) — giai đoạn hỏng: timeout.")
    (bang_chung / "app.stdout.log").write_text(kq.stdout or "",
                                               encoding="utf-8")
    (bang_chung / "app.stderr.log").write_text(kq.stderr or "",
                                               encoding="utf-8")
    ket = {}
    tep_ket = bang_chung / "result.json"
    if tep_ket.is_file():
        ket = json.loads(tep_ket.read_text(encoding="utf-8"))
    log(f"  exe → mã {kq.returncode} sau {time.time() - bat_dau:.0f}s "
        f"({ket.get('giai_doan_hong') or 'không có giai đoạn hỏng'})")
    return kq, ket


def _doi_ma(kq, ket: dict, viec: str) -> dict:
    if kq.returncode != 0:
        loi = ket.get("loi") or ("(exe không ghi được result.json — chết "
                                 "trước khi khởi động xong)")
        raise Hong(f"{viec}: VoxDub.exe trả mã {kq.returncode}, giai đoạn "
                   f"hỏng = {ket.get('giai_doan_hong')!r}. Lỗi: {loi}")
    return ket


# ----------------------------------------------------- soi đường chạy thật --

#: Ổ đĩa Windows ở đầu chuỗi (`D:\\…` hoặc `D:/…`). Bộ lái chạy trên Windows
#: nhưng bằng chứng hay được đọc lại trên Linux, nên phải nhận cả hai kiểu.
_O_DIA = re.compile(r"^[A-Za-z]:[\\/]")


def la_duong_dan(chuoi: str) -> bool:
    r"""Chuỗi này có phải ĐƯỜNG DẪN không — hay chỉ là cờ/bộ lọc của ffmpeg?

    Bản đầu hỏi *"có dấu phân cách hoặc dấu hai chấm không"*, và dấu hai chấm
    là chỗ chết: `-b:v`, `-c:v`, `color=black:s=256x256:d=0.1` đều bị coi là
    tệp (đo được ở run 35618355094). Kêu nhầm ở một bộ canh còn tệ hơn bỏ
    sót — bỏ sót thì mất một lần phát hiện, kêu nhầm thì **mất cả cái chốt**,
    vì lần sau người đọc sẽ bỏ qua nó (bài học D5, commit 1a21d34).

    Nên chỉ nhận ba hình dạng, và **không** nhận dấu hai chấm làm dấu hiệu:

    * tuyệt đối kiểu Windows (`D:\…`) hoặc kiểu POSIX/UNC (`/…`, `\\…`);
    * có dấu phân cách thư mục ở đâu đó (kể cả tương đối: `..\..\autodub\x.py`
      — đường leo ra cây mã nguồn vẫn phải bị bắt);
    * cờ (`-…`) thì KHÔNG bao giờ là đường dẫn.

    Chuỗi lọt lưới (vd `scale=trunc(iw/2)*2`) không gây kêu nhầm: nó tương
    đối, nên được giải theo `cwd` của chính lượt gọi — mà `cwd` đó luôn nằm
    trong hộp cát.
    """
    s = (chuoi or "").strip()
    if not s or s.startswith("-"):
        return False
    if _O_DIA.match(s) or s.startswith(("/", "\\")):
        return True
    return "/" in s or "\\" in s


def _giai_tuyet_doi(chuoi: str, cwd: str) -> str:
    """Đường dẫn tuyệt đối của ``chuoi``, giải theo ``cwd`` của LƯỢT GỌI đó.

    Không bao giờ được dùng `os.path.abspath()` trần ở đây: nó giải theo thư
    mục của **tiến trình đang soi** (bộ lái đứng ở gốc repo), nên mọi chuỗi
    tương đối — kể cả `-b:v` — đều "biến thành" tệp nằm trong cây mã nguồn.
    Đó đúng là cơ chế đã làm run 35618355094 đỏ oan.
    """
    s = (chuoi or "").strip()
    if not s:
        return ""
    if _O_DIA.match(s) or s.startswith(("/", "\\")):
        return os.path.normpath(s)
    if not cwd:
        return ""      # không biết giải theo đâu thì KHÔNG đoán bừa
    ngan = "\\" if ("\\" in cwd and "/" not in cwd) else "/"
    return os.path.normpath(cwd.rstrip("/\\") + ngan + s)


def _cac_duong_da_dung(bang_chung: Path, ket: dict) -> tuple[list[str], list[str]]:
    """``(đường dẫn đã giải tuyệt đối, chuỗi bị bỏ vì không phải đường dẫn)``.

    Trả về luôn phần BỊ BỎ để người đọc bằng chứng soi được bộ lọc này có
    đang giấu đi thứ đáng nhìn không — một bộ lọc không ai kiểm được thì
    chính nó là chỗ giấu lỗi.
    """
    duong: list[str] = []
    bo_qua: list[str] = []
    jsonl = bang_chung / "worker-launches.jsonl"
    if jsonl.is_file():
        for dong in jsonl.read_text(encoding="utf-8").splitlines():
            try:
                muc = json.loads(dong)
            except json.JSONDecodeError:
                continue
            cwd = str(muc.get("cwd") or "")
            for t in [muc.get("chuong_trinh", ""), *muc.get("tham_so", [])]:
                if not isinstance(t, str) or not t.strip():
                    continue
                if not la_duong_dan(t):
                    bo_qua.append(t)
                    continue
                giai = _giai_tuyet_doi(t, cwd)
                (duong if giai else bo_qua).append(giai or t)
    bo_may = ket.get("bo_may", {})
    for ten in ("vieneu", "whisper", "paraformer"):
        muc = bo_may.get(ten) or {}
        if muc.get("san_sang"):
            for t in (muc.get("python", ""), muc.get("thu_muc_model", "")):
                giai = _giai_tuyet_doi(t, "")
                if giai:
                    duong.append(giai)
    return duong, bo_qua


def kiem_duong_chay(bang_chung: Path, ket: dict, goc_cho_phep: list[str],
                    ffmpeg_he_thong: str) -> list[str]:
    """Mọi đường dẫn đã dùng phải nằm trong hộp cát (hoặc ngoại lệ đã khai).

    Đây là chốt chặn ca xanh-giả nguy hiểm nhất: bản đóng gói thiếu tệp nhưng
    lượt chạy vẫn xong vì mượn được của cây mã nguồn nằm cạnh trên máy CI.
    """
    duong, bo_qua = _cac_duong_da_dung(bang_chung, ket)
    # Ngoại lệ khai TƯỜNG MINH: ffmpeg/ffprobe của máy (thiết kế gói cho phép
    # — HUONG_DAN_CAI_DAT.md Bước 1 bảo người dùng cài bằng winget) và thư
    # mục hệ điều hành.
    ngoai_le = [str(Path(ffmpeg_he_thong).parent) if ffmpeg_he_thong else "",
                os.environ.get("SystemRoot", r"C:\Windows")]
    la = duong_ngoai_vung(duong, goc_cho_phep, ngoai_le)
    # HAI KHÁI NIỆM KHÁC NHAU, đừng gộp: "ngoài vùng cho phép" là mọi thứ
    # không nằm trong hộp cát (có thể chỉ là một thư mục hệ điều hành lạ);
    # "mượn cây mã nguồn" là nằm DƯỚI GỐC REPO — thứ mà bản người dùng tải
    # về không bao giờ có. Bản đầu tính cái sau bằng cái trước, nên gán nhãn
    # "mượn mã nguồn" cho cả cờ của ffmpeg (run 35618355094).
    tu_ma_nguon = [d for d in duong if trong_vung(d, str(GOC_REPO))]
    (bang_chung / "duong-da-dung.json").write_text(
        json.dumps(che_bi_mat({"tat_ca": sorted(set(duong)),
                               "ngoai_vung": sorted(set(la)),
                               "tu_cay_ma_nguon": sorted(set(tu_ma_nguon)),
                               "khong_phai_duong_dan": sorted(set(bo_qua)),
                               "goc_repo": str(GOC_REPO),
                               "goc_cho_phep": goc_cho_phep,
                               "ngoai_le": ngoai_le}),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    if tu_ma_nguon:
        raise Hong("Lượt chạy của bản ĐÓNG GÓI đã dùng tệp trong cây mã "
                   f"nguồn: {tu_ma_nguon[:5]} — bản người dùng tải về không "
                   "có cây mã nguồn nào cạnh bên, nên lượt xanh này là giả.")
    if la:
        raise Hong(f"Đường dẫn NGOÀI hộp cát bị dùng: {la[:5]} — "
                   f"gốc cho phép: {goc_cho_phep}")
    return [f"{len(set(duong))} đường dẫn đã dùng, tất cả trong hộp cát"]


# ------------------------------------------------------------ soi tệp ra --

def soi_video_ra(video_nguon: Path, video_ra: Path, bang_chung: Path) -> dict:
    """Soi tệp ra bằng ĐÚNG bộ đo của cổng kiểm mã nguồn (không định nghĩa lại)."""
    if not video_ra.is_file():
        raise Hong("Không có dubbed_video.mp4 — bản đóng gói đi qua được các "
                   "bước nhưng KHÔNG xuất được video.")
    tieng = _ffprobe("-select_streams", "a", "-show_entries",
                     "stream=codec_name", "-of", "default=nw=1:nk=1",
                     str(video_ra))
    muc = _muc_am_trung_binh(video_ra)
    dai_nguon, dai_ra = _thoi_luong(video_nguon), _thoi_luong(video_ra)
    do = {"duong_dan": str(video_ra), "byte": video_ra.stat().st_size,
          "sha256": bam_tep(str(video_ra)), "codec_tieng": tieng,
          "mean_volume_db": muc, "giay_ra": dai_ra, "giay_nguon": dai_nguon}
    (bang_chung / "output-probe.json").write_text(
        json.dumps(do, ensure_ascii=False, indent=2), encoding="utf-8")
    (bang_chung / "output-video.sha256").write_text(
        f"{do['sha256']}  dubbed_video.mp4\n", encoding="utf-8")
    # Giữ luôn tệp ra khi nó còn nhỏ: người đọc bằng chứng NGHE được mới kết
    # luận được "giọng đọc có ra hồn không" — thứ mà mean_volume không nói.
    # Quá cỡ thì thôi, đã có sha256 + số đo ở trên (giới hạn artifact của CI).
    if do["byte"] <= 50 << 20:
        shutil.copy2(video_ra, bang_chung / "output-video.mp4")

    if not tieng:
        raise Hong("Video ra KHÔNG có luồng tiếng — câm hoàn toàn trong khi "
                   "mọi bước đều báo thành công.")
    if muc is None:
        raise Hong("Không đo được mức âm của video ra.")
    if muc <= -70:
        raise Hong(f"Luồng tiếng CÂM (mean_volume {muc:.1f} dB).")
    if dai_nguon > 0 and abs(dai_ra - dai_nguon) / dai_nguon > 0.35:
        raise Hong(f"Thời lượng lệch quá nhiều: nguồn {dai_nguon:.1f}s, ra "
                   f"{dai_ra:.1f}s.")
    return do


# ------------------------------------------------------- một lượt dub gói --

def mot_luot_dub_bang_goi(exe: Path, video: Path, hop: Path, bang_chung: Path,
                          timeout_s: int, goc_cho_phep: list[str],
                          model_nghe: str = "tiny") -> dict:
    """I0-F: hai chặng dub bằng chính `.exe`, rồi soi tệp ra.

    Chặng 1 dừng ở dịch tay (đúng như cổng kiểm mã nguồn), chặng 2 chạy tiếp
    tới video xuất ra. Bản dịch tay do bộ lái ghi — giống hệt vai người dùng
    trong `kiem_chay_that.py`, và dùng lại chính hàm ghi của tệp đó.
    """
    bao_cao: list[str] = []
    thu_muc_ra = hop / "ra"
    thu_muc_ra.mkdir(parents=True, exist_ok=True)
    # Cùng lý do với cổng kiểm mã nguồn (release.yml): kiểm ĐƯỜNG CHẠY chứ
    # không chấm chất lượng nghe, và máy CI không có GPU. Đặt qua biến môi
    # trường nên `.env` của hộp thử không đè được (load_dotenv không override).
    moi_truong = {"WHISPER_MODEL": model_nghe}

    kq, ket = chay_exe(exe, ["--tu-kiem-goi", "--video", str(video),
                             "--thu-muc-ra", str(thu_muc_ra),
                             "--doi-bo-may", "whisper,vieneu",
                             "--bang-chung", str(bang_chung / "chang1")],
                       bang_chung / "chang1", timeout_s, moi_truong)
    _doi_ma(kq, ket, "chặng 1 (nghe + dừng ở dịch tay)")
    if ket.get("trang_thai_pipeline") != "translate_pending":
        raise Hong("Chặng 1 không dừng ở 'translate_pending' mà ở "
                   f"{ket.get('trang_thai_pipeline')!r} — đường dịch tay của "
                   "bản đóng gói không đi tới nơi.")
    work = Path(ket["thu_muc_lam_viec"])
    bao_cao.append(f"chặng 1 (gói): nghe xong, dừng đúng chỗ — {work.name}")

    goc_transcript = work / "data" / "transcript_original.json"
    if not goc_transcript.is_file():
        raise Hong(f"Không có {goc_transcript} sau chặng 1.")
    cau = json.loads(goc_transcript.read_text(encoding="utf-8"))
    if not cau:
        raise Hong("Bản chép lời RỖNG — bộ nghe trong bản đóng gói không "
                   "nghe ra câu nào.")
    _viet_ban_dich_tay(work, cau)
    bao_cao.append(f"đóng vai dịch tay: {len(cau)} câu "
                   f"({len(CAU_DICH_TAY)} câu mẫu, xoay vòng)")

    kq2, ket2 = chay_exe(exe, ["--tu-kiem-goi", "--video", str(video),
                               "--resume-dir", str(work),
                               "--doi-bo-may", "vieneu",
                               "--bang-chung", str(bang_chung / "chang2")],
                         bang_chung / "chang2", timeout_s, moi_truong)
    _doi_ma(kq2, ket2, "chặng 2 (giọng đọc + ghép video)")
    bao_cao.append(f"chặng 2 (gói): {ket2.get('trang_thai_pipeline')} sau "
                   f"{ket2.get('giay_chay')}s, "
                   f"{ket2.get('tien_trinh_con')} tiến trình con")

    do = soi_video_ra(video, Path(ket2.get("video_ra") or
                                  (work / "dubbed_video.mp4")), bang_chung)
    bao_cao.append(f"video ra: {do['byte'] // 1024} KB · tiếng="
                   f"{do['codec_tieng']} · {do['mean_volume_db']} dB · "
                   f"{do['giay_ra']:.1f}s (nguồn {do['giay_nguon']:.1f}s)")

    for ten, nguon in (("chang1", bang_chung / "chang1"),
                       ("chang2", bang_chung / "chang2")):
        bao_cao += [f"{ten}: {d}" for d in kiem_duong_chay(
            nguon, ket2 if ten == "chang2" else ket, goc_cho_phep,
            shutil.which("ffmpeg") or "")]

    # Nhật ký của chính app (ghi cạnh exe) là bằng chứng phía ứng dụng.
    nhat_ky = exe.parent / "logs" / "voxdub.log"
    if nhat_ky.is_file():
        shutil.copy2(nhat_ky, bang_chung / "voxdub.log")
        bao_cao.append("đã giữ lại logs/voxdub.log của bản đóng gói")
    (bang_chung / "result.json").write_text(
        json.dumps(che_bi_mat({"ket_qua": "dat", "giai_doan_hong": None,
                               "chang1": ket, "chang2": ket2,
                               "output_probe": do}),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return {"bao_cao": bao_cao, "probe": do, "chang2": ket2}


# ---------------------------------------------------------- ba chế độ kiểm --

def che_do_sach(args, bang_chung: Path) -> list[str]:
    """I0-D + I0-F: cài mới hoàn toàn, không có gì cạnh bên để mượn."""
    hop = Path(args.goc_thu) / "sach"
    if hop.exists():
        shutil.rmtree(hop, ignore_errors=True)
    cai = giai_nen(Path(args.zip), hop / "cha" / "VoxDub Studio")
    bao_cao = [f"giải nén gói vào {cai}"]
    bao_cao += kiem_hop_cat_sach(cai)
    (bang_chung / "environment.json").write_text(
        json.dumps(chup_moi_truong(cai), ensure_ascii=False, indent=2),
        encoding="utf-8")
    (bang_chung / "executable-path.txt").write_text(
        str(cai / "VoxDub.exe"), encoding="utf-8")

    # Trước khi cài bộ máy: bản cài mới phải NÓI THẬT là chưa có gì — và nói
    # bằng câu người dùng làm được việc, không phải "không có nội dung".
    kq, ket = chay_exe(cai / "VoxDub.exe",
                       ["--tu-kiem-goi", "--chi-do-dac",
                        "--doi-bo-may", "whisper,vieneu",
                        "--bang-chung", str(bang_chung / "truoc-khi-cai")],
                       bang_chung / "truoc-khi-cai", 600)
    kiem_bao_thieu_bo_may(kq, ket, bang_chung / "truoc-khi-cai")
    if ket.get("bo_may", {}).get("env_ban_cu_tim_thay"):
        raise Hong("Bản cài mới tuyên bố tìm thấy .env của bản cũ trong khi "
                   "không có bản cũ nào cạnh bên.")
    bao_cao.append("trước khi cài: báo thiếu đúng bộ máy "
                   f"{ket.get('bo_may_thieu')}, không nhận vơ bản cũ")

    bao_cao += cai_bo_may(cai, args.cai_dat, args.timeout)
    do = mot_luot_dub_bang_goi(cai / "VoxDub.exe", Path(args.video), hop,
                               bang_chung, args.timeout, _goc_cho_phep(args, hop))
    return bao_cao + do["bao_cao"]


def kiem_bao_thieu_bo_may(kq, ket: dict, bang_chung: Path) -> None:
    """Thư mục cài mới chưa cài gì thì bản đóng gói phải NÓI ĐÚNG là thiếu gì.

    Hai ca hỏng ở đây khác hẳn nhau và trước kia bị gộp làm một — lượt CI
    35614850573 trả về đúng mã 5 (sản phẩm từ chối chạy, hoàn toàn đúng) mà bộ
    lái lại kết luận "bản đóng gói KHÔNG báo thiếu", vì nó đọc phải thư mục
    bằng chứng rỗng. Một câu lỗi chỉ đúng một nửa còn tệ hơn không có: nó chỉ
    người đọc đi chẩn sai chỗ. Nên tách:

    * KHÔNG có `result.json` → hỏng ở đường **ghi bằng chứng**;
    * có `result.json` nhưng nội dung sai → hỏng ở **sản phẩm**.
    """
    if not ket:
        raise Hong(
            f"VoxDub.exe trả mã {kq.returncode} nhưng KHÔNG ghi result.json "
            f"vào {bang_chung} — không có bằng chứng thì không kết luận được "
            "gì về sản phẩm. Xem app.stdout.log (exe có in ra thư mục bằng "
            "chứng nó hiểu) và kiểm xem đường dẫn đưa cho exe có tuyệt đối "
            "không.")
    if kq.returncode != 5 or ket.get("giai_doan_hong") != "bo_may_thieu":
        raise Hong("Thư mục cài mới chưa có bộ máy nào, nhưng bản đóng gói "
                   f"KHÔNG báo thiếu (mã {kq.returncode}, giai đoạn "
                   f"{ket.get('giai_doan_hong')!r}) — đúng lớp lỗi 'báo không "
                   "có nội dung' thay vì 'chưa cài, cài thế này'.")


def _goc_cho_phep(args, hop: Path) -> list[str]:
    """Gốc thư mục mà lượt chạy ĐƯỢC PHÉP chạm tới.

    Hộp cát của chế độ + thư mục chứa video mẫu (đã chép ra khỏi cây mã
    nguồn). Mọi đường khác phải là ngoại lệ khai tường minh trong
    :func:`kiem_duong_chay` (ffmpeg của máy, thư mục hệ điều hành).
    """
    return [str(hop), str(Path(args.goc_thu) / "mau")]


def _dung_ban_cu(nguon_zip: Path, thu_muc: Path, args) -> Path:
    """Dựng 'bản cũ' cạnh bên: cùng gói, nhưng ĐÃ cài bộ máy + có .env giả."""
    cu = giai_nen(nguon_zip, thu_muc)
    cai_bo_may(cu, args.cai_dat, args.timeout)
    (cu / "bin").mkdir(exist_ok=True)
    for ten in ("ffmpeg", "ffprobe"):
        that = shutil.which(ten)
        if that:
            shutil.copy2(that, cu / "bin" / Path(that).name)
    # `.env` KHÔNG phải của production: token giả, và chính nó là mồi cho
    # phép kiểm che bí mật ở cuối.
    (cu / ".env").write_text(
        "VOXDUB_API_URL=https://vi-du-khong-co-that.invalid\n"
        f"VOXDUB_TOKEN={TOKEN_GIA}\n"
        "WHISPER_MODEL=tiny\n", encoding="utf-8")
    return cu


def _ban_cu_co_san(args) -> Path | None:
    """Bản cũ ĐÃ dựng ở chế độ nâng cấp, nếu lượt đó chạy trước.

    Ca âm "khác thư mục cha" cần một bản cũ THẬT (có bộ máy) để phép thử có
    nghĩa. Dựng lại từ đầu tốn thêm vài phút CI mà không thêm bằng chứng nào
    — dùng lại bản đã dựng, và chỉ khi nó đủ dấu hiệu cài xong.
    """
    cu = Path(args.goc_thu) / "nang-cap" / "cha" / "VoxDub-previous"
    if (cu / "models" / "vieneu" / "installed_ok.json").is_file():
        return cu
    return None


def che_do_nang_cap(args, bang_chung: Path) -> list[str]:
    """I0-E + I0-F: bản mới giải nén CẠNH bản cũ, dùng lại bộ máy của nó."""
    hop = Path(args.goc_thu) / "nang-cap"
    if hop.exists():
        shutil.rmtree(hop, ignore_errors=True)
    cha = hop / "cha"
    zip_goc = Path(args.zip)
    cu = _dung_ban_cu(zip_goc, cha / "VoxDub-previous", args)
    moi = giai_nen(zip_goc, cha / "VoxDub-candidate")
    bao_cao = [f"bản cũ: {cu} (đã cài bộ máy + .env giả)",
               f"bản mới: {moi} (chưa cài gì)"]

    truoc = manifest_thu_muc(str(cu))
    (bang_chung / "upgrade-previous-before.json").write_text(
        json.dumps(truoc, ensure_ascii=False, indent=2), encoding="utf-8")
    bao_cao.append(f"chụp bản cũ trước: {len(truoc['tep'])} tệp băm đầy đủ + "
                   f"{len(truoc['thu_muc_nang'])} thư mục nặng đếm tệp/byte")

    # 1) Khởi động bản mới theo ĐƯỜNG THẬT của người dùng (chế độ tự kiểm sẵn
    #    có: dựng GUI rồi ghi smoke_test_result.json). Đây là đường duy nhất
    #    chạy phép chép `.env` của bản cũ sang (app.py:1050).
    kq_smoke = subprocess.run([str(moi / "VoxDub.exe")],
                              cwd=str(moi), env=dict(os.environ,
                                                     AUTODUB_SMOKE="1"),
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=600)
    tep_smoke = moi / "smoke_test_result.json"
    if not tep_smoke.is_file():
        raise Hong(f"Bản mới không ghi smoke_test_result.json (mã "
                   f"{kq_smoke.returncode}) — không khởi động được cạnh bản cũ.")
    smoke = json.loads(tep_smoke.read_text(encoding="utf-8"))
    shutil.copy2(tep_smoke, bang_chung / "smoke_test_result.json")
    if not smoke.get("ok"):
        raise Hong(f"Smoke test của bản mới KHÔNG đạt cạnh bản cũ: {smoke}")
    if not smoke.get("vieneu_installed"):
        raise Hong("Bản mới KHÔNG nhận ra bộ giọng VieNeu của bản cũ nằm "
                   "cạnh — đúng lời than 'nâng cấp xong mất hết model' mà "
                   "V77 đã chữa; nếu nó tái phát thì phải đỏ ở đây.")
    bao_cao.append("khởi động cạnh bản cũ: smoke ok, thấy VieNeu của bản cũ")
    if not (moi / ".env").is_file():
        raise Hong("Bản mới không mang `.env` của bản cũ sang (V96) — người "
                   "dùng phải khai báo lại toàn bộ cài đặt.")
    bao_cao.append("cài đặt (.env) của bản cũ đã được mang sang bản mới")

    # 2) Từng bộ máy: dùng lại đúng của bản cũ, không nhận vơ.
    kq, ket = chay_exe(moi / "VoxDub.exe",
                       ["--tu-kiem-goi", "--chi-do-dac",
                        "--doi-bo-may", "whisper,vieneu",
                        "--bang-chung", str(bang_chung / "do-dac")],
                       bang_chung / "do-dac", 600)
    _doi_ma(kq, ket, "đo đạc bộ máy của bản mới")
    for ten in ("whisper", "vieneu"):
        muc = ket["bo_may"][ten]
        if not trong_vung(muc["python"], str(cu)):
            raise Hong(f"{ten}: bản mới báo sẵn sàng nhưng python nằm ở "
                       f"{muc['python']} — không phải của bản cũ ({cu}).")
        bao_cao.append(f"{ten}: dùng lại của bản cũ → {muc['python']}")
    if not trong_vung(ket["bo_may"].get("bin_ban_cu_tim_thay", ""), str(cu)):
        raise Hong("Không thấy bin/ffmpeg của bản cũ — mục 'bin' của I0-E "
                   "không được chứng minh.")
    bao_cao.append("bin/ của bản cũ: tìm thấy và dùng lại được")

    # 3) Dub thật bằng bản MỚI, dùng bộ máy của bản CŨ.
    do = mot_luot_dub_bang_goi(moi / "VoxDub.exe", Path(args.video), hop,
                               bang_chung, args.timeout,
                               _goc_cho_phep(args, hop))
    bao_cao += do["bao_cao"]

    # 4) Bản cũ phải còn NGUYÊN VẸN sau tất cả.
    sau = manifest_thu_muc(str(cu))
    (bang_chung / "upgrade-previous-after.json").write_text(
        json.dumps(sau, ensure_ascii=False, indent=2), encoding="utf-8")
    khac = so_sanh_manifest(truoc, sau)
    (bang_chung / "upgrade-diff.json").write_text(
        json.dumps(khac, ensure_ascii=False, indent=2), encoding="utf-8")
    if not khac["nguyen_ven"]:
        raise Hong(
            "Bản mới LÀM MẤT hoặc ĐỔI tệp của bản cũ — nâng cấp không được "
            f"phép làm hỏng bản đang dùng được.\n  sửa: {khac['sua_doi'][:5]}"
            f"\n  xoá: {khac['bi_xoa'][:5]}"
            f"\n  tệp cũ biến mất: {khac['nang_bi_mat'][:5]}"
            f"\n  tệp cũ đổi kích thước: {khac['nang_doi_kich_thuoc'][:5]}")
    # THÊM là hợp lệ (kho model dùng chung), nhưng phải NÓI RA thêm cái gì:
    # "có thứ gì đó đổi" thì người đọc không có đường nào đi tiếp.
    them_nang = khac["them_moi_trong_thu_muc_nang"]
    bao_cao.append(
        f"bản cũ nguyên vẹn: không tệp nào mất hay đổi kích thước; "
        f"THÊM {len(khac['them_moi'])} tệp thường + {len(them_nang)} tệp "
        f"trong thư mục nặng"
        + (f" (vd {them_nang[:3]})" if them_nang else ""))
    return bao_cao


def che_do_am_tinh(args, bang_chung: Path) -> list[str]:
    """I0-E, ba ca ÂM: khác thư mục cha · thiếu thành phần · cấu hình hỏng."""
    hop = Path(args.goc_thu) / "am-tinh"
    if hop.exists():
        shutil.rmtree(hop, ignore_errors=True)
    zip_goc = Path(args.zip)
    bao_cao = []

    # --- Ca 1: bản cũ nằm ở THƯ MỤC CHA KHÁC → không được nhận vơ ---------
    #
    # Chỗ đặt là CẢ phép kiểm. Đặt bản mới ở một nhánh xa tít thì ca này chỉ
    # chứng minh "app không quét cả ổ đĩa" — đúng nhưng vô nghĩa, và nó ĐÃ
    # vô nghĩa ở bản đầu: cấy lỗi "dò lùi thêm một cấp" vào bản giả mà cổng
    # vẫn xanh. Nên bản mới phải nằm ở thư mục cha NGAY CẠNH thư mục cha của
    # bản cũ — đúng hình dạng mà một phép dò lỏng tay sẽ nhận vơ.
    cu = _ban_cu_co_san(args) or _dung_ban_cu(
        zip_goc, hop / "cha-A" / "VoxDub-previous", args)
    moi = giai_nen(zip_goc, cu.parent.parent / "cha-khac" / "VoxDub-candidate")
    if cu.parent == moi.parent or cu.parent.parent != moi.parent.parent:
        raise Hong(f"Hộp thử ca âm dựng sai hình: bản cũ {cu} và bản mới "
                   f"{moi} phải ở HAI thư mục cha cạnh nhau, không thì phép "
                   "kiểm này không kiểm gì cả.")
    bao_cao.append(f"bản cũ ở {cu.parent.name}/, bản mới ở {moi.parent.name}/ "
                   "— hai thư mục cha cạnh nhau")
    kq, ket = chay_exe(moi / "VoxDub.exe",
                       ["--tu-kiem-goi", "--chi-do-dac",
                        "--bang-chung", str(bang_chung / "khac-cha")],
                       bang_chung / "khac-cha", 600)
    _doi_ma(kq, ket, "ca khác thư mục cha")
    for ten in ("whisper", "vieneu"):
        muc = ket["bo_may"][ten]
        if muc["san_sang"] or trong_vung(muc["python"], str(cu)):
            raise Hong(f"Ca KHÁC THƯ MỤC CHA: bản mới nhận vơ {ten} của bản "
                       f"cũ ở {muc['python']} — lời hứa 'chỉ dùng lại bản "
                       "cạnh bên' bị phá.")
    if ket["bo_may"].get("env_ban_cu_tim_thay"):
        raise Hong("Ca KHÁC THƯ MỤC CHA: bản mới đọc `.env` của bản cũ ở thư "
                   "mục cha khác.")
    bao_cao.append("ca khác thư mục cha: KHÔNG nhận vơ bộ máy lẫn .env")

    # --- Ca 2: bản cũ THIẾU venv (chỉ có dấu cài xong) --------------------
    cha2 = hop / "cha-C"
    thieu = cha2 / "VoxDub-previous"
    (thieu / "models" / "vieneu").mkdir(parents=True)
    (thieu / "models" / "vieneu" / "installed_ok.json").write_text(
        '{"ghi_chu": "hộp thử I0-E: có dấu cài xong nhưng KHÔNG có venv"}',
        encoding="utf-8")
    moi2 = giai_nen(zip_goc, cha2 / "VoxDub-candidate")
    kq, ket = chay_exe(moi2 / "VoxDub.exe",
                       ["--tu-kiem-goi", "--chi-do-dac",
                        "--bang-chung", str(bang_chung / "thieu-thanh-phan")],
                       bang_chung / "thieu-thanh-phan", 600)
    _doi_ma(kq, ket, "ca thiếu thành phần")
    if ket["bo_may"]["vieneu"]["san_sang"]:
        raise Hong("Ca THIẾU THÀNH PHẦN: bản cũ chỉ có dấu `installed_ok` mà "
                   "không có venv, bản mới vẫn báo VieNeu sẵn sàng — một bản "
                   "cài dở dang bị tính là dùng lại được.")
    bao_cao.append("ca thiếu thành phần: KHÔNG báo dùng lại thứ không có")

    # --- Ca 3: `.env` của bản cũ hỏng + có token → không lộ, vẫn chạy được -
    cha3 = hop / "cha-D"
    cu3 = cha3 / "VoxDub-previous"
    (cu3 / "models" / "vieneu").mkdir(parents=True)
    (cu3 / ".env").write_text(
        "KHONG_PHAI_DINH_DANG_ENV\n"
        f"VOXDUB_TOKEN={TOKEN_GIA}\n"
        "=dòng hỏng=\n", encoding="utf-8")
    moi3 = giai_nen(zip_goc, cha3 / "VoxDub-candidate")
    env_cu_truoc = (cu3 / ".env").read_bytes()
    kq, ket = chay_exe(moi3 / "VoxDub.exe",
                       ["--tu-kiem-goi", "--chi-do-dac",
                        "--bang-chung", str(bang_chung / "env-hong")],
                       bang_chung / "env-hong", 600)
    _doi_ma(kq, ket, "ca cấu hình hỏng")
    if (cu3 / ".env").read_bytes() != env_cu_truoc:
        raise Hong("Ca CẤU HÌNH HỎNG: bản mới GHI ĐÈ `.env` của bản cũ.")
    bao_cao.append("ca cấu hình hỏng: bản mới vẫn khởi động, .env bản cũ "
                   "không bị sửa")

    # --- Quét che bí mật trên TOÀN BỘ bằng chứng --------------------------
    lo = []
    for goc_quet, _d, cac_tep in os.walk(bang_chung):
        for ten in cac_tep:
            p = Path(goc_quet) / ten
            try:
                noi_dung = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if TOKEN_GIA in noi_dung:
                lo.append(str(p.relative_to(bang_chung)))
    (bang_chung / "quet-bi-mat.json").write_text(
        json.dumps({"tep_lo_token": lo}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    if lo:
        raise Hong(f"Token của hộp thử LỌT vào tệp bằng chứng: {lo[:5]} — "
                   "artifact CI là nơi ai cũng tải được.")
    bao_cao.append("quét bí mật: token hộp thử không lọt vào tệp bằng chứng "
                   "nào")
    return bao_cao


CHE_DO = {"sach": che_do_sach, "nang-cap": che_do_nang_cap,
          "am-tinh": che_do_am_tinh}

#: Tên cổng để in ra bảng tóm tắt của CI.
TEN_CONG = {"sach": "I0-D cài mới + I0-F dub bằng gói",
            "nang-cap": "I0-E nâng cấp cạnh bên + I0-F",
            "am-tinh": "I0-E ba ca âm"}


def chuan_hoa_duong_dan(args) -> None:
    """Đổi mọi đường dẫn nhận từ dòng lệnh sang TUYỆT ĐỐI, ngay tại cửa vào.

    CI gọi bộ lái với `--bang-chung packaged-dub-evidence` (tương đối, đúng và
    tiện cho việc gom artifact). Bộ lái tự ghi tệp thì không sao — nó đứng ở
    gốc repo. Nhưng nó còn CHUYỂN đường dẫn đó cho `VoxDub.exe`, mà exe chạy ở
    thư mục cài trong hộp cát: cùng một chuỗi, hai chỗ khác nhau. Chuẩn hoá ở
    một cửa duy nhất, thay vì nhớ gọi `abspath` ở tám chỗ gọi (nhớ tay kiểu đó
    thì sót một chỗ là đủ mất bằng chứng — đã sót thật ở run 35614850573).
    """
    for ten in ("bang_chung", "goc_thu", "video", "zip"):
        gia_tri = getattr(args, ten, "") or ""
        if gia_tri:
            setattr(args, ten, str(Path(gia_tri).resolve()))


def _doc(duong: Path) -> dict:
    try:
        return json.loads(duong.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def bang_tom_tat(goc_bang_chung: Path, trang_thai_nguon: str = "") -> str:
    """Bảng Markdown cho phần tóm tắt của lượt chạy CI (mini-spec I0-FDE §F).

    Đọc TỆP BẰNG CHỨNG chứ không nhận trạng thái do người viết YAML gõ tay:
    chế độ nào không để lại `tom-tat.json` thì ghi thẳng là *không chạy*, chứ
    không được im lặng biến mất khỏi bảng (một cổng biến mất khỏi bảng trông
    y như một cổng đã xanh).
    """
    dong = ["| Cổng | Kết quả | Commit ứng viên | SHA-256 gói | Mượn mã nguồn? "
            "| Soi tệp ra | Bằng chứng |",
            "|---|---|---|---|---|---|---|"]
    dong.append(f"| Dub THẬT từ mã nguồn (cổng cũ C45/C55) | "
                f"{trang_thai_nguon or 'xem log bước trước'} | — | n/a | n/a "
                f"| trong log bước đó | log của job |")
    for ten in ("sach", "nang-cap", "am-tinh"):
        thu_muc = goc_bang_chung / ten
        tom = _doc(thu_muc / "tom-tat.json")
        goi = _doc(thu_muc / "candidate-artifact.json")
        probe = _doc(thu_muc / "output-probe.json")
        if not tom:
            dong.append(f"| {TEN_CONG[ten]} | **không chạy** (bước trước đã "
                        f"dừng) | — | — | — | — | — |")
            continue
        duong = _doc(thu_muc / "duong-da-dung.json")
        muon = duong.get("tu_cay_ma_nguon") or duong.get("ngoai_vung")
        soi = (f"{probe['mean_volume_db']} dB · {probe['giay_ra']:.1f}s "
               f"(nguồn {probe['giay_nguon']:.1f}s)") if probe else "—"
        ket = {"dat": "đạt", "hong": "**HỎNG**",
               "bi_chan": "**BỊ CHẶN**"}.get(tom.get("ket_qua"), "?")
        dong.append(
            f"| {TEN_CONG[ten]} | {ket} | `{(tom.get('commit_ung_vien') or '')[:12]}` "
            f"| `{(goi.get('sha256') or '')[:16]}` | "
            f"{'**CÓ**' if muon else 'không'} | {soi} | "
            f"`packaged-dub-evidence/{ten}/` |")
    return "\n".join(dong)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--che-do", choices=sorted(CHE_DO))
    ap.add_argument("--zip", default="", help="gói phát hành ứng viên")
    ap.add_argument("--goc-thu", default="", help="thư mục hộp cát")
    ap.add_argument("--bang-chung", required=True)
    ap.add_argument("--chi-in-bang", action="store_true",
                    help="chỉ in bảng tóm tắt từ bằng chứng đã có (cho CI)")
    ap.add_argument("--trang-thai-nguon", default="",
                    help="kết quả cổng dub từ mã nguồn ở bước trước")
    ap.add_argument("--video", default=str(GOC_REPO / "tap01_clip.mp4"))
    ap.add_argument("--cai-dat", default="bat", choices=("bat", "script"))
    ap.add_argument("--timeout", type=int, default=2700)
    ap.add_argument("--sha", default="", help="commit ứng viên (ghi vào bằng chứng)")
    args = ap.parse_args()

    if args.chi_in_bang:
        print(bang_tom_tat(Path(args.bang_chung), args.trang_thai_nguon))
        return 0
    if not args.che_do or not args.zip or not args.goc_thu:
        print("!! cần --che-do, --zip và --goc-thu (hoặc --chi-in-bang)",
              file=sys.stderr)
        return 2

    chuan_hoa_duong_dan(args)
    bang_chung = Path(args.bang_chung) / args.che_do
    bang_chung.mkdir(parents=True, exist_ok=True)
    tep_zip = Path(args.zip)
    video = Path(args.video)
    if not tep_zip.is_file():
        print(f"!! Không thấy gói {tep_zip}", file=sys.stderr)
        return 2
    if not video.is_file():
        print(f"!! Không thấy video mẫu {video}", file=sys.stderr)
        return 2
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("!! Máy chạy kiểm thiếu ffmpeg/ffprobe — không soi được tệp ra",
              file=sys.stderr)
        return 2

    # Video mẫu phải nằm TRONG hộp cát: đường dẫn đầu vào trỏ về cây mã nguồn
    # thì chính nó đã là một đường mượn.
    hop_mau = Path(args.goc_thu) / "mau"
    hop_mau.mkdir(parents=True, exist_ok=True)
    video_hop = hop_mau / "clip.mp4"
    if not video_hop.is_file():
        shutil.copy2(video, video_hop)
    args.video = str(video_hop)

    (bang_chung / "candidate-artifact.json").write_text(json.dumps({
        "ten_goi": tep_zip.name, "byte": tep_zip.stat().st_size,
        "sha256": bam_tep(str(tep_zip)), "commit_ung_vien": args.sha,
        "che_do": args.che_do,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (bang_chung / "input-fixture.json").write_text(json.dumps({
        "duong_dan": str(video_hop), "nguon_goc": str(video),
        "sha256": bam_tep(str(video_hop)),
        "byte": video_hop.stat().st_size,
        "giay": _thoi_luong(video_hop),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Cổng kiểm bản đóng gói — chế độ {args.che_do}")
    bat_dau = time.time()
    try:
        for dong in CHE_DO[args.che_do](args, bang_chung):
            print(f"  [ok] {dong}")
    except Hong as e:
        print(f"\n  [HỎNG] {e}", file=sys.stderr)
        _ghi_tom_tat(bang_chung, args, "hong", str(e), bat_dau)
        print("\nKẾT LUẬN: KHÔNG phát hành bản này.", file=sys.stderr)
        return 1
    except BiChan as e:
        print(f"\n  [BỊ CHẶN] {e}", file=sys.stderr)
        _ghi_tom_tat(bang_chung, args, "bi_chan", str(e), bat_dau)
        return 2
    _ghi_tom_tat(bang_chung, args, "dat", "", bat_dau)
    print(f"\nKẾT LUẬN: chế độ {args.che_do} ĐẠT bằng chính bản đóng gói "
          f"({time.time() - bat_dau:.0f}s).")
    return 0


def _ghi_tom_tat(bang_chung: Path, args, ket_qua: str, loi: str,
                 bat_dau: float) -> None:
    tom = {"che_do": args.che_do, "ket_qua": ket_qua, "loi": che_bi_mat(loi),
           "giay": round(time.time() - bat_dau, 1),
           "goi": Path(args.zip).name, "commit_ung_vien": args.sha}
    (bang_chung / "tom-tat.json").write_text(
        json.dumps(tom, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
