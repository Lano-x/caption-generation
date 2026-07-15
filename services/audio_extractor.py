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

        # 执行 ffmpeg 命令（使用同步方式避免 Windows asyncio 问题）
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    check=False
                )
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
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
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    check=False
                )
            )

            if result.returncode != 0:
                raise RuntimeError("无法获取视频时长")

            duration = float(result.stdout.decode('utf-8').strip())
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
        将字幕烧录到视频中（使用 moviepy）

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
        from moviepy import VideoFileClip, TextClip, CompositeVideoClip

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

        # 读取 SRT 文件并解析字幕
        segments = self._parse_srt(subtitle_path)

        if not segments:
            raise ValueError("字幕文件为空或格式错误")

        # 在线程池中执行（避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        output_path_result, elapsed_time = await loop.run_in_executor(
            None,
            lambda: self._burn_subtitles_sync(
                str(video_path),
                segments,
                str(output_path),
                font_size,
                font_color
            )
        )

        return output_path_result, elapsed_time

    def _burn_subtitles_sync(
        self,
        video_path: str,
        segments: list,
        output_path: str,
        font_size: int = 24,
        font_color: str = "white"
    ) -> tuple[str, float]:
        """同步执行字幕烧录

        Returns:
            tuple: (输出路径, 烧录耗时秒数)
        """
        from moviepy import VideoFileClip, TextClip, CompositeVideoClip
        import os
        import time

        # 查找可用字体
        font_path = None
        possible_fonts = [
            "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",     # 黑体
            "C:/Windows/Fonts/simsun.ttc",     # 宋体
            "C:/Windows/Fonts/arial.ttf",      # Arial
        ]
        for f in possible_fonts:
            if os.path.exists(f):
                font_path = f
                break

        # 记录开始时间
        start_time = time.time()

        # 加载视频
        video = VideoFileClip(video_path)

        # 创建字幕片段
        text_clips = []
        for i, seg in enumerate(segments):
            # 处理多行文本（双语字幕）
            lines = seg.text.split('\n')

            # 调试：打印前3条字幕
            if i < 3:
                print(f"[DEBUG] 字幕 {i}: text={repr(seg.text)}, lines={lines}, len={len(lines)}")

            if len(lines) > 1:
                # 双语字幕：中文在上，英文在下
                # 创建中文行
                txt_kwargs_cn = {
                    "text": lines[0],
                    "font_size": font_size,
                    "color": font_color,
                    "stroke_color": "black",
                    "stroke_width": 2
                }
                if font_path:
                    txt_kwargs_cn["font"] = font_path

                txt_clip_cn = (
                    TextClip(**txt_kwargs_cn)
                    .with_position(("center", "bottom"))
                    .with_start(seg.start)
                    .with_duration(seg.end - seg.start)
                )

                # 创建英文行
                txt_kwargs_en = {
                    "text": lines[1],
                    "font_size": int(font_size * 0.8),
                    "color": "#FFFF88",  # 浅黄色区分
                    "stroke_color": "black",
                    "stroke_width": 1
                }
                if font_path:
                    txt_kwargs_en["font"] = font_path

                txt_clip_en = (
                    TextClip(**txt_kwargs_en)
                    .with_position(("center", "bottom"))
                    .with_start(seg.start)
                    .with_duration(seg.end - seg.start)
                )

                # 调整位置：中文在上，英文在下
                # 中文在上（距离底部200像素），英文在下（距离底部100像素）
                txt_clip_cn = txt_clip_cn.with_position(lambda t: ("center", video.h - 200))
                txt_clip_en = txt_clip_en.with_position(lambda t: ("center", video.h - 100))

                text_clips.append(txt_clip_cn)
                text_clips.append(txt_clip_en)
            else:
                # 单行字幕
                txt_kwargs = {
                    "text": seg.text,
                    "font_size": font_size,
                    "color": font_color,
                    "stroke_color": "black",
                    "stroke_width": 2
                }
                if font_path:
                    txt_kwargs["font"] = font_path

                txt_clip = (
                    TextClip(**txt_kwargs)
                    .with_position(("center", "bottom"))
                    .with_start(seg.start)
                    .with_duration(seg.end - seg.start)
                )
                text_clips.append(txt_clip)

        # 合成视频
        final = CompositeVideoClip([video] + text_clips)

        # 输出视频（使用 GPU 加速）
        try:
            # 尝试使用 NVENC GPU 加速
            final.write_videofile(
                output_path,
                codec="h264_nvenc",
                audio_codec="aac",
                preset="fast",
                logger=None
            )
        except Exception:
            # 如果 NVENC 失败，回退到 CPU 编码
            final.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",  # 使用最快的预设
                logger=None
            )

        # 清理资源
        video.close()
        final.close()

        # 计算耗时
        elapsed_time = time.time() - start_time

        return output_path, elapsed_time

    def _parse_srt(self, srt_path: Path) -> list:
        """解析 SRT 文件"""
        from utils.subtitle_formatter import SubtitleFormatter
        from services.whisper_service import Segment

        segments = []
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 简单的 SRT 解析
            blocks = content.strip().split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    # 解析时间
                    time_line = lines[1]
                    start_str, end_str = time_line.split(' --> ')

                    # 转换时间为秒
                    start = self._srt_time_to_seconds(start_str.strip())
                    end = self._srt_time_to_seconds(end_str.strip())

                    # 获取文本
                    text = ' '.join(lines[2:])

                    segments.append(Segment(start=start, end=end, text=text))
        except Exception as e:
            raise ValueError(f"解析 SRT 文件失败: {str(e)}")

        return segments

    def _srt_time_to_seconds(self, time_str: str) -> float:
        """将 SRT 时间格式转换为秒"""
        # 格式：HH:MM:SS,mmm
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    def _seconds_to_ffmpeg_time(self, seconds: float) -> str:
        """将秒转换为 FFmpeg 时间格式（使用秒数）"""
        return f"{seconds:.3f}"
