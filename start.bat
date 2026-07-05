@echo off
chcp 65001 >nul
echo ========================================
echo 视频字幕生成系统 - 启动脚本
echo ========================================
echo.

REM 激活 conda 环境
call F:\anaconda\Scripts\activate.bat F:\anaconda\envs\caption-gen

REM 检查 FFmpeg
echo [1/3] 检查 FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [警告] FFmpeg 未安装或未添加到 PATH
    echo 请从 https://ffmpeg.org/download.html 下载安装
    echo.
) else (
    echo [√] FFmpeg 已安装
)

REM 检查 Ollama
echo [2/3] 检查 Ollama 服务...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [警告] Ollama 服务未启动
    echo 请在另一个终端运行: ollama serve
    echo.
) else (
    echo [√] Ollama 服务正常
)

REM 启动应用
echo [3/3] 启动 FastAPI 应用...
echo.
echo ========================================
echo 访问地址: http://localhost:8000
echo 按 Ctrl+C 停止服务
echo ========================================
echo.

python app.py

pause
