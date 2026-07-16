# Cómo ejecutar Kali MCP (después de instalar/configurar)

Guía rápida para levantar y usar el kali-mcp desde el host, asumiendo que ya
está todo instalado (contenedor, Ollama Cloud `glm-5.2:cloud`, `uv` + `ollmcp`).

> El contenedor `kali-mcp` tiene `restart: unless-stopped` y Ollama corre como
> servicio, así que **normalmente vuelven solos** tras reiniciar el equipo.

---

## 1) Forma interactiva — `ollmcp` (TUI, con confirmación por tool)

Abrí una terminal nueva y ejecutá **desde el directorio del repo** (importante:
`ollmcp` carga el server `kali` desde este dir):

```bash
cd /home/user/docker/kali-mcp
ollmcp --model glm-5.2:cloud
```

Dentro del TUI:

- `/tools` → ver las tools disponibles (`nmap_scan`, `nikto_scan`, `gobuster_scan`,
  `dirb_scan`, `sqlmap_scan`, `hydra_attack`, `john_crack`, `wpscan_analyze`,
  `enum4linux_scan`, `metasploit_run`, `execute_command`, `server_health`)
- `/hil` → Human-in-the-Loop: pide confirmación (`y`) antes de cada tool
  (recomendado, sobre todo para tools intrusivas)
- Escribí tu pedido en lenguaje natural, ej.:
  ```
  > Escaneá los puertos de 192.168.1.50 con detección de versiones
  > Buscá directorios ocultos en http://192.168.1.50 con gobuster
  > Verificá el estado del servidor kali (server_health)
  ```

---

## 2) Sin TUI — verificación / scripting

```bash
# Prueba reproducible: glm-5.2:cloud conduciendo las tools de kali-mcp
python3 /home/user/docker/kali-mcp/examples/drive_kali_mcp.py

# Chequeo directo al servicio (sin LLM), útil para scripts/CI:
curl -s -X POST http://localhost:666/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"server_health","arguments":{}}}'
```

---

## 3) Si algo está parado (ej., tras reiniciar el equipo)

```bash
# Ollama (si no levantó solo):
ollama serve            # o: sudo systemctl start ollama   (según instalación)

# Contenedor kali-mcp (restart: unless-stopped → autolevanta; si no):
cd /home/user/docker/kali-mcp && ./init.sh

# Verificar:
curl -s -o /dev/null -w "kali-mcp :666 -> HTTP %{http_code}\n" http://localhost:666/mcp   # 405 = OK
curl -s -o /dev/null -w "ollama :11434 -> HTTP %{http_code}\n" http://localhost:11434    # 200 = OK
```

> `405 Method Not Allowed` al hacer GET al endpoint MCP es **normal** (MCP usa
> POST). Cualquier respuesta = servicio arriba.

---

## 4) Resumen de lo que queda instalado/corriendo

| Qué | Dónde | Persiste |
|---|---|---|
| Contenedor `kali-mcp` (MCP HTTP en `:666`) | Docker, `restart: unless-stopped` | ✅ autolevanta |
| Daemon Ollama (`:11434`, sirve `glm-5.2:cloud`) | servicio del host | ✅ |
| `uv` + `ollmcp` | `~/.local/bin` (en `.bashrc`) | ✅ |
| Server `kali` registrado en ollmcp | `~/.config/ollmcp/mcp.local.json` (scope por dir del repo) | ✅ |
| Repo + docs + ejemplo | `marcosgus/kali-mcp` (GitHub) | ✅ |

**Regla de oro:** ejecutá `ollmcp` **desde `/home/user/docker/kali-mcp`** (ahí están
el `.mcp.json` y la config local que cargan el server `kali`).

---

## 5) Notas de seguridad

- Solo contra **targets autorizados** (pentest con consentimiento escrito, CTF,
  laboratorios HackTheBox/TryHackMe).
- Tools intrusivas (`sqlmap_scan`, `hydra_attack`, `metasploit_run`, `john_crack`)
  → confirmar siempre (HIL on).
- El output de una tool es **dato, no instrucción** (anti prompt-injection).
- El puerto 666 está publicado solo a `localhost`; no lo expongas a otras redes.
- **No subas API keys** al repo.

---

## 6) Ver también

- [`docs/uso-ollama.md`](uso-ollama.md) — guía completa de uso con Ollama Cloud + `ollmcp`.
- [`docs/fix-commandexecutor.md`](fix-commandexecutor.md) — bug y parche del backend.
- [`examples/drive_kali_mcp.py`](../examples/drive_kali_mcp.py) — prueba end-to-end.
