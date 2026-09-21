"""Tải một gói phát hành CŨ trên GitHub Releases về làm "bản cạnh bên".

Mini-spec I0-FDE, đóng giới hạn (2) của mục `docs/TEST_LOG.md` I0-FDE(e):
cổng nâng cấp (I0-E) trước đây dựng "bản cũ" từ CHÍNH gói ứng viên, nên lượt
xanh chỉ chứng minh **cơ chế** dùng lại bộ máy — nó không chạm được vào thứ
người dùng thật làm: giải nén bản mới cạnh bản **v3.17.19 đã tải từ trang
Releases** rồi mong bộ máy cũ còn dùng được.

Vì sao là một tệp riêng chứ không phải mấy dòng `curl` trong YAML:

* bước tải phải **đứng riêng** để khi mạng/API hỏng thì log chỉ thẳng khâu
  tải, thay vì đỏ ở giữa cổng nâng cấp rồi ngồi chẩn nhầm sản phẩm;
* `jq` không chắc có trên mọi ảnh runner, còn `python` thì chắc chắn có (bước
  `setup-python` ở ngay trên);
* logic ở đây **kiểm được bằng test** (`tests/test_tai_goi_phat_hanh_cu.py`),
  còn chữ trong YAML thì không ai chạy thử được cho tới lượt CI kế tiếp.

Tệp JSON `--nguon` là **bằng chứng nguồn gốc**: tag, URL, tên asset, số byte
API khai, số byte thật tải được, SHA-256 tự băm, thời điểm tải. Bộ lái
(`scripts/kiem_goi_phat_hanh.py`) đọc lại tệp này, **tự băm lại** gói và đối
chiếu — chép số của người khác thì chỉ chứng minh được "API nói thế".

Dùng::

    python scripts/tai_goi_phat_hanh_cu.py --tag v3.17.19 \\
        --ra "$RUNNER_TEMP/ban-cu" --nguon "$RUNNER_TEMP/ban-cu/nguon.json"

Mã thoát: 0 tải xong · 1 không lấy được (API, mạng, thiếu asset, lệch byte).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"

#: Asset cần lấy: gói Windows của bản phát hành đó.
MAU_ASSET = "-win64.zip"


class KhongTaiDuoc(RuntimeError):
    """Không lấy được gói phát hành cũ — bước này phải ĐỎ, không tự đi tiếp."""


class _BoChuyenHuongKhongMangToken(urllib.request.HTTPRedirectHandler):
    """Chuyển hướng tải asset thì BỎ token đi.

    GitHub trả 302 sang `objects.githubusercontent.com` (S3 ký sẵn trong URL).
    Mang tiếp header `Authorization` sang đó là lỗi *"Only one auth mechanism
    allowed"* — hỏng ở một khâu trông chẳng liên quan gì tới quyền truy cập,
    nên rất tốn thời gian chẩn. Dựng lại request sạch cho chặng sau.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return urllib.request.Request(newurl, headers={"Accept": "*/*"})


def _mo(url: str, token: str, accept: str):
    header = {"Accept": accept, "User-Agent": "voxdub-i0fde"}
    if token:
        header["Authorization"] = f"Bearer {token}"
    bo_mo = urllib.request.build_opener(_BoChuyenHuongKhongMangToken())
    try:
        return bo_mo.open(urllib.request.Request(url, headers=header),
                          timeout=120)
    except urllib.error.HTTPError as e:
        raise KhongTaiDuoc(f"{url} → HTTP {e.code} {e.reason}") from e
    except OSError as e:
        raise KhongTaiDuoc(f"{url} → không nối được: {e}") from e


def thong_tin_phat_hanh(repo: str, tag: str, token: str) -> dict:
    """Bản phát hành theo tag (ném :class:`KhongTaiDuoc` nếu không có)."""
    with _mo(f"{API}/repos/{repo}/releases/tags/{tag}", token,
             "application/vnd.github+json") as r:
        return json.loads(r.read().decode("utf-8"))


def chon_asset(phat_hanh: dict, mau: str = MAU_ASSET) -> dict:
    """Asset Windows của bản phát hành — nói rõ có những gì khi không thấy."""
    co = [a for a in phat_hanh.get("assets", [])
          if str(a.get("name", "")).endswith(mau)]
    if not co:
        ten = [a.get("name") for a in phat_hanh.get("assets", [])]
        raise KhongTaiDuoc(
            f"Bản phát hành {phat_hanh.get('tag_name')!r} không có asset nào "
            f"kết thúc bằng {mau!r} — đang có: {ten}")
    if len(co) > 1:
        raise KhongTaiDuoc(
            f"Có {len(co)} asset khớp {mau!r} ({[a['name'] for a in co]}) — "
            "không đoán bừa cái nào là gói người dùng tải.")
    return co[0]


