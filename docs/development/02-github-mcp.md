# GitHub MCP Connection

Coding agents manage GitHub Issues and the GitHub Project [Investment-Copilot](https://github.com/users/MaxBernstetter/projects/2) (owner `MaxBernstetter`, number `2`) through the hosted GitHub MCP server. The connection is configured at project scope in `.mcp.json` at the repository root.

## Configuration

`.mcp.json` registers the server `github`:

- URL: `https://api.githubcopilot.com/mcp/`
- Auth: `Authorization: Bearer ${GITHUB_PAT}`. The token is read from the environment and never stored in the repository.
- Toolsets: `repos,issues,projects,labels` (via the `X-MCP-Toolsets` header)

## Setup

1. Create a **classic** personal access token with the scopes `repo` and `project`.
   Fine-grained tokens cannot access Projects owned by a personal account.
2. Export it in your shell profile, outside the repository:
   ```sh
   export GITHUB_PAT=<token>
   ```
3. Restart Claude Code in the project and approve the project MCP server `github` when prompted.
4. Check the connection with `/mcp`. The `github` server should be listed as connected.

## Security

- Never commit the token. `.mcp.json` only contains the variable reference.
- Rotate the token if it is exposed. Use an expiry date.

Related: [[01-task-management]]
