from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
import sqlite3
import tempfile
import json
import os
from typing import Dict, Any, List
import requests
import time

def create_controlled_workflow_tools():
    """Create tools that enforce the specific workflow: Plan → Fetch → Store → Query → Respond"""
    
    @tool
    def plan_data_collection(user_query: str) -> str:
        """PHASE 1: Plan which APIs to call based on user query (LLM intervention)"""
        return json.dumps({
            "query": user_query,
            "status": "planned",
            "next_phase": "collect_data"
        })
    
    @tool
    def collect_and_store_data(tool_calls_json: str) -> str:
        """PHASE 2: Execute API calls and store in SQLite (NO LLM intervention)"""
        try:
            print("📡 PHASE 2: Collecting data from APIs and storing in SQLite...")
            
            # Parse tool calls from the planning phase
            tool_calls = json.loads(tool_calls_json)
            if not isinstance(tool_calls, list):
                tool_calls = [tool_calls]
            
            # Load available API tools as raw dictionaries
            try:
                with open("agents/db/tools.json", 'r') as f:
                    api_tools_config = json.load(f)
                    
                print("🔧 Available tools loaded:")
                for tool in api_tools_config:
                    print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                    
            except Exception as e:
                print(f"❌ Could not load tools.json: {e}")
                return json.dumps({"error": "Could not load API tools", "status": "error"})
            
            # Collect all data
            all_data = []
            execution_log = []
            
            for tool_call in tool_calls:
                tool_name = tool_call.get('tool')
                params = tool_call.get('params', {})
                
                # Find tool config
                tool_config = None
                for config in api_tools_config:
                    if config['name'] == tool_name:
                        tool_config = config
                        break
                
                if not tool_config:
                    print(f"❌ Tool {tool_name} not found in available tools")
                    execution_log.append({
                        "tool": tool_name,
                        "params": params,
                        "error": "Tool not found",
                        "status": "failed"
                    })
                    continue
                
                # Execute API call deterministically
                print(f"🔧 Calling {tool_name} with params: {params}")
                start_time = time.time()
                
                try:
                    api_response = execute_api_call_enhanced(tool_config, params)
                    execution_time = time.time() - start_time
                    
                    # Extract data from response
                    data = extract_data_from_response(api_response, tool_name)
                    
                    if data:
                        all_data.extend(data)
                        execution_log.append({
                            "tool": tool_name,
                            "params": params,
                            "records_fetched": len(data),
                            "execution_time": f"{execution_time:.2f}s",
                            "status": "success"
                        })
                    else:
                        # Use mock data for demo
                        mock_data = get_mock_data_for_tool(tool_name, params)
                        all_data.extend(mock_data)
                        execution_log.append({
                            "tool": tool_name,
                            "params": params,
                            "records_fetched": len(mock_data),
                            "execution_time": f"{execution_time:.2f}s",
                            "status": "mock_data"
                        })
                        
                except Exception as e:
                    print(f"❌ API call failed for {tool_name}: {e}")
                    execution_time = time.time() - start_time
                    
                    # Use mock data as fallback
                    mock_data = get_mock_data_for_tool(tool_name, params)
                    all_data.extend(mock_data)
                    
                    execution_log.append({
                        "tool": tool_name,
                        "params": params,
                        "error": str(e),
                        "records_fetched": len(mock_data),
                        "execution_time": f"{execution_time:.2f}s",
                        "status": "failed_using_mock"
                    })
            
            if not all_data:
                return json.dumps({
                    "error": "No data collected from APIs",
                    "execution_log": execution_log,
                    "status": "error"
                })
            
            # Create SQLite database deterministically
            db_info = create_sqlite_from_data(all_data)
            
            print(f"✅ Data collection complete: {len(all_data)} records stored in SQLite")
            print(f"📊 Tables created: {list(db_info['schemas'].keys())}")
            
            return json.dumps({
                "db_path": db_info["db_path"],
                "schemas": db_info["schemas"],
                "total_records": len(all_data),
                "execution_log": execution_log,
                "status": "success",
                "next_phase": "generate_sql"
            })
            
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})
    
    @tool
    def execute_sql_query(db_info_json: str, sql_query: str) -> str:
        """PHASE 4: Execute SQL query on prepared database (NO LLM intervention)"""
        try:
            print(f"⚡ PHASE 4: Executing SQL query...")
            print(f"🔍 Query: {sql_query}")
            
            db_info = json.loads(db_info_json)
            db_path = db_info.get("db_path")
            
            if not db_path or not os.path.exists(db_path):
                return json.dumps({"error": "Database not found", "status": "error"})
            
            # Execute SQL deterministically
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            start_time = time.time()
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            execution_time = time.time() - start_time
            
            results = [dict(row) for row in rows]
            conn.close()
            
            print(f"📈 Query executed in {execution_time:.2f}s, returned {len(results)} rows")
            
            return json.dumps({
                "results": results,
                "row_count": len(results),
                "execution_time": f"{execution_time:.2f}s",
                "status": "success",
                "next_phase": "generate_response"
            })
            
        except Exception as e:
            print(f"❌ SQL execution error: {e}")
            return json.dumps({"error": str(e), "status": "error"})
    
    @tool
    def cleanup_database(db_info_json: str) -> str:
        """PHASE 5: Cleanup temporary database"""
        try:
            db_info = json.loads(db_info_json)
            db_path = db_info.get("db_path")
            
            if db_path and os.path.exists(db_path):
                os.unlink(db_path)
                print("🗑️ Database cleaned up")
                return json.dumps({"status": "cleaned_up"})
            else:
                return json.dumps({"status": "no_cleanup_needed"})
                
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})
    
    return [plan_data_collection, collect_and_store_data, execute_sql_query, cleanup_database]

