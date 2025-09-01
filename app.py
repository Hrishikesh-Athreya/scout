# Simplified app.py
import asyncio
from agents.db.agent import process_user_query_with_agent
import dotenv
dotenv.load_dotenv()

from langchain.globals import set_verbose, set_debug

# Enable verbose logging globally
set_verbose(True)
set_debug(True)  # For even more detailed output

async def main():
    """Simple main function using enhanced DB agent"""
    
    test_queries = [
        # "Show me all active users with their emails",
        # "Find users in engineering who have made orders",
        # "What's the average order amount by business unit?",
        # "List users who haven't made any orders recently"
        # "Give me a JSON array of all ACTIVE users with their names and emails"
        # "How many users are active"
        # "Give me the names of all users",
        # "How many payments are made"
        "who all made what payments"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: {query}")
        print("-" * 50)
        
        result = await process_user_query_with_agent(query)
        
        if result['status'] == 'success':
            print(f"✅ Response:\n{result['response']}")
        else:
            print(f"❌ Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())
