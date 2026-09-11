"""Đọc lại chữ overlay bằng mô hình nhìn ảnh trên máy chủ — mini-spec H2b
(09/09/2026).

**Vì sao cần**: bộ OCR chạy trên máy (RapidOCR, model bundled
``ch_PP-OCRv4_rec_infer.onnx``) có từ điển đầu ra 6.623 ký tự mà CHỈ 2 ký tự
thuộc bộ tiếng Việt có dấu (``É``, ``Ó``). Các chữ ``ă â đ ê ô ơ ư`` và mọi
dấu thanh KHÔNG nằm trong từ điển, nên model không thể phát ra chúng — dù ảnh
nét tới đâu, dù chỉnh tham số gì. Đo thật 09/09 trên khung hình video nén:
"Đăng ký kênh để không bỏ lỡ video mới!" đọc ra "Dang ky kenh de khong bo lo
video moi", **confidence vẫn 0,84-0,99**.

**Vì sao không chỉ đổi model OCR**: các từ điển thay thế đều không đủ —
``latin_dict`` của PaddleOCR thiếu 102/134 ký tự Việt, ``ppocrv5_latin_dict``
thiếu 90/134, ``vi_dict`` đủ chữ thường nhưng thiếu 66 chữ HOA có dấu.
PaddlePaddle không phát hành model nhận dạng tiếng Việt chính thức. Đo thêm:
Tesseract ``vie`` (nhẹ, 1,5 MB) ra dấu thật nhưng chỉ đúng ~87% và còn nhiễu
ký tự; VietOCR đúng hơn nhưng kéo theo 1,5 GB PyTorch + trọng số 151,8 MB tải
từ một tên miền cá nhân (đo được 60 KB/s ⇒ ~42 phút) nên không hợp cho bản
``.exe`` gửi người dùng cuối.

**Nguyên tắc quan trọng nhất của module này — KHÔNG gửi mọi khung hình lên
máy chủ.** RapidOCR đọc mất dấu nhưng vẫn phân biệt rất tốt "khung này có chữ
KHÁC khung trước", vì phần phụ âm/chữ số vẫn đúng. Nên: dùng RapidOCR (miễn
phí, tại máy) để chia các khung thành từng ĐOẠN chữ giống nhau, rồi chỉ gửi
MỘT khung đại diện cho mỗi đoạn, và áp kết quả đọc đúng cho cả đoạn. Video 60
giây lấy mẫu thích ứng ra ~152 khung nhưng thường chỉ có ~15 caption khác
nhau — tiết kiệm khoảng 10 lần cả tiền lẫn thời gian.
"""
from __future__ import annotations

import logging
from dataclasses import replace

logger = logging.getLogger(__name__)

#: Số khung gửi trong MỘT lượt gọi. Bằng đúng `soAnhToiDa` của tác vụ
#: `doc_chu_khung_hinh` phía máy chủ VÀ trần `images.maxItems` của route
#: `/v1/ai/assist` — gửi quá là bị chặn ở tầng schema với một lỗi trống không.
SO_KHUNG_MOI_LUOT = 6

#: Cạnh dài tối đa của khung hình gửi đi. Đo thật 09/09: thu nhỏ về 640px vẫn
#: đọc đúng 100% trên khung hình video nén, mà nhẹ hơn hẳn ảnh gốc (0,7 MB
#: PNG → ~60 KB JPEG). Trần tổng dung lượng ảnh của máy chủ là thật, không
#: phải lý thuyết: gửi 6 ảnh gốc là chạm trần và bị trả 413.
CANH_DAI_TOI_DA = 640


def _khoa_doan(quan_sat_cua_khung: list) -> str:
    """Dấu hiệu nhận biết "khung này đang hiện đúng chữ đó".

    Ghép nội dung các vùng chữ của MỘT khung theo thứ tự đọc (trên xuống, rồi
    trái sang phải). Dùng bản RapidOCR đọc được — mất dấu cũng không sao, vì
    ở đây chỉ cần so khung này với khung liền trước, không cần đọc hiểu.
    """
    sap = sorted(quan_sat_cua_khung, key=lambda q: (round(q.y, 2), round(q.x, 2)))
    return "".join(q.text.strip().lower() for q in sap if q.text.strip())


