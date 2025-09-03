from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
import json
import os
from typing import Dict, Any, List
import requests
import time
import re

def safe_log(message: str, data: Any) -> None:
    """Safely log complex data structures to avoid f-string formatting errors"""
    try:
        if isinstance(data, (dict, list)):
            print(f"{message}: {json.dumps(data, ensure_ascii=False)}")
        else:
            print(f"{message}: {data}")
    except:
        print(f"{message}: {repr(data)}")

def create_document_generation_tools():
    """Create tools for document generation workflow: Plan → Parse → Generate → Return"""
    
    @tool
    def plan_document_generation(user_query: str) -> str:
        """PHASE 1: Plan document generation based on user request (LLM intervention)"""
        return json.dumps({
            "query": user_query,
            "status": "planned",
            "next_phase": "parse_and_generate"
        })
    
    @tool
    def parse_and_generate_document(generation_plan_json: str) -> str:
        """PHASE 2: Parse content, select template, and generate document (LLM + API intervention)"""
        try:
            print("📄 PHASE 2: Parsing content and generating document...")
            
            # Parse the generation plan
            generation_plan = json.loads(generation_plan_json)
            
            # Load document generation tool config
            try:
                with open("agents/docs/tools.json", 'r') as f:
                    tools_config = json.load(f)
                    
                # Find document generation tool
                doc_tool_config = None
                for tool in tools_config:
                    if tool['name'] == 'generate_document_report':
                        doc_tool_config = tool
                        break
                
                if not doc_tool_config:
                    return json.dumps({"error": "Document generation tool not found", "status": "error"})
                    
            except Exception as e:
                print(f"❌ Could not load tools.json: {e}")
                return json.dumps({"error": "Could not load tools config", "status": "error"})
            
            # Extract document parameters from plan
            template = generation_plan.get('template', 'template2')  # Default to template2
            raw_content = generation_plan.get('content', {})
            password_protection = generation_plan.get('enablePasswordProtection', False)
            
            # Build complete document values structure with all required fields
            document_values = build_complete_document_structure(raw_content, template)
            
            print(f"🔧 Generating document with template: {template}")
            print(f"📋 Content fields populated: {count_populated_fields(document_values)}")
            print(f"🔒 Password protection: {password_protection}")
            
            # Safe logging of document structure
            print(f"📊 Document structure keys: {len(document_values)} fields")
            table0_items = document_values.get('table0Items', [])
            table1_items = document_values.get('table1Items', [])
            print(f"📊 Table0 items: {len(table0_items)}, Table1 items: {len(table1_items)}")
            
            start_time = time.time()
            
            try:
                # Execute document generation API call
                api_response = execute_document_api_call(doc_tool_config, {
                    'template': template,
                    'documentValues': document_values,
                    'enablePasswordProtection': password_protection
                })
                
                execution_time = time.time() - start_time
                
                print(f"✅ Document generated successfully in {execution_time:.2f}s")
                
                return json.dumps({
                    "document_response": api_response,
                    "template_used": template,
                    "fields_populated": count_populated_fields(document_values),
                    "password_protected": password_protection,
                    "execution_time": f"{execution_time:.2f}s",
                    "status": "success"
                })
                
            except Exception as e:
                print(f"❌ Document generation failed: {e}")
                return json.dumps({
                    "error": str(e),
                    "status": "error"
                })
                
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})
    
    return [plan_document_generation, parse_and_generate_document]

def build_complete_document_structure(content: Dict, template: str) -> Dict:
    """Build complete document structure with all required fields, empty strings for missing ones"""
    
    # Base structure that both templates require
    document_values = {
        "reportHeading": content.get("reportHeading", ""),
        "heading0": content.get("heading0", ""),
        "answer0": content.get("answer0", ""),
        "heading1": content.get("heading1", ""),
        "answer1": content.get("answer1", ""),
        "heading2": content.get("heading2", ""),
        "answer2": content.get("answer2", ""),
        
        # Table 0 structure
        "table0Heading": content.get("table0Heading", ""),
        "table0Column0": content.get("table0Column0", ""),
        "table0Column1": content.get("table0Column1", ""),
        "table0Column2": content.get("table0Column2", ""),
        "table0Column3": content.get("table0Column3", ""),
        "table0Column4": content.get("table0Column4", ""),
        "table0Column5": content.get("table0Column5", ""),
        "table0Column6": content.get("table0Column6", ""),
        "table0Items": content.get("table0Items", []),
        
        # Table 1 structure
        "table1Heading": content.get("table1Heading", ""),
        "table1Column0": content.get("table1Column0", ""),
        "table1Column1": content.get("table1Column1", ""),
        "table1Column2": content.get("table1Column2", ""),
        "table1Column3": content.get("table1Column3", ""),
        "table1Column4": content.get("table1Column4", ""),
        "table1Column5": content.get("table1Column5", ""),
        "table1Column6": content.get("table1Column6", ""),
        "table1Items": content.get("table1Items", [])
    }
    
    # Template2 has additional heading3/answer3 fields
    if template == "template2":
        document_values.update({
            "heading3": content.get("heading3", ""),
            "answer3": content.get("answer3", "")
        })
    
    return document_values

def count_populated_fields(document_values: Dict) -> int:
    """Count non-empty fields in document values"""
    count = 0
    for key, value in document_values.items():
        if value:  # Non-empty string or non-empty list
            count += 1
    return count