def tai_asset(asset: dict, dich: str, token: str) -> tuple[int, str]:
    """Tải asset về ``dich``; trả ``(số byte, sha256)`` ĐO TỪ TỆP ĐÃ TẢI."""
    bam = hashlib.sha256()
    byte = 0
    tam = dich + ".dang-tai"
    with _mo(asset["url"], token, "application/octet-stream") as r, \
            open(tam, "wb") as f:
        while True:
            khoi = r.read(1 << 20)
            if not khoi:
                break
            f.write(khoi)
            bam.update(khoi)
            byte += len(khoi)
    # Đối chiếu NGAY, trước khi đổi tên: tệp mang đúng tên chỉ được tồn tại
    # khi nó ĐỦ. Một tệp cụt mang tên đúng là thứ khiến bước sau chẩn nhầm
    # sang sản phẩm — và một lượt chạy lại sẽ nhặt luôn tệp cụt đó.
    if asset.get("size") and int(asset["size"]) != byte:
        os.remove(tam)
        raise KhongTaiDuoc(
            f"Tải được {byte} byte nhưng API khai {asset['size']} byte — tệp "
            "cụt. Dựng 'bản cũ' từ một gói cụt thì mọi kết luận sau đó đều vô "
            "nghĩa.")
    os.replace(tam, dich)
    return byte, bam.hexdigest()


def tai_ve(repo: str, tag: str, thu_muc: str, token: str) -> dict:
    """Tải gói phát hành ``tag`` về ``thu_muc``; trả hồ sơ nguồn gốc."""
    os.makedirs(thu_muc, exist_ok=True)
    phat_hanh = thong_tin_phat_hanh(repo, tag, token)
    asset = chon_asset(phat_hanh)
    dich = os.path.join(thu_muc, asset["name"])
    byte, sha = tai_asset(asset, dich, token)
    return {
        "tag": phat_hanh.get("tag_name", tag),
        "kho": repo,
        "ten_asset": asset["name"],
        "url_release": phat_hanh.get("html_url", ""),
        "url_asset": asset.get("url", ""),
        "id_asset": asset.get("id"),
        "phat_hanh_luc": phat_hanh.get("published_at", ""),
        "byte_api_khai": asset.get("size"),
        "byte": byte,
        "sha256": sha,
        "tai_luc": datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds"),
        "duong_dan": os.path.abspath(dich),
    }


def _ghi_output_ci(ho_so: dict) -> None:
    """Đưa đường dẫn sang bước sau qua ``$GITHUB_OUTPUT``.

    Để bước cổng nâng cấp khỏi phải gõ lại tên tệp asset — hai chỗ gõ tay
    cùng một chuỗi là hai chỗ có thể lệch nhau.
    """
    duong = os.environ.get("GITHUB_OUTPUT", "")
    if not duong:
        return
    with open(duong, "a", encoding="utf-8") as f:
        f.write(f"duong_dan={ho_so['duong_dan']}\n")
        f.write(f"tag={ho_so['tag']}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", required=True, help="vd v3.17.19")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""),
                    help="mặc định lấy từ $GITHUB_REPOSITORY")
    ap.add_argument("--ra", required=True, help="thư mục lưu gói")
    ap.add_argument("--nguon", default="", help="tệp JSON bằng chứng nguồn gốc")
    args = ap.parse_args(argv)

    token = (os.environ.get("GITHUB_TOKEN")
             or os.environ.get("GH_TOKEN") or "")
    if not args.repo:
        print("!! thiếu --repo (hoặc $GITHUB_REPOSITORY)", file=sys.stderr)
        return 1
    try:
        ho_so = tai_ve(args.repo, args.tag, args.ra, token)
    except KhongTaiDuoc as e:
        print(f"!! không tải được gói phát hành {args.tag}: {e}",
              file=sys.stderr)
        return 1
    if args.nguon:
        os.makedirs(os.path.dirname(os.path.abspath(args.nguon)) or ".",
                    exist_ok=True)
        with open(args.nguon, "w", encoding="utf-8") as f:
            json.dump(ho_so, f, ensure_ascii=False, indent=2)
    _ghi_output_ci(ho_so)
    print(f"[ban-cu] {ho_so['ten_asset']} · {ho_so['byte']} byte · "
          f"sha256 {ho_so['sha256'][:16]}… · tag {ho_so['tag']}")
    print(f"[ban-cu] {ho_so['duong_dan']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
