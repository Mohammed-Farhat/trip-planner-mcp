# Part 1 – MCP and the Fetch Server: Summary and Critique

## Key ideas from the article

Ksenia Se's article argues that even capable LLMs are limited by their isolation from data. Before MCP, every data source needed its own brittle custom integration. The Model Context Protocol, released by Anthropic in November 2024, is an open, model-agnostic standard that turns this N×M integration problem into N+M. Each tool is wrapped once as a server that any MCP application can use. Servers expose three primitives: **tools** (actions the model can invoke), **resources** (read-only context) and **prompts** (reusable templates). Clients discover these at runtime. The article contrasts MCP with OpenAI plugins (proprietary), LangChain (a developer-facing interface, not a model-facing protocol) and RAG (passive context, not active fetching). Its listed limits include operational overhead, security, immaturity, and tool quality that depends on descriptions.

The architecture has three roles. The **host** is the AI application (Claude Desktop, an IDE, or my Python agent); it owns the LLM and the conversation. For each server, the host creates one **MCP client**, which holds a dedicated connection and speaks JSON-RPC 2.0 over stdio (local) or Streamable HTTP (remote). The **server** is a program that exposes capabilities. So the host decides, the client carries the messages, and the server executes. In my project, the Agents SDK program is the host, `MCPServerStdio` is the client, and the FastMCP process is the server.

## Critique: the reference Fetch server

The Fetch server exposes a single tool, `fetch(url, max_length=5000, start_index=0, raw=false)`, plus a matching prompt. Its interface is well defined: strictly typed, described parameters and read-only/idempotent annotations. Its behaviour is predictable: robots.txt refusals, HTTP errors and blocked private addresses become explicit tool errors, and long pages are paginated with a "continue from `start_index`" hint.

It does, however, bundle responsibilities. Its own description fails the class "and" test: it "fetches a URL … and optionally extracts its contents as markdown". One call fetches the page, enforces robots.txt, converts HTML to Markdown and paginates, and the `raw` flag turns it into a second tool. The code is already split internally (`fetch_url`, `extract_content_from_html`), so separate tools would cost little and would show whether retrieval or extraction failed. The description also mixes documentation with model steering ("this tool now grants you internet access"). The bundling is a defensible trade-off, since it means fewer round trips and a small tool surface. The Filesystem server, by contrast, uses 13 single-purpose tools with read-only/destructive annotations.

---

**Sources**
- K. Se, "What Is MCP, and Why Is Everyone – Suddenly! – Talking About It?", Hugging Face, 17 Mar 2025: https://huggingface.co/blog/Kseniase/mcp. The full text is at https://www.turingpost.com/p/mcp.
- MCP architecture overview: https://modelcontextprotocol.io/docs/learn/architecture. This is the source of the article's Host/Client/Server diagrams.
- Fetch server: https://github.com/modelcontextprotocol/servers/tree/main/src/fetch
- Filesystem server: https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem
