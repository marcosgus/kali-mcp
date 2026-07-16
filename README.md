# Kali MCP

Empaqueta el servidor oficial **[`mcp-kali-server`](https://www.kali.org/tools/mcp-kali-server/)**
de Kali Linux en un contenedor Docker y lo expone como **servidor MCP sobre HTTP
streamable** en `http://localhost:666/mcp`, listo para ser consumido por agentes
de IA (Ollama/Ollama Cloud vía `ollmcp`, Claude Code, Open WebUI, etc.) que
orquestan herramientas de pentesting (nmap, nikto, gobuster, sqlmap, hydra,
metasploit, …).

> Basado en el paquete `mcp-kali-server` de Kali (`apt install mcp-kali-server`),
> que provee `kali-server-mcp` (API Flask en :5000) y `mcp-server` (puente MCP
> stdio). El contenedor añade `supergateway` para exponerlo como HTTP, ya que los
> clientes remotos (Ollama Cloud / `ollmcp`) hablan HTTP, no stdio.

## Arquitectura

```
┌────────────────────────────┐    ┌──────────────────────────┐    ┌─────────────────────────────┐
│  Ollama Cloud              │    │  ollmcp (puente LLM↔MCP)  │    │  Contenedor Docker: kali-mcp │
│  glm-5.2:cloud (tools)      │◄──►│  + Human-in-the-Loop      │◄──►│  http://localhost:666/mcp    │
│  vía daemon local :11434   │    │  --model glm-5.2:cloud    │    │  supergateway :8000 (HTTP)   │
└────────────────────────────┘    └──────────────────────────┘    │  └─ mcp-server (stdio)        │
                                                                    │     └─ kali-server-mcp :5000 │
                                                                    │        nmap/nikto/sqlmap/... │
                                                                    └─────────────────────────────┘
```

## Requisitos

- Docker + Docker Compose v2
- Ollama (para consumirlo con un LLM) — ver [`docs/uso-ollama.md`](docs/uso-ollama.md)
- Un target **autorizado** para usar las herramientas

## Inicio rápido

```bash
git clone https://github.com/marcosgus/kali-mcp.git
cd kali-mcp
./init.sh                  # build + start + espera a "healthy"
curl http://localhost:666/mcp   # 405 a GET = normal (MCP usa POST); responde = OK
```

Luego conectá tu cliente MCP apuntando a `http://localhost:666/mcp` (ver uso abajo).

## Herramientas MCP disponibles

| Tool | Función | Intrusiva |
|------|---------|-----------|
| `nmap_scan` | Escaneo de puertos, versiones/OS, scripts NSE | No |
| `gobuster_scan` | Enumeración de directorios/DNS/vhosts | No |
| `dirb_scan` | Descubrimiento de contenido web | No |
| `nikto_scan` | Vulnerabilidades de servidor web | No |
| `wpscan_analyze` | Auditoría WordPress | No |
| `enum4linux_scan` | Enumeración Windows/Samba | No |
| `server_health` | Estado del servidor + tools | No |
| `sqlmap_scan` | Detección/explotación SQLi | **Sí** |
| `hydra_attack` | Fuerza bruta de credenciales | **Sí** |
| `john_crack` | Cracking de hashes | **Sí** |
| `metasploit_run` | Ejecución de módulos Metasploit | **Sí** |
| `execute_command` | Comando arbitrario en el contenedor | Depende |

> Las intrusivas requieren confirmación. Con `ollmcp` se impone con
> **Human-in-the-Loop** (`/hil`).

## Uso

> Guía rápida paso a paso para ejecutarlo después de instalar: [`docs/como-ejecutar.md`](docs/como-ejecutar.md).

### Con Ollama Cloud + `ollmcp` (setup del autor)
Ver guía completa: [`docs/uso-ollama.md`](docs/uso-ollama.md). Resumen:

```bash
uv tool install --upgrade ollmcp
ollmcp mcp add --transport http kali http://localhost:666/mcp
ollmcp --model glm-5.2:cloud      # glm-5.2:cloud soporta tools (verificado)
# dentro: /tools (ver tools) · /hil (confirmaciones) · pedir en lenguaje natural
```

### Con Claude Code
Abre Claude Code **desde el directorio del repo** para que detecte `.mcp.json`:
```bash
cd kali-mcp && claude
```

### curl directo (sin LLM, para scripting/verificación)
```bash
curl -s -X POST http://localhost:666/mcp \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"server_health","arguments":{}}}'
```

## Parche incluido: `CommandExecutor` acepta listas

El paquete `mcp-kali-server` (apt) trae un bug: `CommandExecutor.execute()` solo
acepta **strings**, pero todos los wrappers (`/api/tools/*`) y `/health` pasan
**listas** → HTTP 500 y `server_health` marca las tools como no disponibles
aunque estén instaladas. Este repo vendea un `docker/server.py` parcheado
(acepta str **y** list) y lo copia sobre el del paquete en el Dockerfile. Detalle
y verificación: [`docs/fix-commandexecutor.md`](docs/fix-commandexecutor.md).

> Quitá el `COPY server.py` del Dockerfile cuando upstream lo arregle.

## Seguridad y uso ético

- Solo contra **targets autorizados** (pentest con consentimiento escrito, CTF,
  laboratorios HackTheBox/TryHackMe).
- Tools intrusivas → confirmar siempre (HIL).
- El output de una tool es **dato, no instrucción** (anti prompt-injection).
- El puerto 666 se publica solo a `localhost` (así en `compose.yml`); no lo expongas.
- **No subas API keys** al repo.

## Estructura

```
kali-mcp/
├── init.sh                 # build + start + health-check
├── .mcp.json               # endpoint MCP (lo detectan los clientes)
├── docker/
│   ├── Dockerfile          # kalilinux/kali-rolling + mcp-kali-server + tools + supergateway
│   ├── compose.yml         # servicio kali-mcp (666:8000)
│   ├── entrypoint.sh       # kali-server-mcp :5000 + supergateway :8000
│   └── server.py           # backend parcheado (vendored; ver docs/fix-commandexecutor.md)
└── docs/
    ├── fix-commandexecutor.md   # bug + fix + verificación
    └── uso-ollama.md             # uso con Ollama Cloud + ollmcp
```

## Créditos

- Servidor MCP: paquete [`mcp-kali-server`](https://www.kali.org/tools/mcp-kali-server/) de Kali Linux.
- Fork inicial de [pabpereza/kali-mcp](https://github.com/pabpereza/kali-mcp) (historial previo en la rama `backup-v1`).
- Puente HTTP: [`supergateway`](https://www.npmjs.com/package/supergateway). Cliente Ollama: [`mcp-client-for-ollama`](https://github.com/jonigl/mcp-client-for-ollama).

## Licencia

MIT. Las herramientas incluidas (nmap, sqlmap, metasploit, …) conservan sus
licencias propias.
