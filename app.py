import sqlite3
import tempfile
import os
from typing import Dict, List, Any, Optional
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model

from agents.db.agent import build_db_agent
from common.tool_loader import load_tools_from_json

async def process_user_query_flow(user_input: str) -> Dict[str, Any]:
    """
    Complete flow: user input -> db agent -> temp sqlite -> sql generation -> result
    """
    temp_db_path = None
    
    try:
        # Step 1: Initialize DB agent
        db_agent = build_db_agent()
        
        # Step 2: Use DB agent to fetch required rows based on user input
        print(f"🔍 Fetching data for query: {user_input}")
        fetch_result = await db_agent.ainvoke({
            "messages": [{"role": "user", "content": f"Fetch all relevant data for: {user_input}"}]
        })
        
        # Extract the actual data from agent response
        fetched_data = extract_data_from_agent_response(fetch_result)
        
        # Step 3: Create temporary SQLite database and save rows
        print("💾 Creating temporary SQLite tables...")
        temp_db_path, table_schemas = create_temp_sqlite_with_data(fetched_data)
        
        # Step 4: Generate SQL query based on user input and available schemas
        print("🧠 Generating SQL query...")
        sql_query = await generate_sql_from_user_query(user_input, table_schemas)
        
        # Step 5: Execute query and get results
        print("⚡ Executing query on temporary database...")
        result = execute_query_on_temp_db(temp_db_path, sql_query)
        
        return {
            "user_query": user_input,
            "generated_sql": sql_query,
            "result": result,
            "row_count": len(result) if result else 0,
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
    # This depends on how your db agent structures its response
    # Adjust based on your actual agent implementation
    if 'messages' in agent_response:
        last_message = agent_response['messages'][-1]
        if hasattr(last_message, 'content'):
            # Parse the content to extract structured data
            # You might need to adjust this based on your agent's response format
            return parse_agent_data_response(last_message.content)
    
    # Fallback - assume direct data structure
    return agent_response.get('data', [])

def create_temp_sqlite_with_data(fetched_data: List[Dict]) -> tuple[str, Dict[str, List[str]]]:
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
            columns = list(rows[0].keys())
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
    # Logic to determine table name based on data structure
    # You can customize this based on your data patterns
    
    if 'table_type' in item:
        return item['table_type']
    elif 'source' in item:
        return f"data_{item['source']}"
    elif 'type' in item:
        return f"temp_{item['type']}"
    else:
        # Generate based on available keys
        key_signature = "_".join(sorted(item.keys())[:3])  # Use first 3 keys
        return f"temp_{hash(key_signature) % 10000}"

async def generate_sql_from_user_query(user_query: str, table_schemas: Dict[str, List[str]]) -> str:
    """Generate SQL query based on user input and available table schemas"""
    
    # Initialize a model for SQL generation
    model = init_chat_model("anthropic:claude-3-5-sonnet-latest")
    
    # Create schema description
    schema_description = "\n".join([
        f"Table '{table}': {', '.join(columns)}" 
        for table, columns in table_schemas.items()
    ])
    
    prompt = f"""
    Given the following temporary database schema:
    {schema_description}
    
    Generate a SQL query to answer this user question: {user_query}
    
    Rules:
    - Only use the tables and columns shown above
    - Return only the SQL query, no explanation
    - Use proper SQL syntax for SQLite
    - Quote table and column names with double quotes if they contain spaces or special characters
    """
    
    response = await model.ainvoke([{"role": "user", "content": prompt}])
    
    # Extract SQL from response (remove markdown formatting if present)
    sql_query = response.content.strip()
    if sql_query.startswith('```
        sql_query = sql_query.replace('```sql', '').replace('```
    
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

def parse_agent_data_response(content: str) -> List[Dict]:
    """Parse agent response content to extract structured data"""
    # This is a placeholder - implement based on your agent's response format
    # Could be JSON, CSV, or other structured format
    import json
    
    try:
        # Try parsing as JSON first
        return json.loads(content)
    except:
        # Implement other parsing logic based on your agent's format
        return []

# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Example queries
        test_queries = [
            "Show me all users who made purchases last month",
            "What are the top 5 products by sales?",
            "List customers with pending orders"
        ]
        
        for query in test_queries:
            print(f"\n" + "="*50)
            print(f"Processing: {query}")
            print("="*50)
            
            result = await process_user_query_flow(query)
            
            if result['status'] == 'success':
                print(f"✅ Generated SQL: {result['generated_sql']}")
                print(f"📊 Results ({result['row_count']} rows):")
                for row in result['result'][:5]:  # Show first 5 rows
                    print(f"   {row}")
                if result['row_count'] > 5:
                    print(f"   ... and {result['row_count'] - 5} more rows")
            else:
                print(f"❌ Error: {result['error']}")
    
    asyncio.run(main())