def execute_api_call_enhanced(tool_config: Dict, params: Dict) -> Dict:
    """Execute API call with support for both GET and POST requests"""
    
    execution_info = tool_config.get('execution', {})
    method = execution_info.get('method', 'GET').upper()
    url = execution_info.get('url', '')
    headers = execution_info.get('headers', {})
    timeout = execution_info.get('timeout', 30)
    
    print(f"🌐 Making {method} request to {url}")
    
    try:
        if method == 'GET':
            # Handle GET requests with query parameters
            query_map = execution_info.get('query_map', {})
            api_params = {}
            for param_name, param_value in params.items():
                if param_value is not None:
                    api_key = query_map.get(param_name, param_name)
                    api_params[api_key] = param_value
            
            print(f"📋 GET params: {api_params}")
            response = requests.get(url, params=api_params, headers=headers, timeout=timeout)
            
        elif method == 'POST':
            # Handle POST requests with JSON body
            body_map = execution_info.get('body_map', execution_info.get('body', {}))
            request_body = {}
            for param_name, param_value in params.items():
                if param_value is not None:
                    body_key = body_map.get(param_name, param_name)
                    request_body[body_key] = param_value
            
            print(f"📋 POST body: {request_body}")
            response = requests.post(url, json=request_body, headers=headers, timeout=timeout)
            
        else:
            # Handle other HTTP methods (PUT, PATCH, DELETE, etc.)
            print(f"📋 {method} body: {params}")
            response = requests.request(method, url, json=params, headers=headers, timeout=timeout)
        
        response.raise_for_status()
        print(f"✅ API call successful: {response.status_code}")
        
        try:
            return response.json()
        except:
            return {"data": [{"response_text": response.text, "table_type": "raw_response"}]}
            
    except Exception as e:
        print(f"❌ API call failed: {str(e)}")
        raise Exception(f"API call failed: {str(e)}")

