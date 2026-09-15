"""D5 — chốt "prod có theo kịp main không".

Vì sao cần, bằng chứng chứ không phải lo xa (14/09/2026): `df980b2` deploy hỏng
vì cổng Vibe Host 404; commit kế tiếp chỉ sửa tài liệu nên bước "có cần deploy
không" so bản dựng MỚI với bản dựng TRƯỚC, thấy giống nhau, kết luận `app=0` và
bỏ qua deploy. Prod chạy mã cũ 21 giờ với CI xanh toàn bộ.

Hai chốt của D3 không cứu được vì cả hai nằm BÊN TRONG lượt deploy.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(GOC, "scripts"))
import kiem_prod_theo_main as d5  # noqa: E402
sys.path.pop(0)


# ======================================================================
# Chốt TĨNH — danh sách nguồn không được mục nát
# ======================================================================

SCRIPT_SINH = {
    "app": "scripts/gen_vays_control_server_branch.sh",
    "worker": "scripts/gen_vays_dub_worker_branch.sh",
}

#: Biến shell mà script sinh dùng làm tiền tố đường dẫn nguồn.
BIEN = {"$SRC": "control_server/worker-dub"}


def _duong_dan_script_chep(duong_script: str) -> set[str]:
    """Bóc MỌI đường dẫn nguồn mà một script sinh chép vào thư mục build.

    Đọc chính script chứ không tin danh sách chép tay — đó là cả điểm của chốt
    này. Gộp cả dòng nối bằng `\\`.
    """
    with open(os.path.join(GOC, duong_script), encoding="utf-8") as f:
        noi_dung = f.read()
    noi_dung = re.sub(r"\\\n\s*", " ", noi_dung)      # nối dòng tiếp
    ra: set[str] = set()
    for dong in noi_dung.splitlines():
        dong = dong.strip()
        if not dong.startswith("cp "):
            continue
        phan = [p for p in dong.split()[1:] if not p.startswith("-")]
        if len(phan) < 2:
            continue
        for nguon in phan[:-1]:                        # phần cuối là ĐÍCH
            nguon = nguon.strip('"').strip("'")
            for bien, that in BIEN.items():
                nguon = nguon.replace(bien, that)
            if nguon.startswith("$"):                  # biến lạ — chốt dưới bắt
                ra.add(nguon)
                continue
            ra.add(nguon.rstrip("/"))
    return ra


def _duoc_phu(duong: str, danh_sach: list[str]) -> bool:
    return any(duong == d or duong.startswith(d.rstrip("/") + "/")
               for d in danh_sach)


@pytest.mark.parametrize("ten", ["app", "worker"])
def test_BANG_CHUNG_moi_duong_dan_script_CHEP_deu_da_khai(ten):
    """Thêm một dòng `cp` vào script sinh mà quên khai ở `NGUON` ⇒ ĐỎ.

    Không có chốt này thì D5 sẽ im lặng bỏ sót đúng thứ vừa được thêm — kiểu
    hỏng tệ nhất, vì nó báo XANH.
    """
    chep = _duong_dan_script_chep(SCRIPT_SINH[ten])
    assert chep, "không bóc được dòng `cp` nào — bộ đọc script hỏng"
    thieu = sorted(d for d in chep if not _duoc_phu(d, d5.NGUON[ten]))
    assert not thieu, (
        f"script sinh {ten} chép {thieu} nhưng `NGUON['{ten}']` không phủ. "
        "Thêm vào NGUON, nếu không D5 sẽ bỏ sót thay đổi ở đó mà vẫn báo xanh.")


@pytest.mark.parametrize("ten", ["app", "worker"])
def test_chinh_script_sinh_cung_phai_nam_trong_nguon(ten):
    """Sửa script sinh = đổi nội dung thư mục build, kể cả khi nguồn không đổi
    (vd `requirements.txt` viết thẳng bằng heredoc trong script)."""
    assert SCRIPT_SINH[ten] in d5.NGUON[ten]


def test_bo_doc_script_bat_duoc_bien_shell_la():
    """Chốt của chính chốt: script sinh dùng `$BIEN_MOI` chưa biết thì phải lộ
    ra thành đường dẫn không phủ được, chứ không bị nuốt im."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False,
                                     dir=GOC, encoding="utf-8") as f:
        f.write('cp -r "$BIEN_LA/thu_muc" "$TARGET/x"\n')
        ten_tep = os.path.relpath(f.name, GOC)
    try:
        chep = _duong_dan_script_chep(ten_tep)
        assert any(d.startswith("$") for d in chep)
    finally:
        os.unlink(os.path.join(GOC, ten_tep))


