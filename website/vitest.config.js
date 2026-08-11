import { defineConfig } from 'vitest/config'

/** Mini-spec V10 follow-up (docs/PLAN.md) — website/ trước đây 0 test. */
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: false,
  },
})
