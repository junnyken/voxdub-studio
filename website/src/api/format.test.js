import { describe, expect, it } from 'vitest'

import {
  formatCountdown, formatDate, formatRelative, formatVnd, formatVox,
  shortFingerprint,
} from './format'

describe('formatVnd', () => {
  it('định dạng theo chuẩn Việt Nam kèm hậu tố đ', () => {
    expect(formatVnd(50000)).toBe('50.000 đ')
    expect(formatVnd(0)).toBe('0 đ')
  })
  it('giá trị rỗng/undefined coi như 0', () => {
    expect(formatVnd(undefined)).toBe('0 đ')
    expect(formatVnd(null)).toBe('0 đ')
  })
})

describe('formatVox', () => {
  it('định dạng số theo chuẩn Việt Nam, không hậu tố', () => {
    expect(formatVox(1000000)).toBe('1.000.000')
  })
})

describe('formatDate', () => {
  it('trả về gạch ngang khi thiếu giá trị', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate(undefined)).toBe('—')
    expect(formatDate('')).toBe('—')
  })
  it('trả về gạch ngang khi ngày không hợp lệ (không throw)', () => {
    expect(formatDate('không phải ngày')).toBe('—')
  })
  it('định dạng đúng ngày hợp lệ', () => {
    const out = formatDate('2026-08-11T10:30:00Z')
    expect(out).toMatch(/2026/)
  })
})

describe('formatRelative', () => {
  it('mốc rất gần trả về "vừa xong"', () => {
    expect(formatRelative(new Date().toISOString())).toBe('vừa xong')
  })
  it('vài phút trước', () => {
    const t = new Date(Date.now() - 5 * 60 * 1000).toISOString()
    expect(formatRelative(t)).toBe('5 phút trước')
  })
  it('vài giờ trước', () => {
    const t = new Date(Date.now() - 3 * 3600 * 1000).toISOString()
    expect(formatRelative(t)).toBe('3 giờ trước')
  })
  it('vài ngày trước', () => {
    const t = new Date(Date.now() - 2 * 86400 * 1000).toISOString()
    expect(formatRelative(t)).toBe('2 ngày trước')
  })
  it('quá 30 ngày thì rơi về ngày tuyệt đối (formatDate)', () => {
    const t = new Date(Date.now() - 40 * 86400 * 1000).toISOString()
    expect(formatRelative(t)).not.toMatch(/trước|vừa xong/)
  })
  it('giá trị rỗng trả về gạch ngang, không throw', () => {
    expect(formatRelative(null)).toBe('—')
    expect(formatRelative('rác')).toBe('—')
  })
})

describe('formatCountdown', () => {
  it('định dạng mm:ss có số 0 đứng trước', () => {
    expect(formatCountdown(65)).toBe('01:05')
    expect(formatCountdown(5)).toBe('00:05')
  })
  it('số âm bị chặn về 0, không ra chuỗi âm', () => {
    expect(formatCountdown(-10)).toBe('00:00')
  })
  it('làm tròn xuống phần thập phân', () => {
    expect(formatCountdown(65.9)).toBe('01:05')
  })
})

describe('shortFingerprint', () => {
  it('cắt còn đầu-cuối khi dài hơn 16 ký tự (mã máy 64 ký tự thật)', () => {
    const fp = 'a'.repeat(64)
    expect(shortFingerprint(fp)).toBe(`${'a'.repeat(8)}…${'a'.repeat(4)}`)
  })
  it('giữ nguyên chuỗi ngắn', () => {
    expect(shortFingerprint('abc123')).toBe('abc123')
  })
  it('giá trị rỗng không throw', () => {
    expect(shortFingerprint(undefined)).toBe('')
  })
})
