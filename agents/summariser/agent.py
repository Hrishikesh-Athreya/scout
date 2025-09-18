from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
import json
import os
from typing import Dict, Any, List
import requests
import time
from datetime import datetime, timedelta

def create_summariser_workflow_tools():
    """Create tools for summariser workflow: Fetch -> Analyze -> Create Notion Doc"""
    
    # Helper functions defined inside the function scope
    def _format_timeline(messages):
        """Format messages for timeline section"""
        if not messages:
            return "No timeline data available"
        
        formatted = []
        for msg in messages[:15]:  # Limit timeline entries
            if isinstance(msg, dict):
                timestamp = msg.get("timestamp", "Unknown time")
                user = msg.get("user", "Unknown user") 
                text = msg.get("text", "No content")
                if len(text) > 100:
                    text = text[:100] + "..."
                formatted.append(f"**{timestamp}** - {user}: {text}")
            else:
                formatted.append(f"- {str(msg)[:100]}...")
        
        return "\n".join(formatted)
    
    def _format_messages(messages, msg_type):
        """Format messages for incident/resolution sections"""
        if not messages:
            return f"No {msg_type} messages identified in the analyzed timeframe."
        
        formatted = []
        for msg in messages[:8]:  # Limit to 8 entries
            if isinstance(msg, dict):
                timestamp = msg.get("timestamp", "Unknown")
                user = msg.get("user", "Unknown")
                text = msg.get("text", "No content")
                formatted.append(f"**{timestamp}** - {user}:\n{text}\n")
            else:
                formatted.append(f"- {str(msg)}\n")
        
        return "\n".join(formatted)
    
    @tool
    def fetch_slack_messages_mcp(channel_id: str, hours_back: int = 24) -> str:
        """PHASE 1: Fetch messages from Slack channel using MCP server"""
        try:
            print(f"Fetching messages from channel {channel_id} via MCP server...")
            
            # Load MCP tools configuration
            try:
                with open("agents/summariser/tools.json", "r") as f:
                    tools_config = json.load(f)
            except Exception as e:
                return json.dumps({"error": f"Could not load tools config: {e}", "status": "error"})
            
            # Find MCP Slack tool
            mcp_slack_tool = next((tool for tool in tools_config if tool["name"] == "get_slack_messages"), None)
            if not mcp_slack_tool:
                return json.dumps({"error": "MCP Slack tool not configured", "status": "error"})
            
            # Execute MCP API call to fetch messages
            api_response = execute_mcp_api_call(mcp_slack_tool, {
                "channel_id": channel_id,
                "hours_back": hours_back
            })
            
            messages = api_response.get("messages", [])
            print(f"Fetched {len(messages)} messages from MCP Slack API")
            
            return json.dumps({
                "channel_id": channel_id,
                "message_count": len(messages),
                "messages": messages,
                "hours_back": hours_back,
                "status": "success"
            })
            
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})
    
    @tool
    def analyze_and_create_rca_template(messages_json: str) -> str:
        """PHASE 2: Analyze messages and create RCA template structure"""
        try:
            messages_data = json.loads(messages_json)
            if messages_data.get("status") != "success":
                return json.dumps({"error": "Invalid messages data", "status": "error"})
            
            messages = messages_data.get("messages", [])
            channel_id = messages_data.get("channel_id")
            print(f"Analyzing {len(messages)} messages for RCA creation...")
            
            # Extract key information for RCA
            incident_indicators = ["error", "down", "failed", "issue", "problem", "alert", "outage", "incident"]
            resolution_indicators = ["fixed", "resolved", "working", "restored", "deployed", "updated", "solved"]
            
            incidents = []
            resolutions = []
            timeline = []
            
            for msg in messages:
                msg_text = msg.get("text", "").lower() if isinstance(msg, dict) else str(msg).lower()
                msg_formatted = msg if isinstance(msg, dict) else {"text": str(msg), "timestamp": "unknown"}
                
                if any(indicator in msg_text for indicator in incident_indicators):
                    incidents.append(msg_formatted)
                if any(indicator in msg_text for indicator in resolution_indicators):
                    resolutions.append(msg_formatted)
                timeline.append(msg_formatted)
            
            # Create RCA template structure
            rca_template = {
                "title": f"RCA - Channel {channel_id} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "sections": {
                    "incident_overview": {
                        "title": "## Incident Overview",
                        "content": f"**Channel:** {channel_id}\n**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n**Messages Analyzed:** {len(messages)}\n**Incidents Detected:** {len(incidents)}\n**Resolutions Found:** {len(resolutions)}"
                    },
                    "timeline": {
                        "title": "## Timeline",
                        "content": _format_timeline(timeline[:20])  # Fixed: removed self.
                    },
                    "incident_details": {
                        "title": "## Incident Details", 
                        "content": _format_messages(incidents[:10], "incident")  # Fixed: removed self.
                    },
                    "resolution_actions": {
                        "title": "## Resolution Actions",
                        "content": _format_messages(resolutions[:10], "resolution")  # Fixed: removed self.
                    },
                    "root_cause_analysis": {
                        "title": "## Root Cause Analysis",
                        "content": "**[To be completed by incident response team]**\n\n- [ ] Primary root cause identified\n- [ ] Contributing factors documented\n- [ ] Prevention measures defined\n- [ ] Process improvements identified"
                    },
                    "action_items": {
                        "title": "## Action Items",
                        "content": "**[To be completed during review]**\n\n- [ ] Immediate fixes implemented\n- [ ] Long-term improvements planned\n- [ ] Team training requirements\n- [ ] Process updates needed"
                    }
                }
            }
            
            return json.dumps({
                "channel_id": channel_id,
                "rca_template": rca_template,
                "analysis_summary": {
                    "total_messages": len(messages),
                    "incidents_found": len(incidents),
                    "resolutions_found": len(resolutions),
                    "timeline_entries": len(timeline)
                },
                "status": "success"
            })
            
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})
    
    @tool
    def create_notion_document_mcp(template_json: str) -> str:
        """PHASE 3: Create Notion document using MCP server (auto-posts to Slack)"""
        try:
            template_data = json.loads(template_json)
            if template_data.get("status") != "success":
                return json.dumps({"error": "Invalid template data", "status": "error"})
            
            print("Creating Notion RCA document via MCP server...")
            
            # Load MCP tools configuration
            try:
                with open("agents/summariser/tools.json", "r") as f:
                    tools_config = json.load(f)
            except Exception as e:
                return json.dumps({"error": f"Could not load tools config: {e}", "status": "error"})
            
            # Find MCP Notion tool
            mcp_notion_tool = next((tool for tool in tools_config if tool["name"] == "create_notion_rca"), None)
            if not mcp_notion_tool:
                return json.dumps({"error": "MCP Notion tool not configured", "status": "error"})
            
            rca_template = template_data.get("rca_template")
            channel_id = template_data.get("channel_id")
            
            # Execute MCP API call to create Notion doc (MCP handles Slack posting)
            api_response = execute_mcp_api_call(mcp_notion_tool, {
                "channel_id": channel_id,
                "template": rca_template,
                "title": rca_template["title"]
            })
            
            notion_url = api_response.get("notion_url", "")
            success = api_response.get("success", False)
            
            return json.dumps({
                "notion_url": notion_url,
                "channel_id": channel_id,
                "title": rca_template["title"],
                "mcp_handled_slack_post": True,
                "success": success,
                "analysis_summary": template_data.get("analysis_summary"),
                "status": "success" if success else "error"
            })
            
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})
    
    return fetch_slack_messages_mcp, analyze_and_create_rca_template, create_notion_document_mcp

