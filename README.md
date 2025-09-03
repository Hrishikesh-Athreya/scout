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

Slack:
curl --location 'https://scout-shqtd6.5sc6y6-4.usa-e2.cloudhub.io/comms/slack' \
--header 'Content-Type: application/json' \
--data '{
    "fileUrl": "https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/24b2b8e8-9080-4519-9674-d3f3aa7a2ff3.pdf",
    "channelId": "C09BQEU1HCM",
    "threadId": "1756882046.433939",
    "channels": ["C09BQEU1HCM", "C09BRGJPQ58"]
}'
Email:
curl --location 'https://scout-shqtd6.5sc6y6-4.usa-e2.cloudhub.io/comms/email' \
--header 'Content-Type: application/json' \
--data-raw '{
    "fileUrl": "https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/b75dc19a-dbed-4993-86ff-ebdf8ed1a47d.pdf",
    "recipients": ["hrishikesha40@gmail.com"]
}'

```


```
Give me the agent.py and tools.json for a docs/report generation agent that uses this api as a tool with optional parameters if needed. We supply it with a prompt to generate a report on and some data, it has to figure out the rest, put in the format the api expects and call the api to get the report back, in the api body if we arent using any fields, keep them empyty


Template 1 to use:
curl --location 'https://scout-shqtd6.5sc6y6-4.usa-e2.cloudhub.io/document/generate' \
--header 'Content-Type: application/json' \
--data '{
    "template": "template1",
    "documentValues": {
        "reportHeading": "Q&A Section",
        "heading0": "What is MuleSoft?",
        "answer0": "MuleSoft is an integration platform.",
        "heading1": "What is DataWeave?",
        "answer1": "DataWeave is MuleSoft'\''s transformation language.",
        "heading2": "Is MuleSoft part of Salesforce?",
        "answer2": "Yes, it was acquired by Salesforce in 2018."
        "table0Heading": "Integration Types",
        "table0Column0": "Type",
        "table0Column1": "Protocol",
        "table0Column2": "Format",
        "table0Column3": "Security",
        "table0Column4": "Latency",
        "table0Column5": "Throughput",
        "table0Column6": "Use Case",
        "table0Items": [
            {
                "value0": "API",
                "value1": "HTTP",
                "value2": "JSON",
                "value3": "OAuth2",
                "value4": "Low",
                "value5": "High",
                "value6": "Public APIs"
            },
            {
                "value0": "File-based",
                "value1": "FTP",
                "value2": "CSV",
                "value3": "None",
                "value4": "High",
                "value5": "Medium",
                "value6": "Batch Transfers"
            }
        ],
        "table1Heading": "Environment Configurations",
        "table1Column0": "Env",
        "table1Column1": "URL",
        "table1Column2": "Username",
        "table1Column3": "Timeout",
        "table1Column4": "Retries",
        "table1Column5": "Logging",
        "table1Column6": "Notes",
        "table1Items": [
            {
                "value0": "DEV",
                "value1": "https://dev.example.com",
                "value2": "devuser",
                "value3": "30s",
                "value4": "3",
                "value5": "Enabled",
                "value6": "For development use"
            },
            {
                "value0": "PROD",
                "value1": "https://prod.example.com",
                "value2": "produser",
                "value3": "60s",
                "value4": "5",
                "value5": "Enabled",
                "value6": "Live traffic"
            }
        ]
    },
    "enablePasswordProtection": false
}'


Template 2 to use:
curl --location 'https://scout-shqtd6.5sc6y6-4.usa-e2.cloudhub.io/document/generate' \
--header 'Content-Type: application/json' \
--data '{
    "template": "template2",
    "documentValues": {
        "reportHeading": "Q&A Section",
        "heading0": "What is MuleSoft?",
        "answer0": "MuleSoft is an integration platform.",
        "heading1": "What is DataWeave?",
        "answer1": "DataWeave is MuleSoft'\''s transformation language.",
        "heading2": "Is MuleSoft part of Salesforce?",
        "answer2": "Yes, it was acquired by Salesforce in 2018.",
        "heading3": "I'\''m 4 years old",
        "answer3": "You are the youngest person ever",
        "table0Heading": "Integration Types",
        "table0Column0": "Type",
        "table0Column1": "Protocol",
        "table0Column2": "Format",
        "table0Column3": "Security",
        "table0Column4": "Latency",
        "table0Column5": "Throughput",
        "table0Column6": "Use Case",
        "table0Items": [
            {
                "value0": "API",
                "value1": "HTTP",
                "value2": "JSON",
                "value3": "OAuth2",
                "value4": "Low",
                "value5": "High",
                "value6": "Public APIs"
            },
            {
                "value0": "File-based",
                "value1": "FTP",
                "value2": "CSV",
                "value3": "None",
                "value4": "High",
                "value5": "Medium",
                "value6": "Batch Transfers"
            }
        ],
        "table1Heading": "Environment Configurations",
        "table1Column0": "Env",
        "table1Column1": "URL",
        "table1Column2": "Username",
        "table1Column3": "Timeout",
        "table1Column4": "Retries",
        "table1Column5": "Logging",
        "table1Column6": "Notes",
        "table1Items": [
            {
                "value0": "DEV",
                "value1": "https://dev.example.com",
                "value2": "devuser",
                "value3": "30s",
                "value4": "3",
                "value5": "Enabled",
                "value6": "For development use"
            },
            {
                "value0": "PROD",
                "value1": "https://prod.example.com",
                "value2": "produser",
                "value3": "60s",
                "value4": "5",
                "value5": "Enabled",
                "value6": "Live traffic"
            }
        ]
    },
    "enablePasswordProtection": false
}'


```


```
Now I want a supervisor.py that gets a query for a report and where/who to send it. It plans out which of the agents to call and in what order to get the data from the db and then send it to the right people. It should use the db agent to get the data, then use the docs agent to generate a report on that data, then use the comms agent to send that report to the right people. It should handle errors and stop if any agent fails and return the error message.
```
