from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from common.tool_loader import load_tool_specs, build_tools_from_specs

def build_db_agent():
    specs = load_tool_specs("agents/db/tools.json")
    python_tools, _schemas = build_tools_from_specs(specs)
    model = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0)
    agent = create_react_agent(
        model,
        python_tools,
        prompt=(
            "You are a data assistant that retrieves data via the provided DB HTTP tools.\n"
            "- Use read-only endpoints and pass parameters precisely.\n"
            "- Prefer returning concise JSON or bullet summaries."
        ),
    )
    agent.name = "db_agent"
    return agent
