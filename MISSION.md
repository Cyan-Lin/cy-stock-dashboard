# Mission

## Goal

學會 Docker，能獨立運行 cy-stock-dashboard 的三服務 Compose 環境（FastAPI + PostgreSQL + React），並在出錯時能自己 debug。

## Why This Matters

cy-stock-dashboard 的開發環境完全容器化，所有服務都透過 `docker compose up` 啟動。不理解 Docker 就無法：
- 驗證服務是否正確啟動
- 診斷服務崩潰的原因
- 未來把專案搬上 VPS

## Background

- 有開發經驗（React/TypeScript、Python/FastAPI）
- 曾跟著別人用過 Docker，但沒有主動理解過
- 學習風格：先快速掌握能動，不懂再深挖

## Success Criteria

1. 能用 `docker compose up --build` 一鍵啟動三服務
2. 能從 log 判斷服務是否健康
3. 能解讀 `docker-compose.yml` 的每一行
4. 服務掛掉時能自己定位問題（log、exec、inspect）
