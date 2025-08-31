# common/tool_loader.py
# Load tool specs from JSON and create LangChain/LangGraph-compatible tools.
# Supports "http" and "python" execution targets and JSON Schema parameters.

import json
import httpx
import re
import os
from typing import Any, Dict, List, Tuple, Callable
from pydantic import BaseModel, create_model
from langchain_core.tools import tool as lc_tool

def load_tool_specs(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def json_schema_to_pydantic(name: str, schema: Dict[str, Any]) -> type[BaseModel]:
    # Minimal JSON Schema → Pydantic model converter for "object" types.
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: Dict[str, Tuple[Any, Any]] = {}
    for k, _ in props.items():
        default = ... if k in required else None
        fields[k] = (Any, default)
    return create_model(name, **fields)  # type: ignore

def _expand_env(value: str) -> str:
    if not isinstance(value, str):
        return value
    return re.sub(r"\$\{([^}]+)\}", lambda m: os.getenv(m.group(1), ""), value)

def make_http_executor(exec_cfg: Dict[str, Any]) -> Callable[[Dict[str, Any]], Any]:
    method = exec_cfg.get("method", "GET").upper()
    url_template = exec_cfg.get("url", "")
    headers_template = exec_cfg.get("headers", {})
    query_map = exec_cfg.get("query_map", {})
    body_map = exec_cfg.get("body_map", {})
    timeout = exec_cfg.get("timeout", 20)
    send_raw_json = exec_cfg.get("send_raw_json", True)

    def run(params: Dict[str, Any]) -> Any:
        # Expand env in URL and headers
        expanded_url = _expand_env(url_template)
        # Fallback to argument-provided URL keys if env URL is blank
        final_url = expanded_url or params.get("url") or params.get("base_url")
        if not final_url:
            raise ValueError("No URL resolved: set an env URL or pass 'url'/'base_url' in tool args.")

        headers = {k: _expand_env(v) for k, v in headers_template.items()}
        qs = {query_map.get(k, k): v for k, v in params.items() if not query_map or k in query_map}
        # Drop any mapped to "__ignored__"
        qs = {k: v for k, v in qs.items() if k != "__ignored__"}

        body = None
        if body_map:
            body = {body_map.get(k, k): v for k, v in params.items() if k in body_map}
        elif method in ("POST", "PUT", "PATCH", "DELETE") and send_raw_json:
            # By default send validated params as JSON for write endpoints if no body_map
            body = params

        with httpx.Client(timeout=timeout) as client:
            if method == "GET":
                resp = client.get(final_url, params=qs, headers=headers)
            elif method in ("POST", "PUT", "PATCH", "DELETE"):
                json_payload = body if send_raw_json else None
                data_payload = None if send_raw_json else body
                resp = client.request(method, final_url, params=qs, json=json_payload, data=data_payload, headers=headers)
            else:
                resp = client.request(method, final_url, params=qs, json=body, headers=headers)

        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return resp.text

    return run

def make_python_executor(target: str) -> Callable[[Dict[str, Any]], Any]:
    module_path, func_name = target.split(":")
    mod = __import__(module_path, fromlist=[func_name])
    return getattr(mod, func_name)

def build_tools_from_specs(specs: List[Dict[str, Any]]):
    python_tools = []
    provider_tool_schemas = []

    for spec in specs:
        name = spec["name"]
        desc = spec.get("description", "")
        params_schema = spec.get("parameters", {"type": "object", "properties": {}})
        Model = json_schema_to_pydantic(f"{name}_Params", params_schema)

        exec_cfg = spec.get("execution", {})
        exec_type = exec_cfg.get("type", "http")
        if exec_type == "http":
            executor = make_http_executor(exec_cfg)
        elif exec_type == "python":
            executor = make_python_executor(exec_cfg["target"])
        else:
            raise ValueError(f"Unsupported execution type: {exec_type}")

        # Use factory form and concrete signature to satisfy typing
        def _impl(args: dict) -> Any:
            validated = Model(**(args or {})).model_dump()
            return executor(validated)

        tool_fn = lc_tool(
            name,
            args_schema=Model,
            description=desc,
            infer_schema=False,
        )(_impl)
        python_tools.append(tool_fn)

        provider_tool_schemas.append({
            "type": "function",
            "function": {"name": name, "description": desc, "parameters": params_schema},
        })

    return python_tools, provider_tool_schemas
