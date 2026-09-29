import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { adminApi } from '../../api/client'
import { formatRelative, formatVox, shortFingerprint } from '../../api/format'
import { useFetch } from '../../api/useFetch'
import { Badge, Empty, ErrorBox, Loading, Modal, Pager } from '../../components/ui'

const LIMIT = 20

export default function Devices() {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState(params.get('search') || '')

  const page = Number(params.get('page')) || 1
  const status = params.get('status') || ''
  const query = params.get('search') || ''

  const { data, error, loading, reload } = useFetch(
    () => adminApi.devices({ page, limit: LIMIT, status, search: query }),
    [page, status, query])

  function update(next) {
    const merged = { page: '1', status, search: query, ...next }
    setParams(Object.fromEntries(
      Object.entries(merged).filter(([, v]) => v && v !== '1' || v > 1)))
  }

  // -- Chọn nhiều máy (mini-spec C21) ------------------------------------
  //
  // Chọn theo VÂN TAY, không theo chỉ số dòng: đổi trang hay đổi bộ lọc là
  // chỉ số trỏ sang máy khác, mà đây là thao tác không lùi được.
  const [chon, setChon] = useState(() => new Set())
  const [hoi, setHoi] = useState(null)      // { viec, xemTruoc }
  const [dangChay, setDangChay] = useState(false)
  const dangHien = (data?.data || []).map((d) => d.fingerprint)

  function doChon(fp) {
    setChon((cu) => {
      const moi = new Set(cu)
      if (moi.has(fp)) moi.delete(fp)
      else moi.add(fp)
      return moi
    })
  }

  function chonCaTrang(bat) {
    setChon((cu) => {
      const moi = new Set(cu)
      dangHien.forEach((fp) => (bat ? moi.add(fp) : moi.delete(fp)))
      return moi
    })
  }

  /** Hỏi máy chủ trước xem sẽ ảnh hưởng những gì, rồi mới hiện hộp xác nhận. */
  async function xemTruoc(viec) {
    setDangChay(true)
    try {
      const ket = await adminApi.devicesBulk([...chon], viec, '', true)
      setHoi({ viec, ...ket })
    } catch (e) {
      setHoi({ viec, loi: e.message })
    } finally {
      setDangChay(false)
    }
  }

  async function lamThat() {
    setDangChay(true)
    try {
      await adminApi.devicesBulk([...chon], hoi.viec, hoi.reason || '')
      setChon(new Set())
      setHoi(null)
      reload()
    } catch (e) {
      setHoi((cu) => ({ ...cu, loi: e.message }))
    } finally {
      setDangChay(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold">Thiết bị</h1>
        <button onClick={reload} className="btn-ghost text-xs py-1.5 px-3">Tải lại</button>
      </div>

      <div className="card p-4 flex flex-wrap gap-3">
        <form
          className="flex gap-2 flex-1 min-w-[240px]"
          onSubmit={(e) => { e.preventDefault(); update({ search }) }}
        >
          <input
            className="input flex-1"
            placeholder="Tìm theo mã máy, tên máy hoặc email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="btn-ghost text-xs px-3">Tìm</button>
        </form>
        <div className="flex gap-1">
          {[['', 'Tất cả'], ['active', 'Đang hoạt động'], ['blocked', 'Đã khóa']].map(
            ([value, label]) => (
              <button
                key={value}
                onClick={() => update({ status: value })}
                className={`px-3 py-1.5 rounded-lg text-xs whitespace-nowrap ${
                  status === value ? 'bg-primary text-white' : 'btn-ghost'
                }`}
              >
                {label}
              </button>
            ))}
        </div>
      </div>

      {loading && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}

      {data && (
        <div className="card overflow-hidden">
          {chon.size > 0 && (
            <div className="rounded-xl border border-border-subtle bg-panel p-3 mb-3
                            flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">Đã chọn {chon.size} máy</span>
              <button type="button" className="btn-ghost text-xs"
                onClick={() => setChon(new Set())}>Bỏ chọn</button>
              <span className="flex-1" />
              <button type="button" className="btn-ghost text-xs" disabled={dangChay}
                onClick={() => xemTruoc('block')}>Khoá</button>
              <button type="button" className="btn-ghost text-xs" disabled={dangChay}
                onClick={() => xemTruoc('unblock')}>Mở khoá</button>
              <button type="button" className="btn-ghost text-xs text-danger"
                disabled={dangChay} onClick={() => xemTruoc('delete')}>Xoá</button>
            </div>
          )}

          {!data.data.length ? (
            <Empty title="Không có thiết bị nào khớp." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th w-8">
                      <input
                        type="checkbox"
                        aria-label="Chọn tất cả máy đang hiện"
                        checked={dangHien.length > 0 && dangHien.every((f) => chon.has(f))}
                        onChange={(e) => chonCaTrang(e.target.checked)}
                      />
                    </th>
                    <th className="th">Máy</th>
                    <th className="th">Số dư</th>
                    <th className="th">Trạng thái</th>
                    <th className="th">Phiên bản</th>
                    <th className="th">Lần cuối</th>
                    <th className="th" />
                  </tr>
                </thead>
                <tbody>
                  {data.data.map((d) => (
                    <tr key={d.fingerprint} className="hover:bg-panel-hover">
                      <td className="td">
                        <input
                          type="checkbox"
                          aria-label={`Chọn ${d.name || d.fingerprint}`}
                          checked={chon.has(d.fingerprint)}
                          onChange={() => doChon(d.fingerprint)}
                        />
                      </td>
                      <td className="td">
                        <p className="font-medium truncate max-w-[220px]">
                          {d.name || 'Máy không tên'}
                        </p>
                        <p className="font-mono text-xs text-ink-muted mt-0.5">
                          {shortFingerprint(d.fingerprint)}
                        </p>
                      </td>
                      <td className="td font-medium whitespace-nowrap">
                        {formatVox(d.balance)} Vox
                      </td>
                      <td className="td">
                        {d.status === 'active'
                          ? <Badge tone="ok">Hoạt động</Badge>
                          : <Badge tone="danger">Đã khóa</Badge>}
                      </td>
                      <td className="td text-ink-soft text-xs">{d.appVersion || '—'}</td>
                      <td className="td text-ink-soft text-xs whitespace-nowrap">
                        {formatRelative(d.lastSeenAt)}
                      </td>
                      <td className="td text-right">
                        <Link
                          to={`/admin/thiet-bi/${d.fingerprint}`}
                          className="btn-ghost text-xs py-1 px-2.5"
                        >
                          Chi tiết
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pager
            page={page}
            total={data.total}
            limit={LIMIT}
            onPage={(p) => setParams({ page: String(p), status, search: query })}
          />
        </div>
      )}
    
      <Modal
        open={Boolean(hoi)}
        title={hoi?.viec === 'delete' ? 'Xoá các máy đã chọn?'
          : hoi?.viec === 'block' ? 'Khoá các máy đã chọn?'
            : 'Mở khoá các máy đã chọn?'}
        onClose={() => setHoi(null)}
        footer={(
          <div className="flex gap-2 justify-end">
            <button type="button" className="btn-ghost" onClick={() => setHoi(null)}>
              Thôi
            </button>
            <button
              type="button"
              className={hoi?.viec === 'delete' ? 'btn-danger' : 'btn-primary'}
              disabled={dangChay || Boolean(hoi?.loi)}
              onClick={lamThat}
            >
              {dangChay ? 'Đang chạy…'
                : hoi?.viec === 'delete' ? `Xoá ${hoi?.soMay ?? 0} máy`
                  : `Đồng ý với ${hoi?.soMay ?? 0} máy`}
            </button>
          </div>
        )}
      >
        {hoi?.loi ? (
          <ErrorBox message={hoi.loi} />
        ) : (
          <div className="space-y-3 text-sm">
            <p>
              Sẽ áp dụng cho <strong>{hoi?.soMay ?? 0}</strong> máy.
            </p>

            {/* Kể TÊN máy còn tiền, không nói chung chung "một vài máy còn số
                dư" — xoá một ví còn tiền là huỷ tiền, và người bấm cần thấy
                điều đó trước khi bấm chứ không phải sau. */}
            {hoi?.conTien?.length > 0 && (
              <div className={`rounded-xl border p-3 ${
                hoi.viec === 'delete'
                  ? 'border-danger/40 bg-danger/10' : 'border-warning/40 bg-warning/10'}`}
              >
                <p className="font-medium">
                  {hoi.conTien.length} máy còn tổng {hoi.tongVox} Vox
                  {hoi.viec === 'delete' && ' — xoá là mất luôn số Vox này'}
                </p>
                <ul className="mt-1 space-y-0.5 text-xs">
                  {hoi.conTien.slice(0, 10).map((d) => (
                    <li key={d.fingerprint} className="font-mono">
                      {d.name || d.fingerprint} — {d.creditBalance} Vox
                    </li>
                  ))}
                  {hoi.conTien.length > 10 && (
                    <li>… và {hoi.conTien.length - 10} máy nữa</li>
                  )}
                </ul>
              </div>
            )}

            {hoi?.khongThay?.length > 0 && (
              <p className="text-ink-soft text-xs">
                {hoi.khongThay.length} máy đã chọn không còn trong hệ thống —
                sẽ bỏ qua.
              </p>
            )}

            {hoi?.viec === 'block' && (
              <div>
                <label className="label" htmlFor="ly-do-khoa">Lý do (không bắt buộc)</label>
                <input
                  id="ly-do-khoa"
                  className="input"
                  placeholder="máy thử nghiệm"
                  value={hoi.reason || ''}
                  onChange={(e) => setHoi((cu) => ({ ...cu, reason: e.target.value }))}
                />
              </div>
            )}

            {hoi?.viec === 'delete' && (
              <p className="text-danger text-xs">
                Xoá không lùi lại được. Muốn giữ đường quay lại thì dùng
                «Khoá» — máy bị khoá mất token ngay nhưng còn trong hệ thống.
              </p>
            )}
          </div>
        )}
      </Modal>
</div>
  )
}
