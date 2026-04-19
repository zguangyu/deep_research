import os
import re
import json
import argparse
import logging
from datetime import datetime
from typing import Literal, Optional
from tavily import TavilyClient
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from deepagents.backends import FilesystemBackend

import dotenv

dotenv.load_dotenv()

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
model = ChatOpenAI(model="Minimax-M2.7", base_url="https://api.minimaxi.com/v1")
filesystem_backend = FilesystemBackend(root_dir=".", virtual_mode=True)

STATE_FILE = "research_state.json"
LOG_FILE = "research.log"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger(__name__)


logger = setup_logging()


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


class ResearchState:
    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = state_file
        self.state: dict = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
        return {"topics": {}, "last_updated": None}

    def save(self):
        self.state["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def has_topic(self, topic: str) -> bool:
        safe_topic = self._safe_topic(topic)
        return safe_topic in self.state["topics"]

    def get_topic_state(self, topic: str) -> Optional[dict]:
        safe_topic = self._safe_topic(topic)
        return self.state["topics"].get(safe_topic)

    def save_topic_progress(
        self, topic: str, status: str, messages: list = None, error: str = None
    ):
        safe_topic = self._safe_topic(topic)
        if safe_topic not in self.state["topics"]:
            self.state["topics"][safe_topic] = {"topic": topic}
        self.state["topics"][safe_topic].update(
            {
                "status": status,
                "updated_at": datetime.now().isoformat(),
                "error": error,
            }
        )
        if messages is not None:
            self.state["topics"][safe_topic]["messages"] = messages
        self.save()

    def _safe_topic(self, topic: str) -> str:
        return re.sub(r"[^\w\u4e00-\u9fff]", "_", topic)[:50]


state = ResearchState()


def save_report(topic: str, content: str, output_dir: str = "reports"):
    content = re.sub(r"<think>[\s\S]*?</think>", "", content)
    os.makedirs(output_dir, exist_ok=True)
    safe_topic = re.sub(r"[<>:\"/\\|?*]", "", topic)
    safe_topic = safe_topic[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_topic}_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def run_with_logging(topic: str, resume: bool = False):
    print(f"\n正在研究「{topic}」，请稍候...\n")
    print("=" * 60)
    print("          Deep Research Agent - 执行过程")
    print("=" * 60 + "\n")

    topic_state = state.get_topic_state(topic) if resume else None

    for chunk in agent.stream(
        {
            "messages": topic_state.get(
                "messages",
                [
                    {
                        "role": "user",
                        "content": f"请帮我研究以下主题并撰写完整的研究报告：{topic}",
                    }
                ],
            )
            if resume and topic_state
            else [
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
                        logger.info(f"[{source}] 调用工具: {tc['name']}")
                    if tc.get("args"):
                        args_str = str(tc["args"])[:200]
                        print(f"    参数: {args_str}", end="", flush=True)
            elif token.type == "tool":
                content = str(token.content)
                truncated = content[:100] + "..." if len(content) > 100 else content
                print(
                    f"\n[{source}] 工具结果 [{getattr(token, 'name', 'unknown')}]: {truncated}"
                )
                logger.info(f"[{source}] 工具结果: {truncated}")
            elif token.type == "ai" and token.content:
                print(token.content, end="", flush=True)

    print("\n" + "=" * 60)


def run_research(topic: str, output_dir: str = "reports", resume: bool = False):
    state.save_topic_progress(topic, "running")

    try:
        run_with_logging(topic, resume=resume)

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

        filepath = save_report(topic, report, output_dir)
        state.save_topic_progress(topic, "completed")

        logger.info(f"研究报告已保存至: {filepath}")
        print(f"\n\n研究报告已保存至: {filepath}\n")
        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"研究失败: {error_msg}")
        state.save_topic_progress(topic, "failed", error=error_msg)
        print(f"\n\n研究失败: {error_msg}\n")
        return False


def retry_with_backoff(func, max_retries: int = 3, initial_delay: float = 5.0):
    delay = initial_delay
    last_error = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}, retrying in {delay}s..."
                )
                import time

                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"All {max_retries} attempts failed")

    raise last_error


def main():
    parser = argparse.ArgumentParser(description="Deep Research Agent")
    parser.add_argument("-t", "--topic", type=str, help="研究主题")
    parser.add_argument(
        "-o", "--output", type=str, default="reports", help="报告输出目录"
    )
    parser.add_argument("--resume", action="store_true", help="恢复之前的研究")
    parser.add_argument("--list", action="store_true", help="列出进行中的研究")
    args = parser.parse_args()

    print("=" * 60)
    print("          Deep Research Agent")
    print("=" * 60)

    if args.list:
        print("\n进行中的研究:\n")
        for safe_topic, topic_data in state.state.get("topics", {}).items():
            status = topic_data.get("status", "unknown")
            updated = topic_data.get("updated_at", "N/A")
            topic = topic_data.get("topic", safe_topic)
            error = topic_data.get("error", "")
            print(f"  [{status}] {topic}")
            print(f"         更新于: {updated}")
            if error:
                print(f"         错误: {error[:100]}...")
            print()
        return

    if args.resume:
        if not args.topic:
            print("恢复研究需要指定 -t topic\n")
            return
        if not state.has_topic(args.topic):
            print(f"未找到主题「{args.topic}」的研究记录，开始新研究\n")
            args.resume = False

    if args.topic:
        topic = args.topic
        print(f"\n研究主题: {topic}\n")

        if args.resume:
            topic_state = state.get_topic_state(topic)
            print(f"从上次中断处继续 (状态: {topic_state.get('status', 'unknown')})\n")

        success = run_research(topic, args.output, resume=args.resume)

        if not success:
            print(
                f'\n研究失败，可使用 --resume 恢复: python deep_research_agent.py -t "{topic}" --resume\n'
            )

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

            if state.has_topic(topic):
                topic_state = state.get_topic_state(topic)
                status = topic_state.get("status", "unknown")
                print(f"发现已有研究记录 (状态: {status})")
                resume = input("是否恢复继续? (y/n): ").strip().lower() == "y"
            else:
                resume = False

            success = run_research(topic, args.output, resume=resume)

            if success:
                print("-" * 60 + "\n")
            else:
                print(
                    f'\n研究失败，可使用 --resume 恢复: python deep_research_agent.py -t "{topic}" --resume\n'
                )
                print("-" * 60 + "\n")


if __name__ == "__main__":
    main()
