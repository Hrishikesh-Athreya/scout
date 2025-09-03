from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
import json
import os
from typing import Dict, Any
import time
import asyncio

# Import your existing agents
from agents.db.agent import process_user_query_with_agent
from agents.docs.agent import process_document_generation_request
from agents.comms.agent import process_message_request

def create_supervisor_workflow_tools():
    """Create tools that orchestrate DB → Docs → Comms workflow with error handling"""
    
    @tool
    def plan_report_workflow(user_query: str) -> str:
        """PHASE 1: Plan the complete report workflow (LLM intervention)"""
        return json.dumps({
            "query": user_query,
            "status": "planned",
            "next_phase": "execute_db_query",
            "workflow_steps": ["db_agent", "docs_agent", "comms_agent"]
        })
    
    @tool
    def execute_db_query(workflow_plan_json: str) -> str:
        """PHASE 2: Execute DB agent to get data (NO LLM intervention)"""
        try:
            print("🗄️ PHASE 2: Executing DB query to get data...")
            
            workflow_plan = json.loads(workflow_plan_json)
            user_query = workflow_plan.get('query', '')
            
            if not user_query:
                return json.dumps({
                    "error": "No query provided for DB agent",
                    "status": "error"
                })
            
            print(f"📊 Calling DB agent with query: {user_query}")
            start_time = time.time()
            
            # Call the DB agent synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            db_result = loop.run_until_complete(process_user_query_with_agent(user_query))
            loop.close()
            
            execution_time = time.time() - start_time
            
            if db_result.get('status') != 'success':
                error_msg = db_result.get('error', 'Unknown DB agent error')
                print(f"❌ DB agent failed: {error_msg}")
                return json.dumps({
                    "error": f"DB agent failed: {error_msg}",
                    "status": "error"
                })
            
            db_data = db_result.get('response', '')
            print(f"✅ DB agent completed in {execution_time:.2f}s")
            print(f"📄 DB response length: {len(db_data)} characters")
            
            return json.dumps({
                "db_data": db_data,
                "original_query": user_query,
                "execution_time": f"{execution_time:.2f}s",
                "status": "success",
                "next_phase": "generate_document"
            })
            
        except Exception as e:
            print(f"❌ DB agent execution failed: {e}")
            return json.dumps({
                "error": f"DB agent execution failed: {str(e)}",
                "status": "error"
            })
    
    @tool
    def generate_document_report(db_result_json: str) -> str:
        """PHASE 3: Generate document using Docs agent (NO LLM intervention)"""
        try:
            print("📄 PHASE 3: Generating document report...")
            
            db_result = json.loads(db_result_json)
            
            if db_result.get('status') != 'success':
                return json.dumps({
                    "error": "Cannot generate document - DB query failed",
                    "status": "error"
                })
            
            db_data = db_result.get('db_data', '')
            original_query = db_result.get('original_query', '')
            
            # Create document generation prompt
            docs_prompt = f"""
            Generate a professional report based on the following data query and results:
            
            **Original Query:** {original_query}
            
            **Data Results:** {db_data}
            
            Create a comprehensive report with:
            - Report heading based on the query
            - Q&A sections explaining the data
            - Tables showing the data in organized format
            - Use template2 for more detailed reports
            """
            
            print(f"📊 Calling Docs agent to generate report...")
            start_time = time.time()
            
            # Call the Docs agent synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            docs_result = loop.run_until_complete(process_document_generation_request(docs_prompt))
            loop.close()
            
            execution_time = time.time() - start_time
            
            if docs_result.get('status') != 'success':
                error_msg = docs_result.get('error', 'Unknown Docs agent error')
                print(f"❌ Docs agent failed: {error_msg}")
                return json.dumps({
                    "error": f"Docs agent failed: {error_msg}",
                    "status": "error"
                })
            
            docs_response = docs_result.get('response', '')
            print(f"✅ Docs agent completed in {execution_time:.2f}s")
            print(f"📋 Document generated successfully")
            
            return json.dumps({
                "document_response": docs_response,
                "original_query": original_query,
                "db_data": db_data,
                "execution_time": f"{execution_time:.2f}s",
                "status": "success",
                "next_phase": "send_communications"
            })
            
        except Exception as e:
            print(f"❌ Docs agent execution failed: {e}")
            return json.dumps({
                "error": f"Docs agent execution failed: {str(e)}",
                "status": "error"
            })
    
    @tool
    def send_communications(docs_result_json: str, recipients_info: str) -> str:
        """PHASE 4: Send report via Comms agent (NO LLM intervention)"""
        try:
            print("📬 PHASE 4: Sending communications...")
            
            docs_result = json.loads(docs_result_json)
            
            if docs_result.get('status') != 'success':
                return json.dumps({
                    "error": "Cannot send communications - Document generation failed",
                    "status": "error"
                })
            
            original_query = docs_result.get('original_query', '')
            document_response = docs_result.get('document_response', '')
            
            # Extract report file URL from document response (this would be in the actual API response)
            # For now, we'll simulate this
            report_file_url = "https://example.com/generated-report.pdf"
            
            # Create communications prompt with recipients
            comms_prompt = f"""
            Send the generated report to the specified recipients:
            
            **Report Details:** {original_query}
            **Recipients:** {recipients_info}
            **File URL:** {report_file_url}
            
            Send via appropriate channels (email/slack) based on recipient format.
            """
            
            print(f"📧 Calling Comms agent to send report...")
            start_time = time.time()
            
            # Call the Comms agent synchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            comms_result = loop.run_until_complete(process_message_request(comms_prompt))
            loop.close()
            
            execution_time = time.time() - start_time
            
            if comms_result.get('status') != 'success':
                error_msg = comms_result.get('error', 'Unknown Comms agent error')
                print(f"❌ Comms agent failed: {error_msg}")
                return json.dumps({
                    "error": f"Comms agent failed: {error_msg}",
                    "status": "error"
                })
            
            comms_response = comms_result.get('response', '')
            print(f"✅ Comms agent completed in {execution_time:.2f}s")
            print(f"📨 Report sent successfully")
            
            return json.dumps({
                "communications_response": comms_response,
                "report_file_url": report_file_url,
                "recipients": recipients_info,
                "execution_time": f"{execution_time:.2f}s",
                "status": "success",
                "workflow_complete": True
            })
            
        except Exception as e:
            print(f"❌ Comms agent execution failed: {e}")
            return json.dumps({
                "error": f"Comms agent execution failed: {str(e)}",
                "status": "error"
            })
    
    return [plan_report_workflow, execute_db_query, generate_document_report, send_communications]

