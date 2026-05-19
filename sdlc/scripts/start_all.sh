#!/bin/bash
# Start ทุก Agent
echo "🚀 Starting all SDLC Agents..."

# Start Ollama ถ้ายังไม่รัน
if command -v ollama &> /dev/null; then
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Starting Ollama..."
        ollama serve &
        sleep 2
    fi
fi

docker-compose up -d
echo ""
echo "✅ All agents started!"
echo ""
echo "📊 Status:"
docker-compose ps
echo ""
echo "📝 Logs: docker-compose logs -f [ceo-agent|pm-agent|...]"
echo "🛑 Stop: ./scripts/stop_all.sh"
