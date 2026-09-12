"""Trích bằng chứng (ASR + OCR) cho Flow Blueprint — mini-spec H2 (docs/
PLAN.md, Phase H mới "Viral Flow Clone & Brand Rewrite").

Chạy HOÀN TOÀN trên máy người dùng (đúng kiến trúc dự án — không engine AI
nặng nào trong tiến trình control_server): tái dùng nguyên `prepare_audio`/
`transcribe` (ASR, `transcribe_tool.py`/`speech/transcriber.py`) và
`read_text_regions` (OCR, mini-spec H2a — KHÔNG dùng `detect_text_regions`,
hàm đó cố ý vứt nội dung chữ). Kết quả (transcript + quan sát OCR) gửi lên
`saas_client.create_flow_blueprint()` — server chỉ lo bước PHÂN TÍCH (gọi mô
hình) và LƯU, không tải/nghe/đọc chữ gì cả.

Mật độ lấy mẫu OCR THEO ĐÂY, KHÔNG dùng lại mật độ thưa của tính năng làm mờ
chữ (`style_dialog.py`, dựng cho watermark/phụ đề cháy nằm yên nhiều giây) —
đo thật ở H2a: caption ngắn 0,5 giây bị mật độ thưa đó bỏ lọt HOÀN TOÀN.
"""
from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass, field

from autodub.utils import setup_logging

logger = setup_logging("autodub.flow_blueprint")

#: Video ngắn-form H2-MVP cam kết ĐỘ PHỦ ĐẦY ĐỦ (mini-spec H2, Design
#: Choice) — dài hơn vẫn chạy được (không chặn), nhưng phải nói rõ có thể
#: bỏ sót caption chớp nhanh ở đoạn giữa (Scope A #5 của H2).
GIAY_KHUYEN_NGHI_TOI_DA = 90.0
#: Hai đầu video (đầu — hook, cuối — CTA) lấy mẫu DÀY: đo thật H2a xác nhận
#: caption 0,5 giây cần khoảng cách lấy mẫu ~0,2-0,3s mới chắc bắt được.
KHOANG_DAU_CUOI_GIAY = 5.0
GIAY_MOI_KHUNG_DAU_CUOI = 0.2
#: Đoạn giữa lấy mẫu thưa hơn — chấp nhận đánh đổi tốc độ (đo thật H2a:
#: ~1,23 giây/khung OCR trên CPU, dày cho cả video dài là chi phí thật).
GIAY_MOI_KHUNG_GIUA = 0.5


def moc_lay_mau_thich_ung(dai_giay: float) -> list[float]:
    """Mốc thời gian (giây) cần trích khung hình cho OCR — Scope A #4 của H2.

    0-5 giây đầu và 5 giây cuối: mỗi 0,2 giây. Đoạn giữa: mỗi 0,5 giây. Video
    ngắn hơn 10 giây (hai đầu chồng nhau): lấy mẫu dày cho TOÀN BỘ video.
    """
    if dai_giay <= 0:
        return []

    def rai_deu(dau: float, cuoi: float, buoc: float) -> list[float]:
        if cuoi <= dau or buoc <= 0:
            return []
        so = int(round((cuoi - dau) / buoc)) + 1
        return [round(dau + i * buoc, 2) for i in range(so) if dau + i * buoc <= cuoi + 1e-9]

    giua_con_lai = dai_giay - 2 * KHOANG_DAU_CUOI_GIAY
    if giua_con_lai <= 0:
        moc = rai_deu(0.0, dai_giay, GIAY_MOI_KHUNG_DAU_CUOI)
    else:
        moc = (
            rai_deu(0.0, KHOANG_DAU_CUOI_GIAY, GIAY_MOI_KHUNG_DAU_CUOI)
            + rai_deu(KHOANG_DAU_CUOI_GIAY, dai_giay - KHOANG_DAU_CUOI_GIAY,
                     GIAY_MOI_KHUNG_GIUA)
            + rai_deu(dai_giay - KHOANG_DAU_CUOI_GIAY, dai_giay, GIAY_MOI_KHUNG_DAU_CUOI)
        )
    return sorted(set(moc))


