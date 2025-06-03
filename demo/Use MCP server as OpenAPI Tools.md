# Using MCP Servers as OpenAPI Tools with `llm-tools-openapi`

The `llm-tools-openapi` plugin is not limited to standard OpenAPI-compatible APIs. You can also use it to interact with any MCP (Model Context Protocol) server by converting it into an OpenAPI server using [mcpo](https://github.com/open-webui/mcpo).

## Why Use mcpo?

MCP servers typically communicate over raw stdio, which is not compatible with most tools and lacks standard features like authentication, documentation, and error handling. [mcpo](https://github.com/open-webui/mcpo) solves this by acting as a proxy: it exposes any MCP server as a RESTful OpenAPI HTTP server, instantly making it accessible to tools and agents that expect OpenAPI endpoints.

**Benefits:**
- Instantly compatible with OpenAPI tools, SDKs, and UIs
- Adds security, stability, and scalability
- Auto-generates interactive documentation for every tool
- Uses standard HTTP—no custom protocols or glue code required

## How to Set Up

### 1. Start Your MCP Server with mcpo

mcpo also supports serving multiple MCP servers from a single config file. Each tool will be available under its own route, with its own OpenAPI schema and documentation.

Example `demo/mcp-demo.json`

```json
{
    "mcpServers": {
        "basic-memory": {
            "command": "uvx",
            "args": [
                "basic-memory",
                "mcp"
            ]
        },        
        "playwright": {
            "command": "npx",
            "args": ["-y", "@playwright/mcp@latest"]
        }
    }
}
```

Start mcpo with:

```bash
mcpo --config demo/mcp-demo.json
```

Each tool will be accessible at:
- `http://localhost:8000/basic-memory`
- `http://localhost:8000/playwright`

And their OpenAPI docs at:
- `http://localhost:8000/basic-memory/docs`
- `http://localhost:8000/playwright/docs`


### 3. Use with `llm-tools-openapi`

Point the `llm-tools-openapi` plugin to the OpenAPI endpoint provided by mcpo. 
For example:
```
llm \
--td \
--tool 'OpenAPIToolbox(openapi_url="http://0.0.0.0:8000/playwright/openapi.json")' \
--tool 'OpenAPIToolbox(openapi_url="http://0.0.0.0:8000/basic-memory/openapi.json")' \
"Open Hacker News and create a note in News directory
For the ten first articles, create a note like this :
title - url
Number of upvote 
Number of comment 
use snapshot and not screenshot" --cl 30
```

You will obtain a md file with the content you want.


## Summary

By combining `llm-tools-openapi` with mcpo, you can:
- Instantly convert any MCP server into an OpenAPI-compatible API
- Manage and call MCP tools using standard OpenAPI workflows
- Leverage the full power of LLM agents and automation with minimal setup

For more details, see the [mcpo documentation](https://github.com/open-webui/mcpo) and the [Open WebUI docs](https://docs.openwebui.com/openapi-servers/mcp). 


