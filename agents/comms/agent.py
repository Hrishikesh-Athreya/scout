from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from common.tool_loader import load_tools_from_json
from common.prompts import get_agent_prompt

def build_comms_agent():
    """Build the communications agent from tools.json"""
    
    # Load tools from JSON configuration
    tools = load_tools_from_json("/Users/arnavdewan/Desktop/Repos/scout/agents/comms/tools.json")
    
    # Initialize model
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Get custom prompt for communication operations
    system_prompt = get_agent_prompt("comms")
    
    
    # Create agent with tools
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
    )
    
    return agent
