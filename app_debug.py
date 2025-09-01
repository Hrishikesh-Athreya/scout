# Put in app_debug.py, replacing the previous LogAll class
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage

def _safe_name(serialized):
    # serialized may be None, dict, list, or string
    if serialized is None:
        return "unknown"
    if isinstance(serialized, dict):
        return serialized.get("name") or serialized.get("id") or str(serialized)
    if isinstance(serialized, list):
        # Sometimes it's a path like ['langchain_google_genai', 'chat_models', 'ChatGoogleGenerativeAI']
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
        # inputs may be dict or other
        keys = list(inputs.keys()) if isinstance(inputs, dict) else type(inputs).__name__
        print(f"[NODE START] {_safe_name(serialized)} inputs={keys}")

    def on_chain_end(self, outputs, **kwargs):
        # outputs may be dict, message, list, or str
        if isinstance(outputs, dict):
            k = list(outputs.keys())
            print(f"[NODE END] keys={k}")
        elif isinstance(outputs, BaseMessage):
            print(f"[NODE END] message={_preview(outputs.content)}")
        else:
            print(f"[NODE END] {_preview(outputs)}")

    def on_chat_model_start(self, serialized, messages, **kwargs):
        print(f"[LLM START] {_safe_name(serialized)}")

    def on_llm_end(self, response, **kwargs):
        usage = getattr(response, "usage_metadata", None)
        print("[LLM END] usage:", usage)

    # Optional: print token streaming if enabled in your model config
    def on_llm_new_token(self, token: str, **kwargs):
        print(token, end="", flush=True)