def chia_doan(quan_sat: list) -> list[list[int]]:
    """Chia các khung thành từng đoạn LIÊN TIẾP có cùng chữ.

    Trả về danh sách đoạn, mỗi đoạn là danh sách ``frame_index`` theo thứ tự
    tăng dần. Khung không có chữ nào không thuộc đoạn nào (không cần đọc lại).

    Chỉ gộp khung LIỀN KỀ nhau: cùng một câu caption xuất hiện, biến mất, rồi
    xuất hiện lại là hai lần hiện KHÁC nhau trên dòng thời gian — gộp chúng
    làm một là bịa ra một khoảng thời gian liên tục không có thật (cùng lý lẽ
    với `flow_blueprint.gop_quan_sat_lien_tiep`).
    """
    theo_khung: dict[int, list] = {}
    for q in quan_sat:
        theo_khung.setdefault(q.frame_index, []).append(q)

    doan: list[list[int]] = []
    khoa_truoc = None
    for chi_so in sorted(theo_khung):
        khoa = _khoa_doan(theo_khung[chi_so])
        if not khoa:
            khoa_truoc = None
            continue
        lien_tuc = (doan and khoa == khoa_truoc
                    and chi_so == doan[-1][-1] + 1)
        if lien_tuc:
            doan[-1].append(chi_so)
        else:
            doan.append([chi_so])
        khoa_truoc = khoa
    return doan


def _anh_gui_di(duong_dan: str) -> dict | None:
    """Thu nhỏ + mã hoá base64 một khung hình. Trả None nếu ảnh hỏng — thiếu
    một khung không được giết cả lượt đọc.

    Dùng **ffmpeg** qua `thu_nho_de_gui`, KHÔNG dùng PIL. Bản đầu của hàm này
    gọi `PIL.Image` — mà `autodub.spec` cố ý loại PIL khỏi bản đóng gói, luật
    đã ghi sẵn ở `product_scene.chuan_bi_anh()`. Hậu quả khi chạy từ tệp
    `.exe`: mọi khung đều trả None, không khung nào được gửi đi, H2b lặng lẽ
    rơi về bản đọc MẤT DẤU — tức là cổng 2 của pilot không bao giờ đóng được,
    và triệu chứng trông y hệt "mô hình đọc sai".
    """
    import os

    from autodub.product_scene import thu_nho_de_gui

    thu_muc = os.path.dirname(duong_dan) or "."
    ten_tam = f"_gui_{os.path.basename(duong_dan)}.jpg"
    try:
        return thu_nho_de_gui(duong_dan, thu_muc, ten_tam,
                              canh_dai=CANH_DAI_TOI_DA)
    except (OSError, ValueError) as e:
        logger.warning("Không chuẩn bị được khung hình %s (%s)", duong_dan, e)
        return None