# ======================================================================
# Hành vi
# ======================================================================

def _doc_gia(commit):
    def doc(_url, **_kw):
        if commit is None:
            raise d5.KhongKetLuanDuoc("giả lập: prod câm")
        return {"ok": True, **({"commit": commit} if commit else {})}
    return doc


def _hai_commit_that():
    """Hai commit thật trong kho này, chắc chắn KHÁC nhau ở `control_server/`."""
    import subprocess
    kq = subprocess.run(
        ["git", "log", "--format=%H", "-2", "--", "control_server"],
        capture_output=True, text=True, cwd=GOC, check=True)
    dong = kq.stdout.split()
    if len(dong) < 2:
        pytest.skip("kho chưa đủ lịch sử control_server/")
    return dong[0], dong[1]


def test_nguon_GIONG_HET_thi_dung_nhip():
    moi, _cu = _hai_commit_that()
    tt, cau = d5.kiem_mot_dich_vu("app", "http://x/health", moi,
                                  doc=_doc_gia(moi[:12]))
    assert tt == d5.DUNG_NHIP and "đúng nhịp" in cau


def test_nguon_DA_DOI_thi_bao_tut_lai_va_NOI_RO_TEP_NAO():
    moi, cu = _hai_commit_that()
    tt, cau = d5.kiem_mot_dich_vu("app", "http://x/health", moi,
                                  doc=_doc_gia(cu[:12]))
    assert tt == d5.TUT_LAI
    assert "ĐÃ ĐỔI" in cau
    assert "control_server" in cau, "phải nói rõ tệp nào, không chỉ 'có lệch'"


def test_DUNG_SUA_QUA_TAY_commit_chi_sua_tai_lieu_KHONG_bi_bao_tut_lai():
    """Ca này quyết định chốt sống hay chết.

    Commit chỉ sửa tài liệu cố ý KHÔNG deploy lại, nên prod đứng ở commit mã
    gần nhất là ĐÚNG. So SHA trực tiếp sẽ đỏ ở đây — và một bộ canh kêu nhầm
    thì chẳng bao lâu sẽ bị tắt.
    """
    import subprocess
    kq = subprocess.run(["git", "log", "--format=%H", "-40"],
                        capture_output=True, text=True, cwd=GOC, check=True)
    ds = kq.stdout.split()
    for moi, cu in zip(ds, ds[1:]):
        doi = subprocess.run(
            ["git", "diff", "--name-only", cu, moi, "--", *d5.NGUON["app"]],
            capture_output=True, text=True, cwd=GOC, check=True).stdout.strip()
        if not doi:                      # đúng một cặp commit KHÔNG đụng nguồn app
            tt, _ = d5.kiem_mot_dich_vu("app", "http://x/health", moi,
                                        doc=_doc_gia(cu[:12]))
            assert tt == d5.DUNG_NHIP, "commit không đụng nguồn mà vẫn báo lệch"
            return
    pytest.skip("40 commit gần nhất đều đụng nguồn app")


def test_prod_CAM_thi_khong_ket_luan_chu_khong_bao_dung():
    with pytest.raises(d5.KhongKetLuanDuoc):
        d5.kiem_mot_dich_vu("app", "http://x/health", "0" * 40,
                            doc=_doc_gia(None))


def test_prod_KHONG_KHAI_commit_thi_khong_ket_luan():
    """Đây chính là trạng thái của worker TRƯỚC lát này — và nó phải là
    «chưa xác minh được», tuyệt đối không phải «đã đúng»."""
    with pytest.raises(d5.KhongKetLuanDuoc) as e:
        d5.kiem_mot_dich_vu("worker", "http://x/health", "0" * 40,
                            doc=_doc_gia(""))
    assert "commit" in str(e.value)


def test_SHA_prod_khong_co_trong_kho_thi_khong_ket_luan():
    """Clone nông là mặc định của `actions/checkout` — không nở được SHA thì
    phải nói không biết, chứ không im lặng cho qua."""
    with pytest.raises(d5.KhongKetLuanDuoc) as e:
        d5.kiem_mot_dich_vu("app", "http://x/health", "0" * 40,
                            doc=_doc_gia("ffffffffffff"))
    assert "không có commit" in str(e.value)


def test_doc_health_thu_lai_roi_moi_chiu_thua():
    """Một cú chập mạng không được biến thành lượt CI đỏ."""
    lan = {"n": 0}

    def mo_hong(*_a, **_k):
        lan["n"] += 1
        raise OSError("mạng chập")

    with pytest.raises(d5.KhongKetLuanDuoc):
        d5.doc_health("http://x/health", so_lan=3, ngu=lambda _s: None,
                      mo=mo_hong)
    assert lan["n"] == 3, "phải thử lại đủ số lượt trước khi chịu thua"


