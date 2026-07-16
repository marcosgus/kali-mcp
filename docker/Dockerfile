FROM kalilinux/kali-rolling

# --- MCP server (official Kali package) + Node gateway ---
# Ref: https://www.kali.org/tools/mcp-kali-server/
# mcp-kali-server provides:
#   - kali-server-mcp : Flask API server (default :5000)
#   - mcp-server      : MCP stdio bridge -> API server
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    mcp-kali-server \
    nodejs npm \
    curl ca-certificates && \
    apt-get clean

# --- Kali security toolset (driven via MCP tools / execute_command) ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    nmap masscan arp-scan netcat-traditional \
    whatweb theharvester fierce dnsrecon amass sublist3r wafw00f \
    gobuster dirb nikto ffuf wfuzz commix arjun nuclei wpscan \
    enum4linux crackmapexec smbclient impacket-scripts responder snmp tcpdump tshark \
    sqlmap hydra john exploitdb \
    hashcat hash-identifier cewl crunch \
    binwalk foremost steghide libimage-exiftool-perl \
    seclists wordlists \
    && apt-get clean

# rockyou.txt at the canonical plaintext path (shipped gzipped by the wordlists pkg)
RUN if [ -f /usr/share/wordlists/rockyou.txt.gz ]; then gunzip -k /usr/share/wordlists/rockyou.txt.gz; fi

# supergateway exposes the stdio MCP bridge as Streamable HTTP (needed for remote
# clients like ollmcp / Ollama Cloud that speak HTTP, not stdio)
RUN npm install -g supergateway

# --- Patch mcp-kali-server: CommandExecutor must accept list commands ---
# The apt-packaged server.py only accepts string commands, but every tool wrapper
# (/api/tools/*) and /health pass command lists -> HTTP 500 and tools_status=false.
# This vendored copy accepts both str (shell) and list (safe, no shell).
# Ref: https://www.kali.org/tools/mcp-kali-server/  Remove this COPY when upstream fixes it.
COPY server.py /usr/share/mcp-kali-server/server.py

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /tmp/workspace
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=5 \
  CMD curl -sf http://localhost:5000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
