# 深度研究 Agent

一个基于 AI 的研究助手，使用网页搜索和 LLM 研究主题并生成中文研究报告。

## 功能特点

- Tavily API 网页搜索
- Minimax M2.7 LLM 驱动的研究
- 流式输出，实时显示研究进度
- 研究状态持久化（支持恢复中断的研究）
- 指数退避重试机制
- 中文报告生成

## 安装

需要 Python 3.11+。

```bash
# 安装依赖（需要 uv）
uv sync

# 或使用 pip 安装
pip install -e .
```

## 快速开始

```bash
# 复制环境变量模板
cp .env.example .env

# 在 .env 中添加你的 API 密钥
# OPENAI_API_KEY=你的_api密钥
# TAVILY_API_KEY=你的_api密钥

# 交互式运行
python deep_research_agent.py

# 或指定主题运行
python deep_research_agent.py -t "你的研究主题"
```

## 使用方法

```bash
# 交互式模式
python deep_research_agent.py

# 指定主题（非交互式）
python deep_research_agent.py -t "人工智能趋势 2026"

# 自定义输出目录
python deep_research_agent.py -t "人工智能趋势 2026" -o 我的报告/

# 恢复中断的研究
python deep_research_agent.py -t "人工智能趋势 2026" --resume

# 列出进行中的研究
python deep_research_agent.py --list
```

## 输出

研究报告保存到 `reports/` 目录，文件名带时间戳：

```
reports/人工智能趋势_2026_20260419_143022.md
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | LLM API 密钥（Minimax） |
| `TAVILY_API_KEY` | 搜索 API 密钥 |

配置请参考 `.env.example`。