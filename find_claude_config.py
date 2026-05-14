import os, json

appdata = os.environ.get('APPDATA', '')
claude_dir = os.path.join(appdata, 'Claude')
print(f"Claude dir: {claude_dir}")
print(f"Exists: {os.path.exists(claude_dir)}")
if os.path.exists(claude_dir):
    print(f"Contents: {os.listdir(claude_dir)}")
    config_path = os.path.join(claude_dir, 'claude_desktop_config.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            print(f"\nConfig:\n{f.read()}")
