from langchain_core.runnables.config import RunnableConfig
from langchain_core.messages import HumanMessage
from supervisor.supervisor import get_graph
from langchain_core.callbacks import BaseCallbackHandler

graph = get_graph()

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

# Stream values
for state in graph.stream({"messages": [HumanMessage("Do X then Y")]},
                          config=config,
                          stream_mode="values"):
    msgs = state.get("messages", [])
    if msgs:
        print("STREAM MESSAGE:", getattr(msgs[-1], "content", str(msgs[-1])))

# Invoke with callbacks
out = graph.invoke({"messages": [HumanMessage("Plan a report from DB and send via email")]},
                   config=config)
print("FINAL:", getattr(out.get("messages", [])[-1], "content", out))
