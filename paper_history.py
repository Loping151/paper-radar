"""Paper history tracking module for deduplication."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger


class PaperHistory:
    """
    Tracks processed papers to avoid re-processing.

    Stores paper IDs with their processing date and matched keywords.
    Uses a JSON file for persistence.
    """

    def __init__(self, history_file: str = "./cache/paper_history.json"):
        """
        Initialize paper history tracker.

        Args:
            history_file: Path to the history JSON file
        """
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._history: dict = self._load_history()

    def _load_history(self) -> dict:
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.debug(f"Loaded {len(data.get('papers', {}))} papers from history")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load paper history: {e}")
                return {"papers": {}, "last_updated": None}
        return {"papers": {}, "last_updated": None}

    def _save_history(self):
        """Save history to file."""
        self._history["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save paper history: {e}")

    def is_new_paper(self, paper_id: str) -> bool:
        """
        Check if a paper is new (not previously processed).

        Args:
            paper_id: Unique paper identifier (arxiv_id or journal:doi)

        Returns:
            True if paper is new, False if already processed
        """
        return paper_id not in self._history.get("papers", {})

    def add_paper(
        self,
        paper_id: str,
        title: str,
        source: str,
        keywords: list[str] = None,
        pdf_path: str = None,
    ):
        """
        Add a paper to history.

        Args:
            paper_id: Unique paper identifier
            title: Paper title
            source: Source (arxiv, journal name)
            keywords: List of matched keywords
            pdf_path: Path to saved PDF (if any)
        """
        self._history["papers"][paper_id] = {
            "title": title,
            "source": source,
            "keywords": keywords or [],
            "pdf_path": pdf_path,
            "processed_date": datetime.now().strftime("%Y-%m-%d"),
            "processed_time": datetime.now().isoformat(),
        }
        self._save_history()
        logger.debug(f"Added paper to history: {paper_id}")

    def get_paper(self, paper_id: str) -> Optional[dict]:
        """Get paper info from history."""
        return self._history.get("papers", {}).get(paper_id)

    def get_papers_by_date(self, date: str) -> list[dict]:
        """
        Get all papers processed on a specific date.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            List of paper info dicts
        """
        papers = []
        for paper_id, info in self._history.get("papers", {}).items():
            if info.get("processed_date") == date:
                papers.append({"paper_id": paper_id, **info})
        return papers

    def get_papers_by_source(self, source: str) -> list[dict]:
        """
        Get all papers from a specific source.

        Args:
            source: Source name (e.g., "Nature Medicine")

        Returns:
            List of paper info dicts
        """
        papers = []
        for paper_id, info in self._history.get("papers", {}).items():
            if info.get("source") == source:
                papers.append({"paper_id": paper_id, **info})
        return papers

    def get_stats(self) -> dict:
        """Get statistics about paper history."""
        papers = self._history.get("papers", {})

        # Count by source
        by_source = {}
        for info in papers.values():
            source = info.get("source", "unknown")
            by_source[source] = by_source.get(source, 0) + 1

        # Count by date
        by_date = {}
        for info in papers.values():
            date = info.get("processed_date", "unknown")
            by_date[date] = by_date.get(date, 0) + 1

        return {
            "total_papers": len(papers),
            "by_source": by_source,
            "by_date": by_date,
            "last_updated": self._history.get("last_updated"),
        }

    def cleanup_old_papers(self, days: int = 90):
        """
        Remove papers older than specified days.

        Args:
            days: Number of days to keep
        """
        cutoff = datetime.now().strftime("%Y-%m-%d")
        # Calculate cutoff date
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        removed = 0
        papers = self._history.get("papers", {})
        to_remove = []

        for paper_id, info in papers.items():
            if info.get("processed_date", "") < cutoff_date:
                to_remove.append(paper_id)

        for paper_id in to_remove:
            del papers[paper_id]
            removed += 1

        if removed > 0:
            self._save_history()
            logger.info(f"Cleaned up {removed} papers older than {days} days")

        return removed
