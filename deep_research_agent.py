"""
Deep Research Agent - AI-powered research tool for generating reports.

This module provides an AI research agent that uses web search (Tavily) and
large language models (Minimax M2.7) to research topics and generate
comprehensive reports. The report language automatically matches the user's
input language. Features include streaming output, research state persistence,
and automatic retry with exponential backoff.

Example:
    python deep_research_agent.py -t "AI trends 2026"
"""

import os
import re
import json
import argparse
import logging
import logging.handlers
import sys
import time
from datetime import datetime
from typing import Literal
from tavily import TavilyClient
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

import dotenv

dotenv.load_dotenv()

import locale


def get_system_lang() -> str:
    """Detect system language using cross-platform method.

    Checks multiple sources in order:
    1. LC_ALL, LC_MESSAGES, LANG environment variables
    2. Windows registry (on Windows)
    3. locale.getdefaultlocale() (fallback)
    4. English default

    Returns:
        'zh' for Chinese, 'en' for English (default)
    """
    # Check environment variables first (most reliable cross-platform)
    for var in ["LC_ALL", "LC_MESSAGES", "LANG"]:
        lang = os.environ.get(var, "")
        if lang:
            lang = lang.lower()
            if lang.startswith("zh"):
                return "zh"
            elif lang.startswith("en"):
                return "en"

    # Windows registry check
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\International",
                0,
                winreg.KEY_READ
            ) as key:
                locale_name, _ = winreg.QueryValueEx(key, "LocaleName")
                if locale_name.lower().startswith("zh"):
                    return "zh"
        except Exception:
            pass

    # Try locale.getdefaultlocale() as fallback
    try:
        loc = locale.getdefaultlocale()
        if loc[0] and loc[0].lower().startswith("zh"):
            return "zh"
    except Exception:
        pass

    # Default to English
    return "en"


# Initialize system language
SYSTEM_LANG = get_system_lang()


# Internationalization strings
I18N = {
    "en": {
        # CLI and UI
        "app_title": "Deep Research Agent",
        "research_topic": "Research topic",
        "topic_placeholder": "Please enter your research topic",
        "input_topic": "Topic: ",
        "quit_message": "Thanks for using, goodbye!",
        "invalid_topic": "Please enter a valid research topic.\n",
        "existing_record": "Existing research record found (status: {status})",
        "resume_prompt": "Resume previous research? (y/n): ",
        "research_in_progress": "Research in progress:\n",
        "updated_at": "Updated at: {time}",
        "error_label": "Error: {error}",
        "resume_requires_topic": "Resume requires specifying -t topic\n",
        "topic_not_found": "No research record found for '{topic}', starting new research\n",
        "starting_research": "Research topic: {topic}\n",
        "resuming_from": "Resuming from last interruption (status: {status})\n",
        "research_interrupted": "Research interrupted or empty\n",
        "report_saved": "Report saved to: {filepath}\n",
        "research_failed": "Research failed: {error}\n",
        "use_resume_hint": "Research failed, use --resume to resume: python deep_research_agent.py -t \"{topic}\" --resume\n",
        "program_interrupted": "Program interrupted, thanks for using, goodbye!\n",
        "output_dir": "Output directory for reports",
        "resume_help": "Resume previous research",
        "list_help": "List in-progress research",

        # Streaming output
        "result": "Result:",
        "images": "Images:",
        "image_count": "{count} image(s)",
        "search_result": "Search result: {result}...",
        "search_images": "Search results contain {count} image(s)",
        "tool_result": "Tool result [{name}]: {content}",
        "unhandled_token": "Unhandled token type: {type}, content: {content}",
        "research_stopped": "Research stopped by user",
        "report_length": "Report content length: {length} characters",
        "report_saved_log": "Research report saved to: {filepath}",
        "research_failed_log": "Research failed: {error}",
        "all_attempts_failed": "All {count} attempts failed",

        # Error messages
        "error_missing_env": "Error: Missing required environment variable {key}",
        "error_set_env": "Please set {key} in .env file",

        # Research progress
        "researching": "Researching '{topic}'...",
    },
    "zh": {
        # CLI and UI
        "app_title": "深度研究助手",
        "research_topic": "研究主题",
        "topic_placeholder": "请输入您想要研究的主题",
        "input_topic": "研究主题: ",
        "quit_message": "感谢使用，再见！",
        "invalid_topic": "请输入有效的研究主题。\n",
        "existing_record": "发现已有研究记录 (状态: {status})",
        "resume_prompt": "是否恢复继续? (y/n): ",
        "research_in_progress": "进行中的研究:\n",
        "updated_at": "更新于: {time}",
        "error_label": "错误: {error}",
        "resume_requires_topic": "恢复研究需要指定 -t topic\n",
        "topic_not_found": "未找到主题「{topic}」的研究记录，开始新研究\n",
        "starting_research": "研究主题: {topic}\n",
        "resuming_from": "从上次中断处继续 (状态: {status})\n",
        "research_interrupted": "研究被中断或无内容\n",
        "report_saved": "研究报告已保存至: {filepath}\n",
        "research_failed": "研究失败: {error}\n",
        "use_resume_hint": "研究失败，可使用 --resume 恢复: python deep_research_agent.py -t \"{topic}\" --resume\n",
        "program_interrupted": "程序被中断，感谢使用，再见！\n",
        "output_dir": "报告输出目录",
        "resume_help": "恢复之前的研究",
        "list_help": "列出进行中的研究",

        # Streaming output
        "result": "结果:",
        "images": "图片:",
        "image_count": "{count} 张",
        "search_result": "搜索结果: {result}...",
        "search_images": "搜索结果含 {count} 张图片",
        "tool_result": "工具结果 [{name}]: {content}",
        "unhandled_token": "未处理的token类型: {type}, 内容: {content}",
        "research_stopped": "研究被用户中断",
        "report_length": "报告内容长度: {length} 字符",
        "report_saved_log": "研究报告已保存至: {filepath}",
        "research_failed_log": "研究失败: {error}",
        "all_attempts_failed": "所有 {count} 次尝试均失败",

        # Error messages
        "error_missing_env": "错误: 缺少必需的环境变量 {key}",
        "error_set_env": "请在 .env 文件中设置 {key}",

        # Research progress
        "researching": "正在研究「{topic}」...",

        # Status
        "status_running": "running",
        "status_completed": "completed",
        "status_failed": "failed",

        # Research prompt
        "prompt_request": "请帮我研究以下主题并撰写完整的研究报告。报告语言必须与用户输入语言保持一致：{topic}",
    }
}


