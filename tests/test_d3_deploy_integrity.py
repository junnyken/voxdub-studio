"""D3 — Deploy Integrity: prod chỉ nhận một SHA SAU KHI test của chính SHA đó xanh.

Bối cảnh đo được (xem `docs/MINI-SPEC_D3_Deploy_Integrity_AUDIT.md`):

- Lượt chạy thật `84ac00d` (14/09): nhánh deploy bị force-push lúc 03:16:46,
  cổng test cuối cùng mãi 03:20:45 mới xanh — **hở 3 phút 59 giây**.
- Lượt `34584418242` (11/09): `python-tests` ĐỎ lúc 09:33:04, mà
  `sinh-nhanh-deploy` đã force-push xong từ 09:29:14. `trien-khai-prod` bị bỏ
  qua đúng như thiết kế — **nhưng nhánh deploy, tức nguồn sự thật của prod, đã
  mang mã trượt test và nằm lại đó tới lần push xanh kế tiếp.**

Ba phép chứng minh phủ định của mini-spec nằm ở đây:
  1. gỡ `needs` của job sinh nhánh  → bị bắt (`test_BANG_CHUNG_PHU_DINH_1…`)
  2. SHA nhánh deploy lệch SHA vừa sinh → chặn, không deploy
  3. `/health` 200 mà CSDL chưa kết nối → deploy tính là HỎNG
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess

import pytest
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO, ".github", "workflows", "test.yml")

#: Ba cổng bắt buộc. Thêm cổng mới vào CI mà quên thêm vào đây thì nhánh deploy
#: lại được sinh trước nó — nên danh sách này cố ý là một chốt riêng.
CONG_BAT_BUOC = {"python-tests", "node-tests", "chay-that-windows"}


def _wf() -> dict:
    return yaml.safe_load(open(WORKFLOW, encoding="utf-8"))


def _nap_trien_khai():
    spec = importlib.util.spec_from_file_location(
        "trien_khai_vibehost",
        os.path.join(REPO, "scripts", "trien_khai_vibehost.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tk = _nap_trien_khai()


# ============================================ 1. THỨ TỰ CỔNG ================

def test_sinh_nhanh_deploy_phu_thuoc_MOI_cong_bat_buoc():
    """Đây là cả mini-spec D3 gói trong một dòng `needs`."""
    needs = set(_wf()["jobs"]["sinh-nhanh-deploy"].get("needs") or [])
    thieu = CONG_BAT_BUOC - needs
    assert not thieu, (
        f"job sinh nhánh deploy KHÔNG đợi {sorted(thieu)} — nhánh deploy sẽ "
        "mang mã chưa qua cổng đó, và mọi đường redeploy thủ công sẽ đưa nó "
        "lên prod")


def test_BANG_CHUNG_PHU_DINH_1_go_needs_thi_phep_kiem_phai_DO():
    """Chứng minh phép kiểm trên thực sự bắt được, không phải chỉ đọc cho vui.

    Dựng lại đúng trạng thái TRƯỚC D3 (job sinh nhánh không có `needs`) rồi
    đòi cùng một luật phải đỏ.
    """
    wf = _wf()
    wf["jobs"]["sinh-nhanh-deploy"].pop("needs", None)      # ← trạng thái cũ
    needs = set(wf["jobs"]["sinh-nhanh-deploy"].get("needs") or [])
    assert CONG_BAT_BUOC - needs, (
        "gỡ `needs` ra mà luật vẫn thấy ổn ⇒ luật không chốt gì")


def test_trien_khai_prod_van_giu_gate_rieng():
    """Đừng bỏ `needs` của nó chỉ vì job sinh nhánh đã gate.

    Hai job, hai việc: một cái quyết định NHÁNH DEPLOY mang gì, cái kia quyết
    định PROD nhận gì. Dựa vào bắc cầu là để một lần sắp xếp lại job sau này
    lặng lẽ mở lại cổng.
    """
    needs = set(_wf()["jobs"]["trien-khai-prod"].get("needs") or [])
    assert CONG_BAT_BUOC <= needs
    assert "sinh-nhanh-deploy" in needs


def test_drift_khong_duoc_KEU_NHAM_khi_test_do():
    """Test đỏ ⇒ nhánh deploy CỐ Ý đứng lại ⇒ "lệch" là đúng.

    Backlog của chính dự án đã ghi: bộ canh hay kêu nhầm thì người ta tắt nó
    đi, còn tệ hơn không có.
    """
    buoc = _wf()["jobs"]["deploy-branch-drift"]["steps"][-1]
    assert "needs.sinh-nhanh-deploy.result" in yaml.dump(buoc, allow_unicode=True), (
        "bước kiểm drift không đọc kết quả job sinh nhánh ⇒ sẽ báo đỏ trên "
        "mọi lượt test hỏng")
    assert "exit 0" in buoc["run"]


# ==================================== 2. GHIM SHA (chống đua) ===============

@pytest.mark.parametrize("ten", [
    "gen_vays_control_server_branch.sh", "gen_vays_dub_worker_branch.sh"])
def test_script_sinh_nhanh_ghim_SHA_nguon(ten):
    ma = open(os.path.join(REPO, "scripts", ten), encoding="utf-8").read()
    assert 'SHA_NGUON="$(git rev-parse "$GOC_SINH")"' in ma
    assert "Source-SHA: $SHA_NGUON" in ma, (
        f"{ten}: commit nhánh deploy không nói nó dựng từ commit nào")
    assert "SOURCE_SHA" in ma, f"{ten}: không ghi SHA vào thư mục build"


def _kq(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(["git"], returncode, stdout, stderr)


def test_dau_nhanh_khop_thi_di_tiep():
    sha = "a" * 40
    tk.doi_chieu_dau_nhanh("deploy/x", sha,
                           chay=lambda cmd: _kq(stdout=f"{sha}\trefs/heads/deploy/x\n"))


def test_BANG_CHUNG_PHU_DINH_2_dau_nhanh_LECH_thi_CHAN():
    """Lượt push khác chen vào giữa lúc test xanh và lúc gọi deploy."""
    with pytest.raises(tk.DeployHong) as e:
        tk.doi_chieu_dau_nhanh(
            "deploy/x", "a" * 40,
            chay=lambda cmd: _kq(stdout=f"{'b' * 40}\trefs/heads/deploy/x\n"))
    cau = str(e.value)
    assert "bbbbbbbbbbbb" in cau and "aaaaaaaaaaaa" in cau, (
        "phải nói RÕ đang ở đâu và mong đợi gì, không chỉ nói 'lệch'")
    assert "không deploy" in cau.lower()


def test_khong_hoi_duoc_remote_thi_DUNG_chu_khong_doan():
    with pytest.raises(tk.DeployHong, match="KHÔNG deploy"):
        tk.doi_chieu_dau_nhanh("deploy/x", "a" * 40,
                               chay=lambda cmd: _kq(returncode=128, stderr="mạng đứt"))


def test_remote_khong_co_nhanh_thi_DUNG():
    with pytest.raises(tk.DeployHong, match="không có nhánh"):
        tk.doi_chieu_dau_nhanh("deploy/x", "a" * 40, chay=lambda cmd: _kq(stdout=""))


def test_hoi_REMOTE_chu_khong_doc_ban_sao_tren_may():
    """Hỏi bản sao trên máy là tự xác nhận chính mình (bài học C57b)."""
    da_goi = []
    tk.doi_chieu_dau_nhanh(
        "deploy/x", "a" * 40,
        chay=lambda cmd: (da_goi.append(cmd),
                          _kq(stdout=f"{'a' * 40}\trefs/heads/deploy/x\n"))[1])
    assert da_goi[0][:3] == ["git", "ls-remote", "origin"]


# ============================ 3. DỊCH VỤ TỰ KHAI SHA ========================

def test_health_khai_dung_SHA_thi_dat():
    than = json.dumps({"ok": True, "commit": "84ac00d622d2", "db": "đã kết nối"})
    assert tk._sha_lech(than, "84ac00d622d2d268ece533d24b396f1208d6471e") is None


def test_health_khai_SHA_KHAC_thi_bi_bat():
    than = json.dumps({"ok": True, "commit": "ffffffffffff", "db": "đã kết nối"})
    loi = tk._sha_lech(than, "84ac00d622d2d268ece533d24b396f1208d6471e")
    assert loi and "ffffffffffff" in loi


def test_health_KHONG_khai_SHA_la_CHUA_XAC_MINH_chu_khong_phai_dat():
    """Thiếu bằng chứng không bao giờ được tính là có bằng chứng."""
    than = json.dumps({"ok": True, "version": "3.17.16", "db": "đã kết nối"})
    loi = tk._sha_lech(than, "a" * 40)
    assert loi and "SOURCE_SHA" in loi


def test_SHA_lech_luc_dau_la_CHUA_LEN_chu_khong_phai_hong_ngay(monkeypatch):
    """Container CŨ còn trả lời trong lúc bản mới chưa thay xong.

    Hỏng ngay ở lượt đầu là biến một khoảnh khắc chuyển giao bình thường
    thành một lượt deploy đỏ — và lần sau người ta sẽ bỏ chốt này đi.
    """
    lan = {"n": 0}

    class _Resp:
        status = 200

        def __enter__(self): return self
        def __exit__(self, *a): return False

        def read(self):
            lan["n"] += 1
            sha = "old000000000" if lan["n"] < 3 else "84ac00d622d2"
            return json.dumps({"ok": True, "commit": sha,
                               "db": "đã kết nối"}).encode()

    than = tk.kiem_suc_khoe("http://x/health", so_lan=5, ngu=lambda s: None,
                            mo=lambda *a, **k: _Resp(),
                            sha_nguon="84ac00d622d2d268ece533d24b396f1208d6471e")
    assert "84ac00d622d2" in than
    assert lan["n"] == 3, "phải chờ qua các lượt container cũ còn trả lời"


def test_SHA_lech_MAI_thi_cuoi_cung_van_HONG():
    class _Resp:
        status = 200

        def __enter__(self): return self
        def __exit__(self, *a): return False

        def read(self):
            return json.dumps({"ok": True, "commit": "old000000000",
                               "db": "đã kết nối"}).encode()

    with pytest.raises(tk.DeployHong) as e:
        tk.kiem_suc_khoe("http://x/health", so_lan=3, ngu=lambda s: None,
                         mo=lambda *a, **k: _Resp(), sha_nguon="a" * 40)
    assert "old000000000" in str(e.value)


def test_khong_truyen_sha_nguon_thi_giu_nguyen_hanh_vi_cu():
    """Worker `/health` trả chuỗi "ok" thuần — không có gì để khai.

    Bịa một phép kiểm không chạy được ở đó còn tệ hơn không kiểm.
    """
    class _Resp:
        status = 200

        def __enter__(self): return self
        def __exit__(self, *a): return False

        def read(self): return b"ok"

    assert tk.kiem_suc_khoe("http://x/health", so_lan=2, ngu=lambda s: None,
                            mo=lambda *a, **k: _Resp()) == "ok"


# ===== 3b. BẰNG CHỨNG PHỦ ĐỊNH 3: 200 mà CSDL chưa kết nối vẫn là HỎNG =====

def test_BANG_CHUNG_PHU_DINH_3_health_200_ma_CSDL_chua_ket_noi_la_HONG():
    class _Resp:
        status = 200

        def __enter__(self): return self
        def __exit__(self, *a): return False

        def read(self):
            return json.dumps({"ok": True, "version": "3.17.16",
                               "commit": "84ac00d622d2",
                               "db": "mất kết nối"}).encode()

    # CỐ Ý không truyền `sha_nguon`: phép kiểm CSDL có từ C59, TRƯỚC D3. Nếu
    # test này đi kèm tham số mới thì gỡ D3 ra nó sẽ đỏ vì `TypeError`, tức đỏ
    # vì lý do khác hẳn thứ nó nói — một test đỏ nhầm lý do không chứng minh gì.
    # Ở dạng này, nó chỉ đỏ khi chính phép kiểm CSDL bị gỡ.
    with pytest.raises(tk.DeployHong) as e:
        tk.kiem_suc_khoe("http://x/health", so_lan=2, ngu=lambda s: None,
                         mo=lambda *a, **k: _Resp())
    assert "cơ sở dữ liệu" in str(e.value), (
        "200 đơn thuần KHÔNG đủ — đây đúng là ca đã xảy ra thật 31-08")


# ================================= 4. ĐỐI CHIẾU TRƯỚC KHI KÍCH =============

def test_doi_chieu_chay_TRUOC_khi_goi_deploy(monkeypatch):
    """Kiểm sau khi deploy thì mã sai đã nằm trên prod rồi."""
    thu_tu = []

    def _gia_doi_chieu(nhanh, sha, **kw):
        thu_tu.append("đối chiếu")
        raise tk.DeployHong("lệch")

    monkeypatch.setattr(tk, "doi_chieu_dau_nhanh", _gia_doi_chieu)
    monkeypatch.setattr(tk, "goi_cong",
                        lambda *a, **k: thu_tu.append("gọi deploy") or {})

    with pytest.raises(tk.DeployHong):
        tk.trien_khai("du-an", "ten", "http://x/health", cong="c", token="t",
                      ngu=lambda s: None, nhanh_deploy="deploy/x",
                      sha_nhanh="a" * 40)
    assert thu_tu == ["đối chiếu"], (
        f"đã gọi deploy dù đối chiếu hỏng: {thu_tu}")


def test_workflow_truyen_du_ca_hai_SHA_cho_control_server():
    """Chốt CHỖ GỌI, không chỉ chốt hàm — hàm đúng mà không ai truyền vào thì
    chốt chưa từng chạy."""
    wf = open(WORKFLOW, encoding="utf-8").read()
    khoi = wf.split("Đưa voxdub-app lên prod", 1)[1].split("Đưa voxdub-dub-worker", 1)[0]
    assert "--nhanh-deploy deploy/vays-control-server" in khoi
    assert "--sha-nhanh ${{ needs.sinh-nhanh-deploy.outputs.sha_app }}" in khoi
    assert "--sha-nguon ${{ github.sha }}" in khoi


def test_workflow_xuat_SHA_hai_nhanh_deploy():
    out = _wf()["jobs"]["sinh-nhanh-deploy"]["outputs"]
    assert "sha_app" in out and "sha_worker" in out


def test_khai_mot_nua_thi_dung_ngay():
    """`--nhanh-deploy` không kèm `--sha-nhanh` = chốt không bao giờ chạy mà
    lệnh vẫn báo xanh. Thà đỏ ngay."""
    kq = subprocess.run(
        ["python3", os.path.join(REPO, "scripts", "trien_khai_vibehost.py"),
         "--du-an", "x", "--ten", "y", "--suc-khoe", "http://x",
         "--nhanh-deploy", "deploy/x"],
        capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert kq.returncode == 2
    assert "CÙNG NHAU" in kq.stderr


# ================================= 5. /health khai SHA =====================

def test_version_js_doc_SOURCE_SHA_khi_khong_co_bien_moi_truong(tmp_path):
    """Chạy Node THẬT, không đọc mã rồi tin."""
    goc = os.path.join(REPO, "control_server")
    tep = os.path.join(goc, "SOURCE_SHA")
    assert not os.path.exists(tep), "trên main không được có sẵn tệp này"
    try:
        open(tep, "w", encoding="utf-8").write("84ac00d622d2d268ece5\n")
        kq = subprocess.run(
            ["node", "-e",
             "const v=require('./src/version.js');console.log(v.commit)"],
            cwd=goc, capture_output=True, text=True, encoding="utf-8",
            timeout=60, env={**os.environ, "APP_COMMIT": "", "SOURCE_COMMIT": ""})
        assert kq.returncode == 0, kq.stderr
        assert kq.stdout.strip() == "84ac00d622d2"
    finally:
        if os.path.exists(tep):
            os.remove(tep)


def test_gitignore_chan_SOURCE_SHA_lot_len_main():
    """Một tệp cũ lọt vào `main` sẽ khiến `/health` khai một commit KHÁC HẲN
    thứ đang chạy — tệ hơn không khai gì, vì nó trông như bằng chứng."""
    bo_qua = open(os.path.join(REPO, ".gitignore"), encoding="utf-8").read()
    assert "control_server/SOURCE_SHA" in bo_qua
