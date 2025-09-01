# agents/docs/agent.py
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from common.tool_loader import load_tool_specs, build_tools_from_specs

def build_docs_agent():
    specs = load_tool_specs("agents/docs/tools.json")
    python_tools, _schemas = build_tools_from_specs(specs)
    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    agent = create_react_agent(model, python_tools)
    agent.name = "docs_agent"
    return agent