def t(key: str, **kwargs) -> str:
    """Get translated string for current system language.

    Args:
        key: The i18n key to look up
        **kwargs: Format arguments for the string

    Returns:
        The translated string, or the key itself if not found
    """
    lang_dict = I18N.get(SYSTEM_LANG, I18N["en"])
    template = lang_dict.get(key, I18N["en"].get(key, key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template


def get_required_env(key: str) -> str:
    """Get required environment variable or exit with clear message.

    Retrieves an environment variable and terminates the program with
    an error message if the variable is not set.

    Args:
        key: The name of the environment variable to retrieve.

    Returns:
        The value of the environment variable.

    Raises:
        SystemExit: If the environment variable is not set, prints
            error message and exits with code 1.
    """
    value = os.environ.get(key)
    if not value:
        print(t("error_missing_env", key=key), file=sys.stderr)
        print(t("error_set_env", key=key), file=sys.stderr)
        sys.exit(1)
    return value


def _get_tavily_client() -> TavilyClient:
    """Create and return a new TavilyClient instance.

    Initializes a Tavily search client using the API key from
    environment variables.

    Returns:
        A new TavilyClient instance configured with the API key.

    Raises:
        SystemExit: If TAVILY_API_KEY environment variable is not set.
    """
    return TavilyClient(api_key=get_required_env("TAVILY_API_KEY"))

def _get_model() -> ChatOpenAI:
    """Create and return a new ChatOpenAI model instance.

    Initializes a ChatOpenAI client configured for Minimax M2.7
    with settings from environment variables.

    Returns:
        A new ChatOpenAI instance configured with model name and base URL.
    """
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL_NAME", "Minimax-M2.7"),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.minimaxi.com/v1")
    )

# Lazy initialization
_tavily_client: TavilyClient | None = None
_model: ChatOpenAI | None = None

