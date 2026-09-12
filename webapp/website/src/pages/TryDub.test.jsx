/**
 * Test render cho trang thử API lồng tiếng (mini-spec V49, test thêm ở V50).
 *
 * Trọng tâm KHÔNG phải "có hiện chữ không" mà là những chỗ sai sẽ tốn tiền
 * hoặc làm người dùng tưởng hỏng:
 *  - chặn gửi khi file vượt hạn mức (gửi lên chỉ để nhận 413, tốn băng thông
 *    của người dùng và một lượt rate limit),
 *  - hiện đúng giá theo chế độ nhạc nền (150 vs 250 Vox/phút),
 *  - danh sách ngôn ngữ lấy TỪ MÁY CHỦ, không phải bản chép tay trong code,
 *  - API key không bao giờ được ghi vào localStorage.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import TryDub from './TryDub'

const CONFIG = {
  cloudDub: {
    enabled: true,
    maxUploadMb: 300,
    voxPerMinute: 150,
    voxPerMinuteDemucs: 250,
    sourceLangs: ['en-US', 'vi', 'zh'],
    targetLangs: ['vi', 'en'],
  },
}

vi.mock('../api/client', () => ({
  api: { appConfig: vi.fn(() => Promise.resolve(CONFIG)) },
}))

function fakeVideo(name = 'clip.mp4', sizeMb = 1) {
  const file = new File(['x'], name, { type: 'video/mp4' })
  Object.defineProperty(file, 'size', { value: sizeMb * 1024 * 1024 })
  return file
}

beforeEach(() => {
  global.fetch = vi.fn()
  localStorage.clear()
})
afterEach(() => { vi.restoreAllMocks() })

describe('TryDub', () => {
  it('đổ danh sách ngôn ngữ TỪ MÁY CHỦ, không hardcode trong trang', async () => {
    render(<TryDub />)

    await waitFor(() => expect(screen.getByText(/Ngôn ngữ nguồn/)).toBeInTheDocument())
    const source = screen.getByLabelText(/Ngôn ngữ nguồn/)
    const values = [...source.querySelectorAll('option')].map((o) => o.value)
    expect(values).toEqual(['en-US', 'vi', 'zh'])
  })

  it('hiện đúng giá theo chế độ nhạc nền', async () => {
    const user = userEvent.setup()
    render(<TryDub />)
    await waitFor(() => expect(screen.getByText(/150/)).toBeInTheDocument())

    await user.selectOptions(screen.getByLabelText(/Nhạc nền/), 'demucs')
    expect(screen.getByText(/250/)).toBeInTheDocument()
  })

  it('file vượt hạn mức: báo rõ và KHÔNG cho bấm gửi', async () => {
    const user = userEvent.setup()
    render(<TryDub />)
    await waitFor(() => expect(screen.getByText(/Ngôn ngữ nguồn/)).toBeInTheDocument())

    await user.type(screen.getByPlaceholderText('vx_live_...'), 'vx_live_test')
    await user.upload(screen.getByLabelText(/Video cần lồng tiếng/), fakeVideo('to.mp4', 400))

    expect(await screen.findByText(/vượt hạn mức 300 MB/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Lồng tiếng video này/ })).toBeDisabled()
  })

  it('chưa dán key thì không cho gửi, dù đã chọn file', async () => {
    const user = userEvent.setup()
    render(<TryDub />)
    await waitFor(() => expect(screen.getByText(/Ngôn ngữ nguồn/)).toBeInTheDocument())

    await user.upload(screen.getByLabelText(/Video cần lồng tiếng/), fakeVideo())
    expect(screen.getByRole('button', { name: /Lồng tiếng video này/ })).toBeDisabled()
  })

  it('kiểm tra key: hiện quota còn lại khi key đúng', async () => {
    const user = userEvent.setup()
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        orgName: 'Khách A', dubMinutesRemaining: 42, dubMinutesReserved: 0, dubMinutesQuota: 60,
      }),
    })
    render(<TryDub />)
    await waitFor(() => expect(screen.getByText(/Ngôn ngữ nguồn/)).toBeInTheDocument())

    await user.type(screen.getByPlaceholderText('vx_live_...'), 'vx_live_ok')
    await user.click(screen.getByRole('button', { name: 'Kiểm tra' }))

    expect(await screen.findByText('Khách A')).toBeInTheDocument()
    expect(screen.getByText(/42/)).toBeInTheDocument()
    expect(global.fetch).toHaveBeenCalledWith('/api/v1/me', {
      headers: { authorization: 'Bearer vx_live_ok' },
    })
  })

  it('key sai: hiện đúng thông báo của máy chủ, không hiện quota', async () => {
    const user = userEvent.setup()
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ code: 'BAD_API_KEY', message: 'API key không hợp lệ.' }),
    })
    render(<TryDub />)
    await waitFor(() => expect(screen.getByText(/Ngôn ngữ nguồn/)).toBeInTheDocument())

    await user.type(screen.getByPlaceholderText('vx_live_...'), 'sai')
    await user.click(screen.getByRole('button', { name: 'Kiểm tra' }))

    expect(await screen.findByText('API key không hợp lệ.')).toBeInTheDocument()
    expect(screen.queryByText(/phút lồng tiếng/)).not.toBeInTheDocument()
  })

  it('KHÔNG bao giờ ghi API key vào localStorage', async () => {
    const user = userEvent.setup()
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        orgName: 'X', dubMinutesRemaining: 1, dubMinutesReserved: 0, dubMinutesQuota: 1,
      }),
    })
    render(<TryDub />)
    await waitFor(() => expect(screen.getByText(/Ngôn ngữ nguồn/)).toBeInTheDocument())

    await user.type(screen.getByPlaceholderText('vx_live_...'), 'vx_live_secret')
    await user.click(screen.getByRole('button', { name: 'Kiểm tra' }))
    await screen.findByText('X')

    const dump = JSON.stringify(localStorage)
    expect(dump).not.toContain('vx_live_secret')
  })

  it('máy chủ tắt tính năng: báo rõ và khoá nút gửi', async () => {
    const { api } = await import('../api/client')
    api.appConfig.mockResolvedValueOnce({
      cloudDub: { ...CONFIG.cloudDub, enabled: false },
    })
    render(<TryDub />)

    expect(await screen.findByText(/đang tắt/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Lồng tiếng video này/ })).toBeDisabled()
  })
})