def ta_chinh_sach_lay_mau(dai_giay: float) -> str:
    """Mô tả mật độ lấy mẫu đã dùng — lưu vào `samplingPolicyUsed`, và cũng
    là bằng chứng cho mô hình biết độ tin cậy của phần OCR ở đoạn giữa."""
    co_ban = (f"0-{KHOANG_DAU_CUOI_GIAY:.0f}s mỗi {GIAY_MOI_KHUNG_DAU_CUOI}s, "
             f"giữa mỗi {GIAY_MOI_KHUNG_GIUA}s, "
             f"{KHOANG_DAU_CUOI_GIAY:.0f}s cuối mỗi {GIAY_MOI_KHUNG_DAU_CUOI}s")
    if dai_giay > GIAY_KHUYEN_NGHI_TOI_DA:
        return (f"{co_ban} (video {dai_giay:.0f}s, dài hơn mức H2-MVP cam kết "
                f"độ phủ đầy đủ {GIAY_KHUYEN_NGHI_TOI_DA:.0f}s — đoạn giữa có "
                "thể bỏ sót caption chớp nhanh)")
    return co_ban


#: Hai quan sát cùng chữ nhưng cách xa hơn mức này thì coi là HAI LẦN XUẤT
#: HIỆN riêng (chữ đã tắt rồi hiện lại), không phải một khoảng liên tục —
#: gấp đôi bước lấy mẫu thưa nhất (0,5s) + biên an toàn cho việc OCR đôi khi
#: bỏ lỡ đúng 1 khung liên tiếp.
KHOANG_CACH_TOI_DA_DE_GOP_GIAY = 1.0


#: Trần số mẩu bằng chứng gửi lên máy chủ, KHỚP `maxItems` của
#: `control_server/src/routes/flow-blueprints.js`. Có test chốt hai bên không
#: lệch nhau — đổi một bên mà quên bên kia là lỗi quay lại y hệt.
SO_BANG_CHUNG_TOI_DA = 400


def gioi_han_bang_chung(muc: list[dict], *, ten: str,
                        tran: int = SO_BANG_CHUNG_TOI_DA) -> tuple[list[dict], str]:
    """Giữ tối đa ``tran`` mẩu, RẢI ĐỀU dòng thời gian. Trả `(mẩu, ghi chú)`.

    Vì sao cần: người dùng bấm «Bỏ qua, không tốn Vox» thì bản đọc giữ nguyên
    RapidOCR thô — mỗi khung vài vùng chữ, mỗi vùng lệch nhau vài ký tự vì
    OCR tiếng Việt nhiễu. `gop_quan_sat_lien_tiep` so ``text`` NGUYÊN VĂN nên
    gần như không gộp được gì, và số mẩu vượt trần của máy chủ. Lượt chạy
    thật 12/09: người dùng chờ bốn phút rồi nhận đúng một dòng tiếng Anh
    *"must NOT have more than 400 items"*.

    Tức nhánh RẺ TIỀN là nhánh duy nhất hỏng — làm đúng lời khuyên thì mất
    thời gian mà không được gì.

    **Rải đều, không cắt đuôi.** Lấy 400 mẩu đầu rồi bỏ phần sau là mất sạch
    bằng chứng nửa cuối video; mô hình thấy chữ dày đặc ở đầu, im lặng ở
    cuối, rồi kết luận nhịp video đúng như thế. Đó tệ hơn cả việc không có
    bằng chứng.

    Ghi chú trả về phải đi vào ``samplingPolicyUsed`` — cắt im lặng là để mô
    hình nói chắc nịch trên nền bằng chứng đã bị xén (ràng buộc E.1 của
    `docs/MINI-SPEC_E6_Bot_Khung_OCR.md`).
    """
    if len(muc) <= tran:
        return muc, ""
    goc = len(muc)
    # Chọn theo chỉ số rải đều rồi giữ NGUYÊN thứ tự thời gian.
    buoc = goc / tran
    giu = [muc[min(int(i * buoc), goc - 1)] for i in range(tran)]
    ghi_chu = (f"{ten}: giữ {tran}/{goc} mẩu bằng chứng, rải đều dòng thời "
               f"gian (trần của máy chủ) — phần bị lược có thể chứa chữ "
               f"chớp nhanh")
    logger.info("Bằng chứng %s vượt trần: %d -> %d, rải đều", ten, goc, tran)
    return giu, ghi_chu


