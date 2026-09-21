"""Bằng chứng cho cổng kiểm BẢN ĐÓNG GÓI (mini-spec I0-FDE).

Vì sao tệp này tồn tại: cổng kiểm cũ (`scripts/kiem_chay_that.py`) chạy MÃ
NGUỒN — `python -m autodub.cli dub`. Nó chứng minh đường ống còn nguyên, nhưng
KHÔNG chứng minh được bản `.exe` người dùng tải về chạy được: PyInstaller có
thể thiếu tệp worker, `sys._MEIPASS` có thể trỏ sai, tiến trình con có thể
mượn nhầm tệp của cây mã nguồn nằm cạnh. Ba lớp lỗi đó đã xảy ra thật (V74,
V80, V82).

Ở đây chỉ có các hàm THUẦN (không Qt, không engine nặng) dùng chung cho cả hai
phía:

* phía TRONG gói — lệnh chẩn đoán `VoxDub.exe --tu-kiem-goi`
  (`autodub_gui/tu_kiem_goi.py`);
* phía NGOÀI gói — bộ lái chạy trên CI (`scripts/kiem_goi_phat_hanh.py`).

Ba việc chúng làm, mỗi việc chữa một cách nói dối cụ thể:

1. :func:`duong_ngoai_vung` — bắt lượt chạy "xanh" nhờ mượn tệp NGOÀI hộp cát
   (cây mã nguồn, bản cài cũ, cache toàn cục của runner). Một lượt như vậy
   không chứng minh gì về bản người dùng tải.
2. :func:`che_bi_mat` — token/khoá không được rơi vào tệp bằng chứng tải lên
   CI. Hộp thử nâng cấp cố ý có `.env` giả, nên đường này chắc chắn bị chạm.
3. :func:`manifest_thu_muc` / :func:`so_sanh_manifest` — chứng minh bản mới
   KHÔNG sửa/xoá tệp của bản cũ nằm cạnh (lời hứa "nâng cấp không mất model").
"""
from __future__ import annotations

import hashlib
import os
import re

#: Tên khoá bị coi là bí mật khi in ra bằng chứng. Cố ý RỘNG: thà che nhầm
#: một đường dẫn vô hại còn hơn để lọt một token thật lên artifact công khai.
_KHOA_BI_MAT = re.compile(
    r"(?i)(token|api[_-]?key|apikey|secret|password|passwd|mat[_-]?khau"
    r"|authorization|bearer|credential)")

#: `KHOA=giá trị` nằm giữa một đoạn chữ (dòng nhật ký, nội dung `.env`, tham
#: số dòng lệnh). Phần giá trị là thứ phải che.
_GAN_BI_MAT = re.compile(
    r"(?i)\b([A-Za-z0-9_.-]*(?:token|api[_-]?key|apikey|secret|password"
    r"|passwd|authorization|credential)[A-Za-z0-9_.-]*)\s*([:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;]+)")

#: Chuỗi thay thế. Có chữ "che" để người đọc bằng chứng biết là CỐ Ý, không
#: phải giá trị rỗng do lỗi.
CHE = "***(đã che)"


def che_dong(chuoi: str) -> str:
    """Che mọi `KHOA=giá trị` mang tên bí mật trong một đoạn chữ."""
    if not chuoi:
        return chuoi
    return _GAN_BI_MAT.sub(lambda m: f"{m.group(1)}{m.group(2)}{CHE}", str(chuoi))


def che_bi_mat(du_lieu, ten_khoa: str = ""):
    """Bản sao của ``du_lieu`` đã che mọi giá trị bí mật (đệ quy).

    Che theo HAI đường vì cả hai đều đã gặp thật:

    * theo TÊN KHOÁ (``{"api_token": "abc"}``) — dữ liệu có cấu trúc;
    * theo NỘI DUNG (``"VOXDUB_TOKEN=abc"``) — dòng nhật ký, tham số dòng
      lệnh, nội dung tệp cấu hình đọc lên.
    """
    if isinstance(du_lieu, dict):
        return {k: che_bi_mat(v, str(k)) for k, v in du_lieu.items()}
    if isinstance(du_lieu, (list, tuple)):
        # Dòng lệnh tách thành hai phần tử: ``["--hf-token", "abc"]``. Đây là
        # dạng THẬT trong dự án (`scripts/setup_diarization.py` nhận token
        # HuggingFace đúng kiểu này), và luật `KHOA=giá trị` ở trên không
        # nhìn thấy nó — phải che theo CẶP.
        ra = []
        truoc = ""
        for v in du_lieu:
            if (isinstance(v, str) and truoc.startswith("-")
                    and _KHOA_BI_MAT.search(truoc)):
                ra.append(CHE)
            else:
                ra.append(che_bi_mat(v, ten_khoa))
            truoc = v if isinstance(v, str) else ""
        return ra
    if isinstance(du_lieu, str):
        if ten_khoa and _KHOA_BI_MAT.search(ten_khoa):
            return CHE if du_lieu else du_lieu
        return che_dong(du_lieu)
    return du_lieu


