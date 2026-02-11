"""Report generation module.

Generates Markdown and JSON outputs for the PaperRadar web UI.
"""

import json
from pathlib import Path
from typing import Optional

import httpx
import markdown
from loguru import logger

from models import DailyReport, PaperAnalysis


class Reporter:
    """Generates daily reports (Markdown + JSON)."""

    def __init__(self, config: dict):
        self.config = config
        self.output_config = config.get("output", {})
        self.language = self.output_config.get("language", "Chinese")

    @staticmethod
    def _is_preprint_source(source: str, primary_category: str, paper_id: str) -> bool:
        """Detect whether a paper belongs to bioRxiv/medRxiv preprint sources."""
        source_norm = str(source or "").strip().lower()
        category_norm = str(primary_category or "").strip().lower()
        paper_id_norm = str(paper_id or "").strip().lower()
        if source_norm in {"preprint", "arxiv"}:
            return True
        if "biorxiv" in category_norm or "medrxiv" in category_norm:
            return True
        return paper_id_norm.startswith("biorxiv:") or paper_id_norm.startswith("medrxiv:")

    @staticmethod
    def _is_arxiv_preprint_id(paper_id: str) -> bool:
        """Infer whether an ID is a native arXiv identifier."""
        return ":" not in str(paper_id or "")

    def _resolve_source_type(self, source: str, primary_category: str, paper_id: str) -> str:
        """Normalize source type to one of: preprint / journal."""
        source_norm = str(source or "").strip().lower()
        paper_id_norm = str(paper_id or "").strip().lower()
        if source_norm == "journal":
            if self._is_preprint_source(source_norm, primary_category, paper_id_norm):
                return "preprint"
            return "journal"
        if self._is_preprint_source(source_norm, primary_category, paper_id_norm):
            return "preprint"
        if source_norm and source_norm != "journal":
            return "journal"
        if ":" in paper_id_norm:
            return "journal"
        return "preprint"

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
                    source_value = analysis.paper.source if analysis.paper else ""
                    source_name = analysis.paper.primary_category if analysis.paper else ""
                    source_type = self._resolve_source_type(
                        source=source_value,
                        primary_category=source_name,
                        paper_id=analysis.arxiv_id,
                    )
                    is_arxiv_preprint = (
                        source_type == "preprint"
                        and self._is_arxiv_preprint_id(analysis.arxiv_id)
                    )
                    if not source_name and ":" in analysis.arxiv_id:
                        source_name = analysis.arxiv_id.split(":")[0].replace("_", " ").title()

                    if source_type == "preprint" and is_arxiv_preprint:
                        lines.append(
                            f"#### {i}. [{analysis.title}](https://arxiv.org/abs/{analysis.arxiv_id})"
                        )
                    else:
                        lines.append(f"#### {i}. [{analysis.title}]({analysis.pdf_url})")
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

                    if source_type == "journal":
                        lines.append(f"| **来源** | 🔵 **{source_name or 'Journal'}** |")
                    elif source_type == "preprint":
                        if is_arxiv_preprint:
                            lines.append(f"| **来源** | 🟣 **Preprint (arXiv)** ({analysis.arxiv_id}) |")
                        else:
                            lines.append(f"| **来源** | 🟣 **{source_name or 'Preprint'}** |")

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
                    if source_type == "journal":
                        links.append(f"[📄 原文]({analysis.pdf_url})")
                    elif source_type == "preprint" and not is_arxiv_preprint:
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
        lines.append("*本报告由 PaperRadar 自动生成 (支持预印本 + 学术期刊)*")

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
        source_value = paper.source if paper else ""
        primary_category_value = paper.primary_category if paper else ""
        paper_source = self._resolve_source_type(
            source=source_value,
            primary_category=primary_category_value,
            paper_id=analysis.arxiv_id,
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
            is_arxiv_preprint = (
                paper_source == "preprint"
                and self._is_arxiv_preprint_id(analysis.arxiv_id)
            )
            abstract_url = (
                pdf_url
                if paper_source == "journal" or (paper_source == "preprint" and not is_arxiv_preprint)
                else f"https://arxiv.org/abs/{analysis.arxiv_id}"
            )
            published = ""
            updated = ""
            categories = []
            primary_category = ""
            if ":" in analysis.arxiv_id:
                primary_category = analysis.arxiv_id.split(":")[0].replace("_", " ").title()
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

    @staticmethod
    def _markdown_to_html(md_content: str) -> str:
        """Convert markdown report to styled HTML email."""
        body_html = markdown.markdown(
            md_content,
            extensions=["tables", "fenced_code"],
        )
        return f"""\
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  max-width:800px;margin:0 auto;padding:20px;color:#333;line-height:1.6;">
<style>
  h1 {{font-size:24px;border-bottom:2px solid #2563eb;padding-bottom:8px;}}
  h2 {{font-size:20px;color:#1e40af;margin-top:28px;}}
  h3 {{font-size:16px;color:#374151;}}
  h4 {{font-size:15px;margin-bottom:4px;}}
  h4 a {{color:#2563eb;text-decoration:none;}}
  table {{border-collapse:collapse;width:100%;margin:8px 0;font-size:14px;}}
  th,td {{border:1px solid #e5e7eb;padding:6px 10px;text-align:left;}}
  th {{background:#f3f4f6;}}
  blockquote {{border-left:4px solid #2563eb;margin:12px 0;padding:8px 16px;
    background:#eff6ff;color:#1e40af;font-size:14px;}}
  hr {{border:none;border-top:1px solid #e5e7eb;margin:20px 0;}}
  a {{color:#2563eb;}}
  ul {{padding-left:20px;}}
  li {{margin:4px 0;}}
</style>
{body_html}
</body></html>"""

    def send_email(self, report: DailyReport, markdown_content: str) -> dict:
        """Send report via email proxy as styled HTML."""
        email_config = self.config.get("email", {})
        if not email_config.get("enabled", False):
            return {"success": False, "error": "Email not enabled"}

        api_url = email_config.get("api_url", "")
        api_token = email_config.get("api_token", "")
        recipients = email_config.get("recipients", [])
        sender_name = email_config.get("sender_name", "PaperRadar")

        if not api_url or not api_token or not recipients:
            return {"success": False, "error": "Email config incomplete"}

        subject = f"📚 论文每日速递 - {report.date} ({report.matched_papers} 篇匹配)"
        html_body = self._markdown_to_html(markdown_content)

        results = {}
        for to_addr in recipients:
            try:
                resp = httpx.post(
                    f"{api_url}/api/send",
                    headers={
                        "Authorization": f"Bearer {api_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "sender_name": sender_name,
                        "to": to_addr,
                        "subject": subject,
                        "body": markdown_content,
                        "html_body": html_body,
                    },
                    timeout=30,
                )
                data = resp.json()
                if data.get("success"):
                    logger.info(f"Email queued for {to_addr}, task_id={data.get('task_id')}")
                    results[to_addr] = {"success": True, "task_id": data.get("task_id")}
                else:
                    logger.error(f"Email failed for {to_addr}: {data}")
                    results[to_addr] = {"success": False, "error": str(data)}
            except Exception as e:
                logger.error(f"Email send error for {to_addr}: {e}")
                results[to_addr] = {"success": False, "error": str(e)}

        return results

    def generate_and_send(self, report: DailyReport) -> dict:
        """Generate report through all configured output formats and send email."""
        results = {}
        formats = self.output_config.get("formats", {})

        markdown_content = None
        markdown_config = formats.get("markdown", {})
        if markdown_config.get("enabled", True):
            try:
                markdown_content = self.generate_markdown(report)
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

        # Send email
        email_config = self.config.get("email", {})
        if email_config.get("enabled", False):
            if markdown_content is None:
                markdown_content = self.generate_markdown(report)
            try:
                email_results = self.send_email(report, markdown_content)
                results["email"] = email_results
            except Exception as e:
                logger.error(f"Failed to send email: {e}")
                results["email"] = {"success": False, "error": str(e)}

        return results
