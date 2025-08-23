#!/bin/bash
# Vector index rebuild script

set -e

echo "🔄 Rebuilding vector index..."

# Check if server is running
if ! curl -s http://localhost:8123/healthz > /dev/null; then
    echo "❌ Zorix Agent server is not running"
    echo "   Start it with: ./scripts/dev.sh"
    exit 1
fi

# Trigger index rebuild
echo "📊 Triggering index rebuild..."
response=$(curl -s -X POST http://localhost:8123/index/rebuild)

if echo "$response" | grep -q '"ok": true'; then
    echo "✅ Index rebuild completed successfully"
    echo "$response" | python -m json.tool
else
    echo "❌ Index rebuild failed"
    echo "$response"
    exit 1
fi