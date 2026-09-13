# Frontend 이미지 (1단계 Day 3).
# 멀티스테이지: Node 로 빌드 → Nginx 로 정적 파일만 서빙.
# 공개 진입점 reverse proxy 는 루트 `infra/nginx` 가 담당한다.

FROM node:22-alpine AS build

WORKDIR /app
COPY package.json yarn.lock ./
# lockfile 그대로 설치해 CI/로컬과 동일 트리를 맞춘다.
RUN yarn install --frozen-lockfile
COPY . .
RUN yarn build

FROM nginx:1.27-alpine
# SPA fallback (try_files → index.html)
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
