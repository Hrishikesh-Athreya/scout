# supervisor/supervisor.py
# A supervisor that routes tasks between CommsAgent and DocsAgent (Gemini model).
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

from agents.comms.agent import build_comms_agent
from agents.docs.agent import build_docs_agent
from agents.db.agent import build_db_agent

# 1) Define a typed state schema for the graph (not plain dict)
class SupervisorState(TypedDict, total=False):
    # Minimal shared keys; LangGraph will carry these between nodes
    messages: list  # LangChain-style list of chat messages
    result: str     # Optional final result string

# 2) Build worker agents (can be separate services; here in-process)
comms_agent = build_comms_agent()   # this can use any model internally
docs_agent = build_docs_agent()     # this can use any model internally
db_agent = build_db_agent()       # optional third agent

# 3) Expose worker agents as handoff tools available to the supervisor
@tool
def assign_to_comms_agent(task: str) -> str:
    """Delegate a subtask to the Comms Agent; argument should describe the work."""
    out = comms_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return out["messages"][-1].content if "messages" in out else str(out)

@tool
def assign_to_docs_agent(task: str) -> str:
    """Delegate a subtask to the Docs Agent; argument should describe the work."""
    out = docs_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return out["messages"][-1].content if "messages" in out else str(out)

@tool
def assign_to_db_agent(task: str) -> str:
    """Delegate a subtask to the DB Agent; argument should describe the work."""
    out = db_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return out["messages"][-1].content if "messages" in out else str(out)

# 4) Create the supervisor agent that only delegates (Gemini)
supervisor_llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0)
supervisor_agent = create_react_agent(
    supervisor_llm,
    tools=[assign_to_comms_agent, assign_to_docs_agent],  # add assign_to_db_agent if present
    prompt=(
        "You are a supervisor that assigns work to specialized agents.\n"
        "- Use assign_to_comms_agent for email/Slack tasks.\n"
        "- Use assign_to_docs_agent for PDF/text extraction/redaction tasks.\n"
        "- Use assign_to_db_agent for DB/data retrieval tasks.\n"
        "Delegate one step at a time. Do not perform work yourself."
    ),
)
supervisor_agent.name = "supervisor"

# 5) Compose the graph with a proper state schema
builder = StateGraph(SupervisorState)
builder.add_node("supervisor", supervisor_agent)
builder.add_node("comms_agent", comms_agent)
builder.add_node("docs_agent", docs_agent)
builder.add_node("db_agent", db_agent)

# Edges: supervisor decides, worker returns to supervisor
builder.add_edge(START, "supervisor")
builder.add_edge("comms_agent", "supervisor")
builder.add_edge("docs_agent", "supervisor")
builder.add_edge("db_agent", "supervisor")

# Allow supervisor to end when finished
builder.add_edge("supervisor", END)

graph = builder.compile()

def get_graph():
    return graph