def get_tavily_client() -> TavilyClient:
    """Get the singleton TavilyClient instance.

    Returns a cached TavilyClient instance, creating it on the first call.
    Uses lazy initialization to delay client creation until needed.

    Returns:
        The singleton TavilyClient instance.
    """
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = _get_tavily_client()
    return _tavily_client

def get_model() -> ChatOpenAI:
    """Get the singleton ChatOpenAI model instance.

    Returns a cached ChatOpenAI instance, creating it on the first call.
    Uses lazy initialization to delay model creation until needed.

    Returns:
        The singleton ChatOpenAI instance.
    """
    global _model
    if _model is None:
        _model = _get_model()
    return _model

STATE_FILE = "research_state.json"
LOG_FILE = "research.log"


def setup_logging():
    """Configure and return a logger with rotating file handler.

    Sets up logging to write to 'research.log' with rotation at 10MB,
    keeping 5 backup files. Log format includes timestamp, level,
    and message. Only logs to file, not to console to avoid
    duplicate output.

    Returns:
        A logger instance configured with rotating file handler.
    """
    rotate_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10_485_760, backupCount=5, encoding="utf-8"
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            rotate_handler,
            # Remove StreamHandler to avoid duplicate logging to console
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
    """Run a web search using Tavily search API.

    Performs an internet search with configurable parameters
    and returns search results including relevant URLs and snippets.

    Args:
        query: The search query string to look up.
        max_results: Maximum number of search results to return.
            Defaults to 5.
        topic: The topic category for the search. Valid values
            are "general", "news", or "finance". Defaults to "general".
        include_raw_content: Whether to include raw content from
            search sources. Defaults to False.

    Returns:
        A dictionary containing search results with keys such as
        'query', 'results', and optionally 'images' and 'answer'.
    """
    return get_tavily_client().search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )

research_instructions = """You are an expert researcher. Your job is to conduct thorough research and then write a polished report in Chinese.

You have access to an internet search tool as your primary means of gathering information.

## `internet_search`

Use this to run an internet search for a query. You can specify the max number of results to return, the topic, and whether raw content should be included.

## IMPORTANT: Report Output

After completing your research, you MUST output the complete report DIRECTLY in your response (not in any tool call or file).

Do NOT use any file writing tools. Simply write the complete report as your response content.

## Report Format

Write a professional research report with the following structure:

# [Research Topic]

## Summary
Brief overview of the research topic and key findings.

## 1. Background
Background and context of the topic.

## 2. Key Concepts
Definition and explanation of key concepts.

## 3. Main Findings
Key findings from your research.

## 4. Analysis and Discussion
In-depth analysis and discussion.

## 5. Conclusion
Summary and conclusions.

## References
List all sources referenced during research.

Ensure the report is comprehensive, well-structured, and academically rigorous.
"""


def create_research_agent(topic: str):
    """Create a fresh agent for each research topic to avoid conversation history carryover."""
    return create_deep_agent(
        model=get_model(),
        tools=[internet_search],
        system_prompt=research_instructions,
    ), None


def extract_title(content: str) -> str:
    """Extract title from the first Markdown heading in report content.

    Parses the content to find the first line starting with '# '
    (Markdown H1 heading) and returns the title text. The title
    is sanitized for use in filenames by removing special characters.

    Args:
        content: The Markdown content to extract title from.

    Returns:
        The extracted and sanitized title string, or an empty
        string if no heading is found. Maximum 50 characters.
    """
    # Find first # heading
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        title = match.group(1).strip()
        # Sanitize title for filename
        title = re.sub(r"[<>:\"/\\|?*\n]", "", title)[:50]
        return title
    return ""


def save_report(topic: str, content: str, output_dir: str = "reports", title: str = None) -> str:
    """Save report content to a file with timestamp in the filename.

    Creates the output directory if it doesn't exist, sanitizes the
    topic for use in filename, and saves the content with a timestamp.
    The filename format is: sanitized_topic_timestamp.md

    Args:
        topic: The research topic, used as part of the filename.
        content: The Markdown content to save to the file.
        output_dir: Directory path to save the report. Defaults to "reports".
        title: Optional custom title, otherwise extracted from content.

    Returns:
        The full path to the saved report file.
    """
    os.makedirs(output_dir, exist_ok=True)
    # Use provided title or generate one
    safe_title = re.sub(r"[<>:\"/\\|?*]", "", (title or topic))[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_title}_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
DIM = "\033[2m"


