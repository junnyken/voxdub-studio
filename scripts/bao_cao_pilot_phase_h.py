#!/usr/bin/env python3
"""Gom bằng chứng sau lượt pilot Phase H (H2 → H2b → H2c → H3).

Vì sao có tệp này: bảy loại bằng chứng cần thu sau pilot nằm rải rác ở màn
hình app, API và Nhật ký. Chép tay thì vừa sót vừa lẫn giữa các lượt chạy, mà
đây lại là thứ dùng để quyết định có mở H4 hay không.

Chạy trên MÁY ĐÃ CHẠY PILOT (cần `VOXDUB_API_URL` và token thiết bị của chính
máy đó — script đọc qua `saas_client` như app vẫn làm):

    python3 scripts/bao_cao_pilot_phase_h.py
    python3 scripts/bao_cao_pilot_phase_h.py --ra bao-cao.md

**KHÔNG in transcript/caption gốc của video tham khảo.** Dấu vân tay chỉ ra
metadata (số băm, số dòng, có chạm trần không) — đúng cam kết của H2c là máy
chủ không trở thành kho câu chữ nguyên văn của người khác, nên báo cáo cũng
không được phá cam kết đó.
"""
from __future__ import annotations

import argparse
import sys

# Cho phép chạy thẳng từ thư mục gốc dự án mà không cần cài gói.
sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])


def _muc(tieu_de: str) -> str:
    return f"\n## {tieu_de}\n"


def _bang(cot: list[str], hang: list[list[str]]) -> str:
    ra = ["| " + " | ".join(cot) + " |",
          "|" + "|".join("---" for _ in cot) + "|"]
    for h in hang:
        ra.append("| " + " | ".join(str(c).replace("|", "\\|") for c in h) + " |")
    return "\n".join(ra)


def _giay(x) -> str:
    try:
        return f"{float(x):.1f}s"
    except (TypeError, ValueError):
        return "?"


