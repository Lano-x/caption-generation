"""音频提取服务 - 从视频中提取音频"""

import os
import sys
import subprocess
import asyncio
import shutil
from pathlib import Path
from typing import Optional


def find_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件路径"""
    # 1. 先检查系统 PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    # 2. 检查 conda 环境路径（通过 Python 路径推断）
    python_path = Path(sys.executable)
    conda_bin = python_path.parent / "Library" / "bin" / "ffmpeg.exe"
    if conda_bin.exists():
        return str(conda_bin)

    # 3. 检查常见的 conda 路径
    possible_paths = [
        Path("F:/anaconda/envs/caption-gen/Library/bin/ffmpeg.exe"),
        Path("C:/anaconda/envs/caption-gen/Library/bin/ffmpeg.exe"),
        Path.home() / "anaconda3/envs/caption-gen/Library/bin/ffmpeg.exe",
        Path.home() / "miniconda3/envs/caption-gen/Library/bin/ffmpeg.exe",
    ]
    for path in possible_paths:
        if path.exists():
            return str(path)

    # 4. 返回默认名称（让系统尝试查找）
    return "ffmpeg"


def find_ffprobe() -> str:
    """查找 ffprobe 可执行文件路径"""
    # 1. 先检查系统 PATH
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path:
        return ffprobe_path

    # 2. 检查 conda 环境路径（通过 Python 路径推断）
    python_path = Path(sys.executable)
    conda_bin = python_path.parent / "Library" / "bin" / "ffprobe.exe"
    if conda_bin.exists():
        return str(conda_bin)

    # 3. 检查常见的 conda 路径
    possible_paths = [
        Path("F:/anaconda/envs/caption-gen/Library/bin/ffprobe.exe"),
        Path("C:/anaconda/envs/caption-gen/Library/bin/ffprobe.exe"),
        Path.home() / "anaconda3/envs/caption-gen/Library/bin/ffprobe.exe",
        Path.home() / "miniconda3/envs/caption-gen/Library/bin/ffprobe.exe",
    ]
    for path in possible_paths:
        if path.exists():
            return str(path)

    # 4. 返回默认名称
    return "ffprobe"


class AudioExtractor:
    """从视频文件中提取音频"""

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_path = find_ffmpeg()
        self.ffprobe_path = find_ffprobe()

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
            self.ffmpeg_path,
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
            self.ffprobe_path,
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

    async def burn_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str = None,
        font_size: int = 24,
        font_color: str = "white",
        outline_color: str = "black",
        outline_width: int = 2
    ) -> str:
        """
        将字幕烧录到视频中

        Args:
            video_path: 原视频路径
            subtitle_path: 字幕文件路径 (SRT格式)
            output_path: 输出视频路径，None 则自动生成
            font_size: 字体大小
            font_color: 字体颜色
            outline_color: 描边颜色
            outline_width: 描边宽度

        Returns:
            输出视频路径
        """
        video_path = Path(video_path)
        subtitle_path = Path(subtitle_path)

        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        if not subtitle_path.exists():
            raise FileNotFoundError(f"字幕文件不存在: {subtitle_path}")

        # 生成输出文件名
        if output_path is None:
            output_path = self.output_dir / f"{video_path.stem}_subtitled{video_path.suffix}"
        else:
            output_path = Path(output_path)

        # 转换路径为正斜杠（FFmpeg 在 Windows 上需要）
        subtitle_path_str = str(subtitle_path).replace("\\", "/").replace(":", "\\\\:")

        # 构建 FFmpeg 字幕滤镜
        # 使用 subtitles 滤镜烧录字幕
        subtitle_filter = (
            f"subtitles='{subtitle_path_str}'"
            f":force_style='FontSize={font_size},"
            f"PrimaryColour=&H00FFFFFF,"  # 白色
            f"OutlineColour=&H00000000,"  # 黑色描边
            f"Outline={outline_width},"
            f"Shadow=1,"
            f"MarginV=30'"  # 底部边距
        )

        # 构建 FFmpeg 命令
        cmd = [
            self.ffmpeg_path,
            "-i", str(video_path),           # 输入视频
            "-vf", subtitle_filter,           # 字幕滤镜
            "-c:v", "libx264",               # 视频编码
            "-preset", "medium",              # 编码预设
            "-crf", "23",                     # 质量
            "-c:a", "copy",                   # 音频直接复制
            "-y",                             # 覆盖已存在文件
            str(output_path)                  # 输出文件
        ]

        # 执行 FFmpeg 命令
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                raise RuntimeError(f"字幕烧录失败: {error_msg}")

            return str(output_path)

        except FileNotFoundError:
            raise RuntimeError(
                "未找到 ffmpeg，请确保已安装 ffmpeg 并添加到系统 PATH"
            )
