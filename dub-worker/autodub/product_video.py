"""Ghép ảnh sản phẩm ĐÃ ĐƯỢC DUYỆT thành video ngắn (mini-spec C6).

Nối tiếp `product_scene.py`. Cả tính năng chỉ có một lý do tồn tại và một
lý do để cẩn thận, và cả hai là cùng một chuyện: video là thứ TikTok Shop
đem đi đối chiếu với sản phẩm đang bán. Một tấm ảnh lệch nhãn lọt vào video
thì hậu quả không dừng ở tấm ảnh — nó là cái video bị gắn cờ.

Nên ở đây **danh sách nguồn không phải do giao diện quyết định**. Giao diện
chỉ đề nghị; hàm `kiem_lai_truoc_khi_xuat()` mới là chỗ nói được hay không,
và nó chạy lại NGAY TRƯỚC lúc ghép chứ không tin danh sách đã dựng từ trước.

Ba điều kiện để một ảnh được vào video, thiếu một là loại:

1. Phán quyết kiểm bao bì là **đăng bán được** (SAFE và đã kiểm được thật).
2. Đã đóng được nhãn "AI-generated" lên ảnh — luật bắt buộc của C1.
3. **Nội dung tệp còn khớp dấu vân tay lúc kiểm.** Nhật ký chỉ ghi tên tệp
   thì không có gì ngăn người ta thay ruột tệp sau khi kiểm xong: tên vẫn
   thế, phán quyết vẫn "đạt", mà ảnh đã là ảnh khác. Đây là đường lách thật
   duy nhất trong kiến trúc này, và là lý do `product_scene.py` phải băm
   từng ảnh sau khi đóng nhãn.

Việc ghép chạy bằng ffmpeg trong tiến trình con — đúng quy tắc kiến trúc: mã
xử lý ảnh/video nặng không được nằm trong tiến trình chính của giao diện.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field

from autodub.media.video import video_codec_args
from autodub.product_scene import NHAT_KY, bam_tep
from autodub.utils import setup_logging

logger = setup_logging("autodub.product_video")

#: Mỗi ảnh đứng bao lâu, và bao lâu thì chuyển sang ảnh sau.
GIAY_MOI_ANH = 2.5
GIAY_CHUYEN_CANH = 0.5

#: Khung hình đầu ra. Dọc 9:16 vì video sản phẩm gần như luôn xem trên điện
#: thoại; ảnh ngang sẽ được đệm hai bên chứ không bị cắt mất bao bì.
RONG, CAO = 1080, 1920

_TOI_DA_ANH = 8

#: Nhãn đóng ở TẦNG VIDEO, hiện suốt cảnh đầu.
#:
#: Vì sao cần dù C1 đã đóng nhãn lên từng tấm ảnh: nhãn của C1 nằm trên ảnh
#: nào đi qua đường dựng của C1. Ngày nào ghép thêm ảnh từ nguồn khác — ảnh
#: chụp thật, ảnh cũ, ảnh người dùng tự sửa — thì video ra đời không nhãn mà
#: không ai kịp nhận ra. Đóng ở tầng video là chỗ DUY NHẤT phủ được mọi
#: nguồn, vì đây là hàm duy nhất tạo ra tệp video.
#:
#: Không có tham số nào tắt được. Từ 13/5/2026 TikTok bắt buộc nhãn
#: "AI-generated" cho nội dung chỉnh sửa bằng AI đáng kể; một cái nút tắt là
#: một cái nút để bấm nhầm.
NHAN_VIDEO = "AI-generated"


@dataclass
class AnhNguon:
    """Một ảnh ứng viên, kèm lý do vì sao dùng được hoặc không."""

    duong_dan: str
    boi_canh: str
    ket_luan: str
    ly_do: str
    da_kiem: bool
    da_dong_nhan: bool
    bam_luc_kiem: str

    @property
    def dung_duoc(self) -> bool:
        return self.ket_luan == "SAFE" and self.da_kiem and self.da_dong_nhan


@dataclass
class LienTuc:
    """Nhận xét các cảnh có nhìn liền mạch không (mini-spec C7).

    KHÔNG phải cổng chặn. Lệch liên tục là chuyện video xem có mượt hay
    không; lệch bao bì mới là chuyện bị sàn phạt. Trộn hai mức đó làm một là
    dạy người dùng bỏ qua cả hai.
    """

    da_kiem: bool
    muot: bool
    ly_do: str
    vox: int = 0


@dataclass
class KetQuaKiem:
    """Phán quyết cho cả mẻ ngay trước lúc ghép."""

    cho_phep: bool
    bi_chan: list[tuple[str, str]] = field(default_factory=list)  # (tệp, lý do)


def duoc_dung_video() -> tuple[bool, str]:
    """Khâu ghép video có mở cho máy này không.

    Chỉ mở ở nấc chạy thật — tức là chỉ sau khi phán quyết kiểm bao bì đã
    được soi tay đủ và người quản trị đã duyệt. Ghép video ở nấc hiệu chỉnh
    nghĩa là đem những tấm ảnh chưa ai soi đi làm nội dung bán hàng.

    Hỏi máy chủ chứ không đoán: hỏng đường mạng thì trả FALSE. Mặc định phải
    là đóng.
    """
    from autodub import saas_client

    if not saas_client.is_configured():
        return False, "Tính năng này cần tài khoản VoxDub."
    try:
        cfg = saas_client.get_client().app_config()
    except Exception as e:  # noqa: BLE001 — không hỏi được thì coi như đóng
        logger.warning(f"Không hỏi được nấc tính năng ({e})")
        return False, "Chưa hỏi được máy chủ, thử lại sau ít phút."
    nac = str(cfg.get("imageSceneStage") or "")
    if nac == "production":
        return True, ""
    return False, ("Chức năng dựng video mở sau khi ảnh sản phẩm đã qua đợt "
                   "hiệu chỉnh và được duyệt.")


def doc_nhat_ky(thu_muc: str) -> list[AnhNguon]:
    """Đọc nhật ký tra soát, trả về mọi ảnh đã dựng ở thư mục này.

    Trả về CẢ ảnh không dùng được — giao diện cần biết vì sao một ảnh không
    được chọn, chứ không phải thấy nó biến mất không lời giải thích.
    """
    duong = os.path.join(thu_muc, NHAT_KY)
    try:
        with open(duong, encoding="utf-8") as f:
            nhat_ky = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning(f"Không đọc được nhật ký «{duong}» ({e})")
        return []

    ra: list[AnhNguon] = []
    for lan in nhat_ky.get("lich_su", []):
        for muc in lan.get("anh_da_dung", []):
            ra.append(AnhNguon(
                duong_dan=os.path.join(thu_muc, muc.get("tep", "")),
                boi_canh=muc.get("boi_canh", ""),
                ket_luan=muc.get("ket_luan", ""),
                ly_do=muc.get("ly_do", ""),
                da_kiem=bool(muc.get("da_kiem")),
                # Nhật ký của bản cũ không có hai trường này. Thiếu thì coi
                # như CHƯA đạt: mặc định phải nghiêng về phía an toàn, không
                # phải phía tiện.
                da_dong_nhan=bool(muc.get("da_dong_nhan")),
                bam_luc_kiem=str(muc.get("bam") or ""),
            ))
    return ra


def kiem_lai_truoc_khi_xuat(anh: list[AnhNguon]) -> KetQuaKiem:
    """Chạy lại toàn bộ phép kiểm ngay trước lúc ghép.

    Vì sao không tin danh sách đã chọn: giữa lúc người dùng chọn ảnh và lúc
    bấm xuất có thể là vài phút hoặc vài ngày. Tệp bị xoá, bị sửa, bị thay
    bằng ảnh khác cùng tên — không cái nào trong đó làm nhật ký đổi một chữ.
    """
    bi_chan: list[tuple[str, str]] = []
    for a in anh:
        ten = os.path.basename(a.duong_dan)
        if not a.da_kiem:
            bi_chan.append((ten, "chưa kiểm được bao bì"))
        elif a.ket_luan != "SAFE":
            bi_chan.append((ten, a.ly_do or "lệch bao bì so với ảnh gốc"))
        elif not a.da_dong_nhan:
            bi_chan.append((ten, "chưa đóng được nhãn AI-generated"))
        elif not os.path.isfile(a.duong_dan):
            bi_chan.append((ten, "không còn tệp này trên máy"))
        elif not a.bam_luc_kiem:
            # Ảnh dựng bằng bản cũ (nhật ký chưa có dấu vân tay). Không có
            # cách nào biết nó còn nguyên hay không → không cho vào video.
            bi_chan.append((ten, "ảnh dựng bằng bản cũ, chưa có dấu kiểm — "
                                 "dựng lại ảnh này rồi ghép"))
        elif bam_tep(a.duong_dan) != a.bam_luc_kiem:
            bi_chan.append((ten, "tệp đã bị sửa sau khi kiểm — nội dung không "
                                 "còn khớp tấm ảnh đã được duyệt"))
    return KetQuaKiem(cho_phep=not bi_chan and bool(anh), bi_chan=bi_chan)


#: Ảnh gửi đi kiểm liên tục thu nhỏ hẳn: việc cần nhìn là cỡ sản phẩm trong
#: khung, góc máy và tông màu — không cần đọc chữ trên nhãn (đã có bước khác
#: lo). Sáu ảnh cỡ lớn thì vượt trần thân yêu cầu của máy chủ.
_CANH_NHO = 512


def _thu_nho_de_kiem(duong_dan: str, thu_muc_tam: str) -> dict | None:
    """Thu nhỏ một ảnh về cỡ đủ để nhìn bố cục, trả {mimeType, data}."""
    import base64

    ra = os.path.join(thu_muc_tam, f"nho_{os.path.basename(duong_dan)}.jpg")
    ok = _chay_ffmpeg([
        "ffmpeg", "-y", "-i", duong_dan,
        "-vf", f"scale={_CANH_NHO}:{_CANH_NHO}:force_original_aspect_ratio=decrease",
        "-q:v", "6", ra])
    nguon = ra if ok and os.path.isfile(ra) else duong_dan
    try:
        with open(nguon, "rb") as f:
            du_lieu = base64.b64encode(f.read()).decode("ascii")
    except OSError as e:
        logger.warning(f"Không đọc được ảnh để kiểm liên tục ({e})")
        return None
    return {"mimeType": "image/jpeg", "data": du_lieu}


def _chay_ffmpeg(args: list[str], timeout: float = 60.0) -> bool:
    try:
        chay = subprocess.run(args, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning(f"ffmpeg hỏng: {e}")
        return False
    return chay.returncode == 0


def kiem_lien_tuc(anh: list[AnhNguon], *, ghi_chu: str = "",
                  khach=None) -> LienTuc:
    """Hỏi giám khảo xem các cảnh có nhìn liền mạch không.

    Chỉ chạy khi có TỪ HAI ẢNH TRỞ LÊN — một ảnh thì không có gì để so, gọi
    là tiêu tiền lấy một câu trả lời hiển nhiên.

    Hỏng thì trả `da_kiem=False` và KHÔNG chặn gì cả: đây là lớp cảnh báo,
    mất nó thì video xấu hơn chứ không nguy hiểm hơn.
    """
    import tempfile

    from autodub.saas_client import get_client, is_configured, new_job_id

    if len(anh) < 2:
        return LienTuc(da_kiem=False, muot=True, ly_do="")
    if not is_configured():
        return LienTuc(da_kiem=False, muot=True, ly_do="")

    khach = khach or get_client()
    with tempfile.TemporaryDirectory(prefix="lien_tuc_") as tam:
        anh_nho = [_thu_nho_de_kiem(a.duong_dan, tam) for a in anh[:6]]
        anh_nho = [x for x in anh_nho if x]
        if len(anh_nho) < 2:
            return LienTuc(da_kiem=False, muot=True, ly_do="")
        try:
            ket = khach.assist("scene_continuity", {"note": ghi_chu[:400]},
                               job_id=new_job_id(), images=anh_nho, timeout=60)
        except Exception as e:  # noqa: BLE001 — cảnh báo hỏng thì thôi
            logger.warning(f"Không kiểm được liên tục ({str(e)[:120]})")
            return LienTuc(da_kiem=False, muot=True, ly_do="")

    if not ket:
        return LienTuc(da_kiem=False, muot=True, ly_do="")
    dau = ket[0]
    gia_tri = str(dau.get("value", "")).strip().upper()
    if gia_tri not in ("MUOT", "LECH"):
        return LienTuc(da_kiem=False, muot=True, ly_do="")
    return LienTuc(da_kiem=True, muot=gia_tri == "MUOT",
                   ly_do=str(dau.get("reason", "")).strip())


def goi_y_kich_ban(anh: list[AnhNguon], *, san_pham: str = "",
                   khach=None) -> list[tuple[str, str]]:
    """Gợi ý câu dẫn và nhịp cho từng cảnh. Trả [(câu dẫn, gợi ý nhịp)].

    CHỈ gợi ý: không có đường nào từ đây dán chữ vào video. Câu chữ bán hàng
    là thứ người bán chịu trách nhiệm trước sàn, không phải mô hình.
    """
    from autodub.saas_client import get_client, is_configured, new_job_id

    if not anh or not is_configured():
        return []
    khach = khach or get_client()
    try:
        ket = khach.assist("scene_script", {
            "product": san_pham[:200],
            "scenes": [a.boi_canh for a in anh[:6]],
        }, job_id=new_job_id(), timeout=45)
    except Exception as e:  # noqa: BLE001 — gợi ý hỏng thì thôi
        logger.warning(f"Không lấy được gợi ý kịch bản ({str(e)[:120]})")
        return []
    return [(str(r.get("value", "")).strip(), str(r.get("reason", "")).strip())
            for r in (ket or []) if str(r.get("value", "")).strip()]


def _lenh_ghep(anh: list[str], ra: str, giay_moi_anh: float,
               giay_chuyen: float) -> list[str]:
    """Dựng lệnh ffmpeg cho một video trình chiếu có mờ chồng.

    Tách riêng để test đọc được lệnh mà không phải chạy ffmpeg thật.
    """
    lenh: list[str] = ["ffmpeg", "-y"]
    for duong in anh:
        # `-loop 1` biến ảnh tĩnh thành luồng hình; `-t` cắt đúng độ dài cần.
        lenh += ["-loop", "1", "-t", f"{giay_moi_anh:.3f}", "-i", duong]

    loc = []
    for i in range(len(anh)):
        # Đệm cho vừa khung dọc thay vì cắt: cắt là có ngày cắt mất chính
        # cái nhãn mà cả tính năng này sinh ra để giữ.
        loc.append(
            f"[{i}:v]scale={RONG}:{CAO}:force_original_aspect_ratio=decrease,"
            f"pad={RONG}:{CAO}:(ow-iw)/2:(oh-ih)/2:color=white,"
            f"setsar=1,fps=30[v{i}]")

    truoc = "v0"
    for i in range(1, len(anh)):
        sau = f"x{i}"
        mocs = (giay_moi_anh - giay_chuyen) * i
        loc.append(f"[{truoc}][v{i}]xfade=transition=fade:"
                   f"duration={giay_chuyen:.3f}:offset={mocs:.3f}[{sau}]")
        truoc = sau

    # Nhãn đi vào chính luồng RA — không phải một nhánh phụ rồi bỏ đi. Đặt
    # trên đỉnh khung vì nhãn của C1 nằm dưới đáy: chồng lên nhau thì cái sau
    # che cái trước và người xem đọc được đúng một cái.
    loc.append(
        f"[{truoc}]drawtext=text='{NHAN_VIDEO}':fontcolor=white:"
        "fontsize=h/28:box=1:boxcolor=black@0.55:boxborderw=8:"
        f"x=(w-text_w)/2:y=16:enable='lte(t,{giay_moi_anh:.3f})'[ra]")

    lenh += ["-filter_complex", ";".join(loc), "-map", "[ra]"]
    lenh += video_codec_args()
    lenh += ["-pix_fmt", "yuv420p", ra]
    return lenh


def dung_video(anh: list[AnhNguon], duong_ra: str, *,
               giay_moi_anh: float = GIAY_MOI_ANH,
               giay_chuyen: float = GIAY_CHUYEN_CANH,
               timeout: float = 300.0) -> str:
    """Ghép các ảnh đã duyệt thành một video ngắn.

    Gọi lại `kiem_lai_truoc_khi_xuat()` bên trong, KHÔNG tin bên gọi đã
    kiểm: đây là hàm duy nhất tạo ra tệp video, nên nó phải là chỗ cuối cùng
    nói được "không".
    """
    if not anh:
        raise ValueError("Chưa chọn ảnh nào.")
    if len(anh) > _TOI_DA_ANH:
        raise ValueError(f"Mỗi video tối đa {_TOI_DA_ANH} ảnh.")

    kiem = kiem_lai_truoc_khi_xuat(anh)
    if not kiem.cho_phep:
        chi_tiet = "; ".join(f"{t}: {l}" for t, l in kiem.bi_chan)
        raise PermissionError(
            f"Không xuất được video vì có ảnh không dùng để bán được — {chi_tiet}")

    os.makedirs(os.path.dirname(os.path.abspath(duong_ra)) or ".", exist_ok=True)
    lenh = _lenh_ghep([a.duong_dan for a in anh], duong_ra,
                      giay_moi_anh, giay_chuyen)
    try:
        chay = subprocess.run(lenh, capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"Không chạy được ffmpeg: {e}") from e
    if chay.returncode != 0 or not os.path.isfile(duong_ra):
        duoi = (chay.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError("Ghép video hỏng: " + " | ".join(duoi))
    return duong_ra
