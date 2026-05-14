import json, os

config_path = os.path.join(os.environ['APPDATA'], 'Claude', 'claude_desktop_config.json')

with open(config_path, 'r') as f:
    config = json.load(f)

config['mcpServers']['brightdata'] = {
    "command": "npx",
    "args": ["-y", "@brightdata/mcp"],
    "env": {
        "API_TOKEN": "f7f05203-40bf-44ee-9a30-d83999907752"
    }
}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

print("Done. MCP servers now:", list(config['mcpServers'].keys()))
