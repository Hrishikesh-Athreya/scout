# etl_sql_agent.py
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
from langchain_core.messages import HumanMessage, SystemMessage

# Use the db agent to decide params & call the HTTP tool
from agents.db.agent import build_db_agent  # must return JSON-only content from tool [db_get_users] [ref: web:229]

# Minimal SQL agent (schema + query) if needed
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langgraph.prebuilt import create_react_agent

# Env
load_dotenv(override=True)
assert os.getenv("GOOGLE_API_KEY"), "GOOGLE_API_KEY not set"  # [ref: web:99]

DB_FILE = "etl_sql_temp.db"

def llm_fast():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )  # [ref: web:42]

def build_sql_agent():
    # Proper object construction and use; no [] indexing on objects
    db = SQLDatabase.from_uri(f"sqlite:///{DB_FILE}")  # [ref: web:47]
    tk = SQLDatabaseToolkit(db=db, llm=llm_fast())  # [ref: web:213]
    tools = [t for t in tk.get_tools() if t.name in {"sql_db_schema", "sql_db_query"}]
    agent = create_react_agent(llm_fast(), tools, prompt="Use schema tools then one SELECT; return result only.")
    agent.name = "sql_agent"
    return agent

sql_agent = build_sql_agent()
db_agent = build_db_agent()  # from agents/db/agent.py [ref: web:229]

# SQLite helpers
def infer_sqlite_type(value: Any) -> str:
    if value is None: return "TEXT"
    if isinstance(value, bool): return "INTEGER"
    if isinstance(value, int): return "INTEGER"
    if isinstance(value, float): return "REAL"
    return "TEXT"

def unify_keys(rows: List[Dict[str, Any]]) -> List[str]:
    keys: set[str] = set()
    for r in rows:
        keys.update(r.keys())
    return sorted(keys)

def infer_schema(rows: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    sample = next((r for r in rows if isinstance(r, dict) and r), {})
    return [(k, infer_sqlite_type(sample.get(k))) for k in unify_keys(rows)]

def is_sql(text: str) -> bool:
    return bool(re.match(r"^\s*(select|with)\b", text or "", re.IGNORECASE))

# Graph state
class S(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    rows: List[Dict[str, Any]]
    table: str
    result: str
    error: str

# Nodes
def decide_and_fetch_node(state: S) -> S:
    try:
        # Last human message
        user_msg = next((m for m in reversed(state.get("messages", []))
                         if getattr(m, "type", None) == "human" or (isinstance(m, dict) and m.get("role") == "user")), None)
        user_text = getattr(user_msg, "content", "") if user_msg and not isinstance(user_msg, dict) else (user_msg or {}).get("content", "")
        out = db_agent.invoke({"messages": [HumanMessage(content=user_text)]})  # [ref: web:229]
        content = out["messages"][-1].content if isinstance(out, dict) and out.get("messages") else str(out)
        # handle possible code fences
        content_str = content.strip()
        if content_str.startswith("```
            content_str = content_str.strip("`").strip()
            if content_str.lower().startswith("json"):
                content_str = content_str[4:].strip()
        rows = json.loads(content_str) if isinstance(content_str, str) else content_str
        if not isinstance(rows, list):
            return {"error": "DB agent did not return a JSON list"}
        if not rows:
            return {"error": "No rows returned from DB"}
        return {"rows": rows, "messages": [{"role": "assistant", "content": f"Fetched {len(rows)} rows"}]}
    except Exception as e:
        return {"error": f"DB agent fetch failed: {e}"}  # [ref]

def load_to_sqlite_node(state: S) -> S:
    rows = state.get("rows", [])
    if not rows:
        return {"error": "No rows to load"}
    table = f"t_{uuid.uuid4().hex[:8]}"
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cols = [("uid", "TEXT")] + infer_schema(rows)
        cur.execute(f"CREATE TABLE {table} ({', '.join([f'{n} {t}' for n,t in cols])})")
        keys = [n for n, _ in cols]
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

def llm_sql_node(state: S) -> S:
    table = state.get("table")
    if not table:
        return {"error": "No table to query"}  # [ref]
    # Get user question
    user_msg = next((m for m in reversed(state.get("messages", []))
                     if getattr(m, "type", None) == "human" or (isinstance(m, dict) and m.get("role") == "user")), None)
    user_text = getattr(user_msg, "content", "") if user_msg and not isinstance(user_msg, dict) else (user_msg or {}).get("content", "")
    try:
        # Build schema text
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [r for r in cur.fetchall()]  # [ref]
        cur.execute(f"PRAGMA table_info('{table}')")
        info = cur.fetchall()
        schema_lines = []
        for cid, name, typ, notnull, dflt_value, pk in info:  # [ref]
            schema_lines.append(f"{name} {typ}")
        schema_text = f"Tables: {table_names}\nSchema for {table}: " + ", ".join(schema_lines)
        # If the user gave SQL, execute directly
        if is_sql(user_text):
            cur.execute(user_text)
            cols = [d for d in (cur.description or [])]
            data = [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.close()
            # Drop and cleanup
            conn2 = sqlite3.connect(DB_FILE)
            conn2.execute(f"DROP TABLE IF EXISTS {table}")
            conn2.commit()
            conn2.close()
            return {"result": json.dumps({"sql": user_text, "data": data}, ensure_ascii=False)}
        # Else ask LLM for one SELECT
        sys = SystemMessage(
            content=(
                "Generate exactly one valid SQLite SELECT that answers the user request.\n"
                f"Use only the provided table {table} and its columns.\n"
                "- No commentary or code fences; return SQL only."
            )
        )
        prompt = HumanMessage(content=f"{schema_text}\nUser request: {user_text}\nSQL:")
        sql_text = llm_fast().invoke([sys, prompt]).content.strip()  # [ref]
        cur.execute(sql_text)
        cols = [d for d in (cur.description or [])]
        data = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        # Drop temp table after answering
        conn2 = sqlite3.connect(DB_FILE)
        conn2.execute(f"DROP TABLE IF EXISTS {table}")
        conn2.commit()
        conn2.close()
        return {"result": json.dumps({"sql": sql_text, "data": data}, ensure_ascii=False)}
    except Exception as e:
        return {"error": f"SQL generation/execution failed: {e}"}

# Graph wiring
builder = StateGraph(S)  # [ref]
builder.add_node("decide_and_fetch", decide_and_fetch_node)
builder.add_node("load_sqlite", load_to_sqlite_node)
builder.add_node("llm_sql", llm_sql_node)
builder.add_edge(START, "decide_and_fetch")

def after_fetch(state: S):
    # Return a valid label or END sentinel; do not return raw strings elsewhere
    return END if state.get("error") or not state.get("rows") else "load_sqlite"

builder.add_conditional_edges("decide_and_fetch", after_fetch, {"load_sqlite": "load_sqlite"})

def after_load(state: S):
    return END if state.get("error") or not state.get("table") else "llm_sql"

builder.add_conditional_edges("load_sqlite", after_load, {"llm_sql": "llm_sql"})
builder.add_edge("llm_sql", END)

app = builder.compile()  # [ref]

def run_once(user_text: str):
    # Fresh DB per run
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    try:
        # Stream minimal values for visibility
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
        # Best-effort cleanup of any tables and file
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for (tname,) in cur.fetchall():
                cur.execute(f"DROP TABLE IF EXISTS {tname}")
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
