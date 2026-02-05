"""Filter Agent for paper keyword matching using lightweight LLM."""

import json
import re
from typing import Optional
from loguru import logger

from .base import BaseLLMClient
from models import Paper, FilterResult


class FilterAgent:
    """Stage 1: Lightweight LLM agent for filtering papers by keywords."""

    SYSTEM_PROMPT = """你是一个学术论文分类专家。你的任务是判断一篇论文是否与给定的研究关键词相关。

请仔细分析论文的标题和摘要，判断它是否与以下任一关键词领域**高度相关**：

{keywords_description}

请以 JSON 格式返回结果，不要包含任何其他内容：
{{
    "matched": true或false,
    "matched_keywords": ["关键词1", "关键词2"],
    "relevance": "high"或"medium"或"low",
    "reason": "简短说明匹配原因（一句话）"
}}

判断标准：
- 只有当论文主题与关键词**高度相关**时才返回 matched: true
- 仅仅提到相关概念但主题不符的论文应返回 matched: false
- relevance 为 high 表示论文核心主题就是该关键词领域
- relevance 为 medium 表示论文与该关键词领域有较强关联
- relevance 为 low 表示关联较弱，此时应返回 matched: false
- 可以匹配多个关键词，如果论文涉及多个领域"""

    USER_PROMPT = """请分析以下论文是否与给定的关键词相关：

标题: {title}

摘要: {abstract}

请判断这篇论文是否与给定的关键词高度相关，并以 JSON 格式返回结果。"""

    def __init__(self, llm_client: BaseLLMClient, keywords: list[dict]):
        """
        Initialize the filter agent.

        Args:
            llm_client: Lightweight LLM client
            keywords: List of keyword configurations
        """
        self.llm = llm_client
        self.keywords = keywords
        self.keywords_description = self._format_keywords()

    def _format_keywords(self) -> str:
        """Format keywords into description text."""
        lines = []
        for kw in self.keywords:
            lines.append(f"【{kw['name']}】")
            lines.append(f"  描述: {kw['description']}")
            if kw.get("examples"):
                examples = "; ".join(kw["examples"])
                lines.append(f"  示例: {examples}")
            lines.append("")
        return "\n".join(lines)

    def _parse_response(self, response: str) -> Optional[dict]:
        """Parse LLM response to extract JSON."""
        # Try to find JSON in the response
        try:
            # First try direct JSON parsing
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in text
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def filter_paper(self, paper: Paper) -> FilterResult:
        """
        Filter a single paper to determine keyword match.

        Args:
            paper: Paper to filter

        Returns:
            FilterResult with match information
        """
        system_prompt = self.SYSTEM_PROMPT.format(
            keywords_description=self.keywords_description
        )

        user_prompt = self.USER_PROMPT.format(
            title=paper.title,
            abstract=paper.summary,
        )

        try:
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )

            result = self._parse_response(response)

            if result is None:
                logger.warning(f"Failed to parse response for {paper.arxiv_id}: {response[:200]}")
                return FilterResult(
                    paper=paper,
                    matched=False,
                    reason="Failed to parse LLM response",
                )

            matched = result.get("matched", False)
            relevance = result.get("relevance", "low")

            # Only consider matched if relevance is high or medium
            if matched and relevance == "low":
                matched = False

            return FilterResult(
                paper=paper,
                matched=matched,
                matched_keywords=result.get("matched_keywords", []),
                relevance=relevance,
                reason=result.get("reason", ""),
            )

        except Exception as e:
            logger.error(f"Error filtering paper {paper.arxiv_id}: {e}")
            return FilterResult(
                paper=paper,
                matched=False,
                reason=f"Error: {str(e)}",
            )

    def filter_papers(self, papers: list[Paper]) -> list[FilterResult]:
        """
        Filter multiple papers.

        Args:
            papers: List of papers to filter

        Returns:
            List of FilterResult for matched papers only
        """
        results = []
        total = len(papers)

        for i, paper in enumerate(papers, 1):
            logger.info(f"[{i}/{total}] Filtering: {paper.title[:60]}...")

            result = self.filter_paper(paper)

            if result.matched:
                results.append(result)
                logger.info(f"  ✓ Matched: {result.matched_keywords} ({result.relevance})")
            else:
                logger.debug(f"  ✗ Not matched")

        logger.info(f"Filtering complete: {len(results)}/{total} papers matched")
        return results
