"""Report generation and delivery module."""

import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from pathlib import Path
from datetime import datetime
from typing import Optional
import json
from loguru import logger
from jinja2 import Environment, FileSystemLoader

from models import DailyReport, PaperAnalysis


def markdown_to_html(text: str) -> str:
    """
    Convert simple Markdown to HTML for email display.

    Supports:
    - **bold** -> <strong>bold</strong>
    - *italic* -> <em>italic</em>
    - ## Header -> <h3>Header</h3>
    - # Header -> <h2>Header</h2>
    - * list item -> <li>list item</li>
    - Newlines -> <br>
    """
    if not text:
        return ""

    # Escape HTML special characters first (except for our conversions)
    # text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Convert headers (must be done before bold)
    # ### Header -> <h4>
    text = re.sub(r'^### (.+)$', r'<h4 style="margin: 15px 0 10px 0; color: #2c3e50;">\1</h4>', text, flags=re.MULTILINE)
    # ## Header -> <h3>
    text = re.sub(r'^## (.+)$', r'<h3 style="margin: 15px 0 10px 0; color: #2c3e50;">\1</h3>', text, flags=re.MULTILINE)
    # # Header -> <h2>
    text = re.sub(r'^# (.+)$', r'<h2 style="margin: 15px 0 10px 0; color: #1a1a1a;">\1</h2>', text, flags=re.MULTILINE)

    # Convert bold: **text** -> <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Convert italic: *text* -> <em>text</em> (but not if it's a list item)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)

    # Convert unordered list items: * item or - item
    lines = text.split('\n')
    result_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('* ') or stripped.startswith('- '):
            if not in_list:
                result_lines.append('<ul style="margin: 10px 0; padding-left: 20px;">')
                in_list = True
            item_content = stripped[2:]
            result_lines.append(f'<li style="margin: 5px 0;">{item_content}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append(line)

    if in_list:
        result_lines.append('</ul>')

    text = '\n'.join(result_lines)

    # Convert newlines to <br> (but not after block elements)
    text = re.sub(r'\n(?!<[hul/])', '<br>\n', text)

    return text


class Reporter:
    """Generates and delivers daily reports."""

    def __init__(self, config: dict):
        """
        Initialize the reporter.

        Args:
            config: Full configuration dict
        """
        self.config = config
        self.output_config = config.get("output", {})
        self.smtp_config = config.get("smtp", {})
        self.language = self.output_config.get("language", "Chinese")

        # Setup Jinja2 template environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))

    def generate_html(self, report: DailyReport) -> str:
        """
        Generate HTML report from template.

        Args:
            report: DailyReport data

        Returns:
            HTML string
        """
        template = self.jinja_env.get_template("email.html")

        # Convert Markdown summaries to HTML
        html_summaries = {
            keyword: markdown_to_html(summary)
            for keyword, summary in report.summaries.items()
        }

        html = template.render(
            date=report.date,
            total_papers=report.total_papers,
            matched_papers=report.matched_papers,
            analyzed_papers=report.analyzed_papers,
            summaries=html_summaries,
            analyses_by_keyword=report.analyses_by_keyword,
            keywords=report.keywords,
        )

        return html

    def generate_markdown(self, report: DailyReport) -> str:
        """
        Generate Markdown report.

        Args:
            report: DailyReport data

        Returns:
            Markdown string
        """
        lines = [
            f"# 📚 论文每日速递",
            f"",
            f"**日期**: {report.date} | **今日新论文**: {report.total_papers} 篇 | "
            f"**匹配论文**: {report.matched_papers} 篇 | **深度分析**: {report.analyzed_papers} 篇",
            f"",
            f"---",
            f"",
        ]

        for keyword in report.keywords:
            analyses = report.analyses_by_keyword.get(keyword, [])
            summary = report.summaries.get(keyword, "")
            successful_analyses = [a for a in analyses if a.success]

            lines.append(f"## 🔖 {keyword} ({len(successful_analyses)} 篇)")
            lines.append("")

            # Summary section
            if summary:
                lines.append("### 📈 领域进展总结")
                lines.append("")
                lines.append(f"> {summary}")
                lines.append("")

            # Paper details
            if successful_analyses:
                lines.append("### 📄 论文详情")
                lines.append("")

                for i, analysis in enumerate(successful_analyses, 1):
                    # Determine paper source - prefer paper reference, fallback to ID check
                    is_journal = False
                    journal_name = ""
                    if analysis.paper and analysis.paper.source == "journal":
                        is_journal = True
                        journal_name = analysis.paper.primary_category
                    elif ":" in analysis.arxiv_id:
                        is_journal = True
                        journal_name = analysis.arxiv_id.split(":")[0].replace("_", " ").title()

                    if is_journal:
                        # Journal paper - use pdf_url as link
                        lines.append(f"#### {i}. [{analysis.title}]({analysis.pdf_url})")
                    else:
                        # arXiv paper
                        lines.append(f"#### {i}. [{analysis.title}](https://arxiv.org/abs/{analysis.arxiv_id})")
                    lines.append("")
                    lines.append(f"| 项目 | 内容 |")
                    lines.append(f"|------|------|")

                    authors_str = ", ".join(analysis.authors[:3])
                    if len(analysis.authors) > 3:
                        authors_str += " et al."
                    lines.append(f"| **作者** | {authors_str} |")

                    if analysis.affiliations:
                        affiliations_str = ", ".join(analysis.affiliations[:2])
                        lines.append(f"| **机构** | {affiliations_str} |")

                    # Show source (arXiv ID or Journal name) with badge-like format
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

                    # Dataset info
                    if analysis.dataset_info and analysis.dataset_info != '未明确说明':
                        lines.append(f"**📊 数据集:** {analysis.dataset_info}")
                        lines.append("")

                    # Generate appropriate links
                    links = []
                    if is_journal:
                        links.append(f"[📄 原文]({analysis.pdf_url})")
                    else:
                        links.append(f"[📄 PDF]({analysis.pdf_url})")
                        links.append(f"[📋 Abstract](https://arxiv.org/abs/{analysis.arxiv_id})")

                    # Code link
                    if analysis.code_url:
                        links.append(f"[💻 Code]({analysis.code_url})")

                    lines.append(f"**链接:** {' | '.join(links)}")
                    lines.append("")
            else:
                lines.append("*今日该领域暂无相关论文*")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Footer
        lines.append("")
        lines.append("---")
        lines.append("*本报告由 Paper Daily 自动生成 (支持 arXiv + 学术期刊)*")

        return "\n".join(lines)

    def save_markdown(self, report: DailyReport, output_dir: Optional[str] = None) -> Path:
        """
        Save report as Markdown file.

        Args:
            report: DailyReport data
            output_dir: Output directory (uses config if not specified)

        Returns:
            Path to saved file
        """
        if output_dir is None:
            output_dir = self.output_config.get("formats", {}).get("markdown", {}).get("path", "./reports/")

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
        paper_source = paper.source if paper else ("journal" if ":" in analysis.arxiv_id else "arxiv")
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
        """
        Save report as JSON for the web frontend.

        Args:
            report: DailyReport data
            output_dir: Output directory (uses config if not specified)

        Returns:
            Path to saved file
        """
        if output_dir is None:
            output_dir = self.output_config.get("formats", {}).get("json", {}).get("path", "./reports/json/")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = f"paper-radar-{report.date}.json"
        file_path = output_path / filename

        papers_by_keyword = {}
        for keyword, analyses in report.analyses_by_keyword.items():
            papers_by_keyword[keyword] = [
                self._analysis_to_dict(a) for a in analyses if a.success
            ]

        payload = {
            "date": report.date,
            "total_papers": report.total_papers,
            "matched_papers": report.matched_papers,
            "analyzed_papers": report.analyzed_papers,
            "summaries": report.summaries,
            "keywords": report.keywords,
            "papers_by_keyword": papers_by_keyword,
        }

        file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"JSON report saved to: {file_path}")
        return file_path

    def send_email(self, report: DailyReport) -> bool:
        """
        Send report via email.

        Args:
            report: DailyReport data

        Returns:
            True if sent successfully
        """
        server = self.smtp_config.get("server", "")
        port = int(self.smtp_config.get("port", 465))
        sender = self.smtp_config.get("sender", "")
        password = self.smtp_config.get("password", "")
        receiver = self.smtp_config.get("receiver", "")

        if not all([server, sender, password, receiver]):
            logger.warning("Email configuration incomplete, skipping email send")
            return False

        # Support multiple receivers (comma or semicolon separated)
        if isinstance(receiver, str):
            receivers = [r.strip() for r in receiver.replace(";", ",").split(",") if r.strip()]
        else:
            receivers = [receiver]

        try:
            html = self.generate_html(report)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = Header(f"📚 PaperRadar 论文速递 - {report.date}", "utf-8")
            msg["From"] = f"PaperRadar <{sender}>"
            msg["To"] = ", ".join(receivers)

            # Attach HTML content
            html_part = MIMEText(html, "html", "utf-8")
            msg.attach(html_part)

            # Connect and send
            logger.info(f"Connecting to SMTP server: {server}:{port}")

            try:
                # Try SSL first
                smtp_server = smtplib.SMTP_SSL(server, port, timeout=30)
            except Exception:
                # Fallback to TLS
                smtp_server = smtplib.SMTP(server, port, timeout=30)
                smtp_server.starttls()

            smtp_server.login(sender, password)
            smtp_server.sendmail(sender, receivers, msg.as_string())
            smtp_server.quit()

            logger.info(f"Email sent successfully to: {', '.join(receivers)}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def generate_and_send(self, report: DailyReport) -> dict:
        """
        Generate and send report through all configured channels.

        Args:
            report: DailyReport data

        Returns:
            Dict with status of each channel
        """
        results = {}

        formats = self.output_config.get("formats", {})

        # Save Markdown if enabled
        markdown_config = formats.get("markdown", {})
        if markdown_config.get("enabled", True):
            try:
                path = self.save_markdown(report)
                results["markdown"] = {"success": True, "path": str(path)}
            except Exception as e:
                logger.error(f"Failed to save markdown: {e}")
                results["markdown"] = {"success": False, "error": str(e)}

        # Send email if enabled
        email_config = formats.get("email", {})
        if email_config.get("enabled", True):
            success = self.send_email(report)
            results["email"] = {"success": success}

        # Save JSON if enabled (for web frontend)
        json_config = formats.get("json", {})
        if json_config.get("enabled", True):
            try:
                path = self.save_json(report)
                results["json"] = {"success": True, "path": str(path)}
            except Exception as e:
                logger.error(f"Failed to save JSON: {e}")
                results["json"] = {"success": False, "error": str(e)}

        return results
