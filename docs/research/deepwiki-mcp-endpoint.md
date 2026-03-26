# DeepWiki MCP Endpoint (Ground Truth Validation)

DeepWiki exposes a **public MCP JSON-RPC endpoint** — no auth required.

## Endpoint
```
POST https://mcp.deepwiki.com/mcp
Content-Type: application/json
```

## Methods

### `read_wiki_structure`
Returns the table of contents / navigation structure for a repo.

### `read_wiki_contents`
Returns all wiki page content for a repo.

## Example Usage

```json
{
  "jsonrpc": "2.0",
  "method": "read_wiki_contents",
  "params": {
    "repoName": "pallets/flask"
  },
  "id": 1
}
```

## Tools That Use This
- **dw2md** (Rust CLI): `dw2md pallets/flask` — exports DeepWiki to markdown
  - Source: https://github.com/tnguyen21/dw2md
- **deepwiki-to-md** (Docker): https://github.com/suwa-sh/deepwiki-to-md
- **Chrome extension**: "DeepWiki to Markdown"

## Use Case For Us
Pull actual DeepWiki output for test repos (Flask, Spring Boot, etc.) and use it as
**ground truth** for validating our wiki output quality. Side-by-side comparison of:
- Citation density (file:line references per page)
- Diagram count and types per page
- Depth of analysis (word count, section count)
- Accuracy of claims vs actual source code
