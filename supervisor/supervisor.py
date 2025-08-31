# supervisor/supervisor.py
# A supervisor that routes tasks between CommsAgent, DocsAgent, and DB Agent (Gemini supervisor).
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

from agents.comms.agent import build_comms_agent
from agents.docs.agent import build_docs_agent
from agents.db.agent import build_db_agent

# Typed state schema with additive messages list
class SupervisorState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    result: str

# Build worker agents
comms_agent = build_comms_agent()
docs_agent = build_docs_agent()
db_agent = build_db_agent()

# Handoff tools to call workers
@tool
def assign_to_comms_agent(task: str) -> str:
    out = comms_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return out["messages"][-1].content if "messages" in out else str(out)

@tool
def assign_to_docs_agent(task: str) -> str:
    out = docs_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return out["messages"][-1].content if "messages" in out else str(out)

@tool
def assign_to_db_agent(task: str) -> str:
    out = db_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return out["messages"][-1].content if "messages" in out else str(out)

# Supervisor (Gemini)
supervisor_llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0)
supervisor_agent = create_react_agent(
    supervisor_llm,
    tools=[assign_to_comms_agent, assign_to_docs_agent, assign_to_db_agent],
    prompt=(
        "You are a supervisor that assigns work to specialized agents.\n"
        "- Use assign_to_comms_agent for email/Slack tasks.\n"
        "- Use assign_to_docs_agent for PDF tasks.\n"
        "- Use assign_to_db_agent for DB/data tasks.\n"
        "Delegate one step at a time. Do not perform work yourself."
    ),
)
supervisor_agent.name = "supervisor"

# Compose graph
builder = StateGraph(SupervisorState)
builder.add_node("supervisor", supervisor_agent)
builder.add_node("comms_agent", comms_agent)
builder.add_node("docs_agent", docs_agent)
builder.add_node("db_agent", db_agent)

builder.add_edge(START, "supervisor")
builder.add_edge("comms_agent", "supervisor")
builder.add_edge("docs_agent", "supervisor")
builder.add_edge("db_agent", "supervisor")
builder.add_edge("supervisor", END)

graph = builder.compile()

def get_graph():
    return graph
