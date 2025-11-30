#!/bin/bash
# Quick conflict check - run before deployment
echo "🔍 Checking for conflicts..."

# Check port 8001
if sudo lsof -i :8001 > /dev/null 2>&1; then
    echo "❌ Port 8001 in use! Run: sudo lsof -i :8001"
else
    echo "✅ Port 8001 available"
fi

# Check container name
if docker ps -a | grep -q "^fitness-challenge$"; then
    echo "⚠️  Container 'fitness-challenge' exists (will be replaced)"
else
    echo "✅ Container name available"
fi

# Check Caddy
if [ -f /etc/caddy/Caddyfile ]; then
    if grep -q "fitnesschallenge.habitreward.org" /etc/caddy/Caddyfile; then
        echo "⚠️  Subdomain already in Caddyfile"
    else
        echo "✅ Ready to add to Caddyfile"
    fi
fi

echo "Done! See CONFLICT_PREVENTION.md for details"

