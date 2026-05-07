@echo off
cd /d C:\Users\asus\Alpha-Omega-System
del .git\index.lock 2>nul
del .git\HEAD.lock 2>nul
del .git\COMMIT_EDITMSG.lock 2>nul
git status
git add -A
git commit -m "feat: portfolio transparency v2.1 - TSL, entry panel, action log, override SL"
git push origin main
git push vercel main
echo DONE
