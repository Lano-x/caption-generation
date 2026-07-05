"""字幕格式化工具 - 支持 SRT/ASS/VTT 格式"""

from datetime import timedelta
from pathlib import Path
from typing import TextIO

from services.whisper_service import Segment


class SubtitleFormatter:
    """字幕格式化器"""

    @staticmethod
    def format_srt_time(seconds: float) -> str:
        """
        格式化 SRT 时间格式

        Args:
            seconds: 秒数

        Returns:
            HH:MM:SS,mmm 格式的时间字符串
        """
        td = timedelta(seconds=seconds)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        secs = int(td.total_seconds() % 60)
        millis = int((td.total_seconds() % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def format_vtt_time(seconds: float) -> str:
        """
        格式化 VTT 时间格式

        Args:
            seconds: 秒数

        Returns:
            HH:MM:SS.mmm 格式的时间字符串
        """
        td = timedelta(seconds=seconds)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        secs = int(td.total_seconds() % 60)
        millis = int((td.total_seconds() % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    @staticmethod
    def format_ass_time(seconds: float) -> str:
        """
        格式化 ASS 时间格式

        Args:
            seconds: 秒数

        Returns:
            H:MM:SS.cc 格式的时间字符串
        """
        td = timedelta(seconds=seconds)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        secs = int(td.total_seconds() % 60)
        centis = int((td.total_seconds() % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

    def to_srt(self, segments: list[Segment], output_path: str) -> str:
        """
        导出为 SRT 格式

        Args:
            segments: 字幕片段列表
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        output_path = Path(output_path)

        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, start=1):
                f.write(f"{i}\n")
                f.write(
                    f"{self.format_srt_time(seg.start)} --> "
                    f"{self.format_srt_time(seg.end)}\n"
                )
                f.write(f"{seg.text}\n\n")

        return str(output_path)

    def to_vtt(self, segments: list[Segment], output_path: str) -> str:
        """
        导出为 VTT 格式

        Args:
            segments: 字幕片段列表
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        output_path = Path(output_path)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")

            for i, seg in enumerate(segments, start=1):
                f.write(f"{i}\n")
                f.write(
                    f"{self.format_vtt_time(seg.start)} --> "
                    f"{self.format_vtt_time(seg.end)}\n"
                )
                f.write(f"{seg.text}\n\n")

        return str(output_path)

    def to_ass(
        self,
        segments: list[Segment],
        output_path: str,
        font_name: str = "Arial",
        font_size: int = 48
    ) -> str:
        """
        导出为 ASS 格式

        Args:
            segments: 字幕片段列表
            output_path: 输出文件路径
            font_name: 字体名称
            font_size: 字体大小

        Returns:
            输出文件路径
        """
        output_path = Path(output_path)

        # ASS 文件头
        header = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header)

            for seg in segments:
                start_time = self.format_ass_time(seg.start)
                end_time = self.format_ass_time(seg.end)
                f.write(
                    f"Dialogue: 0,{start_time},{end_time},"
                    f"Default,,0,0,0,,{seg.text}\n"
                )

        return str(output_path)

    def to_plain_text(self, segments: list[Segment], output_path: str) -> str:
        """
        导出为纯文本格式

        Args:
            segments: 字幕片段列表
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        output_path = Path(output_path)

        with open(output_path, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"[{self.format_srt_time(seg.start)}] {seg.text}\n")

        return str(output_path)

    def get_supported_formats(self) -> dict[str, str]:
        """获取支持的格式"""
        return {
            "srt": "SubRip 字幕格式 (最常用)",
            "vtt": "WebVTT 字幕格式 (网页用)",
            "ass": "ASS/SSA 字幕格式 (高级样式)",
            "txt": "纯文本格式 (仅文字)"
        }
