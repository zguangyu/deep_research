import os
import re
import argparse
from datetime import datetime
from tavily import TavilyClient
from langchain_openai import ChatOpenAI

import dotenv

dotenv.load_dotenv()

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
model = ChatOpenAI(model="Minimax-M2.7", base_url="https://api.minimaxi.com/v1")


def internet_search(query: str, max_results: int = 5):
    return tavily_client.search(query, max_results=max_results)


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


def simple_research(topic: str) -> str:
    print(f"\n正在研究「{topic}」...\n")

    search_results = internet_search(topic, max_results=3)

    print(f"获取到 {len(search_results.get('results', []))} 条搜索结果\n")

    report = f"# {topic}\n\n"
    report += "## 摘要\n\n"
    report += f"本文档基于网络搜索结果撰写，关于「{topic}」的研究报告。\n\n"
    report += "## 搜索结果\n\n"

    for i, result in enumerate(search_results.get("results", []), 1):
        print(f"处理结果 {i}: {result.get('title', 'N/A')[:30]}...")
        report += f"### {i}. {result.get('title', 'N/A')}\n"
        report += f"{result.get('url', '')}\n\n"
        report += f"{result.get('content', 'N/A')[:200]}...\n\n"

    report += "## 结论\n\n"
    report += "基于以上搜索结果进行了简要总结。\n\n"
    report += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

    return report


def main():
    parser = argparse.ArgumentParser(description="简单研究Agent - 仅测试写文件功能")
    parser.add_argument("-t", "--topic", type=str, help="研究主题")
    parser.add_argument(
        "-o", "--output", type=str, default="reports", help="报告输出目录"
    )
    args = parser.parse_args()

    topic = args.topic or input("请输入研究主题: ").strip()

    if not topic:
        print("请输入有效的研究主题")
        return

    report = simple_research(topic)

    filepath = save_report(topic, report, args.output)
    print(f"\n报告已保存至: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        print(f"\n验证文件内容 ({len(content)} 字符):")
        print("-" * 40)
        print(content[:500])
        if len(content) > 500:
            print("...")
        print("-" * 40)


if __name__ == "__main__":
    main()
