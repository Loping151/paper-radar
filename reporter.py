"""Report generation module.

Generates Markdown and JSON outputs for the PaperRadar web UI.
"""

import json
from pathlib import Path
from typing import Optional

from loguru import logger

from models import DailyReport, PaperAnalysis


class Reporter:
    """Generates daily reports (Markdown + JSON)."""

    def __init__(self, config: dict):
        self.config = config
        self.output_config = config.get("output", {})
        self.language = self.output_config.get("language", "Chinese")

    def generate_markdown(self, report: DailyReport) -> str:
        """Generate Markdown report."""
        lines = [
            "# 📚 论文每日速递",
            "",
            f"**日期**: {report.date} | **今日新论文**: {report.total_papers} 篇 | "
            f"**匹配论文**: {report.matched_papers} 篇 | **深度分析**: {report.analyzed_papers} 篇",
            "",
            "---",
            "",
        ]

        for keyword in report.keywords:
            analyses = report.analyses_by_keyword.get(keyword, [])
            summary = report.summaries.get(keyword, "")
            successful_analyses = [a for a in analyses if a.success]

            lines.append(f"## 🔖 {keyword} ({len(successful_analyses)} 篇)")
            lines.append("")

            if summary:
                lines.append("### 📈 领域进展总结")
                lines.append("")
                lines.append(f"> {summary}")
                lines.append("")

            if successful_analyses:
                lines.append("### 📄 论文详情")
                lines.append("")

                for i, analysis in enumerate(successful_analyses, 1):
                    is_journal = False
                    journal_name = ""
                    if analysis.paper and analysis.paper.source == "journal":
                        is_journal = True
                        journal_name = analysis.paper.primary_category
                    elif ":" in analysis.arxiv_id:
                        is_journal = True
                        journal_name = (
                            analysis.arxiv_id.split(":")[0].replace("_", " ").title()
                        )

                    if is_journal:
                        lines.append(f"#### {i}. [{analysis.title}]({analysis.pdf_url})")
                    else:
                        lines.append(
                            f"#### {i}. [{analysis.title}](https://arxiv.org/abs/{analysis.arxiv_id})"
                        )
                    lines.append("")
                    lines.append("| 项目 | 内容 |")
                    lines.append("|------|------|")

                    authors_str = ", ".join(analysis.authors[:3])
                    if len(analysis.authors) > 3:
                        authors_str += " et al."
                    lines.append(f"| **作者** | {authors_str} |")

                    if analysis.affiliations:
                        affiliations_str = ", ".join(analysis.affiliations[:2])
                        lines.append(f"| **机构** | {affiliations_str} |")

                    if is_journal:
                        lines.append(f"| **来源** | 🔵 **{journal_name}** |")
                    else:
                        lines.append(f"| **来源** | 🔴 **arXiv** ({analysis.arxiv_id}) |")

                    if analysis.tldr:
                        lines.append(f"| **TLDR** | {analysis.tldr} |")

                    lines.append("")

                    if analysis.contributions:
                        lines.append("**主要贡献:**")
                        for contrib in analysis.contributions[:3]:
                            lines.append(f"- {contrib}")
                        lines.append("")

                    if analysis.innovations:
                        innovations_str = "; ".join(analysis.innovations[:2])
                        lines.append(f"**创新点:** {innovations_str}")
                        lines.append("")

                    if analysis.dataset_info and analysis.dataset_info != "未明确说明":
                        lines.append(f"**📊 数据集:** {analysis.dataset_info}")
                        lines.append("")

                    links = []
                    if is_journal:
                        links.append(f"[📄 原文]({analysis.pdf_url})")
                    else:
                        links.append(f"[📄 PDF]({analysis.pdf_url})")
                        links.append(
                            f"[📋 Abstract](https://arxiv.org/abs/{analysis.arxiv_id})"
                        )

                    if analysis.code_url:
                        links.append(f"[💻 Code]({analysis.code_url})")

                    lines.append(f"**链接:** {' | '.join(links)}")
                    lines.append("")
            else:
                lines.append("*今日该领域暂无相关论文*")
                lines.append("")

            lines.append("---")
            lines.append("")

        lines.append("")
        lines.append("---")
        lines.append("*本报告由 PaperRadar 自动生成 (支持 arXiv + 学术期刊)*")

        return "\n".join(lines)

    def save_markdown(self, report: DailyReport, output_dir: Optional[str] = None) -> Path:
        """Save Markdown report to disk."""
        if output_dir is None:
            output_dir = (
                self.output_config.get("formats", {})
                .get("markdown", {})
                .get("path", "./reports/")
            )

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = f"paper-radar-{report.date}.md"
        file_path = output_path / filename

        markdown = self.generate_markdown(report)
        file_path.write_text(markdown, encoding="utf-8")

        logger.info(f"Markdown report saved to: {file_path}")
        return file_path

    def _analysis_to_dict(self, analysis: PaperAnalysis) -> dict:
        paper = analysis.paper
        paper_source = (
            paper.source if paper else ("journal" if ":" in analysis.arxiv_id else "arxiv")
        )
        pdf_url = analysis.pdf_url or (paper.pdf_url if paper else "")

        if paper:
            abstract_url = paper.abstract_url
            published = paper.published.isoformat() if paper.published else ""
            updated = paper.updated.isoformat() if paper.updated else ""
            categories = paper.categories
            primary_category = paper.primary_category
            summary = paper.summary
        else:
            abstract_url = (
                pdf_url
                if paper_source == "journal"
                else f"https://arxiv.org/abs/{analysis.arxiv_id}"
            )
            published = ""
            updated = ""
            categories = []
            primary_category = ""
            summary = ""

        return {
            "id": analysis.arxiv_id,
            "title": analysis.title or (paper.title if paper else ""),
            "authors": analysis.authors or (paper.authors if paper else []),
            "affiliations": analysis.affiliations,
            "summary": summary,
            "tldr": analysis.tldr,
            "contributions": analysis.contributions,
            "methodology": analysis.methodology,
            "experiments": analysis.experiments,
            "innovations": analysis.innovations,
            "limitations": analysis.limitations,
            "code_url": analysis.code_url,
            "dataset_info": analysis.dataset_info,
            "quality_score": analysis.quality_score,
            "score_reason": analysis.score_reason,
            "matched_keywords": analysis.matched_keywords,
            "pdf_url": pdf_url,
            "abstract_url": abstract_url,
            "source": paper_source,
            "primary_category": primary_category,
            "categories": categories,
            "published": published,
            "updated": updated,
        }

    def save_json(self, report: DailyReport, output_dir: Optional[str] = None) -> Path:
        """Save report as JSON for the web frontend."""
        if output_dir is None:
            output_dir = (
                self.output_config.get("formats", {})
                .get("json", {})
                .get("path", "./reports/json/")
            )

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = f"paper-radar-{report.date}.json"
        file_path = output_path / filename

        papers_by_keyword: dict[str, list[dict]] = {}
        for keyword, analyses in report.analyses_by_keyword.items():
            numbered_papers = []
            paper_number = 0
            for analysis in analyses:
                if not analysis.success:
                    continue
                paper_number += 1
                paper_dict = self._analysis_to_dict(analysis)
                paper_dict["paper_number"] = paper_number
                numbered_papers.append(paper_dict)
            papers_by_keyword[keyword] = numbered_papers

        payload = {
            "date": report.date,
            "total_papers": report.total_papers,
            "matched_papers": report.matched_papers,
            "analyzed_papers": report.analyzed_papers,
            "summaries": report.summaries,
            "keywords": report.keywords,
            "papers_by_keyword": papers_by_keyword,
        }

        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logger.info(f"JSON report saved to: {file_path}")
        return file_path

    def generate_and_send(self, report: DailyReport) -> dict:
        """Generate report through all configured output formats (no email)."""
        results = {}
        formats = self.output_config.get("formats", {})

        markdown_config = formats.get("markdown", {})
        if markdown_config.get("enabled", True):
            try:
                path = self.save_markdown(report)
                results["markdown"] = {"success": True, "path": str(path)}
            except Exception as e:
                logger.error(f"Failed to save markdown: {e}")
                results["markdown"] = {"success": False, "error": str(e)}

        json_config = formats.get("json", {})
        if json_config.get("enabled", True):
            try:
                path = self.save_json(report)
                results["json"] = {"success": True, "path": str(path)}
            except Exception as e:
                logger.error(f"Failed to save JSON: {e}")
                results["json"] = {"success": False, "error": str(e)}

        return results

