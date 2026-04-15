import os
import re
import argparse
from datetime import datetime
from typing import Literal
from tavily import TavilyClient
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from deepagents.backends import FilesystemBackend

import dotenv

dotenv.load_dotenv()

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

model = ChatOpenAI(model="Minimax-M2.7", base_url="https://api.minimaxi.com/v1")

filesystem_backend = FilesystemBackend(root_dir=".", virtual_mode=True)


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )


research_instructions = """You are an expert researcher. Your job is to conduct thorough research and then write a polished report in Chinese.

You have access to an internet search tool as your primary means of gathering information.

## `internet_search`

Use this to run an internet search for a given query. You can specify the max number of results to return, the topic, and whether raw content should be included.

## Report Format

Write a professional research report with the following structure:

# [Research Topic]

## 摘要
Brief overview of the research topic and key findings.

## 1. 研究背景
Background and context of the topic.

## 2. 核心概念
Definition and explanation of key concepts.

## 3. 主要发现
Key findings from your research.

## 4. 分析与讨论
In-depth analysis and discussion.

## 5. 结论
Summary and conclusions.

## 参考文献
List all sources referenced during research.

Ensure the report is comprehensive, well-structured, and academically rigorous.
"""

agent = create_deep_agent(
    model=model,
    tools=[internet_search],
    system_prompt=research_instructions,
    backend=filesystem_backend,
)


def save_report(topic: str, content: str, output_dir: str = "reports"):
    os.makedirs(output_dir, exist_ok=True)
    safe_topic = re.sub(r'[<>:"/\\|?*]', "", topic)
    safe_topic = safe_topic[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_topic}_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def run_with_logging(topic: str):
    print(f"\n正在研究「{topic}」，请稍候...\n")
    print("=" * 60)
    print("          Deep Research Agent - 执行过程")
    print("=" * 60 + "\n")

    for chunk in agent.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"请帮我研究以下主题并撰写完整的研究报告：{topic}",
                }
            ]
        },
        stream_mode="messages",
        subgraphs=True,
        version="v2",
    ):
        ns = chunk["ns"]
        is_subagent = any(s.startswith("tools:") for s in ns)
        source = "subagent" if is_subagent else "main"

        if chunk["type"] == "messages":
            token, metadata = chunk["data"]
            if hasattr(token, "tool_call_chunks") and token.tool_call_chunks:
                for tc in token.tool_call_chunks:
                    if tc.get("name"):
                        print(f"\n[{source}] 调用工具: {tc['name']}")
                    if tc.get("args"):
                        print(f"    参数: {tc['args']}", end="", flush=True)
            elif token.type == "tool":
                content = (
                    str(token.content)[:100] + "..."
                    if len(str(token.content)) > 100
                    else str(token.content)
                )
                print(
                    f"\n[{source}] 工具结果 [{getattr(token, 'name', 'unknown')}]: {content}"
                )
            elif token.type == "ai" and token.content:
                print(token.content, end="", flush=True)

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Deep Research Agent")
    parser.add_argument("-t", "--topic", type=str, help="研究主题")
    parser.add_argument(
        "-o", "--output", type=str, default="reports", help="报告输出目录"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("          Deep Research Agent")
    print("=" * 60)

    if args.topic:
        topic = args.topic
        print(f"\n研究主题: {topic}\n")
        run_with_logging(topic)
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"请帮我研究以下主题并撰写完整的研究报告：{topic}",
                    }
                ]
            }
        )
        report = result["messages"][-1].content
        if not report.startswith("#"):
            report = f"# {topic}\n\n" + report
        filepath = save_report(topic, report, args.output)
        print(f"\n\n研究报告已保存至: {filepath}\n")
    else:
        print("\n请输入您想要研究的主题，输入 'quit' 退出程序。\n")
        while True:
            topic = input("研究主题: ").strip()
            if topic.lower() == "quit":
                print("\n感谢使用，再见！")
                break
            if not topic:
                print("请输入有效的研究主题。\n")
                continue

            run_with_logging(topic)

            result = agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"请帮我研究以下主题并撰写完整的研究报告：{topic}",
                        }
                    ]
                }
            )

            report = result["messages"][-1].content
            if not report.startswith("#"):
                report = f"# {topic}\n\n" + report

            filepath = save_report(topic, report, args.output)
            print(f"\n\n研究报告已保存至: {filepath}\n")
            print("-" * 60 + "\n")


if __name__ == "__main__":
    main()
