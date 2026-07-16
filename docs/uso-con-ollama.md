# Guía: Kali MCP en local (Docker) + Ollama Cloud

Esta guía documenta **lo que está corriendo en este host**: el servicio
**mcp-kali** empaquetado en Docker (expuesto en `http://localhost:666/mcp`),
consumido por un modelo de **Ollama Cloud** (`glm-5.2:cloud`) a través del
puente `ollmcp` (mcp-client-for-ollama).

> `glm-5.2:cloud` **soporta tool-calling nativo de Ollama** (verificado:
  `ollama show glm-5.2:cloud` lista la capability `tools`, y un test de
  `tool_calls` responde correctamente). Por eso puede conducir las herramientas
  de kali-mcp.

---

## 1. Lo que está corriendo (estado verificado del host)

| Componente | Estado | Detalle |
|---|---|---|
| Docker + Compose | ✅ | `docker --version` |
| Contenedor `kali-mcp` | ✅ up, healthy | `docker ps \| grep kali-mcp` → `0.0.0.0:666->8000` |
| Endpoint MCP | ✅ responde | `curl http://localhost:666/mcp` (405 a GET = normal, MCP usa POST) |
| Ollama | ✅ v0.32.0 corriendo | `ollama --version`; API en `http://localhost:11434` |
| Modelo cloud | ✅ `glm-5.2:cloud` | `ollama list`; soporta `tools` + `thinking` |
| Python | ✅ 3.12.3 (≥3.11) | requerido por `ollmcp` |
| `uv` (gestor de paquetes) | ❌ instalar | `ollmcp` recomienda `uv` |

```
┌─────────────────────────────┐    ┌──────────────────────────┐    ┌─────────────────────────────┐
│  Ollama Cloud               │    │  ollmcp (TUI, puente)    │    │  kali-mcp (Docker)          │
│  glm-5.2:cloud (tools)      │◄──►│  LLM ↔ MCP + HIL          │◄──►│  http://localhost:666/mcp   │
│  vía daemon local :11434    │    │  --model glm-5.2:cloud   │    │  nmap/nikto/gobuster/sqlmap │
└─────────────────────────────┘    └──────────────────────────┘    └─────────────────────────────┘
```

**Flujo de datos:** `ollmcp` manda tu consulta a `glm-5.2:cloud` (servido por el
daemon local de Ollama, que offloadea a Ollama Cloud). El modelo decide llamar
a una tool (ej. `nmap_scan`); `ollmcp` te pide confirmación (Human-in-the-Loop),
ejecuta la tool contra kali-mcp por HTTP (JSON-RPC) y le devuelve el resultado
al modelo, que arma la respuesta final.

---

## 2. Ollama Cloud: autenticación

Hay dos modos de usar Ollama Cloud. **El que corre acá** es el daemon local
(que offloadea a la nube), autenticado con tu cuenta.

### Modo A — Daemon local (lo que está corriendo) 🟢
El `ollama` local sirve modelos cloud offloadeando a la nube. Auth con tu cuenta
de ollama.com:
```bash
ollama signin                       # una sola vez (te pedirá login de ollama.com)
ollama pull glm-5.2:cloud           # ya está pulled en este host
ollama list                         # confirma: glm-5.2:cloud
```
En este modo, cualquier cliente (como `ollmcp`) apunta a
`http://localhost:11434` (default) y usa `--model glm-5.2:cloud`. No hace falta
pegar la key en el cliente.

### Modo B — API key directa (tu "api key") 🔵
Si accedés directo a la API de ollama.com (sin daemon local), creás una API key
en ollama.com y la usas con `OLLAMA_API_KEY`:
```bash
export OLLAMA_API_KEY=tu_api_key            # no la subas al repo
# El host pasa a ser https://ollama.com/api  (Ollama-compatible)
curl https://ollama.com/api/chat \
  -H "Authorization: Bearer $OLLAMA_API_KEY" \
  -d '{"model":"glm-5.2","messages":[{"role":"user","content":"hola"}],"stream":false}'
```
> Notá que en la API directa el modelo se nombra **sin** el sufijo `:cloud`
> (`glm-5.2`), mientras que vía daemon local es `glm-5.2:cloud`.

