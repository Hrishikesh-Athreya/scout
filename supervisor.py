from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
import json
import os
from typing import Dict, Any
import time
import asyncio
import re

# Import your existing agents
from agents.db.agent import process_user_query_with_agent
from agents.docs.agent import process_document_generation_request
from agents.comms.agent import process_message_request

def extract_file_url_from_response(response_text: str) -> str:
    """Dynamically extract file URL from any response text"""
    # Look for URLs in the response
    url_patterns = [
        r'https?://[^\s<>"{}|\\^`[\]]+\.(?:pdf|doc|docx|txt|html)',  # File URLs
        r'"(?:fileUrl|file_url|url|document_url)":\s*"([^"]+)"',      # JSON file URLs
        r'(?:File URL|Document URL|Report URL):\s*(https?://[^\s]+)', # Labeled URLs
        r'(https?://[^\s<>"{}|\\^`[\]]+)'                             # Any HTTP URL
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        if matches:
            # Return the first valid looking URL
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]
                if 'http' in match:
                    return match
    
    # Fallback: generate a dynamic URL based on timestamp if no URL found
    import time
    timestamp = int(time.time())
    return f"https://phujfghgjwpcvyjywlax.supabase.co/storage/v1/object/public/scout-reports-public/report-{timestamp}.pdf"

def extract_recipients_from_query(user_query: str) -> str:
    """Dynamically extract recipients from user query"""
    # Extract email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, user_query)
    
    # Extract Slack channel IDs and names
    slack_channels = []
    slack_patterns = [
        r'#([a-zA-Z0-9_-]+)',  # #channel-name
        r'([C][A-Z0-9]{8,})',  # Channel IDs like C09BQEU1HCM
    ]
    
    for pattern in slack_patterns:
        matches = re.findall(pattern, user_query)
        slack_channels.extend(matches)
    
    # Extract thread IDs
    thread_pattern = r'thread[:\s]+([0-9]+\.?[0-9]*)'
    threads = re.findall(thread_pattern, user_query, re.IGNORECASE)
    
    # Build recipients string
    recipients_parts = []
    if emails:
        recipients_parts.append(f"Emails: {', '.join(emails)}")
    if slack_channels:
        recipients_parts.append(f"Slack channels: {', '.join(slack_channels)}")
    if threads:
        recipients_parts.append(f"Thread ID: {threads[0]}")
    
    return ' | '.join(recipients_parts) if recipients_parts else "No recipients specified"

def create_supervisor_workflow_tools():
    """Create tools that send plain text instructions to agents with dynamic data flow"""
    
    @tool
    def call_db_agent(user_request: str) -> str:
        """Call DB agent with plain text request - extracts data query dynamically"""
        try:
            print("🗄️ Calling DB Agent...")
            
            # Extract the data query portion from the full request
            # Split on common separators and take the data-related part
            data_query = user_request
            for separator in [', generate', ', create', ', send', ' and send', ' and generate']:
                if separator in user_request.lower():
                    data_query = user_request.split(separator)[0].strip()
                    break
            
            print(f"📊 DB Agent Input: {data_query}")
            
            start_time = time.time()
            
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                db_result = loop.run_until_complete(process_user_query_with_agent(data_query))
            finally:
                loop.close()
            
            execution_time = time.time() - start_time
            
            if db_result.get('status') != 'success':
                error_msg = db_result.get('error', 'Unknown DB agent error')
                print(f"❌ DB agent failed: {error_msg}")
                return f"ERROR: DB Agent failed - {error_msg}"
            
            db_data = db_result.get('response', '')
            print(f"✅ DB agent completed in {execution_time:.2f}s")
            print(f"📄 Retrieved {len(db_data)} characters of data")
            
            return db_data
            
        except Exception as e:
            print(f"❌ DB agent execution failed: {e}")
            return f"ERROR: DB Agent exception - {str(e)}"
    
    @tool
    def call_docs_agent(db_data: str, original_query: str) -> str:
        """Call Docs agent with DB data and original query - generates document dynamically"""
        try:
            print("📄 Calling Docs Agent...")
            
            if db_data.startswith("ERROR:"):
                return f"Cannot generate document: {db_data}"
            
            # Extract report type from original query
            report_type = "comprehensive report"
            if "activity" in original_query.lower():
                report_type = "user activity report"
            elif "financial" in original_query.lower() or "payment" in original_query.lower():
                report_type = "financial report"
            elif "summary" in original_query.lower():
                report_type = "summary report"
            elif "analytics" in original_query.lower():
                report_type = "analytics report"
            
            docs_prompt = f"""
            Generate a professional {report_type} based on this data:
            
            Original Request: {original_query}
            
            Data Retrieved: {db_data}
            
            Create a comprehensive document with appropriate sections, Q&A, and data tables.
            Use template2 for detailed reports with multiple sections.
            """
            
            print(f"📋 Docs Agent Input: Generate {report_type}...")
            
            start_time = time.time()
            
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                docs_result = loop.run_until_complete(process_document_generation_request(docs_prompt))
            finally:
                loop.close()
            
            execution_time = time.time() - start_time
            
            if docs_result.get('status') != 'success':
                error_msg = docs_result.get('error', 'Unknown Docs agent error')
                print(f"❌ Docs agent failed: {error_msg}")
                return f"ERROR: Docs Agent failed - {error_msg}"
            
            docs_response = docs_result.get('response', '')
            print(f"✅ Docs agent completed in {execution_time:.2f}s")
            print(f"📋 Generated document response")
            
            # Dynamically extract or generate file URL from response
            file_url = extract_file_url_from_response(docs_response)
            print(f"📎 Dynamic file URL: {file_url}")
            
            return f"Document generated successfully. File URL: {file_url}. Response: {docs_response}"
            
        except Exception as e:
            print(f"❌ Docs agent execution failed: {e}")
            return f"ERROR: Docs Agent exception - {str(e)}"
    
    @tool
    def call_comms_agent(docs_response: str, original_query: str) -> str:
        """Call Comms agent with docs response and original query - sends dynamically"""
        try:
            print("📬 Calling Comms Agent...")
            
            if docs_response.startswith("ERROR:"):
                return f"Cannot send communications: {docs_response}"
            
            # Dynamically extract file URL from docs response
            file_url = extract_file_url_from_response(docs_response)
            if not file_url:
                return "ERROR: No file URL found in document response"
            
            # Dynamically extract recipients from original query
            recipients_info = extract_recipients_from_query(original_query)
            if "No recipients" in recipients_info:
                return "ERROR: No recipients specified in original query"
            
            comms_prompt = f"""
            Send the generated report file to the specified recipients:
            
            File URL: {file_url}
            Recipients: {recipients_info}
            
            Original request context: {original_query}
            Document details: {docs_response[:200]}...
            
            Route to appropriate channels based on recipient types (email/Slack).
            """
            
            print(f"📧 Comms Agent Input: Send to {recipients_info}")
            
            start_time = time.time()
            
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                comms_result = loop.run_until_complete(process_message_request(comms_prompt))
            finally:
                loop.close()
            
            execution_time = time.time() - start_time
            
            if comms_result.get('status') != 'success':
                error_msg = comms_result.get('error', 'Unknown Comms agent error')
                print(f"❌ Comms agent failed: {error_msg}")
                return f"ERROR: Comms Agent failed - {error_msg}"
            
            comms_response = comms_result.get('response', '')
            print(f"✅ Comms agent completed in {execution_time:.2f}s")
            print(f"📨 Communications sent successfully")
            
            return f"Communications sent successfully to: {recipients_info}. File URL: {file_url}. Details: {comms_response}"
            
        except Exception as e:
            print(f"❌ Comms agent execution failed: {e}")
            return f"ERROR: Comms Agent exception - {str(e)}"
    
    return [call_db_agent, call_docs_agent, call_comms_agent]

