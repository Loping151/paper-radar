"""Summary Agent for generating field progress summaries."""

from loguru import logger

from .base import BaseLLMClient
from models import PaperAnalysis


class SummaryAgent:
    """Stage 3: Agent for generating field progress summaries."""

    SUMMARY_PROMPT = """你是一位AI领域的资深研究顾问。请基于以下今日arXiv新论文的分析结果，撰写「{keyword}」领域的每日研究进展总结。

## 今日该领域相关论文分析:

{papers_analysis}

---

请撰写一份简洁有力的领域进展总结（使用{language}，300-500字）：

1. **今日概览**: 简述今日该领域发表的论文数量和整体趋势

2. **重点突破**: 最值得关注的1-2项研究及其意义（请使用论文编号引用，如"论文1"、"论文3"）

3. **技术趋势**: 观察到的技术方向或方法论趋势

4. **值得跟进**: 建议深入阅读的论文及原因（请使用论文编号引用）

请直接输出总结内容，使用 Markdown 格式，不需要 JSON。在引用论文时，请使用论文编号（如"论文1"、"论文2"），方便读者与下方论文列表对照。"""

    def __init__(self, llm_client: BaseLLMClient, language: str = "Chinese"):
        """
        Initialize the summary agent.

        Args:
            llm_client: LLM client (can reuse light or heavy)
            language: Output language
        """
        self.llm = llm_client
        self.language = language

    def _format_paper_analysis(self, analysis: PaperAnalysis) -> str:
        """Format a single paper analysis for the prompt."""
        authors_str = ", ".join(analysis.authors[:3])
        if len(analysis.authors) > 3:
            authors_str += " et al."

        affiliations_str = ", ".join(analysis.affiliations[:2]) if analysis.affiliations else "未提取"

        contributions_str = "\n".join(f"  - {c}" for c in analysis.contributions[:3])

        innovations_str = "; ".join(analysis.innovations[:2]) if analysis.innovations else "未提取"

        return f"""### {analysis.title}
- **arXiv ID**: {analysis.arxiv_id}
- **作者**: {authors_str}
- **机构**: {affiliations_str}
- **TLDR**: {analysis.tldr}
- **主要贡献**:
{contributions_str}
- **创新点**: {innovations_str}
- **方法**: {analysis.methodology[:200] if analysis.methodology else '未提取'}
"""

    def _format_papers_analysis(self, analyses: list[PaperAnalysis]) -> str:
        """Format multiple paper analyses for the prompt."""
        parts = []
        for i, analysis in enumerate(analyses, 1):
            if analysis.success:
                parts.append(f"## 论文 {i}\n{self._format_paper_analysis(analysis)}")
        return "\n".join(parts)

    def generate_summary(self, keyword: str, analyses: list[PaperAnalysis]) -> str:
        """
        Generate a summary for a specific keyword field.

        Args:
            keyword: The keyword/field name
            analyses: List of paper analyses for this keyword

        Returns:
            Summary text in Markdown format
        """
        # Filter to only successful analyses
        successful_analyses = [a for a in analyses if a.success]

        if not successful_analyses:
            return f"今日「{keyword}」领域暂无相关论文更新。"

        papers_analysis = self._format_papers_analysis(successful_analyses)

        prompt = self.SUMMARY_PROMPT.format(
            keyword=keyword,
            papers_analysis=papers_analysis,
            language=self.language,
        )

        try:
            summary = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=2000,
            )
            return summary
        except Exception as e:
            logger.error(f"Error generating summary for {keyword}: {e}")
            return f"生成「{keyword}」领域总结时发生错误: {str(e)}"

    def generate_all_summaries(
        self,
        analyses_by_keyword: dict[str, list[PaperAnalysis]],
    ) -> dict[str, str]:
        """
        Generate summaries for all keyword fields.

        Args:
            analyses_by_keyword: Dict mapping keyword names to paper analyses

        Returns:
            Dict mapping keyword names to summary texts
        """
        summaries = {}

        for keyword, analyses in analyses_by_keyword.items():
            logger.info(f"Generating summary for: {keyword} ({len(analyses)} papers)")
            summaries[keyword] = self.generate_summary(keyword, analyses)

        return summaries