def build_supervisor_system_prompt() -> str:
    """Build system prompt for supervisor agent"""
    
    return """You are a supervisor agent that orchestrates a complete report workflow using three specialized agents:

**WORKFLOW OVERVIEW:**
1. **DB Agent**: Queries database and retrieves data
2. **Docs Agent**: Generates professional reports from the data
3. **Comms Agent**: Sends reports to specified recipients via email/Slack

**YOUR RESPONSIBILITY:**
Coordinate these agents in sequence, ensuring each step completes successfully before proceeding to the next.

**4-PHASE WORKFLOW:**
1. **PHASE 1 - PLANNING (LLM)**: Plan the complete workflow based on user request
2. **PHASE 2 - DATA RETRIEVAL (Deterministic)**: Execute DB agent to get required data
3. **PHASE 3 - REPORT GENERATION (Deterministic)**: Use Docs agent to create professional report
4. **PHASE 4 - COMMUNICATION (Deterministic)**: Send report via Comms agent to recipients

**WORKFLOW RULES:**
1. Always start with plan_report_workflow to acknowledge and plan the request
2. Call execute_db_query with the workflow plan to get data from database
3. Call generate_document_report with DB results to create the report
4. Call send_communications with document results and recipient info to distribute
5. **CRITICAL**: If ANY agent fails, STOP immediately and return the error - do not continue
6. Provide clear status updates for each phase
7. Report final success with summary of all completed steps

**ERROR HANDLING:**
- Check the "status" field in each agent response
- If status != "success", stop workflow and report the error
- Do not proceed to next agent if current agent failed
- Provide clear error messages indicating which agent failed and why

**EXPECTED USER INPUT FORMAT:**
Users will provide:
- Data query/request (for DB agent)
- Report requirements (for Docs agent)  
- Recipient information - emails, Slack channels, etc. (for Comms agent)

**EXAMPLE WORKFLOW:**

User: "Get all active users data, generate a user activity report, and send it to john@company.com and #management channel"

1. plan_report_workflow("Get all active users data, generate report, send to recipients")
2. execute_db_query(plan_info) → Gets user data from database
3. generate_document_report(db_results) → Creates professional user activity report  
4. send_communications(report_info, "john@company.com and #management channel") → Sends via email and Slack

**SUCCESS CRITERIA:**
- All three agents complete successfully
- Data retrieved, report generated, and communications sent
- Provide comprehensive summary of the entire workflow

Always follow this exact sequence and stop immediately if any agent reports an error.
"""