def test_khong_phai_JSON_thi_KHONG_thu_lai_nhieu_lan():
    """Worker đời cũ trả chuỗi 'ok' — hỏi lại 3 lượt cũng vậy, đừng phí 10 giây."""
    lan = {"n": 0}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        @staticmethod
        def read(): return b"ok"

    def mo(*_a, **_k):
        lan["n"] += 1
        return _Resp()

    with pytest.raises(d5.KhongKetLuanDuoc):
        d5.doc_health("http://x/health", so_lan=3, ngu=lambda _s: None, mo=mo)
    assert lan["n"] == 1


# ======================================================================
# Diễn lại ĐÚNG sự cố đã xảy ra
# ======================================================================

#: Hai commit thật của sự cố 14/09/2026.
#:  - `3a8f680` (H6) là bản prod ĐÃ chạy suốt 21 giờ.
#:  - `df980b2` là bản vá rò rỉ CSDL, deploy hỏng vì cổng Vibe Host 404.
#:  - `6baf2f2` chỉ sửa tài liệu ⇒ bước "có cần deploy không" so bản dựng mới
#:    với bản dựng trước, thấy giống nhau, kết luận `app=0`, BỎ QUA deploy, và
#:    báo THÀNH CÔNG.
PROD_LUC_DO = "3a8f6809c800"
MAIN_LUC_DO = "6baf2f2d46caea63f32a069be9bdd63eb4982dd6"


def test_DIEN_LAI_su_co_14_09_D5_phai_bat_duoc():
    """Nếu chốt này không đỏ ở đây thì nó không giải quyết việc nó sinh ra để
    giải quyết — mọi test còn lại chỉ chứng minh nó chạy, không chứng minh nó
    có ích."""
    import subprocess
    co = subprocess.run(["git", "cat-file", "-e", f"{MAIN_LUC_DO}^{{commit}}"],
                        cwd=GOC, capture_output=True)
    if co.returncode != 0:
        pytest.skip("kho này không có commit của sự cố (clone nông)")

    tt, cau = d5.kiem_mot_dich_vu("app", "http://x/health", MAIN_LUC_DO,
                                  doc=_doc_gia(PROD_LUC_DO))
    assert tt == d5.TUT_LAI, (
        "D5 báo ĐÚNG NHỊP cho đúng trạng thái mà prod đang chạy mã cũ 21 giờ")
    assert "job-storage" in cau or "control_server" in cau, (
        f"phải chỉ ra tệp đã đổi, câu nhận được: {cau}")


def test_DIEN_LAI_luc_do_chot_CU_khong_thay_gi():
    """Chốt cũ (`app==1`) so bản dựng MỚI với bản dựng TRƯỚC. Hai bản ấy giống
    hệt nhau ở lượt `6baf2f2` — đó đúng là lý do nó im lặng. Test này ghim lại
    sự khác nhau giữa hai phép so, để lần sau không ai "đơn giản hoá" D5 thành
    chốt cũ một lần nữa.
    """
    import subprocess
    co = subprocess.run(["git", "cat-file", "-e", f"{MAIN_LUC_DO}^{{commit}}"],
                        cwd=GOC, capture_output=True)
    if co.returncode != 0:
        pytest.skip("kho này không có commit của sự cố")

    # Phép so của chốt CŨ: nguồn giữa df980b2 và 6baf2f2 (hai lượt dựng liền
    # nhau) — không đổi gì, nên `app=0` và deploy bị bỏ qua.
    doi_giua_hai_lan_dung = subprocess.run(
        ["git", "diff", "--name-only", "df980b2", MAIN_LUC_DO,
         "--", *d5.NGUON["app"]],
        cwd=GOC, capture_output=True, text=True, check=True).stdout.strip()
    assert not doi_giua_hai_lan_dung, (
        "tiền đề của sự cố sai: hai lượt dựng liền nhau vốn phải giống nhau")

    # Phép so của D5: nguồn giữa thứ PROD ĐANG CHẠY và main — có đổi.
    doi_so_voi_prod = subprocess.run(
        ["git", "diff", "--name-only", PROD_LUC_DO, MAIN_LUC_DO,
         "--", *d5.NGUON["app"]],
        cwd=GOC, capture_output=True, text=True, check=True).stdout.strip()
    assert doi_so_voi_prod, "D5 phải thấy thứ chốt cũ không thấy"


# ======================================================================
# Nối dây trong CI — chỗ dễ bị "đơn giản hoá" nhất
# ======================================================================

