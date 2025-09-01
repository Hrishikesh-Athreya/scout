import sqlite3
import tempfile
import os
import json
import asyncio
import time
import re
from typing import Dict, List, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import requests
import dotenv

dotenv.load_dotenv()

class DynamicToolExecutor:
    def __init__(self, tools_json_path: str):
        """Load tools from JSON and create dynamic execution capabilities"""
        with open(tools_json_path, 'r') as f:
            self.tools_config = json.load(f)
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        
    async def analyze_user_query(self, user_query: str) -> List[Dict[str, Any]]:
        """Use LLM to determine which tools to use and what parameters"""
        
        tools_description = json.dumps(self.tools_config, indent=2)
        
        prompt = f"""
You are an expert system that analyzes user queries and determines which tools to use.

Available Tools:
{tools_description}

User Query: "{user_query}"

Analyze the query and respond with a JSON array of tool calls needed to fulfill this request.
Each tool call should have:
- "tool": the exact tool name from the available tools
- "params": object with parameter names and values extracted from the user query

Rules:
1. Only use tools that exist in the available tools list
2. Extract parameter values intelligently from the user query
3. Use the DB tool if no other tool fits

Example response:
[
  {{"tool": "db_get_users", "params": {{"status": "ACTIVE", "businessUnit": "engineering"}}}}
]

Respond with only the JSON array, no other text:
"""

        # print(f"🧠 Prompt: {prompt}...")
        start_time = time.time()
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        end_time = time.time()
        
        print(f"🪙 Query Analysis Time: {end_time - start_time:.2f}s")
        
        # Extract JSON from response
        content = response.content if hasattr(response, 'content') else str(response)
        return self._parse_json_response(content)
    
    def _parse_json_response(self, content: Any) -> List[Dict[str, Any]]:
        """Parse JSON from LLM response, handling various formats"""
        try:
            # Ensure content is string
            if not isinstance(content, str):
                content = str(content)
            
            print(f"📝 Raw LLM Response: {content}")
            # Clean the content
            content = content.strip()
            
            # Remove markdown formatting if present
            if content.startswith('```json'):
                content = content.replace('```json', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            # Try to find JSON in the content
            json_pattern = r'($$.*$$|\{.*\})'
            json_match = re.search(json_pattern, content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                result = json.loads(json_str)
                # Ensure it's a list
                if isinstance(result, dict):
                    result = [result]
                return result
            else:
                return []
                
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON response: {e}")
            print(f"Content: {content[:200]}...")
            return []
        except Exception as e:
            print(f"❌ Unexpected error parsing JSON: {e}")
            return []
    
    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with given parameters"""
        
        # Find tool configuration
        tool_config = None
        for config in self.tools_config:
            if config['name'] == tool_name:
                tool_config = config
                break
        
        if not tool_config:
            return {"error": f"Tool {tool_name} not found"}
        
        execution_info = tool_config.get('execution', {})
        method = execution_info.get('method', 'GET').upper()
        url = execution_info.get('url', '')
        headers = execution_info.get('headers', {})
        query_map = execution_info.get('query_map', {})
        timeout = execution_info.get('timeout', 30)
        
        # Process environment variable interpolation
        url = self._interpolate_env_vars(url)
        headers = {k: self._interpolate_env_vars(v) for k, v in headers.items()}
        
        # Map parameters using query_map
        api_params = {}
        for param_name, param_value in params.items():
            if param_value is not None:
                api_key = query_map.get(param_name, param_name)
                api_params[api_key] = param_value
        
        try:
            print(f"🔧 Calling {tool_name} with params: {api_params}")
            
            if method == 'GET':
                response = requests.get(url, params=api_params, headers=headers, timeout=timeout)
            else:
                response = requests.request(method, url, json=api_params, headers=headers, timeout=timeout)
            
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                return response.json()
            except:
                return {"data": response.text}
                
        except requests.RequestException as e:
            print(f"❌ Tool execution error: {e}")
            # Return mock data for demo purposes
            raise Exception(f"Tool execution failed: {e}")
            return self._get_mock_data(tool_name, params)
    
    def _interpolate_env_vars(self, text: str) -> str:
        """Replace ${VAR_NAME} with environment variables"""
        if not isinstance(text, str):
            return text
        
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
        
        def replacer(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) is not None else ''
            return os.getenv(var_name, default_value)
        
        return re.sub(pattern, replacer, text)
    
    def _get_mock_data(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock data when API call fails"""
        
        if 'users' in tool_name.lower():
            return {
                "data": [
                    {
                        "id": "1",
                        "name": "John Doe",
                        "email": "john.doe@company.com",
                        "status": "active",
                        "businessUnit": "engineering",
                        "createdAt": "2024-01-15T10:30:00Z",
                        "table_type": "users"
                    },
                    {
                        "id": "2", 
                        "name": "Jane Smith",
                        "email": "jane.smith@company.com",
                        "status": "active",
                        "businessUnit": "sales",
                        "createdAt": "2024-02-20T09:15:00Z",
                        "table_type": "users"
                    },
                    {
                        "id": "3",
                        "name": "Mike Johnson", 
                        "email": "mike.johnson@company.com",
                        "status": "active",
                        "businessUnit": "marketing",
                        "createdAt": "2024-03-10T11:00:00Z",
                        "table_type": "users"
                    }
                ]
            }
        else:
            return {"data": [], "message": "No mock data available for this tool"}

async def process_dynamic_query_flow(user_input: str, tools_json_path: str) -> Dict[str, Any]:
    """
    Complete dynamic flow: user input -> LLM tool selection -> execution -> SQLite -> SQL generation -> results
    """
    temp_db_path = None
    
    try:
        # Step 1: Initialize dynamic tool executor
        print(f"🔍 Analyzing query with LLM...")
        executor = DynamicToolExecutor(tools_json_path)
        
        # Step 2: Let LLM determine which tools to use and parameters
        tool_calls = await executor.analyze_user_query(user_input)
        
        if not tool_calls:
            return {
                "user_query": user_input,
                "error": "LLM could not determine appropriate tool calls",
                "status": "error"
            }
        
        print(f"🎯 LLM selected {len(tool_calls)} tool(s): {[call['tool'] for call in tool_calls]}")
        
        # Step 3: Execute all tool calls
        all_data = []
        for tool_call in tool_calls:
            tool_name: str = tool_call.get('tool', '')
            params = tool_call.get('params', {})
            
            result = executor.execute_tool(tool_name, params)
            
            # Extract data from result
            if 'data' in result and isinstance(result['data'], list):
                all_data.extend(result['data'])
            elif isinstance(result, list):
                all_data.extend(result)
        
        if not all_data:
            return {
                "user_query": user_input,
                "error": "No data returned from tool executions",
                "status": "error"
            }
        
        # Step 4: Create temporary SQLite database with fetched data
        print(f"💾 Creating SQLite database with {len(all_data)} records...")
        temp_db_path, table_schemas = create_dynamic_sqlite_tables(all_data)
        
        # Step 5: Generate SQL query using LLM based on schema and user query
        print(f"🧠 Generating SQL query...")
        sql_query = await generate_dynamic_sql_query(user_input, table_schemas, executor.llm)
        
        # Step 6: Execute SQL query
        print(f"⚡ Executing: {sql_query}")
        query_results = execute_sql_query(temp_db_path, sql_query)
        
        return {
            "user_query": user_input,
            "tool_calls": tool_calls,
            "generated_sql": sql_query,
            "result": query_results,
            "row_count": len(query_results) if query_results else 0,
            "table_schemas": table_schemas,
            "status": "success"
        }
        
    except Exception as e:
        return {
            "user_query": user_input,
            "error": str(e),
            "status": "error"
        }
    finally:
        # Step 7: Cleanup
        if temp_db_path:
            cleanup_temp_database(temp_db_path)
            print(f"🗑️ Cleaned up temporary database")

def create_dynamic_sqlite_tables(data: List[Dict[str, Any]]) -> tuple:
    """Create SQLite tables dynamically based on data structure"""
    
    # Create temporary database file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db_path = temp_file.name
    temp_file.close()
    
    conn = sqlite3.connect(temp_db_path)
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
            
        # Get columns from first record, excluding metadata
        print(f"🛠️ Creating table '{table_name}' with {len(records)} records")
        print(f"   Sample record: {records[0]}")
        columns = [col for col in records[0].keys() if col not in ['table_type']]
        
        # Create table
        column_defs = ", ".join([f'"{col}" TEXT' for col in columns])
        create_sql = f'CREATE TABLE "{table_name}" ({column_defs})'
        cursor.execute(create_sql)
        
        # Insert data
        placeholders = ", ".join(["?" for _ in columns])
        insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'
        
        for record in records:
            values = [str(record.get(col, '')) for col in columns]
            cursor.execute(insert_sql, values)
        
        table_schemas[table_name] = columns
        
    conn.commit()
    conn.close()
    
    print(f"📊 Created {len(table_schemas)} tables: {list(table_schemas.keys())}")
    return temp_db_path, table_schemas

async def generate_dynamic_sql_query(user_query: str, table_schemas: Dict[str, List[str]], llm) -> str:
    """Generate SQL query dynamically using LLM"""
    
    # Create schema description with enum values if applicable
    schema_desc = []
    for table, columns in table_schemas.items():
        col_list = ", ".join([f'"{col}"' for col in columns])
        schema_desc.append(f"- Table '{table}': Columns: {col_list}")

    schema_text = "\n".join(schema_desc)
    print(f"📚 Database Schema:\n{schema_text}")
    
    prompt = f"""
You are a SQL expert. Generate a SQLite query based on the user's request and database schema.

Database Schema:
{schema_text}

User Query: "{user_query}"

Requirements:
1. Use only tables and columns from the schema above
2. Return ONLY the SQL query, no explanations
3. Use proper SQLite syntax
4. Quote table/column names with double quotes if needed
5. Use JOINs when relating data from multiple tables
6. Use appropriate WHERE, GROUP BY, ORDER BY clauses
7. Make the query answer the user's question precisely

Generate the SQL query:
"""

    start_time = time.time()
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    end_time = time.time()
    
    print(f"🪙 SQL Generation Time: {end_time - start_time:.2f}s")
    
    # Clean up the SQL query
    content = response.content if hasattr(response, 'content') else str(response)
    sql_query = content.strip()
    print(f"📝 Raw SQL from LLM: {sql_query}")
    
    # Remove markdown formatting
    if sql_query.startswith('```sqlite'):
        sql_query = sql_query.replace('```sqlite', '').strip()
        sql_query = sql_query.replace('```', '').strip()
    elif sql_query.startswith('```'):
        sql_query = sql_query.replace('```', '').strip()
    
    return sql_query

def execute_sql_query(db_path: str, sql_query: str) -> List[Dict[str, Any]]:
    """Execute SQL query and return results"""
    
# ❌ SQL Error: You can only execute one statement at a time.
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        rows = cursor.execute(sql_query)
        results = [dict(row) for row in rows]
        return results
        
    except Exception as e:
        print(f"❌ SQL Error: {e}")
        raise e
    finally:
        conn.close()

def cleanup_temp_database(db_path: str):
    """Remove temporary database file"""
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")

# Main execution
async def run_dynamic_examples():
    """Run examples with fully dynamic tool selection and parameter extraction"""
    
    tools_json_path = "agents/db/tools.json"  # Path to your tools.json
    
    test_queries = [
        # "Find all active users",
        # "Show me users in engineering department", 
        # "Get active users from sales and marketing",
        # "Find users created after 2024-01-01"
        # "List all inactive users",
        "List all users names and emails",
    ]
    
    for query in test_queries:
        print(f"\n{'='*70}")
        print(f"🔍 Query: {query}")
        print('='*70)
        
        start_time = time.time()
        result = await process_dynamic_query_flow(query, tools_json_path)
        total_time = time.time() - start_time
        
        if result['status'] == 'success':
            print(f"✅ Tool Calls: {result['tool_calls']}")
            print(f"📊 Generated SQL: {result['generated_sql']}")
            print(f"📈 Results ({result['row_count']} rows):")
            
            for i, row in enumerate(result['result'][:3]):
                print(f"   {i+1}. {row}")
            
            if result['row_count'] > 3:
                print(f"   ... and {result['row_count'] - 3} more rows")
                
            print(f"⏱️ Total Time: {total_time:.2f}s")
        else:
            print(f"❌ Error: {result['error']}")

if __name__ == "__main__":
    # Run the dynamic system
    asyncio.run(run_dynamic_examples())
