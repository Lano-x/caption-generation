"""Ollama AI 服务 - 字幕优化和翻译"""

import json
from typing import AsyncGenerator, Optional

import httpx

from .whisper_service import Segment


class OllamaService:
    """Ollama API 服务"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5",
        timeout: float = 120.0
    ):
        """
        初始化 Ollama 服务

        Args:
            base_url: Ollama API 地址
            model: 使用的模型名称
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def check_health(self) -> bool:
        """
        检查 Ollama 服务是否可用

        Returns:
            服务是否正常
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """
        获取可用模型列表

        Returns:
            模型名称列表
        """
        client = await self._get_client()
        response = await client.get("/api/tags")

        if response.status_code != 200:
            raise RuntimeError("无法获取模型列表")

        data = response.json()
        return [model["name"] for model in data.get("models", [])]

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None
    ) -> str:
        """
        生成文本

        Args:
            prompt: 用户提示
            system: 系统提示

        Returns:
            生成的文本
        """
        client = await self._get_client()

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        if system:
            payload["system"] = system

        response = await client.post("/api/generate", json=payload)

        if response.status_code != 200:
            raise RuntimeError(f"Ollama API 错误: {response.text}")

        return response.json()["response"]

    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文本

        Args:
            prompt: 用户提示
            system: 系统提示

        Yields:
            生成的文本片段
        """
        client = await self._get_client()

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True
        }

        if system:
            payload["system"] = system

        async with client.stream(
            "POST",
            "/api/generate",
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]
                    except json.JSONDecodeError:
                        continue

    async def optimize_subtitles(
        self,
        segments: list[Segment],
        source_lang: str = "zh"
    ) -> list[Segment]:
        """
        优化字幕文本（纠错、断句）

        Args:
            segments: 原始字幕片段
            source_lang: 源语言

        Returns:
            优化后的字幕片段
        """
        system_prompt = f"""你是一个专业的字幕编辑专家。你的任务是优化语音识别生成的字幕文本。

优化规则：
1. 修正错别字和语法错误
2. 保持原意不变
3. 适当断句，使字幕更易读
4. 保持时间戳不变
5. 源语言: {source_lang}

请直接返回优化后的文本，每行对应原始字幕的一个片段，不要添加任何解释。"""

        # 构建输入文本
        input_text = "\n".join([
            f"[{i+1}] {seg.text}"
            for i, seg in enumerate(segments)
        ])

        prompt = f"请优化以下字幕文本：\n\n{input_text}"

        # 调用 Ollama
        result = await self.generate(prompt, system=system_prompt)

        # 解析结果
        optimized_lines = [
            line.strip()
            for line in result.strip().split("\n")
            if line.strip()
        ]

        # 创建优化后的片段
        optimized_segments = []
        for i, seg in enumerate(segments):
            if i < len(optimized_lines):
                # 提取文本（去掉可能的编号）
                text = optimized_lines[i]
                if "]" in text:
                    text = text.split("]", 1)[1].strip()
                optimized_segments.append(
                    Segment(start=seg.start, end=seg.end, text=text)
                )
            else:
                optimized_segments.append(seg)

        return optimized_segments

    async def translate_subtitles(
        self,
        segments: list[Segment],
        source_lang: str = "zh",
        target_lang: str = "en"
    ) -> list[Segment]:
        """
        翻译字幕（分批处理，避免超时）

        Args:
            segments: 原始字幕片段
            source_lang: 源语言代码
            target_lang: 目标语言代码

        Returns:
            翻译后的字幕片段
        """
        lang_names = {
            "zh": "中文",
            "en": "英语",
            "ja": "日语",
            "ko": "韩语",
            "fr": "法语",
            "de": "德语",
            "es": "西班牙语",
            "ru": "俄语"
        }

        src_name = lang_names.get(source_lang, source_lang)
        tgt_name = lang_names.get(target_lang, target_lang)

        system_prompt = f"""你是一个专业的字幕翻译专家。你的任务是将字幕从{src_name}翻译成{tgt_name}。

翻译规则：
1. 准确传达原意
2. 符合目标语言的表达习惯
3. 保持字幕简洁易读
4. 保持时间戳不变
5. 保留原始的编号格式

请直接返回翻译后的文本，每行对应原始字幕的一个片段，不要添加任何解释。"""

        # 分批翻译（每批 20 条）
        batch_size = 20
        translated_segments = []

        for batch_start in range(0, len(segments), batch_size):
            batch_end = min(batch_start + batch_size, len(segments))
            batch_segments = segments[batch_start:batch_end]

            # 构建输入文本
            input_text = "\n".join([
                f"[{i+1}] {seg.text}"
                for i, seg in enumerate(batch_segments)
            ])

            prompt = f"请翻译以下字幕：\n\n{input_text}"

            # 调用 Ollama
            result = await self.generate(prompt, system=system_prompt)

            # 解析结果
            translated_lines = [
                line.strip()
                for line in result.strip().split("\n")
                if line.strip()
            ]

            # 创建翻译后的片段
            for i, seg in enumerate(batch_segments):
                if i < len(translated_lines):
                    text = translated_lines[i]
                    # 去掉可能的编号（如 "1." 或 "[1]"）
                    import re
                    text = re.sub(r'^\d+[\.\)]\s*', '', text)  # 去掉 "1. " 或 "1) "
                    if "]" in text:
                        text = text.split("]", 1)[1].strip()
                    translated_segments.append(
                        Segment(start=seg.start, end=seg.end, text=text)
                    )
                else:
                    translated_segments.append(seg)

        return translated_segments

    def get_model_info(self) -> dict:
        """获取模型信息"""
        return {
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout
        }
