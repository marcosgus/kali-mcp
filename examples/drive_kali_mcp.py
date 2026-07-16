#!/usr/bin/env python3
"""
Ejemplo reproducible: un modelo de Ollama Cloud (glm-5.2:cloud) conduce las
tools de kali-mcp a través de MCP (JSON-RPC sobre HTTP streamable).

Replica el loop que hace ollmcp (LLM + tools -> tool_calls -> MCP -> resultado
al LLM -> respuesta final), pero sin TUI, para verificar el end-to-end.

Requisitos:
  - Contenedor kali-mcp corriendo en http://localhost:666/mcp  (./init.sh)
  - Ollama corriendo en :11434 con glm-5.2:cloud  (ollama signin && ollama pull glm-5.2:cloud)
  - Python 3 (solo stdlib: urllib, json)

Uso:
  python3 examples/drive_kali_mcp.py

Probado: glm-5.2:cloud llama a server_health y nmap_scan correctamente.
"""
import json, urllib.request

MCP = "http://localhost:666/mcp"
OLLAMA = "http://localhost:11434/api/chat"
MODEL = "glm-5.2:cloud"


def mcp(method, params=None, _id=1):
    """Llamada JSON-RPC al servidor MCP (respuestas SSE)."""
    body = json.dumps({"jsonrpc": "2.0", "id": _id, "method": method,
                       "params": params or {}}).encode()
    req = urllib.request.Request(MCP, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=120) as r:
        txt = r.read().decode()
    for line in txt.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(txt)


def ollama(messages, tools):
    body = json.dumps({"model": MODEL, "messages": messages,
                       "tools": tools, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def run(query, maxiter=4):
    print(f"\n[user] {query}")
    messages = [
        {"role": "system",
         "content": "Sos un asistente de pentesting. Usá las tools de kali-mcp cuando haga falta. Solo targets autorizados."},
        {"role": "user", "content": query},
    ]
    for _ in range(maxiter):
        msg = ollama(messages, TOOLS).get("message", {})
        messages.append(msg)
        tcs = msg.get("tool_calls") or []
        if not tcs:
            print(f"[final] {msg.get('content','').strip()[:800]}")
            return
        for tc in tcs:
            fn = tc["function"]["name"]
            args = tc["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            print(f"[tool_call] {fn}({args})")
            res = mcp("tools/call", {"name": fn, "arguments": args})
            out = "".join(c.get("text", "")
                          for c in (res.get("result", {}).get("content") or [])
                          if c.get("type") == "text")
            print(f"[tool_result] {out[:300]}{'...' if len(out) > 300 else ''}")
            messages.append({"role": "tool", "content": out})
    print("[final] (sin respuesta final dentro del límite de iteraciones)")


if __name__ == "__main__":
    tlist = mcp("tools/list")
    TOOLS = [{"type": "function", "function": {
        "name": t["name"],
        "description": t.get("description", ""),
        "parameters": t.get("inputSchema", {"type": "object", "properties": {}})}}
        for t in tlist["result"]["tools"]]
    print(f"[+] kali-mcp tools: {len(TOOLS)}")
    run("Chequeá el estado del servidor kali-mcp usando la tool server_health y decime si todas las herramientas están disponibles.")
    run("Escaneá los puertos de 127.0.0.1 limitado a 5000 (-sT). Usá nmap_scan.")
