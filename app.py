# Simplified app.py
import asyncio
from agents.db.agent import process_user_query_with_agent
import dotenv
dotenv.load_dotenv()

from langchain.globals import set_verbose, set_debug
from flask import Flask, request
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'

# it is a post request with a json body containing the query
@app.route('/query', methods=['POST'])
def handle_query():
    """Handle user query via enhanced DB agent"""
    body = request.json or {}
    query = body.get('query', '')
    result = asyncio.run(process_user_query_with_agent(query))
    if result['status'] == 'success':
        return f"✅ Response:\n{result['response']}"
    else:
        return f"❌ Error: {result['error']}"
# curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"query": "How many payments are made"}'
# curl -X POST http://scout-agent.arnavdewan.dev/query -H "Content-Type: application/json" -d '{"query": "How many payments are made"}'

# async def main():
#     """Simple main function using enhanced DB agent"""
#
#     test_queries = [
#         # "Show me all active users with their emails",
#         # "Find users in engineering who have made orders",
#         # "What's the average order amount by business unit?",
#         # "List users who haven't made any orders recently"
#         # "Give me a JSON array of all ACTIVE users with their names and emails"
#         # "How many users are active"
#         # "Give me the names of all users",
#         # "How many payments are made"
#         # "who all made what payments"
#         "How much does alice pay totally, out put in a JSON with the names of payments and final total. Output in JSON format only. Get all the payments she has made."
#     ]
#
#     for query in test_queries:
#         print(f"\n🔍 Query: {query}")
#         print("-" * 50)
#
#         result = await process_user_query_with_agent(query)
#
#         if result['status'] == 'success':
#             print(f"✅ Response:\n{result['response']}")
#         else:
#             print(f"❌ Error: {result['error']}")
#
# if __name__ == "__main__":
#     asyncio.run(main())
