# Mini-spec V7 (docs/PLAN.md) — Docker hoá control_server (Node/Fastify).
# Multi-stage: build website tĩnh (React/Vite) rồi copy vào image chạy
# control_server, đúng như control_server đang tự serve website/dist cùng
# process (src/app.js) — không đổi kiến trúc, chỉ đóng gói.

FROM node:20-alpine AS website-build
WORKDIR /website
COPY website/package.json website/package-lock.json* ./
RUN npm ci
COPY website/ ./
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app/control_server
ENV NODE_ENV=production
COPY control_server/package.json control_server/package-lock.json* ./
RUN npm ci --omit=dev
COPY control_server/ ./
# app.js mặc định đọc website/dist ở ../../website/dist (2 cấp trên
# control_server) — giữ đúng layout tương đối đó trong image.
COPY --from=website-build /website/dist /app/website/dist

EXPOSE 3001
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:${PORT:-3001}/health || exit 1

CMD ["node", "server.js"]
