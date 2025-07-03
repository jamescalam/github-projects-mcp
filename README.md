## GitHub Projects

This project provides an MCP server for scraping data from GitHub Projects.

### Running with MCP

In Claude Desktop:

```
vim ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

```
{
    "mcpServers": {
        "github-projects": {
            "command": "uv",
            "args": [
                "--directory",
                "/Users/jamesbriggs/Documents/aurelio/corp-agent/github-projects",
                "run",
                "github_projects/mcp/app.py"
            ]
            "env": {
                "GITHUB_PAT": "github_pat_..."
            }
        }
    }
}
```

#### Digging in

We're leaving some quick notes on working and developing with MCP here. First, to view your MCP server and the various tools etc it contains we recommend:

```
npm install -g @modelcontextprotocol/inspector
```

Start the inspector app, inside the terminal you should see a `localhost` URL you can navigate to to open the UI.

```
mcp-inspector
```

Once inside the UI, start and connect to the MCP server with the following adapted to your particular environment. Note that these are the same inputs we provide to Claude Desktop:

```
Command: uv
Arguments: --directory /Users/jamesbriggs/Documents/aurelio/corp-agent/github-projects run python -m github_projects.app
Environment Variables (keep anything already here, just append): GITHUB_PAT: github_pat_...
```

Assuming the server started successfully, you can navigate to `Tools` and view the `@mcp.tool` methods that we have defined.