def _chuan(duong: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(duong)))


def trong_vung(duong: str, goc: str) -> bool:
    """``duong`` có nằm trong (hoặc chính là) thư mục ``goc`` không.

    Dùng so khớp theo THÀNH PHẦN đường dẫn chứ không phải ``startswith``:
    ``C:\\VoxDub-cu`` không được tính là nằm trong ``C:\\VoxDub`` (lỗi kinh
    điển của so khớp chuỗi, mà đây lại đúng là hình dạng thư mục của ca nâng
    cấp cạnh bên).
    """
    if not duong or not goc:
        return False
    d, g = _chuan(duong), _chuan(goc)
    if d == g:
        return True
    return d.startswith(g + os.sep)


def duong_ngoai_vung(duong_dan, goc_cho_phep, ngoai_le=()) -> list[str]:
    """Những đường dẫn KHÔNG nằm trong bất kỳ gốc nào được phép.

    ``ngoai_le`` là các gốc được tha thêm (vd thư mục hệ điều hành, ffmpeg
    của máy) — phải khai TƯỜNG MINH ở nơi gọi, để bản kiểm không lặng lẽ
    chấp nhận một đường mượn mới.
    """
    goc = [g for g in goc_cho_phep if g]
    tha = [g for g in ngoai_le if g]
    la: list[str] = []
    for d in duong_dan:
        if not d:
            continue
        if any(trong_vung(d, g) for g in goc):
            continue
        if any(trong_vung(d, g) for g in tha):
            continue
        la.append(d)
    return la


def bam_tep(duong: str) -> str:
    """SHA-256 của một tệp (chuỗi rỗng nếu không đọc được)."""
    try:
        h = hashlib.sha256()
        with open(duong, "rb") as f:
            for khoi in iter(lambda: f.read(1 << 20), b""):
                h.update(khoi)
        return h.hexdigest()
    except OSError:
        return ""


#: Thư mục KHÔNG lấy dấu vân tay khi chụp bản cài cũ: venv có hàng chục nghìn
#: tệp và `models/` tới hàng GB — băm hết là hàng phút CI cho mỗi lượt chụp.
#: Với các thư mục này chỉ ghi lại SỐ TỆP + TỔNG BYTE (đủ để phát hiện xoá
#: hoặc ghi đè), phần còn lại băm đầy đủ.
NANG_KHONG_BAM = (".venv-", "models", "pw-browsers", "libs", "vendor")


def manifest_thu_muc(goc: str, bam_het: bool = False) -> dict:
    """Dấu vân tay của MỘT bản cài để so trước/sau (mini-spec I0-E).

    Trả về ``{"tep": {đường_dẫn_tương_đối: {...}}, "thu_muc_nang": {...}}``.
    """
    goc = os.path.abspath(goc)
    tep: dict[str, dict] = {}
    nang: dict[str, dict] = {}
    for thu_muc, cac_thu_muc_con, cac_tep in os.walk(goc):
        rel_dir = os.path.relpath(thu_muc, goc).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        goc_nang = rel_dir.split("/", 1)[0] if rel_dir else ""
        la_nang = (not bam_het) and any(
            goc_nang == t or goc_nang.startswith(t) for t in NANG_KHONG_BAM)
        if la_nang:
            muc = nang.setdefault(goc_nang, {"so_tep": 0, "tong_byte": 0})
            for ten in cac_tep:
                try:
                    muc["tong_byte"] += os.path.getsize(
                        os.path.join(thu_muc, ten))
                except OSError:
                    continue
                muc["so_tep"] += 1
            continue
        for ten in cac_tep:
            day_du = os.path.join(thu_muc, ten)
            rel = f"{rel_dir}/{ten}" if rel_dir else ten
            try:
                tep[rel] = {"byte": os.path.getsize(day_du),
                            "sha256": bam_tep(day_du)}
            except OSError:
                continue
    return {"goc": goc, "tep": tep, "thu_muc_nang": nang}


def so_sanh_manifest(truoc: dict, sau: dict) -> dict:
    """Khác biệt giữa hai lần chụp: tệp bị SỬA, bị XOÁ, hoặc mới THÊM.

    Bản mới KHÔNG được sửa hay xoá tệp nào của bản cũ. "Thêm" thì tuỳ ca gọi
    quyết định (vd app ghi nhật ký vào bản cũ cũng là sai, nhưng đó là quyết
    định của tầng trên, không phải của hàm so sánh).
    """
    t, s = truoc.get("tep", {}), sau.get("tep", {})
    sua = sorted(k for k in t if k in s and t[k]["sha256"] != s[k]["sha256"])
    xoa = sorted(k for k in t if k not in s)
    them = sorted(k for k in s if k not in t)
    nang_doi = sorted(
        k for k, v in truoc.get("thu_muc_nang", {}).items()
        if sau.get("thu_muc_nang", {}).get(k, {}) != v)
    return {"sua_doi": sua, "bi_xoa": xoa, "them_moi": them,
            "thu_muc_nang_doi": nang_doi,
            "nguyen_ven": not (sua or xoa or nang_doi)}
