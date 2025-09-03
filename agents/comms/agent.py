from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
import json
import os
from typing import Dict, Any, List
import requests
import time
import re

def create_comms_workflow_tools():
    """Create tools for communications workflow: Plan → Route → Send → Report"""
    
    @tool
    def plan_message_routing(user_query: str) -> str:
        """PHASE 1: Plan message routing based on recipients mentioned (LLM intervention)"""
        return json.dumps({
            "query": user_query,
            "status": "planned",
            "next_phase": "route_and_send"
        })
    
    @tool 
    def route_and_send_messages(routing_plan_json: str) -> str:
        """PHASE 2: Route and send messages to all recipients (NO LLM intervention)"""
        try:
            print("📬 PHASE 2: Routing and sending messages...")
            
            # Parse routing plan from the planning phase
            routing_plan = json.loads(routing_plan_json)
            
            # Load available comms tools
            try:
                with open("agents/comms/tools.json", 'r') as f:
                    comms_tools_config = json.load(f)
                    
                print("🔧 Available comms tools loaded:")
                for tool in comms_tools_config:
                    print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                    
            except Exception as e:
                print(f"❌ Could not load tools.json: {e}")
                return json.dumps({"error": "Could not load comms tools", "status": "error"})
            
            # Extract routing information from plan
            file_url = routing_plan.get('fileUrl', '')
            slack_channels = routing_plan.get('slack_channels', [])
            email_recipients = routing_plan.get('email_recipients', [])
            
            if not file_url:
                return json.dumps({
                    "error": "No file URL provided for sending",
                    "status": "error"
                })
            
            print(f"📄 File URL: {file_url}")
            print(f"📱 Slack channels: {len(slack_channels)}")
            print(f"📧 Email recipients: {len(email_recipients)}")
            
            execution_log = []
            
            # Send to Slack channels
            for channel_info in slack_channels:
                channel_id = channel_info.get('channelId', '')
                thread_ts = channel_info.get('threadTs', '')
                
                if not channel_id:
                    continue
                    
                print(f"📱 Sending to Slack channel: {channel_id}")
                start_time = time.time()
                
                try:
                    # Find Slack tool config
                    slack_tool_config = next(
                        (tool for tool in comms_tools_config if tool['name'] == 'send_slack_message'), 
                        None
                    )
                    
                    if slack_tool_config:
                        api_response = execute_comms_api_call(slack_tool_config, {
                            'fileUrl': file_url,
                            'channelId': channel_id,
                            'threadTs': thread_ts
                        })
                        
                        execution_time = time.time() - start_time
                        execution_log.append({
                            "type": "slack",
                            "channel": channel_id,
                            "thread_ts": thread_ts,
                            "execution_time": f"{execution_time:.2f}s",
                            "status": "success"
                        })
                        
                except Exception as e:
                    print(f"❌ Slack send failed for {channel_id}: {e}")
                    execution_log.append({
                        "type": "slack",
                        "channel": channel_id,
                        "error": str(e),
                        "status": "failed"
                    })
            
            # Send emails in batches
            if email_recipients:
                # Split into batches of 10 for better API management
                batch_size = 10
                total_batches = (len(email_recipients) + batch_size - 1) // batch_size
                
                for batch_num in range(total_batches):
                    start_idx = batch_num * batch_size
                    end_idx = min(start_idx + batch_size, len(email_recipients))
                    batch_recipients = email_recipients[start_idx:end_idx]
                    
                    print(f"📧 Sending to email batch {batch_num + 1}/{total_batches}: {len(batch_recipients)} recipients")
                    start_time = time.time()
                    
                    try:
                        # Find Email tool config
                        email_tool_config = next(
                            (tool for tool in comms_tools_config if tool['name'] == 'send_email_message'),
                            None
                        )
                        
                        if email_tool_config:
                            api_response = execute_comms_api_call(email_tool_config, {
                                'fileUrl': file_url,
                                'recipients': batch_recipients
                            })
                            
                            execution_time = time.time() - start_time
                            execution_log.append({
                                "type": "email",
                                "batch": batch_num + 1,
                                "recipients_count": len(batch_recipients),
                                "execution_time": f"{execution_time:.2f}s",
                                "status": "success"
                            })
                            
                    except Exception as e:
                        print(f"❌ Email send failed for batch {batch_num + 1}: {e}")
                        execution_log.append({
                            "type": "email",
                            "batch": batch_num + 1,
                            "recipients_count": len(batch_recipients),
                            "error": str(e),
                            "status": "failed"
                        })
            
            # Summary
            total_slack = len(slack_channels)
            total_emails = len(email_recipients)
            successful_slack = len([log for log in execution_log if log.get("type") == "slack" and log.get("status") == "success"])
            successful_email_batches = len([log for log in execution_log if log.get("type") == "email" and log.get("status") == "success"])
            
            print(f"✅ Message routing complete!")
            print(f"📱 Slack: {successful_slack}/{total_slack} channels")
            print(f"📧 Email: {sum(log.get('recipients_count', 0) for log in execution_log if log.get('type') == 'email' and log.get('status') == 'success')}/{total_emails} recipients")
            
            return json.dumps({
                "total_slack_channels": total_slack,
                "successful_slack_channels": successful_slack,
                "total_email_recipients": total_emails,
                "successful_email_recipients": sum(log.get('recipients_count', 0) for log in execution_log if log.get('type') == 'email' and log.get('status') == 'success'),
                "execution_log": execution_log,
                "status": "success"
            })
            
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})
    
    return [plan_message_routing, route_and_send_messages]