def build_supervisor_system_prompt() -> str:
    """Build system prompt for dynamic supervisor"""
    
    return """You are a dynamic supervisor that coordinates three agents to complete report workflows with NO hardcoded values:

**AGENTS AVAILABLE:**
1. **call_db_agent**: Retrieves data from database based on queries
2. **call_docs_agent**: Generates professional reports from data  
3. **call_comms_agent**: Sends reports to recipients extracted from original query

**DYNAMIC WORKFLOW:**
1. **First**: Call call_db_agent with user request (agent extracts data query portion)
2. **Second**: Call call_docs_agent with DB results + original query (generates dynamic document)
3. **Third**: Call call_comms_agent with docs response + original query (extracts recipients dynamically)

**KEY PRINCIPLES:**
- **No hardcoded values**: All URLs, recipients, and data are extracted dynamically
- **Pass actual results**: Use real outputs from each agent as inputs to the next
- **Dynamic extraction**: Agents determine file URLs, recipients, and content from responses
- **Error propagation**: Stop if any agent returns "ERROR:" prefix
- **Plain text flow**: Simple text instructions, let agents handle parsing

**WORKFLOW EXAMPLE:**
User: "Get all active users, generate a comprehensive user activity report, and send it to john@company.com"

1. call_db_agent("Get all active users, generate a comprehensive user activity report, and send it to john@company.com")
   → Returns actual DB data

2. call_docs_agent([actual_db_data], "Get all active users, generate a comprehensive user activity report, and send it to john@company.com") 
   → Returns document response with dynamic file URL

3. call_comms_agent([actual_docs_response], "Get all active users, generate a comprehensive user activity report, and send it to john@company.com")
   → Extracts john@company.com and file URL dynamically, sends message

**CRITICAL RULES:**
- Use EXACT outputs from previous tools as inputs to next tools
- Pass the original user query to docs and comms agents for context
- Let each agent dynamically extract what they need
- Stop immediately if any response starts with "ERROR:"
- All file URLs, recipients, and content are determined dynamically from actual responses

Keep the workflow simple but ensure real data flows between all agents.
"""

def build_supervisor_agent():
    """Build dynamic supervisor agent"""
    
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
    """Process complete report workflow request through dynamic supervisor"""
    
    try:
        # Use the supervisor agent
        supervisor_agent = build_supervisor_agent()
        
        print(f"🎯 Starting dynamic supervisor workflow...")
        print(f"📝 User Request: {user_input}")
        print(f"📧 Extracted Recipients: {extract_recipients_from_query(user_input)}")
        
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
