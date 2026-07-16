# Upstream issue draft — `mcp-kali-server` wrapper tools return HTTP 500

Ready-to-file bug report for the upstream project that provides `mcp-kali-server`
(the package installed in `docker/Dockerfile`). Confirm the exact repository URL,
then file this (or let me post it once you point me at the repo).

---

**Title:** Tool wrappers (`nmap_scan`, `nikto_scan`, `hydra_attack`, …) return `500 INTERNAL SERVER ERROR`

**Environment**
- Image: `kalilinux/kali-rolling`
- Package: `mcp-kali-server` (apt)
- API: Flask on `127.0.0.1:5000`, exposed as MCP via `supergateway` on `:8000`
- Container has `NET_RAW` + `NET_ADMIN`; target reachable; binaries present
  (`which nmap nikto gobuster dirb` all resolve under `/usr/bin`).

**Symptom**
Every dedicated tool wrapper fails:

```
POST http://localhost:5000/api/tools/nmap
-> {"error":"Request failed: 500 Server Error: INTERNAL SERVER ERROR", "success": false}
```

The same is observed for `/api/tools/{nikto,gobuster,dirb,...}`. Meanwhile
`execute_command` works perfectly and can invoke the exact same binaries directly:

```
execute_command: nmap -sV -sC -Pn <target>   # succeeds
```

`server_health` returns `status: healthy` but reports
`all_essential_tools_available: false` with `nmap/nikto/gobuster/dirb: false`,
even though those binaries exist and run.

## Confirmed root cause

`CommandExecutor.execute()` only accepts **string** commands and raises
`ValueError("CommandExecutor expects a string, but got list")` for anything
else. Every tool wrapper and `/health` build the command as a **list**
(e.g. `["nmap", ...]`, `["which", tool]`) and pass it to `execute_command()`,
so each call raises and the endpoint returns 500. The `/health` `["which", tool]`
calls fail the same way, which is why `tools_status` is `false` despite the
binaries being installed (`which nmap` and `shutil.which("nmap")` both resolve).

The `execute_command` docstring already promises *"list for safe mode, string
for shell mode"*, so this is a regression: the list branch is missing (the
leftover `cmd_args = shlex.split(self.command)` line is never used).

**Fix:** make `execute_command`/`CommandExecutor.execute()` accept lists too
(`subprocess.Popen(cmd, shell=False)` for lists). See
[`docs/fix-commandexecutor.md`](fix-commandexecutor.md) for the full patch and
verification.

**Impact**
All specialized wrappers are unusable; consumers must route everything through
`execute_command`. This loses the wrappers' argument validation and any
structured output they were meant to provide.

**Expected**
- `CommandExecutor`/`execute_command` should accept command **lists** (safe
  mode, `shell=False`) as well as strings, per its own docstring. With that,
  the tool wrappers and `/health` work and `tools_status` reports `true`.

**Suggested fix**
- In `CommandExecutor.execute()`, branch on type: strings → `shell=True`;
  lists/tuples → `subprocess.Popen([str(c) for c in cmd], shell=False)`.
- Remove the dead `cmd_args = shlex.split(self.command)` line.

**Workaround**
Route all tools through `execute_command` invoking the raw binary. (This repo
previously standardized on that approach; see the TOOLING DIRECTIVE in
`AGENTS.md`.) This repo now ships a patched `docker/server.py` that fixes the
wrappers directly — see [`docs/fix-commandexecutor.md`](fix-commandexecutor.md).
