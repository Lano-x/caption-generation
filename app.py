"""视频字幕生成系统 - FastAPI 主应用"""

import os
import sys
import uuid
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

# 将 FFmpeg 添加到 PATH（Whisper 内部需要）
def setup_ffmpeg_path():
    """将 FFmpeg 路径添加到系统 PATH"""
    import shutil

    # 1. 先检查是否已在 PATH 中
    if shutil.which("ffmpeg"):
        return

    # 2. 通过 Python 路径推断 conda 环境
    python_path = Path(sys.executable)
    conda_ffmpeg_dir = python_path.parent / "Library" / "bin"

    if (conda_ffmpeg_dir / "ffmpeg.exe").exists():
        os.environ["PATH"] = str(conda_ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")

setup_ffmpeg_path()

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from services.audio_extractor import AudioExtractor
from services.whisper_service import WhisperService, Segment
from services.ollama_service import OllamaService
from utils.subtitle_formatter import SubtitleFormatter


# ==================== 配置 ====================

# 获取项目根目录（app.py 所在目录）
BASE_DIR = Path(__file__).resolve().parent

class Settings:
    """应用配置"""
    UPLOAD_DIR = BASE_DIR / "uploads"
    OUTPUT_DIR = BASE_DIR / "outputs"
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    ALLOWED_EXTENSIONS = {
        ".mp4", ".avi", ".mkv", ".mov",
        ".wmv", ".flv", ".webm", ".m4v"
    }

    # Whisper 配置
    WHISPER_MODEL = "medium"  # 使用 medium 模型（769MB），准确度高
    WHISPER_DEVICE = None  # 自动选择
    WHISPER_LANGUAGE = None  # 自动检测

    # Ollama 配置
    OLLAMA_URL = "http://localhost:11434"
    OLLAMA_MODEL = "qwen3:14b"


settings = Settings()

# 创建目录
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 服务初始化 ====================

app = FastAPI(
    title="视频字幕生成系统",
    description="基于 Whisper + Ollama 的智能字幕生成",
    version="1.0.0"
)

# 挂载静态文件和模板
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 初始化服务
audio_extractor = AudioExtractor(output_dir=str(settings.OUTPUT_DIR))
whisper_service = WhisperService(
    model_name=settings.WHISPER_MODEL,
    device=settings.WHISPER_DEVICE,
    language=settings.WHISPER_LANGUAGE
)
ollama_service = OllamaService(
    base_url=settings.OLLAMA_URL,
    model=settings.OLLAMA_MODEL
)
subtitle_formatter = SubtitleFormatter()

# ==================== 数据模型 ====================

class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: str  # pending/processing/completed/failed
    progress: int  # 0-100
    message: str
    created_at: str
    completed_at: Optional[str] = None
    video_name: Optional[str] = None
    segments: Optional[list[dict]] = None
    error: Optional[str] = None


class TranslationRequest(BaseModel):
    """翻译请求"""
    task_id: str
    source_lang: str = "zh"
    target_lang: str = "en"
    optimize: bool = True


# ==================== 任务管理 ====================

# 存储任务状态（生产环境应使用数据库）
tasks: dict[str, TaskStatus] = {}

# WebSocket 连接管理
websocket_connections: dict[str, list[WebSocket]] = {}


async def update_task_status(
    task_id: str,
    status: str,
    progress: int,
    message: str,
    **kwargs
) -> None:
    """更新任务状态并通知 WebSocket 客户端"""
    if task_id in tasks:
        tasks[task_id].status = status
        tasks[task_id].progress = progress
        tasks[task_id].message = message

        for key, value in kwargs.items():
            if hasattr(tasks[task_id], key):
                setattr(tasks[task_id], key, value)

        # 通知 WebSocket 客户端
        if task_id in websocket_connections:
            for ws in websocket_connections[task_id]:
                try:
                    await ws.send_json({
                        "status": status,
                        "progress": progress,
                        "message": message,
                        **kwargs
                    })
                except Exception:
                    pass


# ==================== 路由 ====================

@app.get("/")
async def index(request: Request):
    """主页"""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/info")
async def get_info():
    """获取系统信息"""
    return {
        "whisper": whisper_service.get_model_info(),
        "ollama": ollama_service.get_model_info(),
        "supported_formats": audio_extractor.get_supported_formats(),
        "subtitle_formats": subtitle_formatter.get_supported_formats()
    }


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    上传视频文件

    Args:
        file: 视频文件

    Returns:
        任务 ID 和文件信息
    """
    # 验证文件扩展名
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}"
        )

    # 生成任务 ID
    task_id = str(uuid.uuid4())[:8]

    # 保存文件
    file_path = settings.UPLOAD_DIR / f"{task_id}{ext}"
    try:
        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="文件大小超过限制 (最大 2GB)"
            )

        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"文件保存失败: {str(e)}"
        )

    # 创建任务记录
    tasks[task_id] = TaskStatus(
        task_id=task_id,
        status="pending",
        progress=0,
        message="视频上传成功，等待处理",
        created_at=datetime.now().isoformat(),
        video_name=file.filename
    )

    return {
        "task_id": task_id,
        "filename": file.filename,
        "size": len(content),
        "message": "上传成功"
    }


@app.post("/api/process/{task_id}")
async def process_video(task_id: str):
    """
    处理视频（提取音频 + 语音识别）

    Args:
        task_id: 任务 ID

    Returns:
        处理结果
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task.status == "processing":
        raise HTTPException(status_code=400, detail="任务正在处理中")

    # 异步处理视频
    asyncio.create_task(process_video_task(task_id))

    return {"message": "开始处理", "task_id": task_id}


async def process_video_task(task_id: str):
    """异步处理视频任务"""
    task = tasks[task_id]

    try:
        # 更新状态：提取音频
        await update_task_status(
            task_id, "processing", 10,
            "正在提取音频..."
        )

        # 查找视频文件
        video_file = None
        for ext in settings.ALLOWED_EXTENSIONS:
            potential_path = settings.UPLOAD_DIR / f"{task_id}{ext}"
            if potential_path.exists():
                video_file = potential_path
                break

        if not video_file:
            raise FileNotFoundError("未找到视频文件")

        # 提取音频
        audio_path = await audio_extractor.extract_audio(str(video_file))

        # 更新状态：语音识别
        await update_task_status(
            task_id, "processing", 30,
            "正在进行语音识别（首次使用需下载模型）..."
        )

        # 加载 Whisper 模型
        if whisper_service.model is None:
            await update_task_status(
                task_id, "processing", 40,
                "正在加载 Whisper 模型..."
            )
            await whisper_service.load_model()

        # 执行语音识别
        await update_task_status(
            task_id, "processing", 60,
            "正在识别语音..."
        )

        segments = await whisper_service.transcribe(audio_path)

        # 转换为字典格式
        segments_data = [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            for seg in segments
        ]

        # 生成 SRT 文件
        srt_path = settings.OUTPUT_DIR / f"{task_id}.srt"
        subtitle_formatter.to_srt(segments, str(srt_path))

        # 更新任务完成
        await update_task_status(
            task_id, "completed", 100,
            f"处理完成，共识别 {len(segments)} 条字幕",
            completed_at=datetime.now().isoformat(),
            segments=segments_data
        )

        # 清理临时文件
        # audio_path 文件保留，供后续翻译使用

    except Exception as e:
        import traceback
        # 记录详细错误到文件
        with open(BASE_DIR / "error.log", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        await update_task_status(
            task_id, "failed", 0,
            f"处理失败: {str(e)}",
            error=str(e)
        )


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """获取任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return tasks[task_id]


@app.post("/api/translate")
async def translate_subtitles(request: TranslationRequest):
    """
    翻译字幕

    Args:
        request: 翻译请求

    Returns:
        翻译结果
    """
    task_id = request.task_id

    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if not task.segments:
        raise HTTPException(status_code=400, detail="没有可用的字幕数据")

    try:
        # 转换为 Segment 对象
        segments = [
            Segment(start=s["start"], end=s["end"], text=s["text"])
            for s in task.segments
        ]

        # 优化字幕（可选）
        if request.optimize:
            await update_task_status(
                task_id, "processing", 30,
                "正在优化字幕..."
            )
            segments = await ollama_service.optimize_subtitles(
                segments,
                source_lang=request.source_lang
            )

        # 翻译字幕
        await update_task_status(
            task_id, "processing", 60,
            f"正在翻译字幕 ({request.source_lang} -> {request.target_lang})..."
        )
        translated_segments = await ollama_service.translate_subtitles(
            segments,
            source_lang=request.source_lang,
            target_lang=request.target_lang
        )

        # 生成翻译后的 SRT 文件
        translated_srt_path = settings.OUTPUT_DIR / f"{task_id}_{request.target_lang}.srt"
        subtitle_formatter.to_srt(translated_segments, str(translated_srt_path))

        # 生成双语 SRT 文件（中文在上，英文在下）
        bilingual_srt_path = settings.OUTPUT_DIR / f"{task_id}_bilingual.srt"
        with open(bilingual_srt_path, "w", encoding="utf-8") as f:
            for i, (orig, trans) in enumerate(zip(segments, translated_segments), start=1):
                f.write(f"{i}\n")
                f.write(f"{subtitle_formatter.format_srt_time(orig.start)} --> {subtitle_formatter.format_srt_time(orig.end)}\n")
                f.write(f"{trans.text}\n")  # 中文在上
                f.write(f"{orig.text}\n")   # 英文在下
                f.write("\n")

        # 保存双语字幕到任务（用于烧录）
        tasks[task_id].bilingual_segments = [
            {
                "start": orig.start,
                "end": orig.end,
                "text": f"{trans.text}\n{orig.text}"  # 中文\n英文
            }
            for orig, trans in zip(segments, translated_segments)
        ]

        # 转换为字典格式
        translated_data = [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            for seg in translated_segments
        ]

        await update_task_status(
            task_id, "completed", 100,
            "翻译完成"
        )

        return {
            "task_id": task_id,
            "source_lang": request.source_lang,
            "target_lang": request.target_lang,
            "segments": translated_data,
            "srt_file": f"{task_id}_{request.target_lang}.srt",
            "bilingual_srt_file": f"{task_id}_bilingual.srt"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"翻译失败: {str(e)}"
        )


@app.get("/api/download/{task_id}")
async def download_subtitle(task_id: str, format: str = "srt", lang: str = ""):
    """
    下载字幕文件

    Args:
        task_id: 任务 ID
        format: 字幕格式 (srt/vtt/ass/txt)
        lang: 语言代码（空表示原始语言）

    Returns:
        字幕文件
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    # 确定文件名
    if lang:
        base_name = f"{task_id}_{lang}"
    else:
        base_name = task_id

    # 根据格式生成文件
    if not task.segments:
        raise HTTPException(status_code=400, detail="没有可用的字幕数据")

    segments = [
        Segment(start=s["start"], end=s["end"], text=s["text"])
        for s in task.segments
    ]

    output_path = settings.OUTPUT_DIR / f"{base_name}.{format}"

    if format == "srt":
        subtitle_formatter.to_srt(segments, str(output_path))
    elif format == "vtt":
        subtitle_formatter.to_vtt(segments, str(output_path))
    elif format == "ass":
        subtitle_formatter.to_ass(segments, str(output_path))
    elif format == "txt":
        subtitle_formatter.to_plain_text(segments, str(output_path))
    else:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {format}")

    if not output_path.exists():
        raise HTTPException(status_code=404, detail="文件生成失败")

    return FileResponse(
        path=str(output_path),
        filename=f"{task.video_name or task_id}_{lang or 'original'}.{format}",
        media_type="application/octet-stream"
    )


@app.post("/api/burn-subtitles/{task_id}")
async def burn_subtitles(task_id: str, font_size: int = 24):
    """
    将字幕烧录到视频中

    Args:
        task_id: 任务 ID
        font_size: 字体大小 (默认 24)

    Returns:
        带字幕的视频文件
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if not task.segments:
        raise HTTPException(status_code=400, detail="没有可用的字幕数据")

    try:
        # 查找原视频文件
        video_file = None
        for ext in settings.ALLOWED_EXTENSIONS:
            potential_path = settings.UPLOAD_DIR / f"{task_id}{ext}"
            if potential_path.exists():
                video_file = potential_path
                break

        if not video_file:
            raise HTTPException(status_code=404, detail="未找到原视频文件")

        # 优先使用双语字幕（如果已翻译）
        bilingual_segments = getattr(task, 'bilingual_segments', None)
        if bilingual_segments:
            # 使用双语字幕
            segments = [
                Segment(start=s["start"], end=s["end"], text=s["text"])
                for s in bilingual_segments
            ]
        else:
            # 使用原始字幕
            segments = [
                Segment(start=s["start"], end=s["end"], text=s["text"])
                for s in task.segments
            ]

        srt_path = settings.OUTPUT_DIR / f"{task_id}.srt"
        subtitle_formatter.to_srt(segments, str(srt_path))

        # 烧录字幕到视频
        output_video_path = settings.OUTPUT_DIR / f"{task_id}_subtitled{video_file.suffix}"
        result_path = await audio_extractor.burn_subtitles(
            str(video_file),
            str(srt_path),
            str(output_video_path),
            font_size=font_size
        )

        # 生成下载文件名（去掉原始扩展名）
        original_name = Path(task.video_name).stem if task.video_name else task_id
        download_filename = f"{original_name}_subtitled{video_file.suffix}"

        # 返回视频文件
        return FileResponse(
            path=result_path,
            filename=download_filename,
            media_type="video/mp4"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"字幕烧录失败: {str(e)}")


@app.get("/api/tasks")
async def list_tasks():
    """获取所有任务列表"""
    return {"tasks": list(tasks.values())}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务及其文件"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    # 删除相关文件
    for ext in settings.ALLOWED_EXTENSIONS:
        video_path = settings.UPLOAD_DIR / f"{task_id}{ext}"
        if video_path.exists():
            video_path.unlink()

    # 删除输出文件
    for output_file in settings.OUTPUT_DIR.glob(f"{task_id}*"):
        output_file.unlink()

    # 删除任务记录
    del tasks[task_id]

    return {"message": "任务已删除"}


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket 连接 - 实时接收任务状态更新

    Args:
        websocket: WebSocket 连接
        task_id: 任务 ID
    """
    await websocket.accept()

    # 添加到连接列表
    if task_id not in websocket_connections:
        websocket_connections[task_id] = []
    websocket_connections[task_id].append(websocket)

    try:
        # 发送当前状态
        if task_id in tasks:
            await websocket.send_json(tasks[task_id].dict())

        # 保持连接
        while True:
            data = await websocket.receive_text()
            # 客户端消息可以用于取消任务等操作
    except WebSocketDisconnect:
        # 移除连接
        if task_id in websocket_connections:
            websocket_connections[task_id].remove(websocket)


# ==================== 生命周期事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    print("=" * 50)
    print("视频字幕生成系统启动中...")
    print("=" * 50)

    # 检查 Ollama 服务
    ollama_health = await ollama_service.check_health()
    if ollama_health:
        print("[OK] Ollama 服务连接正常")
        models = await ollama_service.list_models()
        print(f"  可用模型: {', '.join(models)}")
    else:
        print("[WARN] Ollama 服务未启动（字幕优化/翻译功能不可用）")
        print("  请运行 'ollama serve' 启动服务")

    # Whisper 模型信息
    print(f"[OK] Whisper 模型: {settings.WHISPER_MODEL}")
    import torch
    if torch.cuda.is_available():
        print(f"[OK] GPU 可用: {torch.cuda.get_device_name(0)}")
    else:
        print("[WARN] GPU 不可用，将使用 CPU（速度较慢）")

    print("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    await ollama_service.close()
    print("服务已关闭")


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