def run_with_logging(topic: str, resume: bool = False):
    """Run the research agent with streaming output and logging.

    Creates a research agent for the given topic and runs it while
    streaming the output to the console and logging to file. Handles
    interruption gracefully and cleans up the report content.

    Args:
        topic: The research topic to investigate.
        resume: Whether to resume from previous research state.
            Defaults to False.

    Returns:
        The generated research report as a Markdown string,
        or empty string if interrupted.
    """
    print(f"\n{CYAN}{t('researching', topic=topic)}{RESET}\n")

    topic_state = state.get_topic_state(topic) if resume else None

    input_messages = (
        topic_state.get(
            "messages",
            [
                {
                    "role": "user",
                    "content": t( "prompt_request", topic=topic),
                }
            ],
        )
        if resume and topic_state
        else [
            {
                "role": "user",
                "content": t( "prompt_request", topic=topic),
            }
        ]
    )

    report_parts: list[str] = []
    agent, _ = create_research_agent(topic)
    stream_generator = retry_with_backoff(
        lambda: agent.stream(
            {"messages": input_messages},
            stream_mode="messages",
            subgraphs=True,
            version="v2",
        )
    )

    # Thinking content markers
    THINK_START = "<think>"
    THINK_END = "</think>"
    thinking_buffer = ""  # Buffer for thinking content across chunks

    try:
        for chunk in stream_generator:
            ns = chunk["ns"]
            is_subagent = any(s.startswith("tools:") for s in ns)
            source = "subagent" if is_subagent else "main"
            source_color = CYAN if source == "main" else MAGENTA

            if chunk["type"] == "messages":
                token, metadata = chunk["data"]
                if hasattr(token, "tool_call_chunks") and token.tool_call_chunks:
                    for tc in token.tool_call_chunks:
                        if tc.get("name"):
                            tool_name = tc['name']
                            print(f"\n{source_color}[{source}]{RESET} {BOLD}{GREEN}>> {tool_name}{RESET}")
                            logger.info(f"[{source}] Calling tool: {tool_name}")
                        if tc.get("args"):
                            args_str = str(tc["args"])[:150]
                            print(f"    {DIM}{args_str}{RESET}", end="", flush=True)
                elif token.type == "tool":
                    tool_name = getattr(token, 'name', 'unknown')
                    content = str(token.content)

                    # Handle thinking content - find tags and extract
                    if tool_name == "thinking" or content.startswith(THINK_START):
                        while True:
                            start = content.find(THINK_START)
                            end = content.find(THINK_END)
                            if start != -1 and end != -1:
                                thinking = content[start + len(THINK_START):end].strip()
                                if thinking:
                                    print(f"\n{source_color}[{source}]{RESET} {DIM}🤔 Thinking: {thinking[:150]}...{RESET}")
                                content = content[end + len(THINK_END):]
                            elif start != -1:
                                # Opening tag only - accumulate
                                thinking_buffer = content[start + len(THINK_START):]
                                break
                            elif thinking_buffer and end == -1:
                                # Continuation of thinking
                                thinking_buffer += content
                                break
                            elif thinking_buffer and end != -1:
                                # End of thinking block
                                thinking_buffer += content[:end]
                                thinking = thinking_buffer.strip()
                                if thinking:
                                    print(f"\n{source_color}[{source}]{RESET} {DIM}🤔 Thinking: {thinking[:150]}...{RESET}")
                                content = content[end + len(THINK_END):]
                                thinking_buffer = ""
                            else:
                                break
                        continue

                    # Parse JSON results
                    try:
                        result_data = json.loads(content) if content.startswith("{") else None
                    except json.JSONDecodeError:
                        result_data = None

                    if result_data:
                        if "query" in result_data:
                            query = result_data['query'][:60]
                            print(f"\n{source_color}[{source}]{RESET} {YELLOW}🔍 Search:{RESET} {query}")
                            logger.info(f"[{source}] Search: {result_data['query']}")
                        if "answer" in result_data and result_data["answer"]:
                            answer = str(result_data["answer"])[:200]
                            print(f"    {GREEN}✓ {t('result')}{RESET} {DIM}{answer}...{RESET}")
                            logger.info(f"[{source}] {t('search_result', result=answer[:100])}")
                        elif "images" in result_data:
                            img_count = len(result_data.get("images", []))
                            if img_count != 0:
                                print(f"    {GREEN}✓ {t('images')}{RESET} {t('image_count', count=img_count)}")
                                logger.info(f"[{source}] {t('search_images', count=img_count)}")
                    else:
                        if "error" in content.lower() or "fail" in content.lower():
                            truncated = content[:150] + "..." if len(content) > 150 else content
                            print(f"\n{source_color}[{source}]{RESET} {YELLOW}[T] {tool_name}:{RESET} {truncated}")
                        else:
                            truncated = content[:100] + "..." if len(content) > 100 else content
                            print(f"\n{source_color}[{source}]{RESET} {DIM}[T] {tool_name}:{RESET} {truncated}")
                        logger.info(f"[{source}] {t('tool_result', name=tool_name, content=content[:200])}")
                elif token.type == "AIMessageChunk" and token.content:
                    content = token.content

                    # Handle thinking that might span multiple chunks
                    while True:
                        start = content.find(THINK_START)
                        end = content.find(THINK_END)
                        if start != -1 and end != -1:
                            # Complete thinking block in one chunk
                            thinking = content[start + len(THINK_START):end].strip()
                            if thinking:
                                print(f"\n{DIM}🤔 Thinking: {thinking[:100]}...{RESET}", end="", flush=True)
                            content = content[end + len(THINK_END):]
                        elif start != -1:
                            # Opening tag only - accumulate
                            thinking_buffer = content[start + len(THINK_START):]
                            content = content[:start]
                            break
                        elif thinking_buffer and end == -1:
                            # Continuation of thinking
                            thinking_buffer += content
                            content = ""
                            break
                        elif thinking_buffer and end != -1:
                            # End of thinking block
                            thinking_buffer += content[:end]
                            thinking = thinking_buffer.strip()
                            if thinking:
                                print(f"\n{DIM}🤔 Thinking: {thinking[:100]}...{RESET}", end="", flush=True)
                            content = content[end + len(THINK_END):]
                            thinking_buffer = ""
                        else:
                            break

                    if content:  # Only print non-empty content
                        print(content, end="", flush=True)
                    report_parts.append(content)
                else:
                    if hasattr(token, 'type'):
                        content_preview = str(token.content)[:50] if token.content else "None"
                        logger.debug(f"[{source}] {t('unhandled_token', type=token.type, content=content_preview)}")

    except KeyboardInterrupt:
        print("\n\n" + t("research_stopped"))
        logger.info(t("research_stopped"))
        # Return what we have so far
        final_report = "".join(report_parts)
        # Remove thinking content
        while True:
            start = final_report.find(THINK_START)
            end = final_report.find(THINK_END)
            if start != -1 and end != -1:
                final_report = final_report[:start] + final_report[end + len(THINK_END):]
            else:
                break
        final_report = re.sub(r"\n{3,}", "\n\n", final_report)
        final_report = final_report.strip()
        # Find first # heading
        first_heading = final_report.find("# ")
        if first_heading > 0:
            before_heading = final_report[:first_heading].strip()
            intro_keywords = ["我将为您", "让我先", "以下是", "根据您", "研究主题", "I will", "Let me", "Here is", "Based on your", "Research topic"]
            if any(kw in before_heading for kw in intro_keywords):
                final_report = final_report[first_heading:].strip()
        return final_report

    print("\n" + "=" * 60)

    final_report = "".join(report_parts)

    # Clean report: remove thinking content and extra blank lines
    while True:
        start = final_report.find(THINK_START)
        end = final_report.find(THINK_END)
        if start != -1 and end != -1:
            final_report = final_report[:start] + final_report[end + len(THINK_END):]
        else:
            break
    final_report = re.sub(r"\n{3,}", "\n\n", final_report)
    final_report = final_report.strip()

    # Clean thinking content - handle both complete and incomplete tags
    while True:
        start = final_report.find(THINK_START)
        end = final_report.find(THINK_END)
        if start != -1 and end != -1:
            # Complete thinking block
            final_report = final_report[:start] + final_report[end + len(THINK_END):]
        elif start != -1:
            # Incomplete thinking block (no end tag) - remove from start tag onwards
            final_report = final_report[:start]
            break
        else:
            break

    # Find first # heading - everything before it is intro/boilerplate
    first_heading = final_report.find("# ")
    if first_heading > 0:
        before_heading = final_report[:first_heading].strip()
        # If content before heading looks like intro/boilerplate, remove it
        # Keywords that indicate it's not part of the report
        intro_keywords = ["我将为您", "让我先", "以下是", "根据您", "研究主题", "I will", "Let me", "Here is", "Based on your", "Research topic"]
        if any(kw in before_heading for kw in intro_keywords):
            final_report = final_report[first_heading:].strip()

    logger.info(t("report_length", length=len(final_report)))
    return final_report


