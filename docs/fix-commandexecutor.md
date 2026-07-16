# Fix — `CommandExecutor` rejected list commands (all tool wrappers returned 500)

**Date:** 2026-07-16
**Affects:** `mcp-kali-server` (apt package, `/usr/share/mcp-kali-server/server.py`)
**Symptom:** Every dedicated MCP tool wrapper (`nmap_scan`, `nikto_scan`,
`gobuster_scan`, `dirb_scan`, `sqlmap_scan`, `hydra_attack`, `john_crack`,
`wpscan_analyze`, `enum4linux_scan`, `metasploit_run`) returned
`500 INTERNAL SERVER ERROR`, and `server_health` reported
`all_essential_tools_available: false` with `nmap/nikto/gobuster/dirb: false`
— even though the binaries were installed and runnable.

## Root cause

`CommandExecutor.execute()` only accepted **string** commands and raised
`ValueError` for anything else:

```python
if not isinstance(self.command, str):
    raise ValueError(f"CommandExecutor expects a string, but got {type(self.command).__name__}")

cmd_args = shlex.split(self.command)          # computed but never used
...
self.process = subprocess.Popen(
    self.command,
    shell=self.use_shell,
    ...
)
```

But **every** tool wrapper and the `/health` endpoint build the command as a
**list** and pass it to `execute_command()`:

```python
# /api/tools/nmap
command = ["nmap"] + shlex.split(scan_type) + ... + [target]
result = execute_command(command)

# /health
result = execute_command(["which", tool])
```

So each call hit the `ValueError` → caught by the endpoint's `except` →
`500 Server error: CommandExecutor expects a string, but got list`.

The `/health` endpoint's `["which", tool]` calls failed the same way, which is
why `tools_status` reported `false` for tools that were in fact installed
(`which nmap` → `/usr/bin/nmap`, `shutil.which("nmap")` → `/usr/bin/nmap`).

`execute_command` (the generic MCP tool) kept working because it receives a
**string** from the caller.

Notably, the `execute_command` docstring already stated the intended contract —
*"list for safe mode, string for shell mode"* — so this was a regression: the
list branch had been removed/never wired up (the `cmd_args = shlex.split(...)`
line is a leftover from that refactor and was never used).

## Fix

Make `CommandExecutor.execute()` accept both forms, matching the documented
contract:

```python
# Support both string (shell mode) and list (safe mode, no shell) commands.
if isinstance(self.command, str):
    cmd = self.command
    shell = True
elif isinstance(self.command, (list, tuple)):
    cmd = [str(c) for c in self.command]
    shell = False
else:
    raise ValueError(f"CommandExecutor expects a string or list, but got {type(self.command).__name__}")

try:
    self.process = subprocess.Popen(
        cmd,
        shell=shell,
        ...
```

A single change in this shared code path fixes **all** tool wrappers and the
health check at once. Lists run with `shell=False` (safe, no shell injection on
the wrapper side); strings keep the previous shell behavior.

## How the fix is shipped in this repo

The apt package reinstalls the buggy file on every image rebuild, so the patched
copy is vendored and copied over it in `docker/Dockerfile`:

```dockerfile
# --- Patch mcp-kali-server: fix CommandExecutor to accept list commands ---
COPY server.py /usr/share/mcp-kali-server/server.py
```

`docker/server.py` is the patched backend. **Remove that `COPY` (and
`docker/server.py`) once a fixed `mcp-kali-server` package is released upstream.**

## Verification

After applying the patch and rebuilding (`docker compose -f docker/compose.yml
up -d --build`), all endpoints were confirmed end to end via the MCP gateway
(`http://localhost:666/mcp`) with benign/local targets:

| Tool | Test | Result |
|---|---|---|
| `server_health` | — | `all_essential_tools_available: true`; nmap/nikto/gobuster/dirb = `true` |
| `nmap_scan` | `127.0.0.1` | rc 0; real nmap output (found Flask API on 5000/tcp) |
| `nikto_scan` | vs local Flask | Nikto v2.6.0 ran; detected `Werkzeug/3.1.8` |
| `gobuster_scan` | vs local Flask | rc 0 |
| `dirb_scan` | vs local Flask | DIRB v2.22, rc 0 |
| `sqlmap_scan` | `http://127.0.0.1:5000/health?id=1` | rc 0; "does not seem to be injectable" |
| `hydra_attack` | `127.0.0.1` ftp (closed) | hydra ran (rc 255 = no connection, expected) |
| `john_crack` | MD5 of "test" + wordlist "test" | cracked in 0s; `success: true` |
| `wpscan_analyze` | vs local Flask (not WP) | ran (rc 1 = not WordPress, expected) |
| `enum4linux_scan` | `127.0.0.1` (SMB closed) | enum4linux v0.9.1 ran |
| `metasploit_run` | `auxiliary/scanner/portscan/tcp` on localhost | `success: true`; "TCP OPEN"; "Auxiliary module execution completed" |
| `execute_command` | pre-existing | still works |

The non-zero return codes for hydra/wpscan/enum4linux are **expected**: the
benign targets had no vulnerable service to find. The point of the test is that
the wrapper executed the underlying binary and returned its real output instead
of a `500`.

## Files changed

- `docker/server.py` — vendored, patched backend (new).
- `docker/Dockerfile` — `COPY server.py` over the apt-installed file (with
  explanatory comment), placed after the expensive `RUN` layers so rebuilds
  stay fast and cached.
