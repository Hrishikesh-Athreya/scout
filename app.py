# app.py
# Entry point to run and test the multi-agent system.
import os
from dotenv import load_dotenv
from supervisor.supervisor import get_graph

def main():
    load_dotenv()  # loads API keys like EMAIL_API_KEY, SLACK_BOT_TOKEN, PDF_API_KEY, OPENAI_API_KEY
    graph = get_graph()

    # A complex instruction requiring both agents
    query = (
        "Extract text from pages 1-2 of this PDF https://example.com/handbook.pdf, "
        "summarize it in 3 bullets, then email the summary to alex@example.com and "
        "post it to Slack channel #announcements."
    )
    out = graph.invoke({"messages": [{"role": "user", "content": query}]})
    print(out["messages"][-1].content if "messages" in out else out)

if __name__ == "__main__":
    main()
