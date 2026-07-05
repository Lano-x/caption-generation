"""音频提取服务 - 从视频中提取音频"""

import os
import subprocess
import asyncio
from pathlib import Path
from typing import Optional


class AudioExtractor:
    """从视频文件中提取音频"""

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def extract_audio(
        self,
        video_path: str,
        output_format: str = "wav",
        sample_rate: int = 16000
    ) -> str:
        """
        从视频中提取音频

        Args:
            video_path: 视频文件路径
            output_format: 输出音频格式 (wav/mp3)
            sample_rate: 采样率 (Whisper 需要 16000)

        Returns:
            提取的音频文件路径
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 生成输出文件名
        audio_filename = f"{video_path.stem}.{output_format}"
        audio_path = self.output_dir / audio_filename

        # 构建 ffmpeg 命令
        cmd = [
            "ffmpeg",
            "-i", str(video_path),      # 输入文件
            "-vn",                        # 不包含视频
            "-acodec", "pcm_s16le" if output_format == "wav" else "libmp3lame",
            "-ar", str(sample_rate),      # 采样率
            "-ac", "1",                   # 单声道
            "-y",                         # 覆盖已存在文件
            str(audio_path)               # 输出文件
        ]

        # 执行 ffmpeg 命令
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                raise RuntimeError(f"ffmpeg 执行失败: {error_msg}")

            return str(audio_path)

        except FileNotFoundError:
            raise RuntimeError(
                "未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH"
            )

    async def get_video_duration(self, video_path: str) -> float:
        """
        获取视频时长（秒）

        Args:
            video_path: 视频文件路径

        Returns:
            视频时长（秒）
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise RuntimeError("无法获取视频时长")

            duration = float(stdout.decode('utf-8').strip())
            return duration

        except (ValueError, FileNotFoundError):
            raise RuntimeError(
                "未找到 ffprobe，请确保已安装 ffmpeg 并添加到系统 PATH"
            )

    def get_supported_formats(self) -> list[str]:
        """获取支持的视频格式列表"""
        return [
            ".mp4", ".avi", ".mkv", ".mov",
            ".wmv", ".flv", ".webm", ".m4v",
            ".mpg", ".mpeg", ".3gp", ".ts"
        ]

    def validate_video(self, video_path: str) -> bool:
        """
        验证视频文件是否有效

        Args:
            video_path: 视频文件路径

        Returns:
            是否为有效的视频文件
        """
        video_path = Path(video_path)

        # 检查文件是否存在
        if not video_path.exists():
            return False

        # 检查文件格式
        if video_path.suffix.lower() not in self.get_supported_formats():
            return False

        # 检查文件大小 (限制 2GB)
        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        if video_path.stat().st_size > max_size:
            return False

        return True
