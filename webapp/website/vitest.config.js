import { defineConfig } from 'vitest/config'

/** Mini-spec V10 follow-up (docs/PLAN.md) — website/ trước đây 0 test. */
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: false,
    // V50: test render (React Testing Library) cần dọn DOM giữa các test và
    // cần matcher của jest-dom — nạp qua setup chung thay vì lặp ở từng file.
    setupFiles: ['./src/test-setup.js'],
  },
})