def dung_bao_cao(client) -> str:
    from autodub import saas_client

    phan: list[str] = ["# Báo cáo pilot Phase H", ""]
    phan.append(f"Máy chủ: `{saas_client.resolve_api_url()}`")

    # --- 1. Flow Blueprint theo dòng thời gian ---------------------------
    blueprints = client.list_flow_blueprints()
    phan.append(_muc("1. Flow Blueprint"))
    if not blueprints:
        phan.append("**CHƯA CÓ FLOW BLUEPRINT NÀO.** Pilot chưa chạy được bước "
                    "H2 — mọi mục sau đều không kết luận được.")
        return "\n".join(phan)

    bp = client.get_flow_blueprint(blueprints[0]["id"])   # mới nhất
    phan.append(f"- Nguồn: `{bp.get('sourceType')}` — {bp.get('sourceReference')}")
    phan.append(f"- Ngôn ngữ nhận ra: `{bp.get('languageSourceDetected') or '(không rõ)'}`")
    phan.append(f"- Trạng thái: `{bp.get('status')}`")
    phan.append(f"- Mật độ lấy mẫu: {bp.get('samplingPolicyUsed')}")
    phan.append(f"- Tóm tắt bằng chứng: {bp.get('evidenceSummary')}")
    phan.append("")
    phan.append(_bang(
        ["Từ", "Đến", "Vai trò", "Mô tả (trừu tượng)", "Bằng chứng"],
        [[_giay(b.get("startS")), _giay(b.get("endS")), b.get("beatType"),
          (b.get("narrativeFunctionVi") or "")[:70],
          b.get("evidenceStatus")] for b in bp.get("beats") or []]))

    # --- 2. Dấu vân tay H2c (CHỈ metadata) --------------------------------
    phan.append(_muc("2. Dấu vân tay bằng chứng (H2c)"))
    vt = bp.get("evidenceFingerprint")
    if not vt:
        phan.append("**KHÔNG CÓ DẤU VÂN TAY.** H3 sẽ luôn cho ra `unconfirmed` "
                    "với blueprint này — cổng số 3 KHÔNG đóng được.")
    else:
        phan.append(_bang(
            ["Phiên bản bộ kiểm", "Số băm", "Số dòng bằng chứng",
             "Dòng bỏ qua (chưa xác nhận)", "Chạm trần"],
            [[vt.get("v"), vt.get("soBam"), vt.get("soDong"),
              vt.get("soDongBoQua"), "CÓ" if vt.get("dayTran") else "không"]]))
        if vt.get("dayTran"):
            phan.append("\n> Chạm trần nghĩa là vùng phủ KHÔNG đầy đủ — H3 sẽ "
                        "đánh `unconfirmed`, đúng thiết kế.")
        phan.append("\n*(Không in transcript/caption gốc — đúng cam kết H2c.)*")

    # --- 3. Hồ sơ brand dùng cho pilot ------------------------------------
    phan.append(_muc("3. Hồ sơ thương hiệu"))
    brands = client.list_brand_profiles()
    if not brands:
        phan.append("**CHƯA CÓ HỒ SƠ NÀO** — H3 không chạy được.")
    else:
        phan.append(_bang(
            ["Tên", "Có mô tả SP", "Có đối tượng", "Có tone", "Có USP", "Số ràng buộc cấm"],
            [[b.get("tenBrand"),
              "có" if (b.get("moTaSanPham") or "").strip() else "**THIẾU**",
              "có" if (b.get("doiTuongKhach") or "").strip() else "**THIẾU**",
              "có" if (b.get("toneGiong") or "").strip() else "**THIẾU**",
              "có" if (b.get("usp") or "").strip() else "**THIẾU**",
              len(b.get("rangBuocKhongDuocNoi") or [])] for b in brands]))
        phan.append("\n*(Cố ý không in nội dung USP/mô tả — có thể là thông tin "
                    "kinh doanh nhạy cảm.)*")

    # --- 4 + 5. BrandScript theo beat, gồm cả hai ca gate cố tình ---------
    phan.append(_muc("4. Kịch bản đã sinh"))
    scripts = client.list_brand_scripts()
    if not scripts:
        phan.append("**CHƯA CÓ KỊCH BẢN NÀO** — cổng số 4 chưa đóng được.")
    else:
        phan.append(_bang(
            ["#", "Trạng thái", "Số đoạn", "Phiên bản bộ kiểm", "Tạo lúc"],
            [[i + 1, s.get("status"), len(s.get("beats") or []),
              s.get("originalityCheckVersion"), s.get("createdAt")]
             for i, s in enumerate(scripts)]))

        for i, s in enumerate(scripts, 1):
            phan.append(f"\n### Kịch bản {i} — `{s.get('status')}`\n")
            phan.append(_bang(
                ["Đoạn", "Nguyên gốc", "Tuân thủ", "Cụm bị chặn / lý do"],
                [[b.get("beatType"), b.get("originalityFlag"), b.get("complianceFlag"),
                  (b.get("flaggedExcerpt") or b.get("complianceExcerpt")
                   or b.get("lyDoChuaKiem") or "")]
                 for b in s.get("beats") or []]))

        phan.append(_muc("5. Hai ca gate cố tình làm sai"))
        co_chan = [s for s in scripts if s.get("status") == "blocked"]
        co_sach = [s for s in scripts if s.get("status") == "ready"]
        phan.append(_bang(
            ["Ca", "Có bằng chứng chưa?"],
            [["Kịch bản sạch ra `ready`",
              "ĐẠT" if co_sach else "**CHƯA CÓ**"],
             ["Có kịch bản bị `blocked` (gate chặn thật)",
              "ĐẠT" if co_chan else "**CHƯA CÓ** — chưa kích hoạt được gate nào"]]))
        vi_pham = [b for s in scripts for b in (s.get("beats") or [])
                   if b.get("complianceFlag") == "violated"]
        trung = [b for s in scripts for b in (s.get("beats") or [])
                 if b.get("originalityFlag") == "flagged"]
        phan.append("")
        phan.append(f"- Đoạn bị chặn vì **cụm brand tự cấm**: {len(vi_pham)}")
        phan.append(f"- Đoạn bị chặn vì **trùng câu chữ nguồn**: {len(trung)}")
        if not vi_pham:
            phan.append("  > Chưa kích hoạt được ca claim cấm — thêm một cụm "
                        "cấm vào hồ sơ brand rồi sinh lại kịch bản.")

    # --- 6. Số liệu chạy thật --------------------------------------------
    phan.append(_muc("6. Số liệu chạy thật"))
    phan.append("Lấy từ Nhật ký app (dòng do `doc_chu_may_chu` ghi):")
    phan.append("```")
    phan.append("Đọc chữ qua máy chủ: N khung lấy mẫu -> M đoạn chữ khác nhau ->")
    phan.append("gửi K khung (J khung đọc được kết quả)")
    phan.append("```")
    phan.append("- **N** = số khung RapidOCR sàng lọc trên máy (miễn phí)")
    phan.append("- **K** = số khung THẬT SỰ gửi lên máy chủ (tốn Vox)")
    phan.append("- Tỉ lệ K/N là phần tiết kiệm được — thiết kế H2b nhắm ~1/3")
    phan.append(f"\nTóm tắt bằng chứng đã lưu cùng blueprint: "
                f"*{bp.get('evidenceSummary')}*")

    phan.append("\n### Số liệu để định giá lại (nằm ở MÁY CHỦ)\n")
    phan.append("Script này chạy bằng token THIẾT BỊ nên không đọc được sổ máy "
                "chủ. Mỗi lượt gọi mô hình của H2/H3 đã ghi sẵn: số đoạn "
                "(`inputSize`), nhà cung cấp + tên mô hình, token vào/ra, thời "
                "gian chạy, Vox đã trừ, và phán quyết (`ready`/`blocked`/"
                "`unconfirmed`).")
    phan.append("\nNgười quản trị lấy bằng `GET /v1/admin/analytics/assist"
                "?days=7` (cần `X-Admin-Token`). Cần khoảng **10–20 lượt thật** "
                "rồi mới viết mini-spec định giá — giá 12 Vox hiện tại là "
                "PHẲNG theo số đoạn, mà kịch bản 40 đoạn tốn hơn hẳn 5 đoạn.")

    # --- 7. Bốn cổng mở H4 ------------------------------------------------
    phan.append(_muc("7. Bốn cổng mở H4"))
    cong = [
        ["1. H2 tạo được FlowBlueprint thật qua app",
         "ĐẠT" if bp.get("beats") else "**CHƯA**"],
        ["2. H2b đọc đúng caption CÓ DẤU trên máy người dùng",
         "phải xem tay: nguồn có caption tiếng Việt không, và chữ đọc ra có dấu không"],
        ["3. H2c có dấu vân tay và H3 dùng được",
         "ĐẠT" if vt else "**CHƯA**"],
        ["4. H3 có ít nhất một `ready` VÀ hai gate chặn được thật",
         "ĐẠT" if (scripts and any(s.get("status") == "ready" for s in scripts)
                   and any(s.get("status") == "blocked" for s in scripts))
         else "**CHƯA**"],
    ]
    phan.append(_bang(["Cổng", "Kết quả"], cong))
    phan.append("\n> Cổng 2 script không tự kết luận được: nó chỉ biết caption "
                "đọc ra là gì nếu bằng chứng còn lưu, mà H2c cố ý không lưu. "
                "Phải nhìn màn hình lúc chạy.")
    return "\n".join(phan)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ra", metavar="TỆP", help="ghi báo cáo ra tệp Markdown")
    args = p.parse_args()

    from autodub import saas_client

    if not saas_client.is_configured():
        print("Chưa cấu hình VOXDUB_API_URL — script này phải chạy trên chính "
              "máy đã chạy pilot.", file=sys.stderr)
        return 2

    client = saas_client.SaasClient()
    try:
        bao_cao = dung_bao_cao(client)
    except Exception as e:  # noqa: BLE001 — in lý do thật, đừng nuốt
        print(f"Không gom được báo cáo: {e}", file=sys.stderr)
        return 1

    if args.ra:
        with open(args.ra, "w", encoding="utf-8") as f:
            f.write(bao_cao + "\n")
        print(f"Đã ghi {args.ra}")
    else:
        print(bao_cao)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
