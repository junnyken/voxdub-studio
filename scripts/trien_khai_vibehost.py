"""Kích deploy một dịch vụ trên Vibe Host — RỒI KIỂM XEM NÓ CÓ SỐNG KHÔNG.

Vì sao có tệp này (mini-spec C58): tới C57 thì nhánh deploy không thể tụt lại
nữa, nhưng **bấm redeploy vẫn là việc tay**. Nghĩa là prod đi sau `main` một
quãng không ai đo được, và cái quãng đó chỉ lộ ra khi có người tình cờ đi kiểm
— đúng kiểu đã để worker chạy mã trước C53 suốt nhiều ngày.

Tệp này KHÔNG chỉ bấm nút. Một lệnh gọi bắn-rồi-quên ở đây sẽ đẻ ra đúng lớp
lỗi mà C54 vừa dọn: CI xanh, prod chết, không ai biết. Nên nó làm đủ ba việc:

1. Gọi ``redeploy_project`` qua cổng Vibe Host (JSON-RPC trên HTTP).
2. Chờ tác vụ kết thúc, và **thử lại đúng MỘT lần** nếu hỏng vì lỗi hạ tầng
   chập (đã gặp thật 03-09: "fetch failed (đã thử 6/6)", chạy lại thì xong).
3. Gọi đường sức khoẻ THẬT của dịch vụ. Tác vụ báo thành công mà dịch vụ không
   trả lời thì đây vẫn là một lượt deploy HỎNG.

Dùng:
    VIBEHOST_TOKEN=... python3 scripts/trien_khai_vibehost.py \
        --du-an cmsx1rb7d016w0i5fo0cj2r8c --ten voxdub-app \
        --suc-khoe https://voxdub-app.cmc-1.vibenode.matbao.ai/health

Mã thoát khác 0 = deploy KHÔNG thành công (đừng coi là đã lên).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

CONG_MAC_DINH = "https://vibehost.matbao.ai/api/agent/mcp"

#: Tác vụ deploy nặng nhất (worker kéo cả torch) mất ~11 phút thật, nên trần
#: rộng hơn hẳn. Hết giờ KHÔNG có nghĩa là hỏng — chỉ có nghĩa là tôi không
#: biết, và phải nói đúng như vậy.
TRAN_CHO_S = 1500.0
NHIP_HOI_S = 20.0

#: Lỗi hạ tầng chập, đáng thử lại. Cố ý HẸP: thử lại một lượt build hỏng vì
#: mã sai chỉ tốn thêm 11 phút để nhận cùng một câu trả lời.
LOI_DANG_THU_LAI = ("fetch failed", "ETIMEDOUT", "ECONNRESET", "socket hang up")


class DeployHong(Exception):
    """Thông điệp phải nói được: hỏng ở bước nào, và làm gì tiếp."""


def chuan_hoa_khoa(token: str) -> str:
    """Khoá phải đi kèm tiền tố ``Bearer``.

    Khoá lưu trong máy có sẵn tiền tố đó, nhưng người dán vào GitHub Secrets
    rất dễ dán mỗi phần chuỗi. Thiếu tiền tố thì cổng trả 401 và lời báo nói về
    "khoá không hợp lệ" — dẫn thẳng tới việc đi xin cấp lại một khoá vốn không
    hỏng. Tự thêm cho xong, thay vì bắt người dùng đoán.
    """
    token = (token or "").strip()
    if token and not token.lower().startswith("bearer "):
        return f"Bearer {token}"
    return token


def goi_cong(ten_tac_vu: str, tham_so: dict, *, cong: str, token: str,
             timeout: float = 60.0) -> dict:
    """Gọi một công cụ của cổng Vibe Host, trả về phần JSON nó gửi lại."""
    token = chuan_hoa_khoa(token)
    than = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": ten_tac_vu, "arguments": tham_so},
    }).encode("utf-8")
    req = urllib.request.Request(cong, data=than, method="POST", headers={
        "Authorization": token,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            tra_ve = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise DeployHong(f"không gọi được cổng Vibe Host ({e})") from e

    if "error" in tra_ve:
        raise DeployHong(f"cổng báo lỗi: {tra_ve['error']}")
    noi_dung = tra_ve.get("result", {}).get("content") or []
    if not noi_dung:
        raise DeployHong(f"cổng trả nội dung rỗng cho {ten_tac_vu}")
    try:
        return json.loads(noi_dung[0]["text"])
    except (KeyError, json.JSONDecodeError) as e:
        raise DeployHong(f"không đọc được kết quả {ten_tac_vu} ({e})") from e


def doi_chieu_dau_nhanh(nhanh: str, sha_mong_doi: str, *,
                        chay=None) -> None:
    """Đầu nhánh deploy TRÊN REMOTE có đúng bản vừa sinh không — D3.

    Vì sao cần: ``redeploy_project`` **không nhận tham số SHA**. Nền tảng dựng
    từ đầu nhánh *tại thời điểm gọi*. Đo thật trên lượt 84ac00d (14/09): giữa
    lúc cổng test cuối cùng xanh và lúc gọi deploy là 7 giây, giữa lệnh deploy
    và lúc dịch vụ lên là 96 giây. Một lượt push khác rơi vào quãng đó sẽ sinh
    lại nhánh deploy, và lượt chạy của SHA CŨ sẽ đẩy mã của SHA MỚI lên prod
    rồi ghi "thành công" cho SHA cũ — một dòng nhật ký đúng về một việc sai.

    Hỏi REMOTE chứ không đọc bản sao trên máy: bản sao là thứ ta vừa tự ghi ra,
    hỏi nó là tự xác nhận chính mình (cùng bài học với C57b ở
    `kiem_nhanh_deploy.py`).
    """
    import subprocess

    chay = chay or (lambda cmd: subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", timeout=60))
    kq = chay(["git", "ls-remote", "origin", f"refs/heads/{nhanh}"])
    if kq.returncode != 0:
        raise DeployHong(
            f"không hỏi được đầu nhánh {nhanh} trên remote "
            f"({(kq.stderr or '').strip()[:200]}) — KHÔNG deploy khi chưa biết "
            "mình sắp đẩy cái gì")
    dong = (kq.stdout or "").strip()
    if not dong:
        raise DeployHong(f"remote không có nhánh {nhanh} — không deploy")
    thuc_te = dong.split()[0]
    if thuc_te != sha_mong_doi:
        raise DeployHong(
            f"nhánh {nhanh} trên remote đang ở {thuc_te[:12]} nhưng lượt chạy "
            f"này sinh ra {sha_mong_doi[:12]} — có lượt push khác đã chen vào. "
            "DỪNG, không deploy: đẩy tiếp là đưa mã của commit khác lên prod "
            "rồi ghi thành công cho commit này.")


def dang_thu_lai_duoc(loi: str) -> bool:
    return any(k.lower() in (loi or "").lower() for k in LOI_DANG_THU_LAI)


def cho_xong(job_id: str, *, cong: str, token: str,
             tran_s: float = TRAN_CHO_S, ngu=time.sleep,
             dong_ho=time.monotonic) -> dict:
    """Chờ tác vụ deploy kết thúc. Trả về bản ghi tác vụ cuối cùng."""
    het = dong_ho() + tran_s
    while True:
        job = goi_cong("wait_for_job", {"jobId": job_id, "timeoutSeconds": 25},
                       cong=cong, token=token, timeout=60.0).get("job", {})
        if job.get("state") in ("succeeded", "failed", "cancelled"):
            return job
        if dong_ho() >= het:
            raise DeployHong(
                f"quá {tran_s:.0f}s mà tác vụ {job_id} chưa kết thúc "
                f"(đang ở '{job.get('state')}', {job.get('progress')}%) — "
                "KHÔNG kết luận được là hỏng hay chỉ chậm; xem trên Vibe Host")
        ngu(NHIP_HOI_S)


def _phu_thuoc_hong(than: str) -> str | None:
    """Đọc thân `/health`; trả lời phần phụ thuộc nào đang hỏng, hoặc None.

    C59: `/health` của control_server trả `ok: true` KỂ CẢ khi mất kết nối
    MongoDB (đã xảy ra thật 31-08, nền tảng báo `dependency_unreachable` hàng
    giờ mà đường này vẫn xanh). Chấm điểm deploy chỉ bằng mã 200 nghĩa là ghi
    "đã lên" cho một bản thực chất không dùng được.
    """
    try:
        d = json.loads(than)
    except (json.JSONDecodeError, TypeError):
        return None                     # không phải JSON (worker trả "ok")
    db = d.get("db")
    if isinstance(db, str) and db not in ("đã kết nối", "không dùng"):
        return f"cơ sở dữ liệu: {db}"
    return None


def _sha_lech(than: str, sha_mong_doi: str) -> str | None:
    """Dịch vụ có đang chạy ĐÚNG SHA nguồn không — D3. None = đúng.

    Đây là chốt KHÁC với `doi_chieu_dau_nhanh`: chốt kia nói "tôi gửi đúng
    thứ", chốt này hỏi chính dịch vụ "thứ đang chạy có đúng là nó không". Chỉ
    có chốt đầu thì kết luận vẫn là suy luận — mà cả mini-spec D3 sinh ra để
    thay suy luận bằng bằng chứng.

    `/health` khai SHA qua trường `commit` (`control_server/src/version.js`,
    đọc tệp `SOURCE_SHA` nướng vào ảnh lúc dựng). Không khai thì đây là ảnh
    dựng từ bản CHƯA có D3, hoặc tệp không vào được ảnh — cả hai đều là "chưa
    xác minh được", không phải "đã đúng".
    """
    try:
        d = json.loads(than)
    except (json.JSONDecodeError, TypeError):
        return "dịch vụ không trả JSON nên không khai được SHA"
    khai = str(d.get("commit") or "")
    if not khai:
        return ("dịch vụ không khai trường `commit` — ảnh dựng thiếu tệp "
                "SOURCE_SHA (xem scripts/gen_vays_control_server_branch.sh)")
    # Dịch vụ cắt còn 12 ký tự; so theo TIỀN TỐ, và so hai chiều để không phụ
    # thuộc bên nào cắt ngắn hơn.
    if sha_mong_doi.startswith(khai) or khai.startswith(sha_mong_doi):
        return None
    return f"dịch vụ đang chạy {khai} chứ không phải {sha_mong_doi[:12]}"


def kiem_suc_khoe(url: str, *, so_lan: int = 30, nhip_s: float = 10.0,
                  ngu=time.sleep, mo=urllib.request.urlopen,
                  sha_nguon: str = "") -> str:
    """Gọi đường sức khoẻ tới khi 200 VÀ phụ thuộc đều lành.

    Tác vụ deploy báo thành công KHÔNG đủ để kết luận dịch vụ sống: nền tảng
    chấm điểm bằng cổng mạng, còn thứ người dùng gặp là câu trả lời của ứng
    dụng. Và mã 200 cũng chưa đủ — xem `_phu_thuoc_hong`.
    """
    loi_cuoi = ""
    for _ in range(so_lan):
        try:
            with mo(url, timeout=20) as resp:
                than = resp.read().decode("utf-8", "replace")
                if resp.status == 200:
                    hong = _phu_thuoc_hong(than)
                    if hong is None and sha_nguon:
                        # D3 — SHA lệch lúc này thường là CONTAINER CŨ còn
                        # đang trả lời trong khi bản mới chưa thay xong. Coi
                        # nó là "chưa lên" và chờ tiếp, chứ không hỏng ngay:
                        # hỏng ngay là biến một khoảnh khắc chuyển giao bình
                        # thường thành một lượt deploy đỏ. Hết lượt mà vẫn
                        # lệch thì mới là hỏng thật — và lúc đó nó nói rõ
                        # đang chạy cái gì.
                        hong = _sha_lech(than, sha_nguon)
                    if hong is None:
                        return than[:200]
                    # Lúc vừa khởi động, kết nối CSDL có thể chưa xong — cứ
                    # chờ tiếp trong hạn, chỉ kết luận hỏng khi hết lượt.
                    loi_cuoi = f"200 nhưng {hong}"
                else:
                    loi_cuoi = f"HTTP {resp.status}"
        except Exception as e:  # noqa: BLE001 — mọi kiểu hỏng mạng đều là "chưa lên"
            loi_cuoi = str(e)
        ngu(nhip_s)
    raise DeployHong(f"deploy xong nhưng {url} chưa lành ({loi_cuoi}) — "
                     "đừng coi là đã lên")


def trien_khai(du_an: str, ten: str, suc_khoe: str, *, cong: str, token: str,
               ngu=time.sleep, nhanh_deploy: str = "", sha_nhanh: str = "",
               sha_nguon: str = "") -> list[str]:
    """Trả về các dòng báo cáo; ném :class:`DeployHong` khi không thành."""
    bao_cao: list[str] = []

    # D3 — ĐỐI CHIẾU TRƯỚC KHI KÍCH. Đặt ở đây, trước lượt gọi đầu tiên: kiểm
    # sau khi đã deploy thì mã sai đã nằm trên prod rồi, và ta chỉ còn biết
    # viết một dòng nhật ký về việc đó.
    if nhanh_deploy and sha_nhanh:
        doi_chieu_dau_nhanh(nhanh_deploy, sha_nhanh)
        bao_cao.append(
            f"{ten}: đầu nhánh {nhanh_deploy} trên remote đúng bằng "
            f"{sha_nhanh[:12]} — deploy được")

    for lan in (1, 2):
        kq = goi_cong("redeploy_project", {"projectId": du_an},
                      cong=cong, token=token)
        job_id = kq.get("jobId")
        if not job_id:
            raise DeployHong(f"{ten}: cổng không trả jobId ({kq})")
        bao_cao.append(f"{ten}: đã kích deploy (tác vụ {job_id}, lần {lan})")

        job = cho_xong(job_id, cong=cong, token=token, ngu=ngu)
        if job.get("state") == "succeeded":
            break
        loi = job.get("error", "")
        if lan == 1 and dang_thu_lai_duoc(loi):
            bao_cao.append(f"{ten}: hỏng vì lỗi hạ tầng chập ({loi}) — thử lại 1 lần")
            continue
        raise DeployHong(f"{ten}: tác vụ deploy {job.get('state')} ({loi})")

    bao_cao.append(f"{ten}: tác vụ deploy xong — giờ hỏi chính dịch vụ")
    than = kiem_suc_khoe(suc_khoe, ngu=ngu, sha_nguon=sha_nguon)
    bao_cao.append(f"{ten}: {suc_khoe} trả 200 — {than}")
    if sha_nguon:
        bao_cao.append(
            f"{ten}: dịch vụ TỰ KHAI đang chạy SHA nguồn {sha_nguon[:12]}")
    return bao_cao


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--du-an", required=True, help="mã dự án trên Vibe Host")
    ap.add_argument("--ten", required=True, help="tên để in ra nhật ký")
    ap.add_argument("--suc-khoe", required=True, help="URL kiểm dịch vụ sống")
    ap.add_argument("--cong", default=os.environ.get("VIBEHOST_URL", CONG_MAC_DINH))
    ap.add_argument("--nhanh-deploy", default="",
                    help="nhánh nền tảng dựng từ (D3); kèm --sha-nhanh")
    ap.add_argument("--sha-nhanh", default="",
                    help="SHA đầu nhánh deploy mà lượt chạy này vừa sinh (D3)")
    ap.add_argument("--sha-nguon", default="",
                    help="SHA commit nguồn đã pass test; đối chiếu với trường "
                         "`commit` mà /health tự khai (D3)")
    args = ap.parse_args()

    # Khai một nửa là cái bẫy tệ nhất: lệnh chạy trót lọt, báo xanh, mà chốt
    # thì chưa từng chạy. Thà đỏ ngay ở đây.
    if bool(args.nhanh_deploy) != bool(args.sha_nhanh):
        print("!! --nhanh-deploy và --sha-nhanh phải đi CÙNG NHAU.",
              file=sys.stderr)
        return 2

    token = os.environ.get("VIBEHOST_TOKEN", "").strip()
    if not token:
        print("!! Thiếu VIBEHOST_TOKEN — không kích deploy được.", file=sys.stderr)
        return 2

    try:
        for dong in trien_khai(args.du_an, args.ten, args.suc_khoe,
                               cong=args.cong, token=token,
                               nhanh_deploy=args.nhanh_deploy,
                               sha_nhanh=args.sha_nhanh,
                               sha_nguon=args.sha_nguon):
            print(f"  [ok] {dong}", flush=True)
    except DeployHong as e:
        print(f"\n  [HỎNG] {e}", file=sys.stderr)
        return 1
    print(f"\nKẾT LUẬN: {args.ten} đã lên và đang trả lời.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
