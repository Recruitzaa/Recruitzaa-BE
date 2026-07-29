#!/bin/bash
set -e

echo "🚀 Starting Recruitzaa Environment..."

# 1. Start backend infrastructure and Auth Service
echo "📦 Starting Docker containers (Postgres, Mongo, Redis, Kafka, MinIO, Auth, pgAdmin, Mongo Express)..."
cd /home/sumanth/Recruitzaa-BE
docker compose up -d

# 2. Start Cloudflare Tunnel
echo "☁️ Starting Cloudflare Tunnel in background..."
# Kill any existing cloudflared process
killall cloudflared 2>/dev/null || true
nohup cloudflared tunnel run 056ca2a0-28ea-4dd1-9ddb-a60c9d877a0c > /tmp/cloudflared.log 2>&1 &
echo "✅ Cloudflare Tunnel started (Logs: /tmp/cloudflared.log)"

echo ""
echo "🎉 All services are up and running!"
echo "🔗 Auth API Docs: https://api-recruitzaa.sharatpatnayakuni.site/docs"
echo "🐘 pgAdmin:       https://pgadmin-recruitzaa.sharatpatnayakuni.site"
echo "🍃 Mongo Express: https://mongo-recruitzaa.sharatpatnayakuni.site"
echo "🪣 MinIO Console: https://minio-recruitzaa.sharatpatnayakuni.site"
echo "📨 Kafka UI:      https://kafka-recruitzaa.sharatpatnayakuni.site"
