"""Whisper 语音识别服务"""

import os
import sys
import asyncio
import shutil
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import whisper
import torch


def setup_ffmpeg_path():
    """将 FFmpeg 路径添加到系统 PATH（Whisper 内部需要）"""
    # 1. 先检查是否已在 PATH 中
    if shutil.which("ffmpeg"):
        return

    # 2. 通过 Python 路径推断 conda 环境
    python_path = Path(sys.executable)
    conda_ffmpeg_dir = python_path.parent / "Library" / "bin"

    if (conda_ffmpeg_dir / "ffmpeg.exe").exists():
        os.environ["PATH"] = str(conda_ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")

# 初始化时设置 FFmpeg 路径
setup_ffmpeg_path()


@dataclass
class Segment:
    """字幕片段"""
    start: float      # 开始时间（秒）
    end: float        # 结束时间（秒）
    text: str         # 文本内容


# 项目根目录下的 models 文件夹
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models" / "whisper"


class WhisperService:
    """OpenAI Whisper 语音识别服务"""

    def __init__(
        self,
        model_name: str = "medium",
        device: Optional[str] = None,
        language: Optional[str] = None,
        model_dir: Optional[str] = None
    ):
        """
        初始化 Whisper 服务

        Args:
            model_name: 模型名称 (tiny/base/small/medium/large-v3)
            device: 计算设备 (cuda/cpu)，None 则自动选择
            language: 语言代码 (zh/en/ja 等)，None 则自动检测
            model_dir: 模型存储目录，None 则使用项目默认目录
        """
        self.model_name = model_name
        self.language = language
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR

        # 创建模型目录
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # 自动选择设备
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.model = None
        self._load_lock = asyncio.Lock()

    async def load_model(self) -> None:
        """加载 Whisper 模型（异步）"""
        async with self._load_lock:
            if self.model is not None:
                return

            # 在线程池中加载模型（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: whisper.load_model(
                    self.model_name,
                    device=self.device,
                    download_root=str(self.model_dir)
                )
            )

    async def transcribe(
        self,
        audio_path: str,
        progress_callback=None
    ) -> list[Segment]:
        """
        转录音频文件

        Args:
            audio_path: 音频文件路径
            progress_callback: 进度回调函数 (current, total)

        Returns:
            字幕片段列表
        """
        # 确保模型已加载
        if self.model is None:
            await self.load_model()

        # 在线程池中执行转录
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.model.transcribe(
                audio_path,
                language=self.language,
                task="transcribe",
                verbose=False
            )
        )

        # 解析结果
        segments = []
        for seg in result.get("segments", []):
            segments.append(
                Segment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"].strip()
                )
            )

        return segments

    async def detect_language(self, audio_path: str) -> str:
        """
        检测音频语言

        Args:
            audio_path: 音频文件路径

        Returns:
            检测到的语言代码
        """
        if self.model is None:
            await self.load_model()

        loop = asyncio.get_event_loop()

        # 加载音频并检测语言
        audio = await loop.run_in_executor(
            None,
            lambda: whisper.load_audio(audio_path)
        )

        # 使用模型检测语言
        audio_tensor = whisper.pad_or_trim(audio)
        mel = whisper.log_mel_spectrogram(audio_tensor).to(self.device)

        _, probs = self.model.detect_language(mel)
        detected_lang = max(probs, key=probs.get)

        return detected_lang

    def get_supported_languages(self) -> dict[str, str]:
        """获取支持的语言列表"""
        return {
            "zh": "中文",
            "en": "英语",
            "ja": "日语",
            "ko": "韩语",
            "fr": "法语",
            "de": "德语",
            "es": "西班牙语",
            "ru": "俄语",
            "ar": "阿拉伯语",
            "pt": "葡萄牙语",
            "it": "意大利语",
            "th": "泰语",
            "vi": "越南语",
            "id": "印尼语"
        }

    def get_model_info(self) -> dict:
        """获取模型信息"""
        return {
            "model": self.model_name,
            "device": self.device,
            "language": self.language,
            "loaded": self.model is not None,
            "gpu_available": torch.cuda.is_available(),
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        }
