# PaperRadar

[![Docker](https://img.shields.io/badge/Docker-ready-blue)](https://hub.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Automated academic paper monitoring and analysis system powered by dual LLM architecture. Fetches papers from arXiv and academic journals, filters by keywords, and generates daily Markdown/JSON reports with AI-powered summaries (served via a lightweight web UI).

## Features

- **Multi-source Paper Fetching**: Supports arXiv preprints and academic journals (Nature, NEJM, Lancet, etc.)
- **Dual LLM Architecture**:
  - Light LLM for fast keyword matching and filtering
  - Heavy multimodal LLM for deep PDF analysis
- **EZproxy Authentication**: Access paywalled journal PDFs through institutional library
- **Smart Analysis**: Extracts contributions, methodology, datasets, and code links from papers
- **Daily Reports**: Markdown + JSON reports with field summaries
- **Docker Ready**: Easy deployment on NAS or cloud servers

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  arXiv RSS      │     │  Light LLM      │     │  Heavy LLM      │
│  Journal RSS    │────▶│  (Filtering)    │────▶│  (PDF Analysis) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                        ┌─────────────────┐             │
                        │  Markdown/JSON  │◀────────────┘
                        │  Web UI         │
                        └─────────────────┘
```

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/paper-radar.git
cd paper-radar
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys and credentials
```

### 3. Run with Docker

```bash
docker compose up -d
```

See [DEPLOY.md](DEPLOY.md) for detailed deployment instructions.

## Web Frontend

The container also exposes a lightweight web UI on port `8000`:

```
http://<your-server-ip>:8000
```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LIGHT_LLM_API_BASE` | Light LLM API endpoint (OpenAI compatible) |
| `LIGHT_LLM_API_KEY` | Light LLM API key |
| `LIGHT_LLM_MODEL` | Light LLM model name |
| `HEAVY_LLM_API_BASE` | Heavy LLM API endpoint |
| `HEAVY_LLM_API_KEY` | Heavy LLM API key |
| `HEAVY_LLM_MODEL` | Heavy LLM model name (e.g., gemini-2.0-flash) |
| `HKU_LIBRARY_UID` | (Optional) Library credentials for EZproxy |
| `HKU_LIBRARY_PIN` | (Optional) Library credentials for EZproxy |

### Keywords Configuration

Edit `config.yaml` to customize your research keywords:

```yaml
keywords:
  - name: "Medical Image Analysis"
    description: "医学图像分析、医学影像AI"
    examples:
      - "medical image segmentation, detection"
      - "CT, MRI, X-ray analysis"
```

## Supported LLM Providers

- **Light LLM**: Any OpenAI-compatible API (DeepSeek, OpenAI, etc.)
- **Heavy LLM**: Gemini (recommended for PDF analysis), or any multimodal LLM

## Project Structure

```
paper-radar/
├── agents/                 # LLM agents
│   ├── filter_agent.py     # Keyword matching
│   ├── analyzer_agent.py   # PDF analysis
│   └── summary_agent.py    # Field summaries
├── models/                 # Data models
├── scripts/                # Docker scripts
├── config.yaml             # Main configuration
├── main.py                 # Entry point
└── docker-compose.yml      # Docker deployment
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
