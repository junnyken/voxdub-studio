"""Dựng bối cảnh mới cho ảnh sản phẩm, có cổng kiểm tuân thủ — mini-spec C1.

Bối cảnh thật (không phải giả định): người bán gửi ảnh chụp màn hình TikTok
Shop — tài khoản bị **cưỡng chế hủy quyền thương mại điện tử và trừ 1000 điểm
CHR** vì "quảng bá sản phẩm không nhất quán". Chính sách đó đòi sản phẩm trong
video khớp sản phẩm đang bán về màu, kích thước, chất liệu và thiết kế; máy
của TikTok quét bằng thị giác máy tính rồi so với ảnh đăng bán, và **6 lần
cùng loại trong 90 ngày là mất quyền bán bất kể điểm CHR**.

Nên tệp này không phải là "AI vẽ lại bao bì cho đẹp". Nó là ba luật:

1. **Mặc định giữ nguyên sản phẩm** — câu lệnh gửi mô hình đã cấm sửa bao bì
   (xem `control_server/src/prompts/product_scene.js`).
2. **Kiểm lại bằng mắt máy, và KẾT QUẢ KIỂM ĐÈ LÊN CHẾ ĐỘ NGƯỜI DÙNG CHỌN.**
   Mô hình hứa giữ nguyên là một chuyện; nó có giữ hay không là chuyện khác.
   Xin SAFE mà ảnh ra lệch thì ảnh đó vẫn bị đánh dấu CONCEPT.
3. **Hỏng thì nghiêng về phía an toàn.** Không kiểm được (mất mạng, hết Vox,
   máy chủ lỗi) thì coi như CONCEPT — không bao giờ mặc định là an toàn.

Ảnh CONCEPT luôn bị đóng nhãn nhìn thấy được và không được coi là dùng cho
bài đăng bán. Mọi lượt dựng đều ghi vào nhật ký tra soát, để khi TikTok gắn cờ
thì người bán có bằng chứng mình đã dùng ảnh nào.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field

from autodub.utils import save_json_atomic, setup_logging

logger = setup_logging("autodub.product_scene")

#: Trần cạnh dài của ảnh gửi lên. Ảnh điện thoại 4000px vừa tốn tiền vừa
#: chậm mà mô hình không dùng hết độ phân giải đó.
_CANH_DAI_TOI_DA = 1280

#: Trần dung lượng base64 mà máy chủ nhận (schema route). Cắt sớm ở đây để
#: không đẩy vài MB qua mạng chỉ để bên kia từ chối.
_TRAN_BASE64 = 2_800_000

#: Tên tệp nhật ký tra soát, nằm cạnh ảnh kết quả.
NHAT_KY = "nhat_ky_dung_anh.json"


@dataclass
class KetQua:
    """Một ảnh đã dựng, kèm phán quyết tuân thủ."""

    duong_dan: str
    boi_canh: str
    che_do_xin: str          # người dùng xin gì
    che_do_that: str         # sau khi kiểm: SAFE | CONCEPT
    ly_do: str               # vì sao — bằng lời, không phải điểm số
    da_kiem: bool            # False = chưa kiểm được, phải coi như CONCEPT
    vox: int = 0

    @property
    def dung_duoc_de_ban(self) -> bool:
        """Ảnh này có được phép gắn vào bài đăng bán không."""
        return self.che_do_that == "SAFE" and self.da_kiem


@dataclass
class Phien:
    """Một lượt dựng nhiều bối cảnh từ một ảnh gốc."""

    anh_goc: str
    thu_muc: str
    ket_qua: list[KetQua] = field(default_factory=list)

    @property
    def so_dung_duoc(self) -> int:
        return sum(1 for k in self.ket_qua if k.dung_duoc_de_ban)


def _chay_ffmpeg(args: list[str], timeout: float = 60.0) -> bool:
    try:
        ra = subprocess.run(["ffmpeg", "-y", "-v", "error", *args],
                            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"ffmpeg lỗi ({e})")
        return False
    if ra.returncode != 0:
        logger.warning(f"ffmpeg lỗi: {(ra.stderr or '')[-200:]}")
        return False
    return True


def chuan_bi_anh(duong_dan: str, thu_muc_tam: str) -> dict:
    """Đọc ảnh trên máy thành ``{"mimeType", "data"}`` để gửi lên.

    Thu nhỏ trước khi gửi — dùng ffmpeg vì bản đóng gói CỐ Ý không mang theo
    PIL (xem `autodub.spec`), còn ffmpeg thì luôn có mặt.
    """
    if not os.path.isfile(duong_dan):
        raise FileNotFoundError(f"Không thấy ảnh: {duong_dan}")

    os.makedirs(thu_muc_tam, exist_ok=True)
    nho = os.path.join(thu_muc_tam, "_anh_goc_thu_nho.jpg")
    ok = _chay_ffmpeg([
        "-i", duong_dan,
        "-vf", f"scale='min({_CANH_DAI_TOI_DA},iw)':-2",
        "-q:v", "3", nho,
    ])
    nguon = nho if ok and os.path.isfile(nho) else duong_dan

    with open(nguon, "rb") as f:
        raw = f.read()
    data = base64.b64encode(raw).decode()
    if len(data) > _TRAN_BASE64:
        raise ValueError(
            "Ảnh quá nặng ngay cả sau khi thu nhỏ — hãy chụp lại hoặc lưu ở "
            "định dạng JPG.")
    loai = "image/png" if nguon.lower().endswith(".png") else "image/jpeg"
    return {"mimeType": loai, "data": data}


def _bam_anh(anh: dict) -> str:
    return hashlib.sha1((anh.get("data") or "").encode()).hexdigest()[:16]


def dong_nhan_ai(duong_dan: str, che_do: str) -> bool:
    """Đóng nhãn nhìn thấy được lên ảnh.

    Không cho tắt trong bản đầu. Lý do: từ 13/5/2026 TikTok bắt buộc nhãn
    "AI-generated" cho nội dung chỉnh sửa bằng AI đáng kể — và với ảnh
    CONCEPT thì nhãn còn là thứ phân biệt "ảnh ý tưởng" với "ảnh sản phẩm
    đang bán", tức là ranh giới tránh án phạt.
    """
    chu = ("AI-generated — anh y tuong, khong phai san pham dang ban"
           if che_do == "CONCEPT" else "AI-generated")
    tam = duong_dan + ".nhan.jpg"
    ok = _chay_ffmpeg([
        "-i", duong_dan,
        "-vf",
        (f"drawtext=text='{chu}':fontcolor=white:fontsize=h/28:"
         "box=1:boxcolor=black@0.55:boxborderw=8:x=(w-text_w)/2:y=h-th-16"),
        "-q:v", "3", tam,
    ])
    if ok and os.path.isfile(tam):
        os.replace(tam, duong_dan)
        return True
    # Không đóng được nhãn thì KHÔNG im lặng trả về ảnh trần.
    logger.warning("Không đóng được nhãn AI-generated lên ảnh — ảnh này chỉ "
                   "nên dùng để xem, đừng đăng")
    return False


def kiem_tuan_thu(khach, anh_goc: dict, anh_moi: dict, *,
                  ghi_chu: str = "") -> tuple[str, str, bool]:
    """Hỏi máy chủ: ảnh mới còn là sản phẩm thật không?

    Trả ``(che_do, ly_do, da_kiem)``. Hỏng thì trả CONCEPT — nghiêng về phía
    an toàn, vì đoán sai theo hướng "an toàn" chỉ làm mất một tấm ảnh, còn
    đoán sai theo hướng ngược lại là mất tài khoản bán hàng.
    """
    from autodub.saas_client import new_job_id

    try:
        ket = khach.assist(
            "packaging_check", {"note": ghi_chu[:300]},
            images=[anh_goc, anh_moi], job_id=new_job_id(), timeout=90.0)
    except Exception as e:  # noqa: BLE001 — mọi lỗi đều nghiêng về an toàn
        logger.warning(f"Không kiểm được ảnh ({str(e)[:120]}) — đánh dấu là "
                       "ảnh ý tưởng cho chắc")
        return "CONCEPT", "chưa kiểm được, đánh dấu an toàn", False

    if not ket:
        return "CONCEPT", "máy chủ không trả kết quả kiểm", False
    dau = ket[0]
    gia_tri = str(dau.get("value", "")).strip().upper()
    ly_do = str(dau.get("reason", "")).strip() or "không rõ"
    if gia_tri not in ("SAFE", "CONCEPT"):
        return "CONCEPT", f"kết quả kiểm lạ ({gia_tri[:20]})", False
    return gia_tri, ly_do, True


def dung_boi_canh(anh_goc_path: str, boi_canh: list[str], thu_muc_ra: str, *,
                  che_do: str = "SAFE", ghi_chu: str = "",
                  khach=None) -> Phien:
    """Dựng nhiều bối cảnh từ một ảnh, kiểm từng ảnh, ghi nhật ký.

    Mỗi ảnh đi qua đúng ba bước: dựng → kiểm → đóng nhãn. Không có đường tắt
    nào bỏ bước kiểm, kể cả khi người dùng xin SAFE.
    """
    from autodub.saas_client import get_client, is_configured, new_job_id

    if not is_configured():
        raise RuntimeError(
            "Tính năng này cần tài khoản VoxDub — mở Cài đặt để kết nối.")
    khach = khach or get_client()

    os.makedirs(thu_muc_ra, exist_ok=True)
    goc = chuan_bi_anh(anh_goc_path, thu_muc_ra)
    phien = Phien(anh_goc=anh_goc_path, thu_muc=thu_muc_ra)

    for ten_bc in boi_canh:
        try:
            tra_ve = khach.product_scene(goc, ten_bc, job_id=new_job_id(),
                                         mode=che_do, note=ghi_chu)
        except Exception as e:  # noqa: BLE001 — một bối cảnh hỏng không giết cả mẻ
            logger.warning(f"Không dựng được bối cảnh «{ten_bc}» ({str(e)[:120]})")
            continue

        anh_moi = tra_ve.get("image") or {}
        if not anh_moi.get("data"):
            logger.warning(f"Bối cảnh «{ten_bc}»: máy chủ không trả ảnh")
            continue

        ra_path = os.path.join(thu_muc_ra, f"{ten_bc}.jpg")
        with open(ra_path, "wb") as f:
            f.write(base64.b64decode(anh_moi["data"]))

        che_do_that, ly_do, da_kiem = kiem_tuan_thu(
            khach, goc, anh_moi, ghi_chu=ghi_chu)
        # Người dùng xin SAFE không có nghĩa ảnh ra là SAFE — phán quyết của
        # bước kiểm mới là thứ tính.
        dong_nhan_ai(ra_path, che_do_that)

        phien.ket_qua.append(KetQua(
            duong_dan=ra_path, boi_canh=ten_bc, che_do_xin=che_do,
            che_do_that=che_do_that, ly_do=ly_do, da_kiem=da_kiem,
            vox=int(tra_ve.get("creditCharged") or 0)))

    ghi_nhat_ky(phien, goc)
    return phien


def ghi_nhat_ky(phien: Phien, anh_goc: dict) -> str:
    """Ghi lại mọi lượt dựng để người bán tự tra khi bị TikTok gắn cờ.

    Đây không phải log kỹ thuật: nó là bằng chứng "tôi đã dùng ảnh nào cho
    video nào", thứ duy nhất có ích khi phải khiếu nại một án phạt tự động.
    """
    duong = os.path.join(phien.thu_muc, NHAT_KY)
    cu = []
    if os.path.isfile(duong):
        try:
            with open(duong, encoding="utf-8") as f:
                cu = json.load(f).get("lich_su", [])
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Nhật ký cũ không đọc được ({e}) — ghi tiếp bản mới")

    cu.append({
        "luc": time.strftime("%Y-%m-%d %H:%M:%S"),
        "anh_goc": phien.anh_goc,
        "bam_anh_goc": _bam_anh(anh_goc),
        "anh_da_dung": [
            {"tep": os.path.basename(k.duong_dan), "boi_canh": k.boi_canh,
             "xin": k.che_do_xin, "ket_luan": k.che_do_that,
             "ly_do": k.ly_do, "da_kiem": k.da_kiem, "vox": k.vox}
            for k in phien.ket_qua
        ],
    })
    save_json_atomic({"lich_su": cu}, duong)
    return duong
