# 🎬 视频字幕生成系统

基于 Python + FastAPI + Ollama + Whisper 的智能视频字幕生成系统，支持语音识别、AI 翻译、双语字幕和字幕烧录。

## ✨ 功能特性

- **视频上传**: 支持拖拽上传，支持 MP4/AVI/MKV/MOV 等常见格式
- **语音识别**: 使用 OpenAI Whisper 模型，支持 NVIDIA GPU 加速 (CUDA)
- **字幕优化**: 使用 Ollama (Qwen3:14b) 自动修正错别字和语法错误
- **字幕翻译**: 支持中英双向翻译，批量处理优化
- **双语字幕**: 中文在上，英文在下的双语显示
- **字幕烧录**: 使用 moviepy 将字幕烧录到视频中，支持 GPU 编码 (NVENC)
- **音频同步**: 自动检测音频起始时间，校准字幕时间戳
- **多格式导出**: 支持 SRT/VTT/ASS/TXT 格式
- **烧录计时**: 显示字幕烧录耗时

## 🛠️ 技术栈

- **后端**: Python 3.10 + FastAPI + Uvicorn
- **语音识别**: OpenAI Whisper (medium 模型, CUDA 加速)
- **AI 服务**: Ollama + Qwen3:14b
- **视频处理**: moviepy + FFmpeg
- **前端**: HTML + CSS + JavaScript (轮询模式)
- **GPU 加速**: PyTorch 2.5+cu121 + CUDA 12.1

## 📋 系统要求

- Python 3.10+
- NVIDIA GPU (推荐 RTX 3060 以上，CPU 也可用)
- FFmpeg (音视频处理，conda 环境自带)
- Ollama (AI 服务)
- 至少 16GB 内存 (模型加载需要)

## 🚀 快速开始

### 1. 安装 Ollama

```bash
# 下载安装 Ollama
# https://ollama.ai/download

# 拉取 Qwen3:14b 模型
ollama pull qwen3:14b

# 启动 Ollama 服务
ollama serve
```

### 2. 创建 Conda 环境

```bash
# 方式一: 运行环境安装脚本 (Windows)
setup_env.bat

# 方式二: 手动创建
conda create -n caption-gen python=3.10 -y
conda activate caption-gen

# 安装 PyTorch (CUDA 12.1)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# 安装其他依赖
pip install -r requirements.txt
```

### 3. 启动应用

```bash
# 方式一: 运行启动脚本 (Windows)
start.bat

# 方式二: 手动启动
conda activate caption-gen
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问应用

打开浏览器访问: http://localhost:8000

## 📖 使用流程

1. **上传视频** - 拖拽或点击上传视频文件
2. **语音识别** - Whisper 自动识别音频内容
3. **AI 优化** - Ollama 修正错别字和语法
4. **翻译字幕** - 点击翻译按钮，支持中英互译
5. **下载字幕** - 支持 SRT/VTT/ASS/TXT 格式
6. **烧录视频** - 将字幕烧录到视频中

## 📁 项目结构

```
caption generation/
├── app.py                      # FastAPI 主应用
├── requirements.txt            # Python 依赖
├── setup_env.bat               # 环境安装脚本
├── start.bat                   # 启动脚本
├── README.md                   # 项目说明
├── .gitignore                  # Git 忽略配置
├── static/
│   ├── css/
│   │   └── style.css           # 样式文件
│   └── js/
│       └── main.js             # 前端逻辑
├── templates/
│   └── index.html              # 主页面
├── uploads/                    # 上传的视频临时存储 (gitignore)
├── outputs/                    # 生成的字幕文件 (gitignore)
├── models/                     # Whisper 模型缓存 (gitignore)
└── services/
    ├── audio_extractor.py      # 音频提取 + 字幕烧录
    ├── whisper_service.py      # Whisper 语音识别
    └── ollama_service.py       # Ollama AI 翻译服务
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
| `/api/download/{task_id}/{format}` | GET | 下载字幕文件 |
| `/api/burn-subtitles/{task_id}` | POST | 烧录字幕到视频 |

## ⚙️ 配置说明

编辑 `app.py` 中的 `Settings` 类:

```python
class Settings:
    UPLOAD_DIR = "uploads"          # 上传目录
    OUTPUT_DIR = "outputs"          # 输出目录
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 最大文件 500MB

    # Whisper 配置
    WHISPER_MODEL = "medium"        # tiny/base/small/medium/large-v3
    WHISPER_DEVICE = None           # cuda/cpu, None 自动选择
    WHISPER_LANGUAGE = None         # 语言代码, None 自动检测

    # Ollama 配置
    OLLAMA_URL = "http://localhost:11434"
    OLLAMA_MODEL = "qwen3:14b"      # 推荐 qwen3:14b
```

## 🔧 常见问题

### 1. GPU 不可用

检查 CUDA 是否正确安装:
```python
import torch
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
```

### 2. Ollama 连接失败

确保 Ollama 服务正在运行:
```bash
ollama serve
ollama list  # 检查模型是否已下载
```

### 3. 字幕烧录太慢

- 确保使用 GPU 编码 (NVENC)
- 较长视频需要更多时间处理
- 可考虑使用更小的 Whisper 模型

### 4. 字幕与音频不同步

程序会自动检测音频起始时间并校准。如仍有偏差，可在 `app.py` 中手动调整偏移量。

### 5. 内存/显存不足

- 使用更小的 Whisper 模型: `tiny` 或 `base`
- 减少 Ollama 模型大小: `qwen3:8b`
- 或增加系统内存/显存

## 🎯 性能优化

- **GPU 加速**: Whisper 使用 CUDA，字幕烧录使用 NVENC 编码
- **批量翻译**: 每 20 条字幕批量翻译，减少 API 调用
- **异步处理**: 全异步架构，支持并发任务
- **音频校准**: 自动检测音频起始时间，无需手动调整

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📝 更新日志

### v1.1.0 (2026-01-15)
- 添加双语字幕支持 (中文在上，英文在下)
- 添加字幕烧录功能，支持 GPU 编码
- 添加音频起始时间自动检测和校准
- 添加烧录计时显示
- 优化批量翻译性能
- 移除 WebSocket，改用轮询模式

### v1.0.0 (2026-01-05)
- 初始版本发布
- 支持 Whisper 语音识别
- 支持 Ollama AI 翻译
- 支持多格式字幕导出