def execute_mcp_api_call(tool_config: Dict, params: Dict) -> Dict:
    """Execute MCP API call for summariser operations"""
    execution_info = tool_config.get("execution", {})
    method = execution_info.get("method", "POST").upper()
    url = execution_info.get("url", "")
    headers = execution_info.get("headers", {})
    timeout = execution_info.get("timeout", 30)
    
    print(f"Making {method} request to MCP server: {url}")
    
    try:
        body_map = execution_info.get("body_map", {})
        request_body = {}
        
        for param_name, param_value in params.items():
            if param_value is not None:
                body_key = body_map.get(param_name, param_name)
                request_body[body_key] = param_value
        
        print(f"MCP request body keys: {list(request_body.keys())}")
        
        if method == "GET":
            response = requests.get(url, params=request_body, headers=headers, timeout=timeout)
        else:
            response = requests.post(url, json=request_body, headers=headers, timeout=timeout)
        
        response.raise_for_status()
        print(f"MCP API call successful: {response.status_code}")
        
        try:
            return response.json()
        except:
            return {"response_text": response.text, "status_code": response.status_code}
            
    except Exception as e:
        print(f"MCP API call failed: {str(e)}")
        raise Exception(f"MCP API call failed: {str(e)}")

def build_summariser_system_prompt() -> str:
    """Build system prompt for summariser agent using MCP server"""
    return """You are a specialized RCA (Root Cause Analysis) summariser agent that creates incident documentation from Slack conversations using MCP server APIs.

**PRIMARY RESPONSIBILITIES:**
1. Fetch Slack channel messages via MCP server API
2. Analyze conversations to identify incidents, timelines, and resolutions  
3. Generate structured RCA templates with professional formatting
4. Create Notion documents via MCP server (which automatically posts back to Slack)

**3-PHASE MCP WORKFLOW:**

**PHASE 1 - FETCH MESSAGES (MCP)**
- Use `fetch_slack_messages_mcp` to get channel messages via MCP server
- MCP server handles Slack API authentication and rate limiting
- Extract messages from specified timeframe (default: 24 hours)

**PHASE 2 - ANALYZE & TEMPLATE**  
- Use `analyze_and_create_rca_template` to process fetched messages
- Identify incident patterns: errors, alerts, outages, failures
- Identify resolution patterns: fixes, deployments, updates
- Create comprehensive RCA template structure with all sections

**PHASE 3 - CREATE NOTION DOC (MCP AUTO-POSTS)**
- Use `create_notion_document_mcp` to generate Notion RCA document
- MCP server creates Notion page AND automatically posts link back to Slack
- No manual Slack posting needed - MCP handles the complete flow

**RCA TEMPLATE SECTIONS:**
- **Incident Overview**: Summary, channel, analysis metadata
- **Timeline**: Chronological sequence of key events  
- **Incident Details**: Specific error messages and alerts
- **Resolution Actions**: Steps taken to resolve issues
- **Root Cause Analysis**: Template for team investigation
- **Action Items**: Template for follow-up tasks

**MCP SERVER ADVANTAGES:**
- Handles all API authentication and rate limiting
- Automatically posts Notion links back to originating Slack channel
- Simplified error handling and retry logic
- Consistent API interface for both Slack and Notion operations

**WORKFLOW EXAMPLE:**
User: "Create RCA for channel C09BQEU1HCM from last 8 hours"

1. `fetch_slack_messages_mcp("C09BQEU1HCM", 8)` → MCP gets messages
2. `analyze_and_create_rca_template(messages_json)` → Create RCA structure  
3. `create_notion_document_mcp(template_json)` → MCP creates doc + posts to Slack

**ERROR HANDLING:**
- Stop workflow if any phase returns error status
- MCP server provides unified error responses
- Clear feedback on API failures or missing data

Always follow the exact 3-phase sequence and let MCP server handle the Slack posting."""

def build_summariser_agent():
    """Build summariser agent with MCP workflow capabilities"""
    workflow_tools = create_summariser_workflow_tools()
    
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    system_prompt = build_summariser_system_prompt()
    
    agent = create_react_agent(model=model, tools=workflow_tools, prompt=system_prompt)
    return agent

async def process_summariser_request(user_input: str) -> Dict[str, Any]:
    """Process RCA summariser request via MCP server"""
    try:
        summariser_agent = build_summariser_agent()
        print(f"Starting MCP RCA summariser workflow for: {user_input[:100]}...")
        
        result = summariser_agent.invoke({"messages": [{"role": "user", "content": user_input}]})
        
        if result and "messages" in result and result["messages"]:
            final_message = result["messages"][-1]
            response_content = final_message.content if hasattr(final_message, "content") else str(final_message)
            
            return {
                "user_query": user_input,
                "response": response_content,
                "status": "success"
            }
        else:
            return {
                "user_query": user_input,
                "error": "No response from summariser agent",
                "status": "error"
            }
            
    except Exception as e:
        return {
            "user_query": user_input,
            "error": str(e),
            "status": "error"
        }
