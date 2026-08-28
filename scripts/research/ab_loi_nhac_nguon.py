"""Đo A/B hai phiên bản LỜI NHẮC DỊCH trên cùng một bản chép lời thật.

Vì sao có tệp này (mini-spec C44): sửa lời nhắc là đổi chất lượng dịch của
MỌI người dùng ngay lập tức, mà "prompt đọc có vẻ tốt hơn" không phải bằng
chứng. Muốn biết luật mới có tác dụng thật hay không thì phải dịch CÙNG một
bản chép lời hai lần, chỉ đổi đúng một biến: lời nhắc.

Gọi thẳng Gemini theo đúng cách `ai-gateway.service.js` gọi (systemInstruction
+ responseSchema + responseMimeType JSON), nên kết quả sát đường sản xuất chứ
không phải một phép thử tương tự.

Dùng:
    GEMINI_API_KEY=... python3 scripts/research/ab_loi_nhac_nguon.py \\
        --transcript duong/dan/transcript.json \\
        --nguon en-US --dich vi \\
        --ref-cu HEAD~1 --model gemini-3.5-flash

Có sẵn một bản chép lời thật để chạy ngay: `scripts/research/
mau_chep_loi_tap01_en.json` — 8 câu Whisper nghe từ `tap01_clip.mp4`
(nhận ra tiếng Anh 98,9%), giữ nguyên lỗi nghe thật: câu 1 dính hai
người nói và mất dấu câu, câu 3 sai ngữ pháp "What is it come with".
Đúng loại câu mà luật đọc hiểu nguồn sinh ra để xử lý.

`--ref-cu` là git ref chứa lời nhắc CŨ (mặc định HEAD~1 — commit ngay trước
C44). Script tự lấy tệp prompt ở ref đó ra thư mục tạm rồi nạp, nên không đụng
gì tới cây làm việc.

KHÔNG có khoá thì script DỪNG, không bịa kết quả.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]
PROMPT_JS = "control_server/src/prompts/translate.js"


def _node(script: str) -> dict:
    """Chạy một đoạn JS và đọc JSON nó in ra."""
    ket_qua = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True,
        cwd=str(GOC / "control_server"))
    if ket_qua.returncode != 0:
        raise RuntimeError(f"node lỗi: {ket_qua.stderr.strip()[:400]}")
    return json.loads(ket_qua.stdout)


def dung_loi_nhac(duong_dan_module: str, segments: list[dict],
                  nguon: str, dich: str, cps: float) -> dict:
    """{system, user, schema} đúng như máy chủ dựng cho một lô."""
    js = f"""
    const p = require({json.dumps(duong_dan_module)});
    const segs = {json.dumps(segments, ensure_ascii=False)};
    const t = p.resolveTargetLang({json.dumps(dich)});
    process.stdout.write(JSON.stringify({{
      system: p.buildTranslateSystemPrompt({{
        sourceLang: {json.dumps(nguon)}, targetKey: {json.dumps(dich)},
        context: {{}}, cpsBudget: {cps},
      }}),
      user: p.buildTranslateUserPrompt({{ segments: segs, targetField: t.field }}),
      field: t.field,
      schema: p.translateSchema(t.field),
    }}));
    """
    return _node(js)


def lay_file_o_ref(ref: str, thu_muc: Path) -> str:
    """Lấy bản `translate.js` ở một git ref ra thư mục tạm, trả đường dẫn."""
    noi_dung = subprocess.run(
        ["git", "show", f"{ref}:{PROMPT_JS}"], capture_output=True, text=True,
        cwd=str(GOC))
    if noi_dung.returncode != 0:
        raise SystemExit(f"Không lấy được {PROMPT_JS} ở ref {ref}: "
                         f"{noi_dung.stderr.strip()[:200]}")
    dich = thu_muc / "translate_cu.js"
    dich.write_text(noi_dung.stdout, encoding="utf-8")
    return str(dich)


def goi_gemini(api_key: str, model: str, system: str, user: str,
               schema: dict, temperature: float = 0.3,
               max_tokens: int = 8192) -> dict:
    """Gọi Gemini y như `callGemini` của ai-gateway."""
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent")
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            # Gemini không nhận `additionalProperties` — gỡ như toGeminiSchema.
            "responseSchema": _schema_gemini(schema),
            # Bài học project_seo_gemini_thinking_gotcha: phần "suy nghĩ" ăn
            # hết hạn mức token đầu ra, câu trả lời ra rỗng.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Gemini trả {e.code}: {e.read().decode()[:400]}")
    cand = (data.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        raise SystemExit(f"Gemini trả rỗng (finishReason="
                         f"{cand.get('finishReason')})")
    return {"json": json.loads(text), "usage": data.get("usageMetadata", {})}


def _schema_gemini(schema):
    if isinstance(schema, dict):
        return {k: _schema_gemini(v) for k, v in schema.items()
                if k != "additionalProperties"}
    if isinstance(schema, list):
        return [_schema_gemini(v) for v in schema]
    return schema


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcript", required=True,
                    help="JSON [{id,text,start,end,duration}] — bản chép lời THẬT")
    ap.add_argument("--nguon", default="en-US", help="ngôn ngữ nguồn cánh MỚI")
    ap.add_argument("--nguon-cu", default=None,
                    help="ngôn ngữ nguồn cánh CŨ (mặc định: rỗng — đúng thứ app "
                         "gửi khi bật tự nhận ngôn ngữ trước C44)")
    ap.add_argument("--dich", default="vi")
    ap.add_argument("--ref-cu", default="HEAD~1")
    ap.add_argument("--model", default="gemini-3.5-flash")
    ap.add_argument("--cps", type=float, default=12.5)
    ap.add_argument("--ra", default="", help="ghi kết quả đầy đủ ra tệp JSON")
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("Chưa có GEMINI_API_KEY — script DỪNG.\n"
              "Không có khoá thì không có phép đo; đoán bừa kết quả còn tệ hơn "
              "không đo.", file=sys.stderr)
        return 2
    if not shutil.which("node"):
        print("Không tìm thấy node — cần nó để dựng đúng lời nhắc máy chủ.",
              file=sys.stderr)
        return 2

    segments = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
    # max_chars đúng như client tính, nếu không thì cánh nào cũng bị chấm sai
    # tiêu chí "vừa chỗ trống".
    sys.path.insert(0, str(GOC))
    from autodub.text.translate_hint import annotate_slots, payload_segment
    lo = [payload_segment(s, args.cps) for s in annotate_slots(list(segments))]

    nguon_cu = args.nguon_cu if args.nguon_cu is not None else ""
    with tempfile.TemporaryDirectory() as tmp:
        cu = dung_loi_nhac(lay_file_o_ref(args.ref_cu, Path(tmp)),
                           lo, nguon_cu, args.dich, args.cps)
        moi = dung_loi_nhac(str(GOC / PROMPT_JS), lo, args.nguon,
                            args.dich, args.cps)

    print(f"Lời nhắc CŨ ({args.ref_cu}, nguồn={nguon_cu or 'RỖNG'}): "
          f"{len(cu['system'])} ký tự")
    print(f"Lời nhắc MỚI (cây làm việc, nguồn={args.nguon}): "
          f"{len(moi['system'])} ký tự")
    print(f"Model: {args.model} · {len(lo)} câu\n")

    kq = {}
    for nhan, bo in (("CŨ", cu), ("MỚI", moi)):
        print(f"— đang gọi cánh {nhan} …")
        kq[nhan] = goi_gemini(api_key, args.model, bo["system"], bo["user"],
                              bo["schema"])

    field = moi["field"]
    def _lay(bo):
        return {int(s["id"]): s.get(field, "")
                for s in bo["json"].get("segments", [])}
    a, b = _lay(kq["CŨ"]), _lay(kq["MỚI"])

    print("\n" + "=" * 78)
    for seg in lo:
        i = int(seg["id"])
        print(f"\n[{i}] GỐC : {seg['text']}")
        print(f"    CŨ  : {a.get(i, '(thiếu)')}")
        print(f"    MỚI : {b.get(i, '(thiếu)')}")
        if a.get(i) == b.get(i):
            print("    → giống hệt nhau")
    print("\n" + "=" * 78)
    for nhan in ("CŨ", "MỚI"):
        u = kq[nhan]["usage"]
        print(f"{nhan}: {u.get('promptTokenCount', '?')} token vào, "
              f"{u.get('candidatesTokenCount', '?')} token ra")

    if args.ra:
        Path(args.ra).write_text(json.dumps(
            {"segments": lo, "cu": kq["CŨ"], "moi": kq["MỚI"],
             "nguon_cu": nguon_cu, "nguon_moi": args.nguon,
             "ref_cu": args.ref_cu, "model": args.model},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nĐã ghi {args.ra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
