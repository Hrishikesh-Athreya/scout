# etl_flow.py
import os
import re
import json
import uuid
import sqlite3
from typing import Any, Dict, List, Tuple, Optional

from dotenv import load_dotenv
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage

# Optional LLM fallback for NL->SQL (single-call if needed)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langgraph.prebuilt import create_react_agent

# Load env
load_dotenv(override=True)
assert os.getenv("GOOGLE_API_KEY"), "GOOGLE_API_KEY not set"  # [12]

# Load the HTTP tool (db_get_users) from JSON
from common.tool_loader import load_tool_specs, build_tools_from_specs
TOOLS_PATH = "agents/db/tools.json"
specs = load_tool_specs(TOOLS_PATH)  # List[Dict[str, Any]] [11]
http_tools, _ = build_tools_from_specs(specs)  # [11]
get_users = next((t for t in http_tools if getattr(t, "name", "") == "db_get_users"), None)
assert get_users is not None, "db_get_users not found in tools.json"  # [11]

DB_FILE = "etl_temp.db"

# 1) Intent: map NL to fetch params + a goal
def classify_and_params(text: str) -> Tuple[Dict[str, Any], str]:
    t = (text or "").lower()
    params: Dict[str, Any] = {}
    goal = "query_all"
    if "active" in t:
        params["status"] = "ACTIVE"
        goal = "query_active"
    if "report" in t and "active" in t:
        goal = "report_active"
    return params, goal  # [13]

# 2) Schema helpers
def infer_sqlite_type(value: Any) -> str:
    if value is None: return "TEXT"
    if isinstance(value, bool): return "INTEGER"
    if isinstance(value, int): return "INTEGER"
    if isinstance(value, float): return "REAL"
    return "TEXT"  # store complex as TEXT/JSON [14]

def unify_keys(rows: List[Dict[str, Any]]) -> List[str]:
    keys: set[str] = set()
    for r in rows:
        keys.update(r.keys())
    return sorted(keys)

def infer_schema(rows: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    sample = next((r for r in rows if isinstance(r, dict) and r), {})
    cols: List[Tuple[str, str]] = []
    for k in unify_keys(rows):
        cols.append((k, infer_sqlite_type(sample.get(k))))
    return cols  # [14]

# 3) Minimal SQL agent (fallback only; flow uses direct SQL for the basics)
def build_sql_agent():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )  # [15]
    db = SQLDatabase.from_uri(f"sqlite:///{DB_FILE}")  # [16]
    tk = SQLDatabaseToolkit(db=db, llm=llm)  # [17]
    tools = [t for t in tk.get_tools() if t.name in {"sql_db_schema", "sql_db_query"}]
    agent = create_react_agent(llm, tools, prompt="Use schema tools then run one SELECT; return only the result.")
    agent.name = "sql_agent"
    return agent

sql_agent = build_sql_agent()

# 4) State
class S(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    params: Dict[str, Any]
    goal: str
    table: str
    rows: List[Dict[str, Any]]
    error: str
    result: str

# 5) Nodes
def intent_node(state: S) -> S:
    # Last human message
    q = ""
    msgs = state.get("messages", [])
    for m in reversed(msgs):
        if getattr(m, "type", None) == "human" or (isinstance(m, dict) and m.get("role") == "user"):
            q = getattr(m, "content", "") if not isinstance(m, dict) else m.get("content", "")
            break
    params, goal = classify_and_params(q)
    return {"params": params, "goal": goal, "messages": [{"role": "assistant", "content": f"Intent={goal}, params={params}"}]}

def fetch_node(state: S) -> S:
    try:
        out = get_users.invoke(state.get("params", {}))  # [11]
        rows = out
        if isinstance(rows, str):
            rows = json.loads(rows)
        if not isinstance(rows, list):
            return {"error": "Fetch did not return a list"}
        if not rows:
            return {"error": "No rows returned"}
        return {"rows": rows, "messages": [{"role": "assistant", "content": f"Fetched {len(rows)} rows"}]}
    except Exception as e:
        return {"error": f"Fetch failed: {e}"}

def load_node(state: S) -> S:
    rows = state.get("rows", [])
    if not rows:
        return {"error": "No rows to load"}
    table = f"t_{uuid.uuid4().hex[:8]}"
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        # Synthetic unique id
        cols = [("uid", "TEXT")] + infer_schema(rows)  # [14]
        # Create table
        col_defs = [f"{name} {typ}" for name, typ in cols]
        cur.execute(f"CREATE TABLE {table} ({', '.join(col_defs)})")
        # Insert rows
        keys = [name for name, _ in cols]
        placeholders = ", ".join(["?"] * len(keys))
        for r in rows:
            vals = [uuid.uuid4().hex] + [
                json.dumps(r.get(k), ensure_ascii=False) if isinstance(r.get(k), (dict, list)) else r.get(k)
                for k in keys[1:]
            ]
            cur.execute(f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})", vals)
        conn.commit()
        conn.close()
        return {"table": table, "messages": [{"role": "assistant", "content": f"Loaded into {table}"}]}
    except Exception as e:
        return {"error": f"Load failed: {e}"}