def run_research(topic: str, output_dir: str = "reports", resume: bool = False):
    """Run complete research flow for a topic and save the report.

    Orchestrates the research process: saves topic progress, runs the
    agent with logging, extracts title, saves the report to file,
    and updates the topic status.

    Args:
        topic: The research topic to investigate.
        output_dir: Directory to save the report. Defaults to "reports".
        resume: Whether to resume from previous state. Defaults to False.

    Returns:
        True if research completed and report was saved successfully,
        False otherwise.
    """
    state.save_topic_progress(topic, "running")

    try:
        report = run_with_logging(topic, resume=resume)

        if not report:
            print("\n\n" + t("research_interrupted"))
            return False

        # Only add title if report doesn't have one
        if not re.search(r"^#\s+.+", report, re.MULTILINE):
            report = f"# {topic}\n\n{report}"

        # Extract title from the first # heading in the report
        extracted_title = extract_title(report)

        filepath = save_report(topic, report, output_dir, title=extracted_title)
        state.save_topic_progress(topic, "completed")

        logger.info(t("report_saved_log", filepath=filepath))
        print("\n\n" + t("report_saved", filepath=filepath))
        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(t("research_failed_log", error=error_msg))
        state.save_topic_progress(topic, "failed", error=error_msg)
        print("\n\n" + t("research_failed", error=error_msg))
        return False


