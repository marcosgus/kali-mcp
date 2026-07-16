#!/bin/bash
set -e

# 1) Kali MCP API server (Flask) on :5000  (kali-server-mcp, from mcp-kali-server pkg)
kali-server-mcp --ip 127.0.0.1 --port 5000 &

# 2) Wait until the API is healthy
echo "[*] Waiting for Kali API server on port 5000..."
until curl -sf http://localhost:5000/health > /dev/null 2>&1; do
    sleep 1
done
echo "[+] Kali API server is ready"

# 3) Expose MCP as Streamable HTTP on :8000 via supergateway + the stdio bridge
#    (mcp-server --server http://localhost:5000  ->  kali-server-mcp API)
echo "[*] Starting MCP gateway on port 8000..."
exec supergateway \
    --stdio "mcp-server --server http://localhost:5000" \
    --port 8000 \
    --cors \
    --outputTransport streamableHttp
