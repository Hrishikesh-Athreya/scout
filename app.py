# # Simplified app.py
# import asyncio
# from agents.db.agent import process_user_query_with_agent
# import dotenv
# dotenv.load_dotenv()
#
# from langchain.globals import set_verbose, set_debug
# from flask import Flask, request
# app = Flask(__name__)
#
# @app.route('/')
# def hello_world():
#     return 'Hello, World!'
#
# # it is a post request with a json body containing the query
# @app.route('/query', methods=['POST'])
# def handle_query():
#     """Handle user query via enhanced DB agent"""
#     body = request.json or {}
#     query = body.get('query', '')
#     result = asyncio.run(process_user_query_with_agent(query))
#     if result['status'] == 'success':
#         return f"✅ Response:\n{result['response']}"
#     else:
#         return f"❌ Error: {result['error']}"
#




# curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"query": "How many payments are made"}'
# curl -X POST https://scout-agent.arnavdewan.dev/query -H "Content-Type: application/json" -d '{"query": "How many payments are made"}'

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



## Report agent example
# import asyncio
# from agents.docs.agent import process_document_generation_request
# import dotenv
# dotenv.load_dotenv()
#
# async def main():
#     """Test document generation agent"""
#
#     test_queries = [
#         # """Generate a comprehensive MuleSoft integration report with:
#         # - Report title: "MuleSoft Integration Guide 2024"
#         # - Q&A section covering: What is MuleSoft? What is DataWeave? Is MuleSoft part of Salesforce? Why choose MuleSoft?
#         # - Integration types comparison table with columns: Type, Protocol, Format, Security, Latency, Throughput, Use Case
#         # - Environment configurations table with: Env, URL, Username, Timeout, Retries, Logging, Notes
#         # - Include sample data for both tables
#         # - Enable password protection""",
#
#         """Create a simple technical document about APIs with:
#         - Title: "API Integration Basics"  
#         - 3 questions: What are APIs? How do REST APIs work? What are the benefits?
#         - One table comparing API types
#         - No password protection needed""",
#         #
#         # """Generate a report on DataWeave transformations including:
#         # - Main heading: "DataWeave Transformation Guide"
#         # - Questions about DataWeave basics, syntax, and use cases
#         # - Comparison table of transformation types
#         # - Configuration examples table"""
#     ]
#
#     for i, query in enumerate(test_queries, 1):
#         print(f"\n{'='*70}")
#         print(f"📄 Test {i}: Document Generation")
#         print('='*70)
#
#         result = await process_document_generation_request(query)
#
#         if result['status'] == 'success':
#             print(f"✅ Response:\n{result['response']}")
#         else:
#             print(f"❌ Error: {result['error']}")
#
# if __name__ == "__main__":
#     asyncio.run(main())


## comms agent example
# import asyncio
# import os
# import sys
# from typing import Dict, Any
# import dotenv
#
# # Load environment variables
# dotenv.load_dotenv()
#
# # Add the project root to Python path for imports
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
#
# from agents.comms.agent import process_message_request
#
# async def test_comms_agent():
#     """Comprehensive test suite for the updated communications agent"""
#
#     print("🚀 Starting Updated Comms Agent Test Suite")
#     print("=" * 80)
#
#     test_cases = [
#         {
#             "name": "Single Email Recipient",
#             "query": "Send the weekly report to arnavdewan.dev@gmail.com. File URL: https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/0f0c58f1-ce2f-4be4-8182-16cb73ad0daf.pdf"
#         },
#         # {
#         #     "name": "Multiple Email Recipients", 
#         #     "query": "Send the quarterly analysis to john@company.com, jane@company.com, alice@company.com. File: https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/q1-analysis.pdf"
#         # },
#         # {
#         #     "name": "Multiple Slack Channels",
#         #     "query": "Share the presentation with channels C09BQEU1HCM, C09BRGJPQ58. File URL: https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/presentation.pdf"
#         # },
#         # {
#         #     "name": "Slack Channels with Thread Reply",
#         #     "query": "Reply to thread 1756882046.433939 in channels C09BQEU1HCM, C09BRGJPQ58 with the updated document. File: https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/updated-doc.pdf"
#         # },
#         # {
#         #     "name": "Mixed Email and Slack Recipients",
#         #     "query": "Send the project update to team@company.com, manager@company.com, and channels C09BQEU1HCM, C09BRGJPQ58. File URL: https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/project-status.pdf"
#         # },
#         # {
#         #     "name": "Email Only with Multiple Recipients",
#         #     "query": "Distribute the newsletter to hrishikesha40@gmail.com, user1@company.com, user2@company.com, user3@company.com. File: https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/newsletter.pdf"
#         # }
#     ]
#
#     results = []
#
#     for i, test_case in enumerate(test_cases, 1):
#         print(f"\n📋 Test Case {i}: {test_case['name']}")
#         print("-" * 60)
#         print(f"Query: {test_case['query'][:100]}{'...' if len(test_case['query']) > 100 else ''}")
#         print("-" * 60)
#
#         try:
#             # Execute the test
#             result = await process_message_request(test_case['query'])
#
#             if result.get('status') == 'success':
#                 print("✅ SUCCESS")
#                 print(f"Response: {result.get('response', 'No response content')}")
#                 results.append({"test": test_case['name'], "status": "✅ PASSED"})
#             else:
#                 print("❌ FAILED")
#                 print(f"Error: {result.get('error', 'Unknown error')}")
#                 results.append({"test": test_case['name'], "status": "❌ FAILED", "error": result.get('error')})
#
#         except Exception as e:
#             print("💥 EXCEPTION")
#             print(f"Exception: {str(e)}")
#             results.append({"test": test_case['name'], "status": "💥 EXCEPTION", "error": str(e)})
#
#     # Print summary
#     print("\n" + "=" * 80)
#     print("📊 TEST SUMMARY")
#     print("=" * 80)
#
#     passed = sum(1 for r in results if "✅" in r['status'])
#     failed = sum(1 for r in results if "❌" in r['status'])
#     exceptions = sum(1 for r in results if "💥" in r['status'])
#
#     print(f"Total Tests: {len(results)}")
#     print(f"✅ Passed: {passed}")
#     print(f"❌ Failed: {failed}")  
#     print(f"💥 Exceptions: {exceptions}")
#     print(f"Success Rate: {(passed/len(results)*100):.1f}%")
#
#     print("\nDetailed Results:")
#     for result in results:
#         status_icon = result['status'].split()[0]
#         print(f"{status_icon} {result['test']}")
#         if 'error' in result:
#             print(f"   Error: {result['error']}")
#
# if __name__ == "__main__":
#     asyncio.run(test_comms_agent())