def extract_data_from_response(api_response: Dict, tool_name: str) -> List[Dict]:
    """Extract data from API response and add table_type"""
    
    # Try different common response formats
    data = None
    
    if isinstance(api_response, list):
        data = api_response
    elif isinstance(api_response, dict):
        # Try common keys for data
        for key in ['data', 'results', 'items', 'records']:
            if key in api_response and isinstance(api_response[key], list):
                data = api_response[key]
                break
        
        # If no array found, treat the whole response as a single record
        if data is None:
            data = [api_response]
    else:
        data = [{"raw_response": str(api_response)}]
    
    # Add table_type based on tool name
    table_type = determine_table_type_from_tool(tool_name)
    
    # Ensure each record has table_type
    for record in data:
        if isinstance(record, dict):
            record['table_type'] = table_type
    
    return data

def determine_table_type_from_tool(tool_name: str) -> str:
    """Determine table type based on tool name"""
    
    tool_lower = tool_name.lower()
    
    if 'user' in tool_lower:
        return 'users'
    elif 'payment' in tool_lower:
        return 'payments'
    elif 'order' in tool_lower:
        return 'orders'
    elif 'product' in tool_lower:
        return 'products'
    elif 'customer' in tool_lower:
        return 'customers'
    else:
        return 'main_data'

def get_mock_data_for_tool(tool_name: str, params: Dict) -> List[Dict]:
    """Generate mock data when API fails - enhanced for all tool types"""
    
    table_type = determine_table_type_from_tool(tool_name)
    
    if 'user' in tool_name.lower():
        return [
            {
                "id": "1",
                "name": "John Doe",
                "email": "john.doe@company.com", 
                "status": "ACTIVE",
                "businessUnit": "engineering",
                "createdAt": "2024-01-15T10:30:00Z",
                "table_type": table_type
            },
            {
                "id": "2",
                "name": "Jane Smith",
                "email": "jane.smith@company.com",
                "status": "ACTIVE",
                "businessUnit": "sales",
                "createdAt": "2024-02-20T09:15:00Z",
                "table_type": table_type
            }
        ]
    elif 'payment' in tool_name.lower():
        return [
            {
                "id": "1",
                "userId": "1",
                "amount": "150.00",
                "status": "completed",
                "paymentDate": "2024-08-15T10:00:00Z",
                "paymentMethod": "credit_card",
                "table_type": table_type
            },
            {
                "id": "2",
                "userId": "2", 
                "amount": "75.00",
                "status": "completed",
                "paymentDate": "2024-08-20T14:30:00Z",
                "paymentMethod": "bank_transfer",
                "table_type": table_type
            }
        ]
    else:
        return [
            {
                "id": "1",
                "message": f"Mock data for {tool_name}",
                "generated_at": "2024-08-31T20:00:00Z",
                "table_type": table_type
            }
        ]

def create_sqlite_from_data(data: List[Dict]) -> Dict:
    """Create SQLite database from collected data"""
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = temp_file.name
    temp_file.close()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Group data by table type
    tables = {}
    for record in data:
        table_name = record.get('table_type', 'main_data')
        if table_name not in tables:
            tables[table_name] = []
        tables[table_name].append(record)
    
    table_schemas = {}
    
    # Create tables and insert data
    for table_name, records in tables.items():
        if not records:
            continue
            
        columns = [col for col in records[0].keys() if col != 'table_type']
        column_defs = ", ".join([f'"{col}" TEXT' for col in columns])
        
        cursor.execute(f'CREATE TABLE "{table_name}" ({column_defs})')
        
        # Insert data
        placeholders = ", ".join(["?" for _ in columns])
        insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'
        
        for record in records:
            values = [str(record.get(col, '')) for col in columns]
            cursor.execute(insert_sql, values)
        
        table_schemas[table_name] = columns
    
    conn.commit()
    conn.close()
    
    return {
        "db_path": db_path,
        "schemas": table_schemas
    }

