# 🎬 视频字幕生成系统

基于 Python + FastAPI + Ollama + HTML 的智能视频字幕生成系统。

## ✨ 功能特性

- **视频上传**: 支持拖拽上传，支持 MP4/AVI/MKV/MOV 等常见格式
- **语音识别**: 使用 OpenAI Whisper 模型，支持 GPU 加速
- **字幕优化**: 使用 Ollama (Qwen2.5) 自动修正错别字和语法错误
- **字幕翻译**: 支持中英日韩等多语言双向翻译
- **多格式导出**: 支持 SRT/VTT/ASS/TXT 格式
- **实时进度**: WebSocket 实时推送处理进度

## 🛠️ 技术栈

- **后端**: Python 3.10 + FastAPI
- **语音识别**: OpenAI Whisper (medium 模型)
- **AI 服务**: Ollama + Qwen2.5
- **前端**: HTML + CSS + JavaScript
- **GPU 加速**: PyTorch + CUDA

## 📋 系统要求

- Python 3.10+
- NVIDIA GPU (推荐，CPU 也可用)
- FFmpeg (音视频处理)
- Ollama (AI 服务)

## 🚀 快速开始

### 1. 安装 FFmpeg

Windows 用户可以从 https://ffmpeg.org/download.html 下载，并添加到系统 PATH。

### 2. 安装 Ollama

```bash
# 下载安装 Ollama
# https://ollama.ai/download

# 拉取 Qwen2.5 模型
ollama pull qwen2.5

# 启动 Ollama 服务
ollama serve
```

### 3. 创建 Conda 环境

```bash
# 运行环境安装脚本
setup_env.bat

# 或手动创建
conda create -n caption-gen python=3.10 -y
conda activate caption-gen

# 安装 PyTorch (CUDA 12.1)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# 安装其他依赖
pip install -r requirements.txt
```

### 4. 启动应用

```bash
# 方式一: 运行启动脚本
start.bat

# 方式二: 手动启动
conda activate caption-gen
python app.py
```

### 5. 访问应用

打开浏览器访问: http://localhost:8000

## 📁 项目结构

```
caption generation/
├── app.py                  # FastAPI 主应用
├── requirements.txt        # Python 依赖
├── setup_env.bat           # 环境安装脚本
├── start.bat               # 启动脚本
├── README.md               # 项目说明
├── static/
│   ├── css/
│   │   └── style.css       # 样式文件
│   └── js/
│       └── main.js         # 前端逻辑
├── templates/
│   └── index.html          # 主页面
├── uploads/                # 上传的视频临时存储
├── outputs/                # 生成的字幕文件
├── services/
│   ├── audio_extractor.py  # 音频提取服务
│   ├── whisper_service.py  # Whisper 语音识别
│   └── ollama_service.py   # Ollama AI 服务
└── utils/
    └── subtitle_formatter.py # 字幕格式化工具
```

## 📖 API 文档

启动应用后访问: http://localhost:8000/docs

### 主要接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/upload` | POST | 上传视频文件 |
| `/api/process/{task_id}` | POST | 开始处理视频 |
| `/api/status/{task_id}` | GET | 获取任务状态 |
| `/api/translate` | POST | 翻译字幕 |
| `/api/download/{task_id}` | GET | 下载字幕文件 |
| `/ws/{task_id}` | WebSocket | 实时进度推送 |

## ⚙️ 配置说明

编辑 `app.py` 中的 `Settings` 类:

```python
class Settings:
    # Whisper 配置
    WHISPER_MODEL = "medium"      # tiny/base/small/medium/large-v3
    WHISPER_DEVICE = None         # cuda/cpu, None 自动选择
    WHISPER_LANGUAGE = None       # 语言代码, None 自动检测

    # Ollama 配置
    OLLAMA_URL = "http://localhost:11434"
    OLLAMA_MODEL = "qwen2.5"
```

## 🔧 常见问题

### 1. FFmpeg 未找到

确保 FFmpeg 已安装并添加到系统 PATH:
```bash
ffmpeg -version
```

### 2. GPU 不可用

检查 CUDA 是否正确安装:
```python
import torch
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
```

### 3. Ollama 连接失败

确保 Ollama 服务正在运行:
```bash
ollama serve
```

### 4. 内存不足

- 使用更小的 Whisper 模型 (tiny/base/small)
- 或增加系统内存/显存

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
