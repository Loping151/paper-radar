"""Simple FastAPI server for PaperRadar web frontend."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", BASE_DIR / "reports"))
JSON_DIR = REPORTS_DIR / "json"
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="PaperRadar Web")


app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def _list_report_files() -> list[Path]:
    if not JSON_DIR.exists():
        return []
    # Support both old (arxiv-daily-) and new (paper-radar-) naming
    files = list(JSON_DIR.glob("paper-radar-*.json"))
    files.extend(JSON_DIR.glob("arxiv-daily-*.json"))
    return sorted(files, reverse=True)


def _date_from_filename(path: Path) -> Optional[str]:
    name = path.stem
    if name.startswith("paper-radar-"):
        return name.replace("paper-radar-", "")
    if name.startswith("arxiv-daily-"):
        return name.replace("arxiv-daily-", "")
    return None


def _load_report(date: Optional[str] = None) -> dict:
    if date:
        # Try new naming first, then old
        target = JSON_DIR / f"paper-radar-{date}.json"
        if not target.exists():
            target = JSON_DIR / f"arxiv-daily-{date}.json"
        if not target.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        return json.loads(target.read_text(encoding="utf-8"))

    files = _list_report_files()
    if not files:
        raise HTTPException(status_code=404, detail="No reports available")
    return json.loads(files[0].read_text(encoding="utf-8"))


@app.get("/")
def index():
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/dates")
def list_dates():
    dates = []
    for path in _list_report_files():
        date = _date_from_filename(path)
        if date:
            dates.append(date)
    return dates


@app.get("/api/report")
def get_report(date: Optional[str] = None):
    return _load_report(date)


@app.get("/favicon.ico")
def favicon():
    icon_path = WEB_DIR / "favicon.ico"
    if icon_path.exists():
        return FileResponse(str(icon_path))
    raise HTTPException(status_code=404, detail="Not found")
