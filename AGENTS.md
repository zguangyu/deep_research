# Agents Guidance

## Project Overview

This is a Deep Research Agent that uses web search (Tavily) + LLM (Minimax via langchain_openai) to research topics and generate Chinese reports. Single-file project: `deep_research_agent.py`.

## Running the Agent

```bash
# Interactive mode
python deep_research_agent.py

# With topic (non-interactive)
python deep_research_agent.py -t "your topic"

# With output directory
python deep_research_agent.py -t "your topic" -o reports/

# Resume interrupted research
python deep_research_agent.py -t "your topic" --resume

# List in-progress research
python deep_research_agent.py --list
```

## Environment Setup

Required env vars (copy `.env.example` to `.env`):
- `OPENAI_API_KEY` - LLM API key
- `TAVILY_API_KEY` - Search API key

Model/endpoint is hardcoded to Minimax: `ChatOpenAI(model="Minimax-M2.7", base_url="https://api.minimaxi.com/v1")`

## Key Files

| File | Purpose |
|------|---------|
| `deep_research_agent.py` | Entry point, agent logic, state management |
| `research_state.json` | Persists research progress (auto-created) |
| `research.log` | Execution logs (auto-created) |
| `reports/` | Output directory for generated reports |

## Architecture Notes

- Uses `deepagents` package (internal/custom) with `FilesystemBackend(virtual_mode=True)`
- Streaming mode with `stream_mode="messages"` and `subgraphs=True`
- Subagent tool calls are identified by namespace prefix `tools:`
- State tracks: status (running/completed/failed), messages, updated_at, error

## Important Conventions

- Report filenames are sanitized (special chars stripped) with 50-char topic limit + timestamp
- Chinese prompt hardcoded: "请帮我研究以下主题并撰写完整的研究报告"
- Retry with exponential backoff (3 attempts, 5s initial delay)
- Tool call logging distinguishes `main` vs `subagent` source
