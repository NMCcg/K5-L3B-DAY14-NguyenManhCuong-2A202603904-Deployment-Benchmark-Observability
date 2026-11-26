# Deployment Information

## Public URL
https://k5-l3b-day14-nguyenmanhcuong-2a202603904-deploym-production.up.railway.app

## Platform
Railway (deploy từ `06-lab-complete/` bằng `railway.toml` + `Dockerfile`, kết hợp Railway Redis add-on)

## Test Commands

### 1. Health Check (expected: 200)
```bash
curl -i https://k5-l3b-day14-nguyenmanhcuong-2a202603904-deploym-production.up.railway.app/health
# Expected: {"status":"ok"}
```

### 2. Readiness Check (expected: 200)
```bash
curl -i https://k5-l3b-day14-nguyenmanhcuong-2a202603904-deploym-production.up.railway.app/ready
# Expected: {"ready":true}
```

### 3. Authentication Check — Không có API key (expected: 401)
```bash
curl -i -X POST https://k5-l3b-day14-nguyenmanhcuong-2a202603904-deploym-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### 4. API Test — Có `X-API-Key` hợp lệ (expected: 200)
```bash
curl -i -X POST https://k5-l3b-day14-nguyenmanhcuong-2a202603904-deploym-production.up.railway.app/ask \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

## Environment Variables Set (trên Railway Dashboard)
- `PORT` (Railway tự inject)
- `REDIS_URL` (tham chiếu tới service Redis: `${{Redis.REDIS_URL}}`)
- `AGENT_API_KEY` (đặt bí mật trên Railway Variables, không ghi vào code/Git)
- `ENVIRONMENT` (`production`)
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`1.0`)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
