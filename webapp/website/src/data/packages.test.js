import { describe, expect, it } from 'vitest'

import { estimateCapacity, PACKAGE_DETAILS } from './packages'

describe('estimateCapacity', () => {
  it('tính đúng theo công thức đã ghi trong comment (12 Vox/câu, 10 câu/phút, 10 phút/video)', () => {
    // 1000 Vox -> 83 câu -> 8 phút -> tối thiểu 1 video (làm tròn xuống 0 thì kẹp về 1).
    const r = estimateCapacity(1000)
    expect(r.segments).toBe(83)
    expect(r.minutes).toBe(8)
    expect(r.videos).toBe(1)
  })

  it('đủ Vox cho nhiều video thì tính đúng số video, không kẹp về 1', () => {
    // 120000 Vox -> 10000 câu -> 1000 phút -> 100 video.
    const r = estimateCapacity(120000)
    expect(r.videos).toBe(100)
  })

  it('0 Vox vẫn trả về video tối thiểu 1 (không âm/0) — không hứa hẹn sai', () => {
    const r = estimateCapacity(0)
    expect(r.segments).toBe(0)
    expect(r.minutes).toBe(0)
    expect(r.videos).toBe(1)
  })
})

describe('PACKAGE_DETAILS', () => {
  it('mọi gói công khai (mini/starter/standard/pro/studio) đều có mô tả', () => {
    for (const id of ['mini', 'starter', 'standard', 'pro', 'studio']) {
      expect(PACKAGE_DETAILS[id], `thiếu mô tả cho gói ${id}`).toBeTruthy()
      expect(Array.isArray(PACKAGE_DETAILS[id].perks)).toBe(true)
      expect(PACKAGE_DETAILS[id].perks.length).toBeGreaterThan(0)
    }
  })
})
