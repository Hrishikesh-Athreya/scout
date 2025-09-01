from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
import json
import os
from typing import Dict, Any
import requests
import time

def create_document_workflow_tools():
    """Create tools for document generation workflow"""
    
    @tool
    def plan_document_creation(user_query: str) -> str:
        """PHASE 1: Plan document creation based on user query"""
        return json.dumps({
            "query": user_query,
            "status": "planned",
            "next_phase": "create_document"
        })
    
    @tool
    def create_document_from_data(document_data_json: str) -> str:
        """PHASE 2: Create document using provided data with exact API format"""
        try:
            print("📄 PHASE 2: Creating document with provided data...")
            
            # Parse the document data
            document_data = json.loads(document_data_json)
            
            # Extract template and values
            template = document_data.get('template', 'template2')
            provided_values = document_data.get('documentValues', {})
            
            # Build exact payload format matching your API specification
            # All fields must be present, empty strings if not provided
            exact_document_values = {
                "reportHeading": provided_values.get("reportHeading", ""),
                "heading0": provided_values.get("heading0", ""),
                "answer0": provided_values.get("answer0", ""),
                "heading1": provided_values.get("heading1", ""),
                "answer1": provided_values.get("answer1", ""),
                "heading2": provided_values.get("heading2", ""),
                "answer2": provided_values.get("answer2", ""),
                "heading3": provided_values.get("heading3", ""),
                "answer3": provided_values.get("answer3", ""),
                "table0Heading": provided_values.get("table0Heading", ""),
                "table0Column0": provided_values.get("table0Column0", ""),
                "table0Column1": provided_values.get("table0Column1", ""),
                "table0Column2": provided_values.get("table0Column2", ""),
                "table0Column3": provided_values.get("table0Column3", ""),
                "table0Column4": provided_values.get("table0Column4", ""),
                "table0Column5": provided_values.get("table0Column5", ""),
                "table0Column6": provided_values.get("table0Column6", ""),
                "table0Items": provided_values.get("table0Items", []),
                "table1Heading": provided_values.get("table1Heading", ""),
                "table1Column0": provided_values.get("table1Column0", ""),
                "table1Column1": provided_values.get("table1Column1", ""),
                "table1Column2": provided_values.get("table1Column2", ""),
                "table1Column3": provided_values.get("table1Column3", ""),
                "table1Column4": provided_values.get("table1Column4", ""),
                "table1Column5": provided_values.get("table1Column5", ""),
                "table1Column6": provided_values.get("table1Column6", ""),
                "table1Items": provided_values.get("table1Items", [])
            }
            
            print(f"🔧 Creating document with template: {template}")
            print(f"📋 Fields provided: {len([k for k, v in exact_document_values.items() if v])}")
            
            start_time = time.time()
            
            try:
                # Make API call with exact format
                api_response = call_document_api(template, exact_document_values)
                execution_time = time.time() - start_time
                
                print(f"✅ Document created successfully in {execution_time:.2f}s")
                
                return json.dumps({
                    "document_response": api_response,
                    "template_used": template,
                    "fields_populated": len([k for k, v in exact_document_values.items() if v]),
                    "execution_time": f"{execution_time:.2f}s",
                    "status": "success"
                })
                
            except Exception as e:
                print(f"❌ Document creation failed: {e}")
                return json.dumps({
                    "error": str(e),
                    "status": "error"
                })
                
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})
    
    return [plan_document_creation, create_document_from_data]

def call_document_api(template: str, document_values: Dict) -> str:
    """Call document creation API with exact payload format"""
    
    url = "http://localhost:8081/document/create"
    headers = {"Content-Type": "application/json"}
    
    # Build payload with exact structure matching your curl example
    payload = {
        "template": template,
        "documentValues": document_values
    }
    
    print(f"🌐 Making POST request to {url}")
    print(f"📋 Payload template: {template}")
    print(f"📋 DocumentValues keys: {list(document_values.keys())}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"✅ API call successful: {response.status_code}")
        
        try:
            return response.json()
        except:
            return response.text
            
    except Exception as e:
        print(f"❌ API call failed: {str(e)}")
        raise Exception(f"Document API call failed: {str(e)}")

def build_document_agent():
    """Build document generation agent"""
    
    # Create workflow tools
    workflow_tools = create_document_workflow_tools()
    
    # Initialize model  
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Build system prompt
    system_prompt = """You are a document generation agent that creates documents using a specific API format.

**WORKFLOW:**
1. Always start with plan_document_creation to acknowledge the user query
2. Next, call create_document_from_data with the document data provided by the user
3. The API requires an exact format with all fields present (empty strings if missing)

**REQUIRED API FORMAT:**
The document API expects these exact fields:
- reportHeading, heading0, answer0, heading1, answer1, heading2, answer2, heading3, answer3
- table0Heading, table0Column0-6, table0Items (array of objects with value0-6)  
- table1Heading, table1Column0-6, table1Items (array of objects with value0-6)

**USER INPUT FORMAT:**
Users will provide data as JSON in their prompt containing:
- template: Template name (e.g., "template2")
- documentValues: Object with document content

**EXAMPLE:**
User: "Create document with: {\"template\": \"template2\", \"documentValues\": {...}}"

1. plan_document_creation("Create document with provided data")  
2. create_document_from_data(user_provided_json)
3. Return success/failure message

Always follow this exact sequence and provide clear feedback about the document creation result.
"""
    
    # Create agent
    agent = create_react_agent(
        model=model,
        tools=workflow_tools,
        prompt=system_prompt
    )
    
    return agent

# Main processing function
async def process_document_request(user_input: str) -> Dict[str, Any]:
    """Process document creation request"""
    
    try:
        # Use the document generation agent
        doc_agent = build_document_agent()
        
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