def doc_lai_bang_may_chu(quan_sat: list, image_paths: list[str], *,
                         client=None, cancel_event=None) -> list:
    """Đọc lại nội dung chữ bằng mô hình nhìn ảnh, giữ nguyên dòng thời gian.

    ``quan_sat`` là kết quả RapidOCR tại máy (đã mất dấu). Hàm này giữ lại
    khung/mốc thời gian của chúng, chỉ THAY nội dung chữ bằng bản đọc đúng.

    Hỏng ở bất kỳ đâu (chưa cấu hình máy chủ, mạng lỗi, hết Vox) thì **trả về
    nguyên bản đọc cục bộ**, không ném. Lý do: chữ mất dấu vẫn dùng được cho
    việc phân tích cấu trúc, còn ném lỗi ở đây là giết cả lượt phân tích chỉ
    vì phần làm-cho-đẹp-hơn không chạy được. Chỗ hỏng vẫn phải LỘ RA trong
    Nhật ký, không nuốt im lặng.
    """
    doan = chia_doan(quan_sat)
    if not doan:
        return quan_sat

    from autodub import saas_client
    if client is None:
        if not saas_client.is_configured():
            logger.info("Chưa cấu hình máy chủ VoxDub — giữ bản đọc tại máy "
                        "(chữ tiếng Việt sẽ không có dấu)")
            return quan_sat
        client = saas_client.SaasClient()

    dai_dien = [d[0] for d in doan]
    doc_duoc: dict[int, list[str]] = {}

    for dau in range(0, len(dai_dien), SO_KHUNG_MOI_LUOT):
        if cancel_event is not None and cancel_event.is_set():
            break
        lo = dai_dien[dau:dau + SO_KHUNG_MOI_LUOT]
        anh = []
        khung_cua_anh = []
        for chi_so in lo:
            if chi_so >= len(image_paths):
                continue
            goi = _anh_gui_di(image_paths[chi_so])
            if goi is not None:
                anh.append(goi)
                khung_cua_anh.append(chi_so)
        if not anh:
            continue
        try:
            ket = client.assist(
                "doc_chu_khung_hinh", {"soAnh": len(anh)},
                job_id=saas_client.new_job_id(), images=anh)
        except Exception as e:  # noqa: BLE001 — mọi lỗi đều rơi về bản cục bộ
            logger.warning("Đọc chữ qua máy chủ hỏng (%s) — giữ bản đọc tại "
                           "máy cho lô này", e)
            continue
        for muc in ket or []:
            so = muc.get("anh") if isinstance(muc, dict) else None
            if not isinstance(so, int) or not 1 <= so <= len(khung_cua_anh):
                continue
            dong = [str(d).strip() for d in (muc.get("dong") or []) if str(d).strip()]
            doc_duoc[khung_cua_anh[so - 1]] = dong

    # Ghi lại đúng con số đã tiết kiệm được. Không có dòng này thì không ai
    # kiểm chứng được lời hứa "chỉ gửi khung đại diện" — mà đó là tiền thật:
    # mỗi khung gửi đi tốn ~1.150 token.
    logger.info(
        "Đọc chữ qua máy chủ: %d khung lấy mẫu -> %d đoạn chữ khác nhau -> "
        "gửi %d khung (%d khung đọc được kết quả)",
        len(image_paths), len(doan), len(dai_dien), len(doc_duoc))

    if not doc_duoc:
        return quan_sat

    return _ap_ket_qua(quan_sat, doan, doc_duoc)


def _ap_ket_qua(quan_sat: list, doan: list[list[int]],
                doc_duoc: dict[int, list[str]]) -> list:
    """Áp bản đọc đúng của khung đại diện cho MỌI khung trong cùng đoạn.

    Đoạn nào máy chủ không đọc được thì giữ nguyên quan sát cục bộ của đoạn
    đó — trộn được phần nào hay phần đó, không phải được-tất-cả-hoặc-không.
    """
    theo_khung: dict[int, list] = {}
    for q in quan_sat:
        theo_khung.setdefault(q.frame_index, []).append(q)

    # Khoá sắp xếp phụ = thứ tự ĐƯA VÀO, không phải nội dung chữ: phụ đề
    # song ngữ ("Excuse me" trên, "Xin lỗi" dưới) mà xếp theo chữ cái là đảo
    # mất thứ tự đọc trên→dưới của khung đó.
    ra: list[tuple[int, int, object]] = []
    da_xu_ly: set[int] = set()
    for cac_khung in doan:
        dai_dien = cac_khung[0]
        if dai_dien not in doc_duoc:
            continue
        dong = doc_duoc[dai_dien]
        for chi_so in cac_khung:
            da_xu_ly.add(chi_so)
            mau = theo_khung.get(chi_so) or []
            if not mau:
                continue
            # Giữ mốc thời gian của khung, thay nội dung. Không có dòng nào
            # (máy chủ đọc ra "khung này không chữ") thì khung đó biến mất
            # khỏi kết quả — đúng nghĩa "không có chữ", không phải giữ lại
            # bản đọc sai của OCR cục bộ.
            for thu_tu, van_ban in enumerate(dong):
                goc = mau[min(thu_tu, len(mau) - 1)]
                ra.append((chi_so, thu_tu, replace(
                    goc, text=van_ban, confidence=None, source="may_chu",
                    status="ok")))

    for chi_so, mau in theo_khung.items():
        if chi_so not in da_xu_ly:
            ra.extend((chi_so, thu_tu, q) for thu_tu, q in enumerate(mau))

    ra.sort(key=lambda muc: (muc[0], muc[1]))
    return [q for _khung, _thu_tu, q in ra]