def is_sql(text: str) -> bool:
    return bool(re.match(r"^\s*(select|with)\b", text or "", re.IGNORECASE))

def query_node(state: S) -> S:
    table = state.get("table")
    if not table:
        return {"error": "No table to query"}  # [12]
    # User request again
    q = ""
    msgs = state.get("messages", [])
    for m in reversed(msgs):
        if getattr(m, "type", None) == "human" or (isinstance(m, dict) and m.get("role") == "user"):
            q = getattr(m, "content", "") if not isinstance(m, dict) else m.get("content", "")
            break
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        # Tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [r for r in cur.fetchall()]  # [18]
        # PRAGMA schema for our temp table
        cur.execute(f"PRAGMA table_info('{table}')")
        schema_rows = cur.fetchall()
        schema_cols = ["cid", "name", "type", "notnull", "dflt_value", "pk"]  # fixed order [3]
        schema = [dict(zip(schema_cols, r)) for r in schema_rows]
        # Execute user SQL or simple mapped SQL
        if is_sql(q):
            cur.execute(q)
        else:
            goal = state.get("goal", "query_all")
            if goal == "query_active":
                cur.execute(f"SELECT * FROM {table} WHERE status='ACTIVE'")
            else:
                cur.execute(f"SELECT * FROM {table}")
        # Convert to JSON-safe dicts using d for column names
        cols = [d for d in (cur.description or [])]
        data = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        # Drop temp table
        conn2 = sqlite3.connect(DB_FILE)
        conn2.execute(f"DROP TABLE IF EXISTS {table}")
        conn2.commit()
        conn2.close()
        return {"result": json.dumps({"tables": table_names, "schema": {table: schema}, "data": data}, ensure_ascii=False)}
    except Exception as e:
        return {"error": f"Query failed: {e}"}  # [18][3]

# 6) Wiring with fail-fast and cleanup
builder = StateGraph(S)
builder.add_node("intent", intent_node)
builder.add_node("fetch", fetch_node)
builder.add_node("load", load_node)
builder.add_node("query", query_node)
builder.add_edge(START, "intent")

def after_intent(state: S):
    return END if state.get("error") else "fetch"

builder.add_conditional_edges("intent", after_intent, {"fetch": "fetch"})

def after_fetch(state: S):
    return END if state.get("error") or not state.get("rows") else "load"

builder.add_conditional_edges("fetch", after_fetch, {"load": "load"})

def after_load(state: S):
    return END if state.get("error") or not state.get("table") else "query"

builder.add_conditional_edges("load", after_load, {"query": "query"})
builder.add_edge("query", END)

app = builder.compile()

def run_once(user_text: str):
    # fresh db
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    try:
        for st in app.stream({"messages": [HumanMessage(content=user_text)]}, stream_mode="values"):
            if "error" in st:
                print("Error:", st["error"])
                break
            if st.get("messages"):
                last = st["messages"][-1]
                print(getattr(last, "content", str(last)))
        out = app.invoke({"messages": [HumanMessage(content=user_text)]})
        if isinstance(out, dict) and out.get("error"):
            print("FINAL ERROR:", out["error"])
        else:
            print("FINAL:", out.get("result") or getattr(out.get("messages", [])[-1], "content", out))
    finally:
        # delete all temp tables and file
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for (tname,) in cur.fetchall():
                try:
                    cur.execute(f"DROP TABLE IF EXISTS {tname}")
                except Exception:
                    pass
            conn.commit()
            conn.close()
        except Exception:
            pass
        if os.path.exists(DB_FILE):
            try:
                os.remove(DB_FILE)
            except Exception:
                pass

if __name__ == "__main__":
    # Examples:
    # run_once("give me all the users")
    # run_once("give me the active users")
    # run_once("Generate a report from the active users")
    run_once("give me the active users")