import yaml  # noqa: E402

WORKFLOW = os.path.join(GOC, ".github", "workflows", "test.yml")


@pytest.fixture(scope="module")
def cong_viec():
    with open(WORKFLOW, encoding="utf-8") as f:
        return yaml.safe_load(f)["jobs"]


def test_job_D5_chay_SAU_luot_deploy_va_chay_CA_KHI_deploy_hong(cong_viec):
    """Hai điều kiện này là cả bản vá.

    Chạy TRƯỚC deploy ⇒ mọi commit mã đều đỏ oan vì prod chưa kịp lên.
    Bỏ `always()` ⇒ deploy hỏng thì job này cũng bị bỏ qua theo, tức im lặng
    đúng ở ca duy nhất cần lên tiếng — chính là ca 14/09.
    """
    j = cong_viec["kiem-prod-theo-main"]
    assert "trien-khai-prod" in j["needs"]
    assert "always()" in j["if"]


def test_job_D5_lay_lich_su_DAY_DU(cong_viec):
    """Clone nông là mặc định của `actions/checkout`. Không có lịch sử thì
    không nở được SHA prod khai ra, và chốt sẽ trả «không kết luận được» ở MỌI
    lượt — tức xanh mãi mãi mà chẳng kiểm gì."""
    checkout = [b for b in cong_viec["kiem-prod-theo-main"]["steps"]
                if str(b.get("uses", "")).startswith("actions/checkout")]
    assert checkout, "job D5 không checkout"
    assert checkout[0].get("with", {}).get("fetch-depth") == 0


def test_job_D5_BO_QUA_khi_test_chua_xanh(cong_viec):
    """Test đỏ ⇒ deploy cố ý bị bỏ qua ⇒ prod đứng lại là ĐÚNG. Báo đỏ ở đó là
    kêu nhầm, và bộ canh kêu nhầm thì sẽ bị tắt."""
    j = cong_viec["kiem-prod-theo-main"]
    for can in ("python-tests", "node-tests", "chay-that-windows"):
        assert can in j["needs"], f"không đọc được kết quả {can} để bỏ qua"
    buoc = [b for b in j["steps"] if "kiem_prod_theo_main.py" in str(b.get("run", ""))]
    assert buoc, "không thấy bước chạy chốt D5"
    assert "exit 0" in buoc[0]["run"], "thiếu đường thoát khi test chưa xanh"


def test_worker_NAY_duoc_doi_chieu_SHA_nguon(cong_viec):
    """Trước D5 bước này phải bỏ trống `--sha-nguon` vì worker trả chuỗi "ok".
    Worker đã khai SHA rồi mà vẫn bỏ trống thì mất trắng nửa chốt."""
    buoc = [b for b in cong_viec["trien-khai-prod"]["steps"]
            if "voxdub-dub-worker" in str(b.get("run", ""))]
    assert buoc, "không thấy bước deploy worker"
    assert "--sha-nguon" in buoc[0]["run"]


def test_BANG_CHUNG_prod_DI_TRUOC_khong_duoc_bao_la_TUT_LAI():
    """Đo thật 15/09, ngay lượt chạy thứ hai của chốt này.

    Lượt CI của `5af86a3` đi tới bước D5 **sau khi** bản đẩy kế tiếp `f6384e0`
    đã lên prod. Chốt thấy prod khác commit của lượt mình và báo **"prod tụt
    lại"** — trong khi prod đang đi TRƯỚC. CI đỏ oan.

    Kêu nhầm là thứ giết một bộ canh: `deploy-branch-drift` đã phải tránh đúng
    bẫy này, và backlog ghi sẵn *bộ canh hay kêu nhầm thì người ta tắt nó đi*.
    """
    import subprocess
    cu, moi = "5af86a3692da", "f6384e00ad15"
    for sha in (cu, moi):
        if subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                          cwd=GOC, capture_output=True).returncode != 0:
            pytest.skip("kho này không có commit của sự cố")

    tt, cau = d5.kiem_mot_dich_vu("app", "http://x/health", cu,
                                  doc=_doc_gia(moi))
    assert tt == d5.DI_TRUOC, f"báo sai chiều: {tt} — {cau}"
    assert "ĐỜI SAU" in cau


def test_di_truoc_KHONG_bi_gop_vao_dung_nhip():
    """Gộp vào «đúng nhịp» thì mất thông tin: người đọc nhật ký sẽ tưởng lượt
    này đã kiểm prod, trong khi nó chưa kiểm gì cả — lượt mới hơn mới kiểm."""
    assert d5.DI_TRUOC != d5.DUNG_NHIP
