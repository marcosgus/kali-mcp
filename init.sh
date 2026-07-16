#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/docker"

echo "[*] Building and starting kali-mcp container..."
docker compose -f "$DOCKER_DIR/compose.yml" up -d --build

echo "[*] Waiting for MCP server to be ready..."
until curl -so /dev/null http://localhost:666/mcp 2>/dev/null; do
    sleep 1
done

echo "[+] Kali MCP is running at http://localhost:666/mcp"
echo "    Verify tools:  curl -s -X POST http://localhost:666/mcp \\"
echo "      -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \\"
echo "      -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"server_health\",\"arguments\":{}}}'"
