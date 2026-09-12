/**
 * `ProviderModal` cấu hình nơi gọi mô hình AI (dịch/nội dung/trợ lý/sinh
 * ảnh) — sai một chỗ ở đây là tốn CHI PHÍ VẬN HÀNH thật: chọn nhầm giao
 * thức cho vai «Sinh ảnh» khiến mọi lượt dựng ảnh trả 404 âm thầm (comment
 * gốc trong Providers.jsx), hoặc rò key cũ nếu quy ước "để trống = giữ key
 * cũ" hoạt động sai chiều.
 *
 * Trọng tâm test:
 *  - chặn submit khi tạo mới thiếu name/model/apiKey,
 *  - CHO PHÉP submit khi sửa dù apiKey để trống (đúng quy ước "giữ key cũ"),
 *    và payload gửi đi KHÔNG có field apiKey khi để trống lúc sửa,
 *  - cảnh báo lệch vai trò/giao thức hiện đúng lúc, KHÔNG chặn submit (đúng
 *    thiết kế — người dùng có quyền cứ lưu nếu thấy chấp nhận được).
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { adminApi } from '../../api/client'

vi.mock('../../api/client', () => ({
  adminApi: {
    createProvider: vi.fn().mockResolvedValue({}),
    updateProvider: vi.fn().mockResolvedValue({}),
    providers: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

// Providers.jsx không export riêng ProviderModal — component export mặc
// định là trang Providers. Import lại module để lấy đúng hàm nội bộ qua
// đường vòng: render trang thật rồi mở modal bằng nút "Thêm nơi gọi", thay
// vì cố import riêng (giữ test bám sát đường người dùng thật đi qua).
import Providers from './Providers'

async function openAddModal() {
  const user = userEvent.setup()
  render(<Providers />)
  await screen.findByText('Nơi gọi mô hình')
  await user.click(screen.getByText('Thêm nơi gọi'))
  return user
}

beforeEach(() => {
  vi.clearAllMocks()
  adminApi.providers.mockResolvedValue({ data: [] })
})

describe('ProviderModal — tạo mới', () => {
  it('thiếu tên/model/apiKey thì nút Lưu bị khoá', async () => {
    await openAddModal()
    expect(screen.getByText('Lưu')).toBeDisabled()
  })

  it('điền đủ tên+model+apiKey thì Lưu mở khoá và gửi đúng payload', async () => {
    const user = await openAddModal()
    await user.type(screen.getByPlaceholderText('openrouter'), 'my-provider')
    await user.type(screen.getByPlaceholderText('google/gemini-2.5-flash'), 'gpt-4o-mini')
    await user.type(screen.getByPlaceholderText('sk-or-v1-…'), 'sk-secret-key')
    expect(screen.getByText('Lưu')).not.toBeDisabled()

    await user.click(screen.getByText('Lưu'))
    expect(adminApi.createProvider).toHaveBeenCalledTimes(1)
    const payload = adminApi.createProvider.mock.calls[0][0]
    expect(payload.name).toBe('my-provider')
    expect(payload.model).toBe('gpt-4o-mini')
    expect(payload.apiKey).toBe('sk-secret-key')
    // Số phải được ép kiểu Number, không gửi chuỗi (backend validate kiểu).
    expect(payload.temperature).toBe(0.3)
    expect(typeof payload.maxTokens).toBe('number')
  })

  it('thiếu API key khi tạo mới thì vẫn khoá dù đã có tên+model', async () => {
    const user = await openAddModal()
    await user.type(screen.getByPlaceholderText('openrouter'), 'my-provider')
    await user.type(screen.getByPlaceholderText('google/gemini-2.5-flash'), 'gpt-4o-mini')
    expect(screen.getByText('Lưu')).toBeDisabled()
  })
})

describe('ProviderModal — sửa (apiKey để trống = giữ key cũ)', () => {
  const editingProvider = {
    _id: 'p1', name: 'openrouter', label: 'OpenRouter', role: 'translate',
    type: 'openai_compat', baseUrl: 'https://openrouter.ai/api/v1',
    model: 'google/gemini-2.5-flash', temperature: 0.3, maxTokens: 16384,
    priority: 100, enabled: true, timeoutMs: 180000,
  }

  async function openEditModal() {
    adminApi.providers.mockResolvedValue({ data: [editingProvider] })
    const user = userEvent.setup()
    render(<Providers />)
    await screen.findByText('OpenRouter')  // h2 hiện `label || name`
    await user.click(screen.getByText('Sửa'))
    return user
  }

  it('apiKey trống nhưng có tên+model sẵn -> Lưu KHÔNG bị khoá', async () => {
    await openEditModal()
    expect(screen.getByText('Lưu')).not.toBeDisabled()
  })

  it('lưu khi apiKey để trống -> payload KHÔNG có field apiKey (giữ key cũ)', async () => {
    const user = await openEditModal()
    await user.click(screen.getByText('Lưu'))
    expect(adminApi.updateProvider).toHaveBeenCalledTimes(1)
    const [id, payload] = adminApi.updateProvider.mock.calls[0]
    expect(id).toBe('p1')
    expect(payload).not.toHaveProperty('apiKey')
  })

  it('gõ apiKey mới lúc sửa -> payload CÓ field apiKey với giá trị mới', async () => {
    const user = await openEditModal()
    // Không query bằng placeholder tiếng Việt (rủi ro lệch chuẩn hoá
    // Unicode giữa hai chuỗi NHÌN giống hệt nhau) — ô apiKey là input
    // type="password" duy nhất trong form.
    await user.type(document.querySelector('input[type="password"]'), 'key-moi')
    await user.click(screen.getByText('Lưu'))
    const [, payload] = adminApi.updateProvider.mock.calls[0]
    expect(payload.apiKey).toBe('key-moi')
  })
})

describe('ProviderModal — cảnh báo lệch vai trò/giao thức (KHÔNG chặn submit)', () => {
  it('vai Sinh ảnh + giao thức Chuẩn OpenAI (chỉ chữ): cảnh báo hiện ra', async () => {
    const user = await openAddModal()
    await user.selectOptions(screen.getByDisplayValue('Dịch (translate)'), 'image')
    expect(screen.getByText(/cần một giao thức sinh được ảnh/)).toBeInTheDocument()
  })

  it('vai Sinh ảnh + giao thức Google Gemini (sinh được ảnh): KHÔNG cảnh báo', async () => {
    const user = await openAddModal()
    await user.selectOptions(screen.getByDisplayValue('Dịch (translate)'), 'image')
    await user.selectOptions(
      screen.getByDisplayValue('Chuẩn OpenAI — chữ (OpenRouter, DeepSeek…)'), 'google')
    expect(screen.queryByText(/cần một giao thức sinh được ảnh/)).not.toBeInTheDocument()
  })

  it('vai Dịch (chữ) + giao thức chỉ-sinh-ảnh: cảnh báo khác hiện ra', async () => {
    const user = await openAddModal()
    await user.selectOptions(
      screen.getByDisplayValue('Chuẩn OpenAI — chữ (OpenRouter, DeepSeek…)'),
      'openrouter_images')
    expect(screen.getByText(/chỉ sinh ảnh, không dùng được cho vai chữ/)).toBeInTheDocument()
  })

  it('cảnh báo hiện ra nhưng KHÔNG khoá nút Lưu — người dùng có quyền cứ lưu', async () => {
    const user = await openAddModal()
    await user.type(screen.getByPlaceholderText('openrouter'), 'x')
    await user.type(screen.getByPlaceholderText('google/gemini-2.5-flash'), 'm')
    await user.type(screen.getByPlaceholderText('sk-or-v1-…'), 'k')
    await user.selectOptions(screen.getByDisplayValue('Dịch (translate)'), 'image')
    expect(screen.getByText(/cần một giao thức sinh được ảnh/)).toBeInTheDocument()
    expect(screen.getByText('Lưu')).not.toBeDisabled()
  })
})
