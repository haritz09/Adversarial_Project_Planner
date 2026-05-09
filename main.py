# main.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from langgraph.types import Command
from graph.pipeline import graph

def main():
    user_input = input("Describe your project: ").strip()
    if not user_input:
        user_input = "Build a real-time chat app in 3 weeks with 2 developers"

    config = {"configurable": {"thread_id": "run-1"}}
    print("\n🚀 Starting Adversarial Project Planner...\n")

    inputs = {"raw_input": user_input}

    while True:
        interrupted = False

        for step in graph.stream(inputs, config=config, stream_mode="updates"):
            node = list(step.keys())[0]

            if node == "__interrupt__":
                interrupted = True
                question = step["__interrupt__"][0].value
                print(f"\n❓ {question}")
                answer = input("Your answer: ").strip()
                inputs = Command(resume=answer)
                break

            print(f"✅ {node} completed")

        if not interrupted:
            break

    print("\n📄 Pages created in Notion:")
    final = graph.get_state(config).values
    for key, url in final.get("notion_urls", {}).items():
        print(f"  {key}: {url}")

if __name__ == "__main__":
    main()