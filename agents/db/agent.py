from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.globals import set_debug, set_verbose
from common.tool_loader import load_tools_from_json
from common.prompts import get_agent_prompt

def build_db_agent():
    """Build the database agent from tools.json"""
    
    # Enable debugging
    set_debug(True)  # Shows all internal operations
    set_verbose(True)  # Shows important events
    
    # Load tools from JSON configuration
    tools = load_tools_from_json("/Users/arnavdewan/Desktop/Repos/scout/agents/db/tools.json")
    
    print(f"🔧 Loaded {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
    
    # Initialize model
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Get custom prompt for database operations
    system_prompt = get_agent_prompt("db")
    print(f"📝 System prompt: {system_prompt[:100]}...")
    
    # Create agent with tools
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt
    )
    
    return agent