def gop_quan_sat_lien_tiep(quan_sat: list[dict]) -> list[dict]:
    """Gộp các quan sát OCR GIỐNG HỆT NHAU, xuất hiện GẦN NHAU về thời gian
    (không quá `KHOANG_CACH_TOI_DA_DE_GOP_GIAY`), thành một dòng — Scope A
    của H2: "có thể gộp các observation giống nhau liên tiếp NẾU VÀ CHỈ NẾU
    có rule xác định, test được, và không làm mất timestamp".

    Rule: cùng ``text`` (so sánh nguyên văn, không chuẩn hoá — hai lần đọc
    RA CHỮ KHÁC NHAU dù chỉ khác 1 ký tự vẫn là 2 dòng riêng) VÀ cùng
    ``status``, VÀ khoảng cách tới lần xuất hiện liền trước không vượt
    `KHOANG_CACH_TOI_DA_DE_GOP_GIAY` — nếu không, dù trùng nội dung vẫn tách
    thành quan sát riêng (chữ đã biến mất rồi xuất hiện lại KHÔNG phải một
    khoảng thời gian liên tục). Không mất mốc thời gian (chỉ mất các mốc
    TRÙNG LẶP ở giữa một chuỗi thật sự liên tục).

    ``quan_sat``: mỗi item ``{"text","status","start_s"/"timestamp_s","end_s"?}``
    — nhận cả quan sát thô của `read_text_regions()` (chỉ có `timestamp_s`,
    một điểm) lẫn dạng đã có khoảng (`start_s`/`end_s`).
    """
    if not quan_sat:
        return []

    def moc(o: dict) -> tuple[float, float]:
        if "start_s" in o and "end_s" in o:
            return float(o["start_s"]), float(o["end_s"])
        t = float(o.get("timestamp_s") or 0.0)
        return t, t

    sap = sorted(quan_sat, key=lambda o: moc(o)[0])
    ra: list[dict] = []
    for o in sap:
        dau, cuoi = moc(o)
        text = str(o.get("text", ""))
        status = str(o.get("status", ""))
        lien_tuc = (ra and ra[-1]["text"] == text and ra[-1]["status"] == status
                   and dau - ra[-1]["end_s"] <= KHOANG_CACH_TOI_DA_DE_GOP_GIAY)
        if lien_tuc:
            ra[-1]["end_s"] = max(ra[-1]["end_s"], cuoi)
            continue
        ra.append({"text": text, "status": status, "start_s": dau, "end_s": cuoi})
    return ra


@dataclass
class BangChungFlowBlueprint:
    """Bằng chứng đã trích, sẵn sàng gửi cho
    `saas_client.create_flow_blueprint()` — KHÔNG lưu xuống đĩa dự án (khác
    hồ sơ dub), chỉ tồn tại trong bộ nhớ cho một lượt gọi."""

    source_type: str          # "url" | "file"
    source_reference: str
    title: str = ""
    language_source_detected: str = ""
    sampling_policy_used: str = ""
    evidence_summary: str = ""
    transcript: list[dict] = field(default_factory=list)     # [{start_s,end_s,text}]
    ocr_evidence: list[dict] = field(default_factory=list)    # [{start_s,end_s,status,text}]


