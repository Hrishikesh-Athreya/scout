# app_db_only.py
# Run only the DB agent to fetch users data from the single API, with streaming + robust logs.

import os
from dotenv import load_dotenv

# 1) Load .env before any model/agent imports
DOTENV_PATH = os.path.join(os.getcwd(), ".env")
load_dotenv(DOTENV_PATH, override=True)
print("Loaded .env:", DOTENV_PATH)
print("GOOGLE_API_KEY present:", bool(os.getenv("GOOGLE_API_KEY")))
print("USERS_API_BASE:", os.getenv("USERS_API_BASE"))

from langchain_core.messages import HumanMessage
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables.config import RunnableConfig
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from common.tool_loader import load_tool_specs, build_tools_from_specs

# 2) Build the DB agent using the single db_get_users tool
def build_db_agent():
    specs = load_tool_specs("agents/db/tools.json")
    python_tools, _schemas = build_tools_from_specs(specs)
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )
    agent = create_react_agent(
        llm,
        python_tools,
        prompt=(
            "You are a data assistant that retrieves users via the provided HTTP tool(s).\n"
            "- To get all users, call the users API without filters.\n"
            "- If filters are provided, pass them precisely as query params.\n"
            "- Return concise JSON if possible."
        ),
    )
    agent.name = "db_agent"
    return agent

# 3) Robust console logger
from langchain_core.messages import BaseMessage

def _safe_name(serialized):
    if serialized is None:
        return "unknown"
    if isinstance(serialized, dict):
        return serialized.get("name") or serialized.get("id") or str(serialized)
    if isinstance(serialized, list):
        return " > ".join(map(str, serialized))
    return str(serialized)

def _preview(obj, maxlen=200):
    try:
        s = str(obj)
    except Exception:
        s = repr(obj)
    return s if len(s) <= maxlen else s[:maxlen] + "…"

class LogAll(BaseCallbackHandler):
    def on_tool_start(self, serialized, input_str, **kwargs):
        print(f"[TOOL START] {_safe_name(serialized)} args={_preview(input_str)}")
    def on_tool_end(self, output, **kwargs):
        print(f"[TOOL END] output={_preview(output)}")
    def on_chain_start(self, serialized, inputs, **kwargs):
        keys = list(inputs.keys()) if isinstance(inputs, dict) else type(inputs).__name__
        print(f"[NODE START] {_safe_name(serialized)} inputs={keys}")
    def on_chain_end(self, outputs, **kwargs):
        if isinstance(outputs, dict):
            print(f"[NODE END] keys={list(outputs.keys())}")
        elif isinstance(outputs, BaseMessage):
            print(f"[NODE END] message={_preview(outputs.content)}")
        else:
            print(f"[NODE END] {_preview(outputs)}")
    def on_chat_model_start(self, serialized, messages, **kwargs):
        print(f"[LLM START] {_safe_name(serialized)}")
    def on_llm_end(self, response, **kwargs):
        usage = getattr(response, "usage_metadata", None)
        print("[LLM END] usage:", usage)
    def on_llm_new_token(self, token: str, **kwargs):
        # Uncomment if you want token stream
        # print(token, end="", flush=True)
        pass

# 4) Runner
def main():
    # Ensure essential envs
    assert os.getenv("GOOGLE_API_KEY"), "GOOGLE_API_KEY not loaded"
    # USERS_API_BASE should be set for a clean call, otherwise tool can accept base_url argument
    if not os.getenv("USERS_API_BASE"):
        print("Warning: USERS_API_BASE is not set; the tool can still work if a base_url argument is provided.")

    db_agent = build_db_agent()

    # A natural-language instruction that will cause the agent to call the only tool with no filters
    user_goal = "Get all users from the users API and return the JSON."

    print("\n=== Stream values (state after each step) ===")
    for state in db_agent.stream({"messages": [HumanMessage(content=user_goal)]}, stream_mode="values"):
        msgs = state.get("messages", [])
        if msgs:
            last = msgs[-1]
            print("STREAM MESSAGE:", getattr(last, "content", str(last)))

    print("\n=== Invoke with callbacks (single run) ===")
    config: RunnableConfig = {"callbacks": [LogAll()], "run_name": "db_agent_run"}
    out = db_agent.invoke({"messages": [HumanMessage(content=user_goal)]}, config=config)

    # Print final assistant message or raw output
    final_msgs = out.get("messages", [])
    final_text = getattr(final_msgs[-1], "content", out) if final_msgs else out
    print("\nFINAL:", final_text)

if __name__ == "__main__":
    main()