def execute_comms_api_call(tool_config: Dict, params: Dict) -> Dict:
    """Execute API call for communications"""
    
    execution_info = tool_config.get('execution', {})
    method = execution_info.get('method', 'POST').upper()
    url = execution_info.get('url', '')
    headers = execution_info.get('headers', {})
    timeout = execution_info.get('timeout', 30)
    
    print(f"🌐 Making {method} request to {url}")
    
    try:
        # Handle POST request with JSON body
        body_map = execution_info.get('body_map', {})
        request_body = {}
        for param_name, param_value in params.items():
            if param_value is not None:
                body_key = body_map.get(param_name, param_name)
                request_body[body_key] = param_value
        
        print(f"📋 Request body keys: {list(request_body.keys())}")
        response = requests.post(url, json=request_body, headers=headers, timeout=timeout)
        
        response.raise_for_status()
        print(f"✅ API call successful: {response.status_code}")
        
        try:
            return response.json()
        except:
            return {"response_text": response.text, "status_code": response.status_code}
            
    except Exception as e:
        print(f"❌ API call failed: {str(e)}")
        raise Exception(f"Comms API call failed: {str(e)}")

def extract_recipients_from_query(user_query: str) -> Dict:
    """Extract email addresses and channel mentions from user query"""
    
    # Extract email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, user_query)
    
    # Extract Slack channel IDs (format: C followed by alphanumeric)
    channel_pattern = r'#?([C][A-Z0-9]{8,})'
    channels = re.findall(channel_pattern, user_query)
    
    # Extract Slack channel names (format: #channelname)
    channel_name_pattern = r'#([a-zA-Z0-9_-]+)'
    channel_names = re.findall(channel_name_pattern, user_query)
    
    return {
        "emails": emails,
        "channel_ids": channels,
        "channel_names": channel_names
    }

def build_comms_system_prompt() -> str:
    """Build system prompt for communications agent"""
    
    try:
        # Load tools to create dynamic prompt
        with open("agents/comms/tools.json", 'r') as f:
            tools_config = json.load(f)
        
        # Create tool descriptions
        tool_descriptions = []
        for tool in tools_config:
            name = tool['name']
            desc = tool.get('description', 'No description')
            tool_descriptions.append(f"- {name}: {desc}")
        
        tools_text = "\n".join(tool_descriptions)
        
    except Exception as e:
        print(f"⚠️ Could not load tools for dynamic prompt: {e}")
        tools_text = "- send_slack_message: Send messages to Slack channels\n- send_email_message: Send messages via email"
    
    return f"""You are a communications agent that sends messages via Slack and Email using a 2-phase workflow:

**PHASE 1 - PLANNING (LLM)**: Analyze user query and identify all recipients
**PHASE 2 - ROUTING & SENDING (Deterministic)**: Send messages to all identified recipients via appropriate channels

**WORKFLOW RULES:**
1. Always start with plan_message_routing to acknowledge the user query
2. Extract ALL recipients from the user's message including:
   - Email addresses (user@domain.com format)
   - Slack channel IDs (C followed by alphanumeric)
   - Slack channel names (#general, #team, etc.)
3. Call route_and_send_messages with routing plan containing:
   - fileUrl: The file URL to send
   - slack_channels: Array of objects with channelId and optional threadTs
   - email_recipients: Array of email addresses
4. The system will automatically batch email recipients and send multiple API calls if needed
5. Provide clear summary of delivery results

**AVAILABLE COMMUNICATION TOOLS:**
{tools_text}

**RECIPIENT EXTRACTION RULES:**
- Email: Extract any valid email addresses from the query
- Slack Channels: Extract channel IDs (C09BQEU1HCM) or channel names (#general)
- Multiple Recipients: Send to ALL identified recipients using appropriate channels
- Batching: Emails are automatically batched for efficient delivery

**EXAMPLE WORKFLOWS:**

User: "Send the report https://example.com/report.pdf to john@company.com, jane@company.com and C09BQEU1HCM"
1. plan_message_routing("Send the report to john@company.com, jane@company.com and C09BQEU1HCM")
2. route_and_send_messages({{
   "fileUrl": "https://example.com/report.pdf",
   "slack_channels": [{{"channelId": "C09BQEU1HCM"}}],
   "email_recipients": ["john@company.com", "jane@company.com"]
}})

User: "Share document https://example.com/document.pdf with team@company.com and reply in thread 1756882046.433939 in C09BQEU1HCM"
1. plan_message_routing("Share document with team@company.com and reply in thread...")
2. route_and_send_messages({{
   "fileUrl": "https://example.com/document.pdf", 
   "slack_channels": [{{"channelId": "C09BQEU1HCM", "threadTs": "1756882046.433939"}}],
   "email_recipients": ["team@company.com"]
}})

Always follow this exact sequence and provide clear delivery status for each recipient type.
"""

def build_comms_agent():
    """Build communications agent with routing capabilities"""
    
    # Create workflow tools
    workflow_tools = create_comms_workflow_tools()
    
    # Initialize model  
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Build system prompt
    system_prompt = build_comms_system_prompt()
    
    # Create agent
    agent = create_react_agent(
        model=model,
        tools=workflow_tools,
        prompt=system_prompt
    )
    
    return agent

# Main processing function
async def process_message_request(user_input: str) -> Dict[str, Any]:
    """Process message sending request"""
    
    try:
        # Use the communications agent
        comms_agent = build_comms_agent()
        
        print(f"📬 Starting message routing for: {user_input[:100]}...")
        
        # Let the agent handle the workflow
        result = comms_agent.invoke({
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
                "error": "No response from agent",
                "status": "error"
            }
            
    except Exception as e:
        return {
            "user_query": user_input,
            "error": str(e),
            "status": "error"
        }
