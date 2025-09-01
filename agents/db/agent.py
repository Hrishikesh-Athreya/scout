from langgraph.prebuilt import create_react_agent
from langchain.chat_models import init_chat_model
from common.tool_loader import load_tools_from_json
from common.prompts import get_agent_prompt

def build_db_agent():
    """Build the database agent from tools.json"""
    
    # Load tools from JSON configuration
    tools = load_tools_from_json("db/tools.json")
    
    # Initialize model
    model = init_chat_model(
        model="gemini-2.5-flash",
        temperature=0,
        max_retries=3
    )
    
    # Get custom prompt if available
    system_prompt = get_agent_prompt("db") or """
    You are a database agent. Your job is to fetch relevant data based on user queries.
    Always return structured data that can be easily processed.
    When fetching data, include all relevant fields that might be useful for analysis.
    """
    
    # Create agent with tools
    agent = create_react_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )
    
    return agent