def execute_document_api_call(tool_config: Dict, params: Dict) -> Dict:
    """Execute API call for document generation"""
    
    execution_info = tool_config.get('execution', {})
    method = execution_info.get('method', 'POST').upper()
    url = execution_info.get('url', '')
    headers = execution_info.get('headers', {})
    timeout = execution_info.get('timeout', 60)
    
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
        print(f"📋 Document template: {request_body.get('template', 'unknown')}")
        
        # Safe logging of complex objects - avoid f-string formatting errors
        document_values = request_body.get('documentValues', {})
        if document_values:
            table0_items = document_values.get('table0Items', [])
            table1_items = document_values.get('table1Items', [])
            print(f"📊 Table0 items count: {len(table0_items)}")
            print(f"📊 Table1 items count: {len(table1_items)}")
            
            # Safe sample logging without direct dict in f-string
            if table0_items:
                try:
                    sample_item = table0_items[0]
                    if isinstance(sample_item, dict):
                        print(f"📊 Sample table0 item keys: {list(sample_item.keys())}")
                    else:
                        print("📊 Sample table0 item: not a dictionary")
                except:
                    print("📊 Sample table0 item: could not parse")
        
        response = requests.post(url, json=request_body, headers=headers, timeout=timeout)
        
        response.raise_for_status()
        print(f"✅ API call successful: {response.status_code}")
        
        try:
            return response.json()
        except:
            return {"response_text": response.text, "status_code": response.status_code}
            
    except Exception as e:
        print(f"❌ API call failed: {str(e)}")
        raise Exception(f"Document API call failed: {str(e)}")

def build_document_system_prompt() -> str:
    """Build system prompt for document generation agent"""
    
    try:
        # Load tools to create dynamic prompt
        with open("agents/docs/tools.json", 'r') as f:
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
        tools_text = "- generate_document_report: Generate reports using templates"
    
    return f"""You are a document/report generation agent that creates professional documents using a 2-phase workflow:

**PHASE 1 - PLANNING (LLM)**: Analyze user request and plan document generation
**PHASE 2 - GENERATION (LLM + API)**: Parse content, select template, format data, and generate document

**WORKFLOW RULES:**
1. Always start with plan_document_generation to acknowledge the user query
2. Next, call parse_and_generate_document with a generation plan containing:
   - template: "template1" (3 Q&A sections) or "template2" (4 Q&A sections)
   - content: Object with document content extracted from user input
   - enablePasswordProtection: boolean (default false)
3. The API requires ALL fields to be present - use empty strings for missing content
4. Choose template based on content amount - template2 for more extensive content

**AVAILABLE TEMPLATES:**
- **template1**: 3 Q&A sections + 2 tables (reportHeading, heading0-2, answer0-2, table0, table1)
- **template2**: 4 Q&A sections + 2 tables (reportHeading, heading0-3, answer0-3, table0, table1)

**DOCUMENT STRUCTURE:**
All templates require these fields (empty strings if not provided):
- reportHeading: Main title of the report
- heading0-2 (or heading0-3 for template2): Question headings  
- answer0-2 (or answer0-3 for template2): Answer content
- table0Heading, table0Column0-6, table0Items: First table with data
- table1Heading, table1Column0-6, table1Items: Second table with data

**TABLE ITEMS FORMAT:**
Each table item should be an object with value0-6 properties:
[
{{"value0": "API", "value1": "HTTP", "value2": "JSON", "value3": "OAuth2", "value4": "Low", "value5": "High", "value6": "Public APIs"}},
{{"value0": "File-based", "value1": "FTP", "value2": "CSV", "value3": "None", "value4": "High", "value5": "Medium", "value6": "Batch Transfers"}}
]

**AVAILABLE DOCUMENT TOOLS:**
{tools_text}

**EXAMPLE WORKFLOWS:**

User: "Generate a report about MuleSoft integration with Q&A section and comparison table"
1. plan_document_generation("Generate a report about MuleSoft...")
2. parse_and_generate_document({{
   "template": "template2",
   "content": {{
     "reportHeading": "MuleSoft Integration Guide",
     "heading0": "What is MuleSoft?",
     "answer0": "MuleSoft is an integration platform...",
     "table0Heading": "Integration Types",
     "table0Column0": "Type",
     "table0Items": [...]
   }},
   "enablePasswordProtection": false
}})

User: "Create a technical document with password protection"
1. plan_document_generation("Create a technical document...")
2. parse_and_generate_document({{
   "template": "template1",
   "content": {{...}},
   "enablePasswordProtection": true
}})

Always follow this exact sequence and provide clear feedback about the document generation results.
"""

def build_document_generation_agent():
    """Build document generation agent"""
    
    # Create workflow tools
    workflow_tools = create_document_generation_tools()
    
    # Initialize model  
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Build system prompt
    system_prompt = build_document_system_prompt()
    
    # Create agent
    agent = create_react_agent(
        model=model,
        tools=workflow_tools,
        prompt=system_prompt
    )
    
    return agent

# Main processing function
async def process_document_generation_request(user_input: str) -> Dict[str, Any]:
    """Process document generation request"""
    
    try:
        # Use the document generation agent
        doc_agent = build_document_generation_agent()
        
        print(f"📄 Starting document generation for request...")
        
        # Let the agent handle the workflow
        result = doc_agent.invoke({
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
