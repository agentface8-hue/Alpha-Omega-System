import subprocess, os

src = r"C:\Users\asus\Alpha-Omega-System\frontend\src"
for root, dirs, files in os.walk(src):
    for f in files:
        if f.endswith(('.jsx', '.js')):
            path = os.path.join(root, f)
            with open(path, encoding='utf-8', errors='ignore') as fh:
                for i, line in enumerate(fh, 1):
                    if any(x in line.lower() for x in ['waking', 'wake', 'backend waking', 'coldstart', 'cold-start', 'cold_start']):
                        print(f"{path}:{i}: {line.rstrip()}")