def trich_bang_chung(
    source: str, work_dir: str, settings, *,
    cancel_event=None, progress=None, xin_phep=None,
) -> BangChungFlowBlueprint:
    """Tải video (nếu là liên kết) + chép lời (ASR) + đọc chữ overlay (OCR)
    — Scope C.1/C.2 của H2.

    ``source``: liên kết (TikTok/Facebook/YouTube dùng pipeline tải đã có;
    Douyin cần cookie, thiếu thì báo lỗi rõ chứ không thử lại vô ích — hành
    vi này đã có sẵn ở `download_one`/`prepare_audio`, không cần code
    riêng) hoặc đường dẫn file trên máy.

    ``xin_phep(so_vox, so_khung) -> bool`` đi thẳng xuống `read_text_regions`
    rồi `doc_lai_bang_may_chu`, nơi hỏi người dùng trước khi tiêu quá
    `NGUONG_XIN_PHEP_VOX`. Không truyền thì chạy như cũ.

    Không đọc được ASR/OCR (thiếu bộ cài, engine lỗi) KHÔNG chặn cả lượt —
    Constraint 5 của H2: đánh dấu evidence thiếu, không bịa nội dung. Chỉ
    ném lỗi khi KHÔNG tải/đọc được video (không có gì để phân tích).
    """
    def say(step: str, detail: str = "") -> None:
        logger.info("%s %s", step, detail)
        if progress:
            progress(step, detail)

    from autodub.speech.transcriber import TranscribeCancelled
    from autodub.transcribe_tool import TranscribeError, prepare_audio

    say("download", "Đang chuẩn bị video…")
    tmp_dir = os.path.join(work_dir, "_flow_blueprint_tam")
    os.makedirs(tmp_dir, exist_ok=True)
    audio_path, title, media_path = prepare_audio(source, tmp_dir, settings=settings)

    # --- ASR (Scope C.2) --------------------------------------------------
    say("asr", "Đang nghe và chép lời…")
    from autodub.speech.transcriber import transcribe as run_asr

    detected: dict = {}
    canh_bao: list[str] = []
    try:
        segments = run_asr(audio_path, "", settings, cancel_event=cancel_event,
                           detected_out=detected)
        transcript = [{"start_s": round(float(s.get("start", 0)), 2),
                      "end_s": round(float(s.get("end", 0)), 2),
                      "text": str(s.get("text", "")).strip()}
                     for s in segments if str(s.get("text", "")).strip()]
    except TranscribeCancelled:
        # Người dùng bấm Dừng — KHÔNG phải hỏng. Để nó bay lên nguyên vẹn cho
        # worker nhận ra là huỷ; nuốt ở đây thì lượt chạy đi tiếp sau khi đã
        # được bảo dừng.
        raise
    except RuntimeError as e:
        # Bắt RuntimeError chứ KHÔNG chỉ `TranscribeError` — tìm ra 11/09.
        #
        # `TranscribeError` là CON của `RuntimeError`, nhưng `transcriber.py`
        # ném `RuntimeError` TRẦN ở bảy chỗ: chưa cài `.venv-whisper`, máy hết
        # bộ nhớ cho mọi model, worker Whisper trả lỗi… Những lỗi đó lọt qua
        # `except TranscribeError` và **giết cả lượt phân tích**, trong khi
        # docstring của hàm này hứa ngược lại:
        #
        #   "Không đọc được ASR/OCR (thiếu bộ cài, engine lỗi) KHÔNG chặn cả
        #    lượt — Constraint 5 của H2"
        #
        # Hậu quả thật: máy chưa cài bộ nghe thì người dùng nhận "Phân tích
        # thất bại" thay vì một Flow Blueprint dựng từ chữ trên hình — mà OCR
        # thì vẫn chạy tốt.
        logger.warning("ASR không chạy được cho Flow Blueprint (%s)", e)
        transcript = []
        canh_bao.append(f"Không chép lời được: {e}")

    ngon_ngu = str(detected.get("language") or "")

    # --- OCR (Scope C.2 — tái dùng H2a, KHÔNG dùng detect_text_regions) ---
    say("ocr", "Đang đọc chữ trên hình…")
    from autodub.media.video import extract_frame, probe_duration_s

    dai_giay = probe_duration_s(media_path) or 0.0
    moc = moc_lay_mau_thich_ung(dai_giay)
    chinh_sach = ta_chinh_sach_lay_mau(dai_giay)

    ocr_evidence: list[dict] = []
    # Khai báo TRƯỚC nhánh `if moc`: video không đọc được thời lượng thì `moc`
    # rỗng, và phần tóm tắt ở cuối hàm vẫn đọc ba biến này. Để chúng bên trong
    # nhánh là ném NameError đúng vào lúc mọi thứ đã trục trặc sẵn.
    anh_paths: list[str] = []
    moc_lay_duoc: list[float] = []
    chon_bo_doc = ""
    if moc:
        with tempfile.TemporaryDirectory(prefix="voxdub_flow_ocr_") as khung_dir:
            for i, t in enumerate(moc):
                if cancel_event is not None and cancel_event.is_set():
                    break
                out = os.path.join(khung_dir, f"khung_{i}.png")
                try:
                    extract_frame(media_path, out, at_seconds=t)
                except Exception as e:  # noqa: BLE001 — thiếu 1 khung không sao
                    logger.warning("Không trích được khung %.2fs (%s)", t, e)
                    continue
                anh_paths.append(out)
                moc_lay_duoc.append(t)

            if anh_paths:
                from autodub.media.text_regions import (
                    BO_DOC_CUC_BO, BO_DOC_MAY_CHU, ChuaCaiOcr, DocChuThatBai,
                    read_text_regions,
                )

                # H2b: OCR tại máy KHÔNG phát ra được dấu tiếng Việt (giới
                # hạn từ điển của model, xem docs/MINI-SPEC_H2b...). Có máy
                # chủ thì đọc lại bằng mô hình nhìn ảnh — chỉ những khung
                # THẬT SỰ đổi chữ mới bị gửi đi, xem `doc_chu_may_chu`.
                # Chưa cấu hình máy chủ thì vẫn chạy, chỉ là chữ mất dấu:
                # thà phân tích với bằng chứng kém còn hơn không phân tích.
                from autodub import saas_client
                chon_bo_doc = (BO_DOC_MAY_CHU if saas_client.is_configured()
                              else BO_DOC_CUC_BO)

                try:
                    _bat_dau_ocr = time.monotonic()
                    ket = read_text_regions(anh_paths, settings=settings,
                                            cancel_event=cancel_event,
                                            moc_thoi_gian=moc_lay_duoc,
                                            bo_doc=chon_bo_doc,
                                            xin_phep=xin_phep)
                    # E6 giai đoạn 0 — CHỈ ĐO, không đổi hành vi. Đây là tầng
                    # duy nhất có đủ cả bằng chứng OCR lẫn transcript, mà câu
                    # hỏi chính ("bao nhiêu đoạn OCR trùng lời đọc") cần cả
                    # hai. Tốn 0 Vox: chỗ này chạy kể cả khi người dùng bấm
                    # "Bỏ qua" ở cổng xin phép.
                    from autodub.media.doc_chu_may_chu import ghi_chan_doan_ocr
                    ghi_chan_doan_ocr(
                        work_dir, ket.quan_sat, transcript=transcript,
                        giay_ocr=time.monotonic() - _bat_dau_ocr,
                        dai_giay=dai_giay, so_moc=len(moc),
                        thoi_gian_ocr=getattr(ket, "thoi_gian", None))
                    tho = [{"text": q.text, "status": q.status,
                           "timestamp_s": q.timestamp_s}
                          for q in ket.quan_sat]
                    ocr_evidence = gop_quan_sat_lien_tiep(tho)
                except ChuaCaiOcr as e:
                    logger.info("Chưa cài OCR — Flow Blueprint chạy tiếp không "
                               "có bằng chứng chữ trên hình (%s)", e)
                    canh_bao.append(
                        "Chưa cài bộ đọc chữ overlay — phân tích chỉ dựa trên "
                        "lời nói/timeline.")
                except DocChuThatBai as e:
                    logger.warning("Đọc chữ overlay lỗi (%s)", e)
                    canh_bao.append(
                        "Không đọc được chữ overlay do lỗi kỹ thuật — phân "
                        "tích chỉ dựa trên lời nói/timeline.")

    # Áp trần TRƯỚC khi chốt `sampling_policy_used`: ghi chú cắt bớt phải vào
    # được lời nhắc, nếu không mô hình không biết bằng chứng đã bị xén.
    ocr_evidence, _ghi_ocr = gioi_han_bang_chung(ocr_evidence, ten="OCR")
    transcript, _ghi_asr = gioi_han_bang_chung(transcript, ten="Lời nói")
    for _g in (_ghi_ocr, _ghi_asr):
        if _g:
            chinh_sach = f"{chinh_sach}. {_g}" if chinh_sach else _g
            canh_bao.append(_g)

    if not transcript and not ocr_evidence:
        raise TranscribeError(
            "Không có lời nói lẫn chữ overlay nào đọc được từ video này — "
            "không đủ bằng chứng để phân tích cấu trúc.")

    # Số khung lấy mẫu đi vào tóm tắt: nó LƯU cùng blueprint nên về sau còn
    # đối chiếu được "lấy mẫu bao nhiêu / còn lại bao nhiêu quan sát", thay vì
    # chỉ nằm trong Nhật ký của một lượt chạy rồi mất.
    tom_tat = (f"ASR: {len(transcript)} câu"
              + (f" (ngôn ngữ: {ngon_ngu})" if ngon_ngu else " (chưa nhận ra ngôn ngữ)")
              + f". OCR: {len(ocr_evidence)} quan sát"
              + f" từ {len(moc_lay_duoc)} khung lấy mẫu."
              + (f" Bộ đọc: {chon_bo_doc}." if anh_paths else ""))
    if canh_bao:
        tom_tat += " " + " ".join(canh_bao)

    return BangChungFlowBlueprint(
        source_type=("url" if source.lower().startswith(("http://", "https://")) else "file"),
        source_reference=source,
        title=title,
        language_source_detected=ngon_ngu,
        sampling_policy_used=chinh_sach,
        evidence_summary=tom_tat,
        transcript=transcript,
        ocr_evidence=ocr_evidence,
    )
