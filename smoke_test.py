import sys
sys.path.insert(0, '.')
from backend.main import app
print("FastAPI OK")

# Verify the momentum cache exists (from our earlier live test)
import json
from pathlib import Path
cache = Path("calibration/momentum_screen_cache.json")
if cache.exists():
    data = json.loads(cache.read_text())
    results = data.get("results", [])
    # Simulate what the endpoint does for Tech sector
    tech = [r["ticker"] for r in results if r.get("sector") == "Technology"][:30]
    real_estate = [r["ticker"] for r in results if r.get("sector") == "Real Estate"][:30]
    print(f"Tech top 10 by momentum: {tech[:10]}")
    print(f"Real Estate top 10 by momentum: {real_estate[:10]}")
else:
    print("Cache not found - will be built on first sector click")
print("ALL OK")
