# Fix — `CommandExecutor` rechazaba comandos tipo lista (todos los wrappers daban 500)

**Paquete afectado:** `mcp-kali-server` (apt, `/usr/share/mcp-kali-server/server.py`)
**Referencia upstream:** https://www.kali.org/tools/mcp-kali-server/

## Síntoma

Todos los wrappers de tools (`nmap_scan`, `nikto_scan`, `gobuster_scan`,
`dirb_scan`, `sqlmap_scan`, `hydra_attack`, `john_crack`, `wpscan_analyze`,
`enum4linux_scan`, `metasploit_run`) devolvían `500 INTERNAL SERVER ERROR`, y
`server_health` reportaba `all_essential_tools_available: false` con
`nmap/nikto/gobuster/dirb: false` — aunque los binarios estaban instalados.

## Causa raíz

`CommandExecutor.execute()` solo aceptaba **strings** y lanzaba `ValueError`
para cualquier otra cosa:

```python
if not isinstance(self.command, str):
    raise ValueError(f"CommandExecutor expects a string, but got {type(self.command).__name__}")
cmd_args = shlex.split(self.command)   # calculado pero nunca usado
...
self.process = subprocess.Popen(self.command, shell=self.use_shell, ...)
```

Pero **todos** los wrappers y `/health` construyen el comando como **lista** y lo
pasan a `execute_command()`:

```python
# /api/tools/nmap
command = ["nmap"] + shlex.split(scan_type) + ... + [target]
execute_command(command)

# /health
execute_command(["which", tool])
```

Cada llamada levantaba el `ValueError` → atrapado por el `except` del endpoint →
`500 Server error: CommandExecutor expects a string, but got list`. El `["which",
tool]` de `/health` fallaba igual, por eso `tools_status` daba `false` con los
binarios instalados (`which nmap` y `shutil.which("nmap")` resuelven).

El propio docstring de `execute_command` decía *"list for safe mode, string for
shell mode"*: era una regresión (la rama para listas no estaba cableada; el
`cmd_args = shlex.split(...)` es un resto de ese refactor). `execute_command`
(el tool MCP genérico) seguía funcionando porque recibe un **string** del cliente.

## Fix

Hacer que `CommandExecutor.execute()` acepte ambas formas (cumpliendo el
contrato del docstring):

```python
# Soporta string (shell) y lista (safe, sin shell).
if isinstance(self.command, str):
    cmd = self.command
    shell = True
elif isinstance(self.command, (list, tuple)):
    cmd = [str(c) for c in self.command]
    shell = False
else:
    raise ValueError(f"CommandExecutor expects a string or list, but got {type(self.command).__name__}")

self.process = subprocess.Popen(cmd, shell=shell, ...)
```

Un único cambio en la ruta compartida arregla **todos** los wrappers + el health
check. Las listas corren con `shell=False` (modo seguro, sin inyección de shell
del lado del wrapper); los strings mantienen el comportamiento previo.

## Cómo se entrega en este repo

El paquete apt reinstala el archivo buggy en cada rebuild, así que la copia
parcheada se vendea y se copia encima en `docker/Dockerfile`:

```dockerfile
COPY server.py /usr/share/mcp-kali-server/server.py
```

`docker/server.py` es el backend parcheado. **Quitá ese `COPY` (y
`docker/server.py`) cuando upstream publique un paquete arreglado.**

## Verificación (tras build + restart)

```
server_health  -> all_essential_tools_available: true
                  nmap/nikto/gobuster/dirb: true
nmap_scan 127.0.0.1 -> success: true, return_code: 0, "5000/tcp open"
```

Repro del bug antes del parche (paquete fresh):

```
server_health -> all_essential_tools_available: false (nmap/nikto/gobuster/dirb: false)
nmap_scan     -> 500 "CommandExecutor expects a string, but got list"
```
