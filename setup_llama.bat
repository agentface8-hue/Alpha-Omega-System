@echo off
echo ===================================
echo  Alpha-Omega: Switch to Llama Setup
echo ===================================

echo [1/2] Installing langchain-ollama package...
pip install langchain-ollama --break-system-packages 2>nul || pip install langchain-ollama
if errorlevel 1 (
    echo Trying with pip3...
    pip3 install langchain-ollama
)

echo.
echo [2/2] Pulling llama3.2 model via Ollama...
echo (This downloads ~2GB — takes a few minutes)
ollama pull llama3.2

echo.
echo ===================================
echo  Done! Llama3.2 is ready.
echo  Restart your backend to use it.
echo ===================================
pause
