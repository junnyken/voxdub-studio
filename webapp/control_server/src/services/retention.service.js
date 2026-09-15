'use strict'

/**
 * Retention cohort theo tuần (mini-spec V10, xem docs/PLAN.md) — dùng LẠI
 * dữ liệu Device đã có sẵn (`firstSeenAt`/`lastSeenAt`, đã ghi từ trước cho
 * mục "Thiết bị hoạt động" ở Dashboard), KHÔNG thêm thu thập dữ liệu mới,
 * KHÔNG đụng client (autodub_gui/saas_client.py) — an toàn về quyền riêng
 * tư, không cần quyết định minh bạch mới như phễu hoàn thành/bỏ dở (việc
 * đó cần thêm telemetry ở client, xem "Remaining Limits" trong
 * docs/TEST_LOG.md mục V10, CHƯA làm trong đợt này).
 */
const MS_PER_WEEK = 7 * 24 * 3600 * 1000

function startOfWeek(date) {
  // Tuần bắt đầu từ Thứ Hai (ISO), giờ UTC — chỉ cần nhất quán nội bộ,
  // không cần khớp múi giờ người xem báo cáo.
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()))
  const day = d.getUTCDay() || 7
  if (day !== 1) d.setUTCDate(d.getUTCDate() - (day - 1))
  return d
}

function weekLabel(date) {
  return date.toISOString().slice(0, 10)
}

/**
 * `devices`: [{ firstSeenAt, lastSeenAt }, ...] (đọc thẳng, không mutate).
 * `weeks`: số tuần cohort muốn xem (tính từ tuần cũ nhất có dữ liệu).
 * `now`: mốc "hiện tại" — truyền vào để test được (không dùng Date.now()
 * trực tiếp, xem ghi chú Date.now() cấm trong workflow script — áp dụng
 * luôn cho code thường để nhất quán dễ test).
 *
 * Trả về: [{ cohortWeek, cohortSize, retention: [{offsetWeeks, active, pct}] }]
 * — mỗi cohort là nhóm thiết bị có `firstSeenAt` rơi vào đúng 1 tuần;
 * `retention[i]` là % thiết bị trong cohort đó còn `lastSeenAt` >= tuần
 * cohort + i tuần (offset 0 luôn 100% vì chính tuần đăng ký).
 */
function computeWeeklyRetention(devices, weeks, now) {
  const nowWeek = startOfWeek(now)
  const cohorts = new Map()   // weekLabel -> [{firstSeenAt, lastSeenAt}]

  for (const dev of devices) {
    if (!dev.firstSeenAt) continue
    const cohortWeek = startOfWeek(new Date(dev.firstSeenAt))
    const label = weekLabel(cohortWeek)
    if (!cohorts.has(label)) cohorts.set(label, { week: cohortWeek, members: [] })
    cohorts.get(label).members.push(dev)
  }

  const sorted = [...cohorts.values()].sort((a, b) => a.week - b.week)
  const recent = sorted.slice(-weeks)

  return recent.map(({ week, members }) => {
    const maxOffset = Math.floor((nowWeek - week) / MS_PER_WEEK)
    const retention = []
    for (let offset = 0; offset <= Math.min(maxOffset, weeks - 1); offset += 1) {
      const boundary = new Date(week.getTime() + offset * MS_PER_WEEK)
      const active = members.filter((m) => m.lastSeenAt && new Date(m.lastSeenAt) >= boundary).length
      retention.push({
        offsetWeeks: offset,
        active,
        pct: members.length ? Math.round((active / members.length) * 1000) / 10 : 0,
      })
    }
    return { cohortWeek: weekLabel(week), cohortSize: members.length, retention }
  })
}

module.exports = { computeWeeklyRetention, startOfWeek, weekLabel }