def build_supervisor_agent():
    """Build supervisor agent that orchestrates DB → Docs → Comms workflow"""
    
    # Create workflow tools
    workflow_tools = create_supervisor_workflow_tools()
    
    # Initialize model  
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Build system prompt
    system_prompt = build_supervisor_system_prompt()
    
    # Create agent
    agent = create_react_agent(
        model=model,
        tools=workflow_tools,
        prompt=system_prompt
    )
    
    return agent

# Main processing function
async def process_supervisor_request(user_input: str) -> Dict[str, Any]:
    """Process complete report workflow request through supervisor"""
    
    try:
        # Use the supervisor agent
        supervisor_agent = build_supervisor_agent()
        
        print(f"🎯 Starting supervisor workflow for: {user_input[:100]}...")
        
        # Let the supervisor handle the complete workflow
        result = supervisor_agent.invoke({
            "messages": [{"role": "user", "content": user_input}]
        })
        
        # Extract the final response
        if result and 'messages' in result and result['messages']:
            final_message = result['messages'][-1]
            response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
            
            return {
                "user_query": user_input,
                "response": response_content,
                "status": "success"
            }
        else:
            return {
                "user_query": user_input,
                "error": "No response from supervisor",
                "status": "error"
            }
            
    except Exception as e:
        return {
            "user_query": user_input,
            "error": str(e),
            "status": "error"
        }

# Convenience function for testing
def run_supervisor(query: str, recipients: str = ""):
    """Synchronous wrapper for supervisor processing"""
    
    full_query = f"{query}. Send the report to: {recipients}" if recipients else query
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(process_supervisor_request(full_query))
        return result
    finally:
        loop.close()

# Example usage and testing
if __name__ == "__main__":
    test_queries = [
        {
            "query": "Get all active users in engineering department, generate a user activity report",
            "recipients": "john@company.com, jane@company.com, #engineering-team"
        },
        {
            "query": "Fetch payment data for the last quarter, create financial summary report",
            "recipients": "finance@company.com, #finance-reports"
        },
        {
            "query": "Query user data and payment information, generate combined analytics report",
            "recipients": "analytics@company.com, #data-team, C09BQEU1HCM"
        }
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"🎯 Supervisor Test {i}")
        print('='*80)
        
        result = run_supervisor(test["query"], test["recipients"])
        
        if result['status'] == 'success':
            print(f"✅ Workflow completed successfully:")
            print(f"{result['response']}")
        else:
            print(f"❌ Workflow failed: {result['error']}")