def build_dynamic_system_prompt() -> str:
    """Build system prompt dynamically based on available tools"""
    
    try:
        # Load tools to create dynamic prompt
        with open("agents/db/tools.json", 'r') as f:
            tools_config = json.load(f)
        
        # Create tool descriptions
        tool_descriptions = []
        for tool in tools_config:
            name = tool['name']
            desc = tool.get('description', 'No description')
            
            # Extract parameter info
            params_info = []
            properties = tool.get('parameters', {}).get('properties', {})
            for param_name, param_config in properties.items():
                param_type = param_config.get('type', 'string')
                param_desc = param_config.get('description', '')
                enum_values = param_config.get('enum', [])
                
                if enum_values:
                    param_info = f"{param_name}: {enum_values}"
                else:
                    param_info = f"{param_name}: {param_type}"
                
                if param_desc:
                    param_info += f" ({param_desc})"
                
                params_info.append(param_info)
            
            tool_desc = f"- {name}: {desc}"
            if params_info:
                tool_desc += f"\n  Parameters: {', '.join(params_info)}"
            
            tool_descriptions.append(tool_desc)
        
        tools_text = "\n".join(tool_descriptions)
        
    except Exception as e:
        print(f"⚠️ Could not load tools for dynamic prompt: {e}")
        tools_text = "- db_get_users: Fetch users with optional filters"
    
    return f"""You are a data analysis agent that follows a strict 5-phase workflow:

**PHASE 1 - PLANNING (LLM)**: Analyze user query and decide which API tools to call
**PHASE 2 - DATA COLLECTION (Deterministic)**: Execute API calls and store data in SQLite
**PHASE 3 - SQL GENERATION (LLM)**: Generate SQL query based on user question + database schema  
**PHASE 4 - SQL EXECUTION (Deterministic)**: Execute SQL query on local database
**PHASE 5 - RESPONSE (LLM)**: Interpret results and generate final answer

**WORKFLOW RULES:**
1. Always start with plan_data_collection to acknowledge the user query
2. Next, call collect_and_store_data with a JSON array of tool calls
3. Generate SQL query based on the returned database schema and user question
4. Call execute_sql_query with the database info and your generated SQL
5. Interpret the SQL results to provide a clear, formatted answer
6. Finally call cleanup_database to clean up

**AVAILABLE API TOOLS (for phase 2):**
{tools_text}

**EXAMPLE WORKFLOWS:**

User: "Show me all active users"
1. plan_data_collection("Show me all active users")
2. collect_and_store_data('[{{"tool": "db_get_users", "params": {{"status": "ACTIVE"}}}}]')
3. Generate SQL based on returned schema
4. execute_sql_query(db_info, generated_sql)
5. Format results and respond
6. cleanup_database(db_info)

User: "Show me payments for user 1"  
1. plan_data_collection("Show me payments for user 1")
2. collect_and_store_data('[{{"tool": "db_get_payments", "params": {{"userId": [1]}}}}]')
3. Generate SQL based on returned schema
4. execute_sql_query(db_info, generated_sql)
5. Format results and respond
6. cleanup_database(db_info)

Always follow this exact sequence and explain what you're doing in each phase.
"""

def build_controlled_workflow_agent():
    """Build agent with controlled workflow phases - fully dynamic"""
    
    # Create workflow tools
    workflow_tools = create_controlled_workflow_tools()
    
    # Initialize model  
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Build dynamic system prompt based on available tools
    system_prompt = build_dynamic_system_prompt()
    
    # Create agent
    agent = create_react_agent(
        model=model,
        tools=workflow_tools,
        prompt=system_prompt
    )
    
    return agent

# Updated main processing function
async def process_user_query_with_agent(user_input: str) -> Dict[str, Any]:
    """Process user query using controlled workflow agent"""
    
    try:
        # Use the controlled workflow agent
        db_agent = build_controlled_workflow_agent()
        
        print(f"🚀 Starting controlled workflow for: {user_input}")
        
        # Let the agent handle the workflow
        result = db_agent.invoke({
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