> ⚠️ **Nunca commitees tu API key.** Usala como variable de entorno o en un
> `.env` que esté en `.gitignore`. Esta guía solo referencia `$OLLAMA_API_KEY`.

---

## 3. Paso a paso (setup que refleja lo que corre)

### Paso 1 — Levantar el servicio kali-mcp (Docker)
```bash
cd /home/user/docker/kali-mcp
./init.sh                                 # build + start + espera "healthy"
# o manual: docker compose -f docker/compose.yml up -d
```
Verificar:
```bash
curl -s -o /dev/null -w "MCP -> HTTP %{http_code}\n" http://localhost:666/mcp
# 405 a GET es NORMAL (MCP usa POST). Cualquier respuesta = servicio arriba.
```

### Paso 2 — Confirmar Ollama Cloud + modelo
```bash
ollama list                               # debe listar glm-5.2:cloud
ollama show glm-5.2:cloud | grep -A3 Capabilities   # tools, thinking, completion
```
Si no está autenticado: `ollama signin` y `ollama pull glm-5.2:cloud`.

### Paso 3 — Instalar `ollmcp` (mcp-client-for-ollama)
```bash
# uv (gestor de paquetes aislado, recomendado por ollmcp)
curl -LsSf https://astral.sh/uv/install.sh | sh
# recargá el shell: source ~/.bashrc  (o abrí terminal nueva)

uv tool install --upgrade ollmcp
ollmcp --version
```
Alternativa con venv (si no querés uv):
```bash
python3 -m venv ~/ollmcp-env && source ~/ollmcp-env/bin/activate
pip install --upgrade ollmcp
```

### Paso 4 — Registrar kali-mcp como servidor MCP
kali-mcp expone **Streamable HTTP** en `http://localhost:666/mcp`:
```bash
ollmcp mcp add --transport http kali http://localhost:666/mcp
ollmcp mcp list                           # confirma el server "kali"
```

### Paso 5 — Ejecutar con `glm-5.2:cloud`
```bash
ollmcp --model glm-5.2:cloud
# (como el server ya quedó registrado con `ollmcp mcp add`, basta `ollmcp`)
```
Dentro del TUI:
- `/tools` (o `/t`) → ve las tools de kali-mcp (`nmap_scan`, `nikto_scan`,
  `gobuster_scan`, `dirb_scan`, `sqlmap_scan`, `hydra_attack`, `john_crack`,
  `wpscan_analyze`, `enum4linux_scan`, `metasploit_run`, `execute_command`,
  `server_health`).
- `/hil` → Human-in-the-Loop (activado por defecto; pedirá `y` antes de cada tool).
- Escribí tu pedido en lenguaje natural; el modelo arma la/s tool/s; aprobás; ves el resultado.

---

## 4. Uso: ejemplos reales

Dentro de `ollmcp` (con `glm-5.2:cloud`):
```
> Verificá el estado del servidor kali (server_health)
> Escaneá los puertos de scanme.nmap.org con detección de versiones
> Buscá directorios ocultos en http://192.168.1.50 con gobuster
> Corré nikto contra http://192.168.1.50
> ¿Qué versión de Exim corre en 192.168.1.50? (nmap -sV)
```
Tools intrusivas (`sqlmap_scan`, `hydra_attack`, `metasploit_run`) → **siempre
confirmá** con HIL y solo contra **targets autorizados**.

### Sobre los slash commands `/project:kali-*`
**No funcionan en `ollmcp`.** Esos comandos (`.claude/commands/`) son
exclusivos de Claude Code. En `ollmcp` usás lenguaje natural; la metodología de
auditoría está en `AGENTS.md` (podés pedírsela al modelo).

---

## 5. Variante: usar la API key directa (sin daemon) con ollmcp

