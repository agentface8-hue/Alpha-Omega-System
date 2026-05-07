@echo off
echo Committing revert of Ollama changes...
cd /d C:\Users\asus\Alpha-Omega-System

del /f .git\index.lock 2>nul

git add agents/base_agent.py ^
        agents/bear_case_advocate.py ^
        agents/contrarian.py ^
        agents/executioner.py ^
        agents/historian.py ^
        agents/macro_strategist.py ^
        agents/newsroom.py ^
        agents/portfolio_architect.py ^
        agents/regime_detector.py ^
        agents/risk_officer.py ^
        config/settings.py ^
        core/telegram_agent.py ^
        requirements.txt ^
        setup_llama.bat ^
        frontend/.env.production

git commit -m "revert: restore Google Gemini + Anthropic Claude as production backends

- agents/base_agent.py: default llm_backend back to 'google'; keep ollama as option
- All 9 agent files: default llm_backend back to 'google'
- config/settings.py: restore gemini-pro + claude-3-opus model defaults
- core/telegram_agent.py: restore Claude API call for intent parsing
- requirements.txt: keep langchain-ollama (harmless on Render)
- setup_llama.bat: kept as local dev tool only
- frontend/.env.production: fix VITE_API_URL baked into build

Reason: Ollama runs locally only. Production is on Render which has no Ollama."

git push origin main
if errorlevel 1 (
    echo ERROR: Push failed. Check your connection or git credentials.
    pause
    exit /b 1
)

echo.
echo Done! Revert committed and pushed to origin main.
pause
