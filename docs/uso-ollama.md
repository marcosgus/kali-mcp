# Uso con Ollama Cloud + `ollmcp`

Cómo conducir las tools de kali-mcp con un modelo de **Ollama Cloud** desde el
host Linux. Refleja el setup con el que se construyó este repo.

## Componentes

| Componente | Rol |
|---|---|
| Contenedor `kali-mcp` (Docker) | servidor MCP HTTP en `http://localhost:666/mcp` |
| Ollama (daemon local `:11434`) | sirve modelos cloud offloadeando a Ollama Cloud |
| `glm-5.2:cloud` | modelo con capability **`tools`** (verificado: devuelve `tool_calls`) |
| `ollmcp` (mcp-client-for-ollama) | puente LLM↔MCP, soporta HTTP streamable + Human-in-the-Loop |

> Ollama **no** habla MCP por sí mismo; `ollmcp` es el puente.

## 1) Levantar kali-mcp
```bash
cd kali-mcp && ./init.sh
curl -s -o /dev/null -w "MCP -> HTTP %{http_code}\n" http://localhost:666/mcp   # 405 a GET = normal
```

## 2) Ollama Cloud + modelo
```bash
ollama signin                 # una vez (cuenta ollama.com) — modo daemon local
ollama pull glm-5.2:cloud
ollama show glm-5.2:cloud | grep -A3 Capabilities   # tools, thinking, completion
```
### Alternativa: API key directa (sin daemon)
```bash
export OLLAMA_API_KEY=tu_api_key   # NO la subas al repo
# host = https://ollama.com/api  (modelo: glm-5.2, sin sufijo :cloud)
```

## 3) Instalar `ollmcp`
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh && uv tool install --upgrade ollmcp
ollmcp --version
```

## 4) Registrar kali-mcp y arrancar
```bash
ollmcp mcp add --transport http kali http://localhost:666/mcp
ollmcp --model glm-5.2:cloud
# dentro del TUI:
#   /tools  -> ver tools (nmap_scan, nikto_scan, ...)
#   /hil    -> Human-in-the-Loop (on por defecto; pide 'y' antes de cada tool)
```

## 5) Ejemplos (lenguaje natural, dentro de ollmcp)
```
> Verificá el estado del servidor kali (server_health)
> Escaneá los puertos de scanme.nmap.org con detección de versiones
> Buscá directorios ocultos en http://192.168.1.50 con gobuster
> Corré nikto contra http://192.168.1.50
```
Tools intrusivas (sqlmap, hydra, metasploit) → confirmar siempre; solo targets autorizados.

## Notas
- Los slash commands `/project:kali-*` son exclusivos de **Claude Code**, no existen en `ollmcp`.
- El backend tiene ~3 min de timeout por tool; usá opciones acotadas (`-T4`, `-maxtime`, `--top-ports`).
- Variante sin LLM: curl directo a `http://localhost:666/mcp` (JSON-RPC), útil para scripting.

## Troubleshooting
| Problema | Solución |
|---|---|
| `ollmcp` no instala (PEP 668) | usar `uv tool install ollmcp` o un venv |
| El modelo no llama tools | confirmar `ollama show glm-5.2:cloud` → `tools`; en ollmcp `/tools` |
| Tools dan 500 / `server_health` false | ya parcheado en este repo (ver `docs/fix-commandexecutor.md`); rebuild con `./init.sh` |
| Cloud auth error | `ollama signin` o verificar `OLLAMA_API_KEY`/host |

## Prueba reproducible (verificación end-to-end)

Este repo incluye `examples/drive_kali_mcp.py`: un harness mínimo (solo stdlib de
Python) que replica el loop de `ollmcp` sin TUI, para verificar que
`glm-5.2:cloud` conduce las tools de kali-mcp.

### Cómo correrlo
```bash
# 1) kali-mcp arriba
./init.sh
# 2) Ollama Cloud + modelo
ollama signin && ollama pull glm-5.2:cloud
# 3) prueba
python3 examples/drive_kali_mcp.py
```

### Resultado verificado (build de este repo, glm-5.2:cloud)
```
[+] kali-mcp tools: 12  (nmap_scan, gobuster_scan, dirb_scan, nikto_scan, ...)

[user] Chequeá el estado del servidor kali-mcp usando la tool server_health ...
[tool_call] server_health({})
[tool_result] {"all_essential_tools_available": true, "tools_status": {"dirb":true,"gobuster":true,"nikto":true,"nmap":true}, ...}
[final] ...todas las herramientas esenciales verificadas... (tabla con Nmap/Gobuster/Dirb/Nikto ✅)

[user] Escaneá los puertos de 127.0.0.1 limitado a 5000 (-sT). Usá nmap_scan.
[tool_call] nmap_scan({'target': '127.0.0.1', 'scan_type': '-sT', 'ports': '1-5000'})
[tool_result] {"return_code":0,"stdout":"...5000/tcp open..."}
[final] ...resumen del escaneo nmap...
```

Esto confirma el stack completo: **Ollama Cloud `glm-5.2:cloud` → kali-mcp (Docker,
parcheado) → tools reales**. Para uso interactivo con confirmación humana por cada
tool, usá `ollmcp` (sección anterior, `/hil`).
