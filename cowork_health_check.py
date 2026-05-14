"""
cowork_health_check.py — Daily full system health check.

Called by Cowork scheduled task "alpha-omega-health-check" every morning.
Runs all 9 checks and fires Telegram alert if anything is RED or YELLOW.
"""
import sys, os
sys.path.insert(0, r"C:\Users\asus\Alpha-Omega-System")
os.chdir(r"C:\Users\asus\Alpha-Omega-System")
from dotenv import load_dotenv
load_dotenv()

from core.system_health import run_full_check

report = run_full_check(send_telegram=True)

# Print summary for Cowork logs
print(f"Health check complete: {report['overall']}")
print(f"GREEN={report['summary']['green']} YELLOW={report['summary']['yellow']} RED={report['summary']['red']}")

for r in report["checks"]:
    icon = "OK" if r["status"] == "GREEN" else r["status"]
    print(f"  [{icon}] {r['name']}: {r['detail']}")

if report["overall"] == "GREEN":
    print("All systems operational.")
else:
    print("\nISSUES DETECTED — Telegram alert sent.")
    for r in report["reds"] + report["yellows"]:
        print(f"  -> {r['name']}: {r['detail']}")
    sys.exit(1)