def retry_with_backoff(func, max_retries: int = 3, initial_delay: float = 5.0):
    """Retry a function with exponential backoff on failure.

    Executes the provided function up to max_retries times, doubling
    the delay after each failed attempt. Logs warning messages for
    each retry and error message when all attempts fail.

    Args:
        func: The function to execute. Should not require arguments.
        max_retries: Maximum number of retry attempts. Defaults to 3.
        initial_delay: Initial wait time in seconds before first retry.
            Defaults to 5.0.

    Returns:
        The return value of func if successful.

    Raises:
        Exception: The last exception that occurred if all retries fail.
    """
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
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(t("all_attempts_failed", count=max_retries))

    raise last_error


class ResearchState:
    """Manages research state persistence across sessions.

    Handles loading, saving, and querying research state including
    topic status, error messages, and conversation history for
    resuming interrupted research. State is persisted to a JSON file.

    Attributes:
        state_file: Path to the JSON file storing research state.
        state: Dictionary containing all persisted state data.
    """

    def __init__(self, state_file: str = STATE_FILE):
        """Initialize ResearchState with file path and load existing state.

        Args:
            state_file: Path to the state JSON file. Defaults to STATE_FILE.
        """
        self.state_file = state_file
        self.state: dict = self._load()

    def _load(self) -> dict:
        """Load state from JSON file or return default state.

        Attempts to read and parse the state file. If the file is
        missing, corrupted, or contains invalid data, returns a
        default empty state and logs a warning.

        Returns:
            A dictionary containing the loaded state or default state.
        """
        default_state = {"topics": {}, "last_updated": None, "version": 1}
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    if not isinstance(state, dict):
                        raise ValueError("State must be a dictionary")
                    return state
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"State file corrupted (parse error): {e}. Using defaults.")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}. Using defaults.")
        return default_state

    def save(self):
        """Persist current state to JSON file.

        Updates the last_updated timestamp and writes the entire state
        dictionary to the state file in UTF-8 encoding with indentation.
        Logs an error if the write fails.
        """
        self.state["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def save_topic_progress(self, topic: str, status: str, error: str = ""):
        """Save or update the progress status for a research topic.

        Records the topic name, current status (e.g., 'running',
        'completed', 'failed'), error message if any, and timestamp.
        Sanitizes the topic name for safe key storage.

        Args:
            topic: The research topic name.
            status: Current status string ('running', 'completed', 'failed').
            error: Optional error message string. Defaults to empty string.
        """
        safe_topic = re.sub(r"[<>:\"/\\|?*]", "", topic)
        if "topics" not in self.state:
            self.state["topics"] = {}
        self.state["topics"][safe_topic] = {
            "topic": topic,
            "status": status,
            "updated_at": datetime.now().isoformat(),
            "error": error,
        }
        self.save()

    def get_topic_state(self, topic: str) -> dict | None:
        """Retrieve the state data for a specific topic.

        Looks up the topic in the state dictionary using a sanitized
        key and returns all stored data including status, error,
        updated_at timestamp, and conversation messages.

        Args:
            topic: The research topic name to look up.

        Returns:
            A dictionary containing topic state data if found,
            None otherwise.
        """
        safe_topic = re.sub(r"[<>:\"/\\|?*]", "", topic)
        return self.state.get("topics", {}).get(safe_topic)

    def has_topic(self, topic: str) -> bool:
        """Check if a topic exists in the state.

        Determines whether a research topic record exists by checking
        for its sanitized key in the topics dictionary.

        Args:
            topic: The research topic name to check.

        Returns:
            True if the topic exists in state, False otherwise.
        """
        safe_topic = re.sub(r"[<>:\"/\\|?*]", "", topic)
        return safe_topic in self.state.get("topics", {})


state = ResearchState()


def main():
    """Main entry point for the Deep Research Agent CLI.

    Parses command-line arguments and either runs an interactive
    research session, executes a single research topic, lists
    in-progress research, or resumes previous research.

    Supports the following modes:
        - Interactive mode: Prompts for topic input
        - Topic mode: Research a specific topic provided via -t
        - List mode: Show all in-progress research via --list
        - Resume mode: Continue previous research via --resume
    """
    parser = argparse.ArgumentParser(description="Deep Research Agent")
    parser.add_argument("-t", "--topic", type=str, help=t("research_topic"))
    parser.add_argument(
        "-o", "--output", type=str, default="reports", help=t("output_dir")
    )
    parser.add_argument("--resume", action="store_true", help=t("resume_help"))
    parser.add_argument("--list", action="store_true", help=t("list_help"))
    args = parser.parse_args()

    print("=" * 60)
    print(f"          {t('app_title')}")
    print("=" * 60)

    if args.list:
        print("\n" + t("research_in_progress"))
        for safe_topic, topic_data in state.state.get("topics", {}).items():
            status = topic_data.get("status", "unknown")
            updated = topic_data.get("updated_at", "N/A")
            topic = topic_data.get("topic", safe_topic)
            error = topic_data.get("error", "")
            print(f"  [{status}] {topic}")
            print(f"         {t('updated_at', time=updated)}")
            if error:
                print(f"         {t('error_label', error=error[:100])}...")
            print()
        return

    if args.resume:
        if not args.topic:
            print(t("resume_requires_topic"))
            return
        if not state.has_topic(args.topic):
            print(t("topic_not_found", topic=args.topic))
            args.resume = False

    if args.topic:
        topic = args.topic
        print("\n" + t("starting_research", topic=topic))

        if args.resume:
            topic_state = state.get_topic_state(topic)
            print(t("resuming_from", status=topic_state.get('status', 'unknown')))

        success = run_research(topic, args.output, resume=args.resume)

        if not success:
            print(t("use_resume_hint", topic=topic))

    else:
        print("\n" + t("topic_placeholder") + " ('quit' to exit)\n")
        try:
            while True:
                topic = input(t("input_topic")).strip()
                if topic.lower() == "quit":
                    print("\n" + t("quit_message"))
                    break
                if not topic:
                    print(t("invalid_topic"))
                    continue

                if state.has_topic(topic):
                    topic_state = state.get_topic_state(topic)
                    status = topic_state.get("status", "unknown")
                    print(t("existing_record", status=status))
                    resume = input(t("resume_prompt")).strip().lower() == "y"
                else:
                    resume = False

                success = run_research(topic, args.output, resume=resume)

                if success:
                    print("-" * 60 + "\n")
                else:
                    print(t("use_resume_hint", topic=topic))
                    print("-" * 60 + "\n")
        except KeyboardInterrupt:
            print("\n\n" + t("program_interrupted"))


if __name__ == "__main__":
    main()
