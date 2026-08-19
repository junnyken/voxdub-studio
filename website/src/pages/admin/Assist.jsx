import { useState } from 'react'

import { adminApi } from '../../api/client'
import { formatVnd, formatVox } from '../../api/format'
import { useFetch } from '../../api/useFetch'
import { Badge, Empty, ErrorBox, Loading } from '../../components/ui'

/**
 * Bảng theo dõi cổng trợ lý — mini-spec V89 giai đoạn 3.
 *
 * Trang này phải trả lời đúng ba câu đã hứa trong bản kế hoạch: tuần rồi tốn
 * bao nhiêu, việc nào tốn nhất, và mô hình nào hay hỏng. Không thêm biểu đồ
 * cho đẹp — số liệu ít mà đọc được thì hơn.
 */

const KHOANG = [
  { days: 1, label: 'Hôm nay' },
  { days: 7, label: '7 ngày' },
  { days: 30, label: '30 ngày' },
]

/** Tên việc bằng tiếng người — khớp đúng danh mục ở prompts/assist.js. */
const TEN_VIEC = {
  music_suggest: 'Gợi ý nhạc nền',
  explain_error: 'Giải thích lỗi',
  video_summary: 'Tóm tắt video',
  character_name: 'Đặt tên nhân vật',
  series_glossary: 'Quy ước dịch',
  tighten_line: 'Rút gọn câu',
}

function tenViec(task) {
  return TEN_VIEC[task] || task || '(không rõ)'
}

function ToneHong({ luot, hong }) {
  if (!luot) return <span className="text-ink-soft">—</span>
  const ty = Math.round((hong / luot) * 1000) / 10
  if (!hong) return <Badge tone="success">0%</Badge>
  return <Badge tone={ty >= 10 ? 'danger' : 'warning'}>{ty}%</Badge>
}

