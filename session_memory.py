import os, json, subprocess, datetime, re
from pathlib import Path

BASE = Path(r"C:\Users\asus\Alpha-Omega-System")
MK   = BASE / "MASTER-KNOWLEDGE.md"
CL   = BASE / "CLAUDE.md"
LG   = BASE / "calibration" / "session_log.json"
os.chdir(BASE)


def R(cmd):
    return subprocess.run(cmd, cwd=BASE, text=True, capture_output=True)


def get_commits(hours=48):
    since = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")
    r = R(["git", "log", f"--since={since}", "--pretty=format:%h|||%s|||%ai", "--name-only"])
    commits, cur = [], None
    for line in r.stdout.strip().split("\n"):
        if "|||" in line:
            h, msg, ts = line.split("|||")
            cur = {"h": h.strip(), "m": msg.strip(), "t": ts.strip()[:16], "f": []}
            commits.append(cur)
        elif line.strip() and cur:
            cur["f"].append(line.strip())
    return commits


def make_section(commits):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = ["## 16. RECENT SESSION CHANGES", f"*Auto-updated: {now}*\n"]
    if not commits:
        lines.append("No commits in last 48h.\n")
        return "\n".join(lines)
    for c in commits[:10]:
        lines.append(f"### `{c['h']}` {c['t']} - {c['m']}")
        for f in c["f"][:5]:
            lines.append(f"- `{f}`")
        lines.append("")
    return "\n".join(lines)


def update_file(path, commits, label):
    if not path.exists():
        print(f"  SKIP {label}")
        return
    txt = path.read_text(encoding="utf-8")
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    txt = re.sub(r"# Last [Uu]pdated: \d{4}-\d{2}-\d{2}", f"# Last Updated: {today}", txt)
    txt = re.sub(r"# Last updated: \d{4}-\d{2}-\d{2}", f"# Last updated: {today}", txt)
    sec = make_section(commits)
    if "## 16. RECENT SESSION CHANGES" in txt:
        txt = re.sub(r"## 16\. RECENT SESSION CHANGES.*?(?=\n## |\Z)", sec + "\n\n", txt, flags=re.DOTALL)
    else:
        txt = txt.rstrip() + "\n\n" + sec + "\n"
    path.write_text(txt, encoding="utf-8")
    print(f"  OK   {label}")


def git_push():
    R(["git", "add", "MASTER-KNOWLEDGE.md", "CLAUDE.md", "calibration/session_log.json"])
    r = R(["git", "commit", "-m", f"auto: session memory {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"])
    if "nothing to commit" in r.stdout + r.stderr:
        print("  OK   Nothing new to commit")
        return
    r2 = R(["git", "push", "origin", "main"])
    print("  OK   Pushed" if r2.returncode == 0 else f"  WARN: {r2.stderr[:100]}")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  SESSION MEMORY UPDATER - Alpha-Omega")
    print(f"  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50 + "\n")
    commits = get_commits(48)
    print(f"Commits found (48h): {len(commits)}")
    for c in commits[:5]:
        print(f"  [{c['t']}] {c['m']}")
    print()
    update_file(MK, commits, "MASTER-KNOWLEDGE.md")
    update_file(CL, commits, "CLAUDE.md")
    LG.parent.mkdir(exist_ok=True)
    log = []
    if LG.exists():
        try:
            log = json.loads(LG.read_text())
        except Exception:
            pass
    log.append({"ts": datetime.datetime.utcnow().isoformat(),
                 "commits": len(commits),
                 "messages": [c["m"] for c in commits[:10]]})
    LG.write_text(json.dumps(log[-100:], indent=2))
    git_push()
    print("\nDone. Both knowledge files updated and pushed.")
    print("Next session starts fully informed.\n")
