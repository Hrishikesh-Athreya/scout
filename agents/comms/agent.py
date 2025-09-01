# agents/comms/agent.py
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from common.tool_loader import load_tool_specs, build_tools_from_specs
import os

def build_comms_agent():
    specs = load_tool_specs("agents/comms/tools.json")
    python_tools, _schemas = build_tools_from_specs(specs)

    if "GOOGLE_API_KEY" not in os.environ:
        print("WARNING: GOOGLE_API_KEY not set. Set it in a .env file or environment variable.")
    else:
        print("GOOGLE_API_KEY is set.", os.environ["GOOGLE_API_KEY"][:5] + "...")

    model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    # create_react_agent binds tools and builds a ReAct loop
    agent = create_react_agent(model, python_tools)
    agent.name = "comms_agent"
    return agent
