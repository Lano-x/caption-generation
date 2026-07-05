@echo off
echo ========================================
echo 创建 Conda 环境: caption-gen
echo ========================================
echo.

REM 创建 conda 环境
conda create -n caption-gen python=3.10 -y

REM 激活环境
call conda activate caption-gen

REM 安装 PyTorch (CUDA 12.1)
echo.
echo 安装 PyTorch (CUDA 12.1)...
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

REM 安装其他依赖
echo.
echo 安装其他依赖...
pip install -r requirements.txt

echo.
echo ========================================
echo 环境创建完成！
echo 请运行以下命令激活环境:
echo conda activate caption-gen
echo ========================================
pause
