# app_debug.py
from dotenv import load_dotenv
load_dotenv()  # load variables from .env into process env

from supervisor.supervisor import get_graph
from langchain_core.messages import HumanMessage
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables.config import RunnableConfig

graph = get_graph()

def print_last_message(state):
    msgs = state.get("messages", [])
    if msgs:
        last = msgs[-1]
        content = getattr(last, "content", str(last))
        print("STREAM MESSAGE:", content)

print("=== Stream values (state after each step) ===")
for value_state in graph.stream({"messages": [HumanMessage(content="Do X then Y")]}, stream_mode="values"):
    print_last_message(value_state)

print("\n=== Stream messages (LLM/tokens) ===")
for chunk, meta in graph.stream({"messages": [HumanMessage(content="Summarize PDF then email")]}, stream_mode="messages"):
    if isinstance(chunk, str):
        print("TOKEN:", chunk, end="", flush=True)
    else:
        print("\nMESSAGE:", getattr(chunk, "content", str(chunk)))

print("\n\n=== Invoke with callbacks ===")
class LogAll(BaseCallbackHandler):
    def on_tool_start(self, serialized, input_str, **kwargs):
        print(f"[TOOL START] {serialized.get('name') or serialized.get('id')} args={input_str}")
    def on_tool_end(self, output, **kwargs):
        print(f"[TOOL END] output={str(output)[:200]}")
    def on_chain_start(self, serialized, inputs, **kwargs):
        print(f"[NODE START] {serialized.get('id') or serialized.get('name')} keys={list(inputs.keys())}")
    def on_chain_end(self, outputs, **kwargs):
        print(f"[NODE END] keys={list(outputs.keys())}")
    def on_chat_model_start(self, serialized, messages, **kwargs):
        print(f"[LLM START] {serialized.get('id') or serialized.get('name')}")
    def on_llm_end(self, response, **kwargs):
        usage = getattr(response, "usage_metadata", None)
        print("[LLM END] usage:", usage)

config: RunnableConfig = {"callbacks": [LogAll()], "run_name": "supervisor_run"}
out = graph.invoke({"messages": [HumanMessage(content="Plan a report from DB and send via email")]}, config=config)
print("\nFINAL:", getattr(out.get("messages", [])[-1], "content", out))
