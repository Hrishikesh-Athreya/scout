```
agents/
comms/
tools.json — API tools for email/Slack (JSON Schema + HTTP configs).[](https://langchain-ai.github.io/langgraph/how-tos/tool-calling/)
agent.py — builds CommsAgent from tools.json.[](https://python.langchain.com/docs/tutorials/agents/)
docs/
tools.json — API tools for PDF operations.[](https://langchain-ai.github.io/langgraph/how-tos/tool-calling/)
agent.py — builds DocsAgent from tools.json.
db/
tools.json — API tools for db operations.
agent.py — builds db agent from tools.json.[](https://python.langchain.com/docs/tutorials/agents/)
supervisor/
supervisor.py — supervisor agent and multi‑agent graph composition.[](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/)
common/
tool_loader.py — JSON→tool factory, HTTP executors, safe env interpolation.[](https://langchain-ai.github.io/langgraph/how-tos/tool-calling/)
prompts.py — optional system prompts per agent.[](https://python.langchain.com/docs/tutorials/agents/)
app.py — entry point: compile graph, run an example, or serve.



Give me a simple flow that takes in user input -> uses the db agent to fetch the rows that are needed -> saves those rows and data to temp local sqlite tables for later use -> takes the table names and the schema from the sqlite table to generate an sql query based on the users query -> fetches the required data and then deletes the temp tables and returns the output of the query[](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/)
```
