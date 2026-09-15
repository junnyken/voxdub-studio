/**
 * Setup chung cho test render (mini-spec V50).
 *
 * `website/` trước đây chỉ có test logic thuần (utils/store) — trang
 * `/thu-dub` (V49) là màn hình đầu tiên có luồng nhiều bước đáng test thật:
 * dán key → chọn file → theo dõi job → tải kết quả.
 */
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Không dọn thì component của test trước còn nằm trong DOM và
// `getByText` bắt nhầm sang nó — kiểu lỗi rất khó đọc.
afterEach(cleanup)
