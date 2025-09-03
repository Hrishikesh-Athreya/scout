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


```
Give me the agent.py and tools.json for a comms agent that sends messages using these apis as tools. It should figure out who to send it to and handle multiple recipients if needed. Send multiple calls if needed to send to all recipients. Mix and match email and slack as needed.

SLACK:
curl --location 'http://localhost:8081/comms/slack' \
--header 'Content-Type: application/json' \
--data '{
    "fileUrl": "https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/24b2b8e8-9080-4519-9674-d3f3aa7a2ff3.pdf",
    "channelId": "C09BQEU1HCM",
    "threadTs": "1756882046.433939"
}'

EMAIL:
curl --location 'http://localhost:8081/comms/email' \
--header 'Content-Type: application/json' \
--data-raw '{
    "fileUrl": "https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/b75dc19a-dbed-4993-86ff-ebdf8ed1a47d.pdf",
    "recipients": ["arnavdewan.dev@gmail.com"]
}'

```


```
Give me the agent.py and tools.json for a report generation agent that uses this api as a tool with optional parameters if needed. We supply it with a prompt to generate a report on and some data, it has to figure out the rest, put in the format the api expects and call the api to get the report back, in the api body if we arent using any fields, keep them empyty


```
