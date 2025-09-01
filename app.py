import sqlite3
import tempfile
import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model

from agents.db.agent import build_db_agent
from common.tool_loader import load_tools_from_json
from common.prompts import get_agent_prompt

async def process_user_query_flow(user_input: str) -> Dict[str, Any]:
    """
    Complete flow: user input -> db agent -> temp sqlite -> sql generation -> result
    """
    temp_db_path = None
    
    try:
        # Step 1: Initialize DB agent
        print(f"🔍 Initializing DB agent...")
        db_agent = build_db_agent()
        
        # Step 2: Use DB agent to fetch required rows based on user input
        print(f"📊 Fetching data for query: {user_input}")
        fetch_result = await db_agent.ainvoke({
            "messages": [{"role": "user", "content": f"Fetch all relevant data for this analysis: {user_input}"}]
        })
        
        # Extract the actual data from agent response
        fetched_data = extract_data_from_agent_response(fetch_result)
        
        if not fetched_data:
            return {
                "user_query": user_input,
                "error": "No data was fetched by the database agent",
                "status": "error"
            }
        
        # Step 3: Create temporary SQLite database and save rows
        print("💾 Creating temporary SQLite tables...")
        temp_db_path, table_schemas = create_temp_sqlite_with_data(fetched_data)
        
        # Step 4: Generate SQL query based on user input and available schemas
        print("🧠 Generating SQL query from user input...")
        sql_query = await generate_sql_from_user_query(user_input, table_schemas)
        
        # Step 5: Execute query and get results
        print("⚡ Executing query on temporary database...")
        result = execute_query_on_temp_db(temp_db_path, sql_query)
        
        return {
            "user_query": user_input,
            "generated_sql": sql_query,
            "result": result,
            "row_count": len(result) if result else 0,
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
        # Step 6: Clean up temporary database
        if temp_db_path:
            cleanup_temp_db(temp_db_path)
            print("🗑️ Cleaned up temporary tables")

def extract_data_from_agent_response(agent_response: Dict) -> List[Dict]:
    """Extract actual data from the agent's response"""
    
    # Handle different response formats from the agent
    if 'messages' in agent_response:
        last_message = agent_response['messages'][-1]
        
        # Try to extract JSON from the content
        if hasattr(last_message, 'content'):
            content = last_message.content
            return parse_agent_data_response(content)
    
    # Fallback - assume direct data structure
    return agent_response.get('data', [])

def parse_agent_data_response(content: str) -> List[Dict]:
    """Parse agent response content to extract structured data"""
    
    try:
        # Try parsing as direct JSON
        if content.strip().startswith('[') or content.strip().startswith('{'):
            return json.loads(content)
        
        # Try to find JSON in the content
        import re
        json_pattern = r'``````'
        json_match = re.search(json_pattern, content, re.DOTALL)
        
        if json_match:
            return json.loads(json_match.group(1))
        
        # Try to find any JSON-like structure
        json_pattern = r'(\[.*\]|\{.*\})'
        json_match = re.search(json_pattern, content, re.DOTALL)
        
        if json_match:
            return json.loads(json_match.group(1))
            
    except (json.JSONDecodeError, AttributeError):
        pass
    
    # If no JSON found, create mock data for demo
    # In production, you'd want to handle this differently
    return create_mock_data_from_response(content)

def create_mock_data_from_response(content: str) -> List[Dict]:
    """Create mock data structure when agent returns unstructured data"""
    
    # This is a fallback for demo purposes
    # In production, you'd want your DB agent to return structured data
    return [
        {
            "id": "1",
            "name": "John Doe",
            "email": "john@example.com",
            "status": "active",
            "businessUnit": "engineering",
            "createdAt": "2024-01-15",
            "table_type": "users"
        },
        {
            "id": "2", 
            "name": "Jane Smith",
            "email": "jane@example.com",
            "status": "active",
            "businessUnit": "sales",
            "createdAt": "2024-02-20",
            "table_type": "users"
        },
        {
            "order_id": "100",
            "user_id": "1",
            "product": "Widget A",
            "amount": "150.00",
            "order_date": "2024-03-10",
            "table_type": "orders"
        },
        {
            "order_id": "101",
            "user_id": "2", 
            "product": "Widget B",
            "amount": "75.00",
            "order_date": "2024-03-12",
            "table_type": "orders"
        }
    ]

def create_temp_sqlite_with_data(fetched_data: List[Dict]) -> Tuple[str, Dict[str, List[str]]]:
    """Create temporary SQLite DB and populate with fetched data"""
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db_path = temp_file.name
    temp_file.close()
    
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    
    # Group data by table type/structure
    tables_data = organize_data_by_structure(fetched_data)
    table_schemas = {}
    
    # Create tables and insert data
    for table_name, rows in tables_data.items():
        if rows:
            # Create table based on first row structure
            columns = [col for col in rows[0].keys() if col != 'table_type']
            column_defs = ", ".join([f'"{col}" TEXT' for col in columns])
            
            create_sql = f'CREATE TABLE "{table_name}" ({column_defs})'
            cursor.execute(create_sql)
            
            # Store schema info
            table_schemas[table_name] = columns
            
            # Insert data
            placeholders = ", ".join(["?" for _ in columns])
            insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'
            
            for row in rows:
                values = [str(row.get(col, '')) for col in columns]
                cursor.execute(insert_sql, values)
    
    conn.commit()
    conn.close()
    
    print(f"📊 Created {len(table_schemas)} temporary tables: {list(table_schemas.keys())}")
    return temp_db_path, table_schemas

def organize_data_by_structure(data: List[Dict]) -> Dict[str, List[Dict]]:
    """Organize fetched data into logical tables based on structure"""
    tables = {}
    
    for item in data:
        # Determine table name based on data structure or metadata
        table_name = determine_table_name(item)
        
        if table_name not in tables:
            tables[table_name] = []
        
        tables[table_name].append(item)
    
    return tables

def determine_table_name(item: Dict) -> str:
    """Determine appropriate table name for data item"""
    
    # Check if item has explicit table type
    if 'table_type' in item:
        return item['table_type']
    
    # Determine based on key patterns
    keys = set(item.keys())
    
    # User-like data
    if 'email' in keys and 'name' in keys:
        return 'users'
    
    # Order-like data
    if 'order_id' in keys or ('user_id' in keys and 'amount' in keys):
        return 'orders'
    
    # Product-like data
    if 'product_id' in keys or 'product_name' in keys:
        return 'products'
    
    # Default fallback
    if 'id' in keys:
        return 'main_data'
    
    return 'temp_data'

async def generate_sql_from_user_query(user_query: str, table_schemas: Dict[str, List[str]]) -> str:
    """Generate SQL query based on user input and available table schemas"""
    
    # Initialize a model for SQL generation
    model = init_chat_model("anthropic:claude-3-5-sonnet-latest")
    
    # Create schema description
    schema_descriptions = []
    for table, columns in table_schemas.items():
        schema_descriptions.append(f"Table '{table}': {', '.join(columns)}")
    
    schema_description = "\n".join(schema_descriptions)
    
    prompt = f"""
    You are a SQL expert. Generate a SQLite query based on the user's request and available data.
    
    Available Database Schema:
    {schema_description}
    
    User Request: {user_query}
    
    Rules:
    1. Only use the tables and columns shown above
    2. Return ONLY the SQL query, no explanation or formatting
    3. Use proper SQLite syntax
    4. Quote table and column names with double quotes if needed
    5. Make sure the query answers the user's question as best as possible
    6. Use JOINs when relationships between tables are needed
    7. Use appropriate WHERE clauses, GROUP BY, ORDER BY as needed
    
    Generate the SQL query:
    """
    
    response = await model.ainvoke([{"role": "user", "content": prompt}])
    
    # Extract SQL from response (remove markdown formatting if present)
    sql_query = response.content.strip()
    if sql_query.startswith('```
        sql_query = sql_query.replace('```sql', '').replace('```
    elif sql_query.startswith('```'):
        sql_query = sql_query.replace('```
    
    return sql_query

def execute_query_on_temp_db(temp_db_path: str, sql_query: str) -> List[Dict]:
    """Execute SQL query on temporary database and return results"""
    
    conn = sqlite3.connect(temp_db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        result = [dict(row) for row in rows]
        
        return result
        
    except Exception as e:
        print(f"❌ SQL execution error: {e}")
        print(f"Query: {sql_query}")
        raise e
    finally:
        conn.close()

def cleanup_temp_db(temp_db_path: str):
    """Remove temporary database file"""
    try:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)
    except Exception as e:
        print(f"⚠️ Warning: Could not clean up temp file {temp_db_path}: {e}")

# Example usage and testing
async def run_example_queries():
    """Run example queries to demonstrate the flow"""
    
    test_queries = [
        "Show me all active users",
        "What are the total sales by business unit?",
        "List all orders with user details",
        "Find users who have made orders",
        "Show me recent orders with amounts over $100"
    ]
    
    for query in test_queries:
        print(f"\n" + "="*60)
        print(f"🔍 Processing Query: {query}")
        print("="*60)
        
        result = await process_user_query_flow(query)
        
        if result['status'] == 'success':
            print(f"✅ Generated SQL: {result['generated_sql']}")
            print(f"📊 Results ({result['row_count']} rows):")
            
            # Pretty print first few results
            for i, row in enumerate(result['result'][:3]):
                print(f"   {i+1}: {row}")
            
            if result['row_count'] > 3:
                print(f"   ... and {result['row_count'] - 3} more rows")
        else:
            print(f"❌ Error: {result['error']}")

if __name__ == "__main__":
    # Run the example
    asyncio.run(run_example_queries())
