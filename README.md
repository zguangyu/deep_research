# Deep Research Agent

An AI-powered research agent that uses web search and LLM to research topics and generate comprehensive reports in Chinese.

[中文](README_zh.md)

## Features

- Web search via Tavily API
- LLM-powered research with Minimax M2.7
- Streaming output with real-time progress
- Research state persistence (resume interrupted research)
- Automatic retry with exponential backoff
- Chinese report generation

## Installation

Requires Python 3.11+.

```bash
# Install dependencies (requires uv)
uv sync

# Or install with pip
pip install -e .
```

## Quick Start

```bash
# Copy environment template
cp .env.example .env

# Add your API keys to .env
# OPENAI_API_KEY=your_api_key
# TAVILY_API_KEY=your_api_key

# Run interactively
python deep_research_agent.py

# Or with a topic
python deep_research_agent.py -t "your research topic"
```

## Usage

```bash
# Interactive mode
python deep_research_agent.py

# With topic (non-interactive)
python deep_research_agent.py -t "AI trends 2026"

# With custom output directory
python deep_research_agent.py -t "AI trends 2026" -o my_reports/

# Resume interrupted research
python deep_research_agent.py -t "AI trends 2026" --resume

# List in-progress research
python deep_research_agent.py --list
```

## Output

Reports are saved to `reports/` directory with timestamped filenames:

```
reports/AI_trends_2026_20260419_143022.md
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | LLM API key (Minimax) | - |
| `OPENAI_BASE_URL` | LLM API endpoint | `https://api.minimaxi.com/v1` |
| `OPENAI_MODEL_NAME` | LLM model name | `Minimax-M2.7` |
| `TAVILY_API_KEY` | Tavily search API key | - |

See `.env.example` for configuration.