export default function Assist() {
  const [days, setDays] = useState(7)
  const { data, error, loading, reload } = useFetch(
    () => adminApi.assistStats(days), [days])

  if (loading) return <Loading label="Đang tính…" />
  if (error) return <ErrorBox error={error} onRetry={reload} />

  const t = data.tomTat
  const trong = !t.luot

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-lg font-bold">Cổng trợ lý</h1>
        <div className="flex gap-1">
          {KHOANG.map((k) => (
            <button
              key={k.days}
              type="button"
              onClick={() => setDays(k.days)}
              className={`px-2.5 py-1 rounded-lg text-xs transition-colors ${
                days === k.days ? 'bg-panel text-ink' : 'text-ink-soft hover:text-ink'
              }`}
            >
              {k.label}
            </button>
          ))}
        </div>
        <span className="text-xs text-ink-soft ml-auto">
          Hạn mức mỗi máy: {data.hanMucNgay} lượt/ngày
        </span>
      </div>

      {trong ? (
        <Empty
          title="Chưa có lượt nào"
          hint="Cổng trợ lý chưa được gọi trong khoảng thời gian này. Nhớ cấu
                hình một nơi gọi mô hình cho vai trò «assist» ở trang Nơi gọi
                mô hình — chưa có thì hệ thống dùng chung vai «translate», đắt
                hơn nhiều lần."
        />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[
              ['Số lượt', t.luot.toLocaleString('vi-VN')],
              ['Đã thu', `${formatVox(t.vox)} · ${formatVnd(t.vnd)}`],
              ['Token vào / ra',
                `${(t.tokenVao / 1000).toFixed(1)}k / ${(t.tokenRa / 1000).toFixed(1)}k`],
              ['Dùng lại kết quả cũ', `${t.dungLai || 0} lượt · 0đ`],
              ['Tốn nhất', tenViec(t.tacVuTonNhat)],
            ].map(([nhan, gia_tri]) => (
              <div key={nhan} className="rounded-xl bg-panel border border-border-subtle p-3">
                <div className="text-[11px] uppercase tracking-wide text-ink-soft">{nhan}</div>
                <div className="text-base font-semibold mt-0.5 tabular-nums">{gia_tri}</div>
              </div>
            ))}
          </div>

          {data.dungChungVaiDich && (
            <div className="rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm">
              <strong>Đang chạy nhờ vai «dịch thuật».</strong> Chưa có nơi gọi
              mô hình nào đặt vai trò «assist», nên mỗi lượt trợ lý đang dùng
              đúng mô hình dành cho dịch — đắt hơn nhiều lần cho việc ngắn như
              thế này. Thêm một dòng ở trang «Nơi gọi mô hình», vai trò
              «assist», trỏ vào mô hình rẻ.
            </div>
          )}

          {t.tyLeHong >= 5 && (
            <div className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm">
              <strong>{t.tyLeHong}% số lượt bị hỏng.</strong> Xem bảng «Mô hình»
              bên dưới: hỏng dồn vào một nơi gọi thì đổi thứ tự ưu tiên, hỏng đều
              khắp thì nhiều khả năng là prompt hoặc khuôn kết quả.
            </div>
          )}

          <section className="space-y-2">
            <h2 className="text-sm font-semibold">Theo từng việc</h2>
            <div className="overflow-x-auto rounded-xl border border-border-subtle">
              <table className="w-full text-sm">
                <thead className="text-[11px] uppercase tracking-wide text-ink-soft">
                  <tr className="border-b border-border-subtle">
                    <th className="text-left px-3 py-2">Việc</th>
                    <th className="text-right px-3 py-2">Lượt</th>
                    <th className="text-right px-3 py-2">Máy</th>
                    <th className="text-right px-3 py-2">Dùng lại</th>
                    <th className="text-right px-3 py-2">Vox</th>
                    <th className="text-right px-3 py-2">Token vào/ra</th>
                    <th className="text-right px-3 py-2">Trung bình</th>
                    <th className="text-right px-3 py-2">Hỏng</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {data.tacVu.map((r) => (
                    <tr key={r.task} className="border-b border-border-subtle last:border-0">
                      <td className="px-3 py-2 font-medium">{tenViec(r.task)}</td>
                      <td className="px-3 py-2 text-right">{r.luot}</td>
                      <td className="px-3 py-2 text-right">{r.soMay}</td>
                      <td className="px-3 py-2 text-right text-ink-soft">
                        {r.dungLai || 0}
                      </td>
                      <td className="px-3 py-2 text-right">{r.vox}</td>
                      <td className="px-3 py-2 text-right text-ink-soft">
                        {r.tokenVao} / {r.tokenRa}
                      </td>
                      <td className="px-3 py-2 text-right text-ink-soft">
                        {(r.thoiGianMs / 1000).toFixed(1)}s
                      </td>
                      <td className="px-3 py-2 text-right">
                        <ToneHong luot={r.luot} hong={r.hong} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold">Theo mô hình</h2>
            <div className="overflow-x-auto rounded-xl border border-border-subtle">
              <table className="w-full text-sm">
                <thead className="text-[11px] uppercase tracking-wide text-ink-soft">
                  <tr className="border-b border-border-subtle">
                    <th className="text-left px-3 py-2">Nơi gọi</th>
                    <th className="text-left px-3 py-2">Mô hình</th>
                    <th className="text-right px-3 py-2">Lượt</th>
                    <th className="text-right px-3 py-2">Token vào/ra</th>
                    <th className="text-right px-3 py-2">Hỏng</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {data.moHinh.map((r) => (
                    <tr key={`${r.provider}-${r.model}`}
                      className="border-b border-border-subtle last:border-0">
                      <td className="px-3 py-2">{r.provider || '—'}</td>
                      <td className="px-3 py-2 text-ink-soft">{r.model || '—'}</td>
                      <td className="px-3 py-2 text-right">{r.luot}</td>
                      <td className="px-3 py-2 text-right text-ink-soft">
                        {r.tokenVao} / {r.tokenRa}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <ToneHong luot={r.luot} hong={r.hong} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {data.maLoi.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold">Lỗi hay gặp</h2>
              <div className="flex flex-wrap gap-2">
                {data.maLoi.map((r) => (
                  <span key={r.ma}
                    className="rounded-lg bg-panel border border-border-subtle px-2.5 py-1 text-xs">
                    {r.ma || 'không rõ'} <span className="text-ink-soft">×{r.luot}</span>
                  </span>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