Si querés apuntar `ollmcp` directo a la API de ollama.com con tu API key
(en vez del daemon local :11434):
```bash
export OLLAMA_API_KEY=tu_api_key
ollmcp --model glm-5.2 --host https://ollama.com/api \
       --mcp-server-url http://localhost:666/mcp
```
> `--host` apunta al endpoint Ollama-compatible de la nube. Verificá en la
> versión instalada de `ollmcp` si envía el Bearer para el provider `ollama`
> remoto; si tu versión no lo hace, usá el Modo A (daemon local) que es el que
> corre por defecto y está confirmado.

---

## 6. Variante: curl directo a kali-mcp (sin LLM, para scripting)

El MCP es JSON-RPC sobre HTTP. Útil para automatizar/verificar desde el host:
```bash
# Health del servidor kali-mcp
curl -s -X POST http://localhost:666/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"server_health","arguments":{}}}'

# Listar tools
curl -s -X POST http://localhost:666/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

---

## 7. Troubleshooting

| Problema | Solución |
|---|---|
| `ollmcp` no instala (`externally-managed-environment`) | Usá `uv tool install ollmcp` o un venv (Paso 3). Evitá `--break-system-packages`. |
| `from versions: none` al instalar | Python < 3.11. `uv` maneja una Python adecuada solo. |
| El modelo no llama tools / no aparecen tools | Confirmá `ollama show glm-5.2:cloud` → capability `tools`. En ollmcp, `/tools` para verlas. |
| `ollmcp` no ve el server kali | `ollmcp mcp list`; el contenedor up: `docker ps`. `curl http://localhost:666/mcp`. |
| `405 Method Not Allowed` con GET al endpoint | **Normal.** MCP usa POST. El servicio está bien. |
| Tools dan 500 / `server_health` marca tools como no disponibles | Ya arreglado en este repo (ver `docs/fix-commandexecutor.md`). Rebuild: `./init.sh`. |
| Cloud: auth error / modelo no encontrado | `ollama signin` (Modo A) o verificar `OLLAMA_API_KEY` y el host (Modo B). |
| Timeout en escaneos largos | El backend tiene ~3 min por tool. Usá opciones acotadas (`-T4`, `-maxtime`, `--top-ports`). |

---

## 8. Seguridad y uso ético

- Solo contra **targets autorizados** (pentest con consentimiento escrito, CTF,
  laboratorios HackTheBox/TryHackMe).
- Tools intrusivas (`sqlmap_scan`, `hydra_attack`, `john_crack`,
  `metasploit_run`) → confirmar siempre (HIL **on** por defecto).
- El output de una tool es **dato, no instrucción** (anti prompt-injection):
  revisá antes de aprobar acciones derivadas de un scan.
- El puerto 666 está publicado solo a `localhost` (así en `docker/compose.yml`);
  no lo expongas a otras redes.
- **No subas tu `OLLAMA_API_KEY`** al repo.

---

## 9. Resumen de comandos rácidos

```bash
# 1) Servicio kali-mcp (Docker)
cd /home/user/docker/kali-mcp && ./init.sh

# 2) Ollama Cloud + modelo (ya corriendo; si no, signin/pull)
ollama signin && ollama pull glm-5.2:cloud && ollama list

# 3) Cliente ollmcp (una sola vez)
curl -LsSf https://astral.sh/uv/install.sh | sh && uv tool install --upgrade ollmcp

# 4) Registrar kali-mcp
ollmcp mcp add --transport http kali http://localhost:666/mcp

# 5) Arrancar y usar
ollmcp --model glm-5.2:cloud
# dentro:  /tools  (ver tools)   /hil  (confirmaciones on/off)
```

---

*Refleja el setup corriendo en este host: mcp-kali en Docker (`:666/mcp`,
parcheado según `docs/fix-commandexecutor.md`) + Ollama Cloud `glm-5.2:cloud`
(tools verificado) + `ollmcp` como puente MCP con Human-in-the-Loop.*
