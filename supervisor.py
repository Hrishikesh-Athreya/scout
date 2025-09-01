from typing import Dict, List, Any
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain.globals import set_debug, set_verbose

from agents.db.agent import build_db_agent
from agents.docs.agent import build_docs_agent  
from agents.comms.agent import build_comms_agent
from common.prompts import get_agent_prompt

import dotenv
dotenv.load_dotenv()

def build_supervisor_agent():
    """Build the supervisor agent that coordinates other agents"""
    
    # Enable debugging
    set_debug(True)
    set_verbose(True)
    
    print("🏗️ Building specialized agents...")
    
    # Build specialized agents
    agents = {
        "db": build_db_agent(),
        "docs": build_docs_agent(), 
        "comms": build_comms_agent()
    }
    
    print(f"✅ Built {len(agents)} agents: {list(agents.keys())}")
    
    def supervisor_node(state: MessagesState):
        """Main supervisor logic with enhanced debugging"""
        
        last_message = state["messages"][-1]
        user_query = extract_message_content(last_message)
        
        print(f"\n📨 Processing query: {user_query}")
        
        # Analyze query to determine which agents to use
        agent_plan = analyze_query_for_agents(user_query)
        print(f"🎯 Selected agents: {agent_plan}")
        
        if len(agent_plan) == 1:
            # Single agent workflow
            agent_name = agent_plan[0]
            agent = agents[agent_name]
            
            print(f"🤖 Calling {agent_name} agent...")
            
            # Add more specific instructions for the agent
            enhanced_query = f"""
            Please use your available tools to find information about: {user_query}
            
            Be sure to:
            1. Use the appropriate filters and parameters
            2. Return structured data if possible
            3. If no data is found, explain what you searched for
            """
            
            result = agent.invoke({
                "messages": [HumanMessage(content=enhanced_query)]
            })
            
            print(f"📊 Agent result: {result}")
            return {"messages": result["messages"]}
        else:
            # Multi-agent workflow
            results = {}
            for agent_name in agent_plan:
                print(f"🤖 Calling {agent_name} agent...")
                agent = agents[agent_name]
                result = agent.invoke({"messages": state["messages"]})
                results[agent_name] = result
                print(f"📊 {agent_name} result: {result}")
            
            # Synthesize results
            synthesized_response = synthesize_multi_agent_results(results, user_query)
            return {"messages": state["messages"] + [synthesized_response]}
    
    # Create supervisor graph
    builder = StateGraph(MessagesState)
    builder.add_node("supervisor", supervisor_node)
    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", END)
    
    # Compile the graph without checkpointer
    supervisor_graph = builder.compile()
    
    return supervisor_graph

def extract_message_content(message) -> str:
    """Extract content from different message types"""
    if hasattr(message, 'content'):
        return message.content
    elif isinstance(message, dict) and 'content' in message:
        return message['content']
    else:
        return str(message)

def analyze_query_for_agents(query: str) -> List[str]:
    """Analyze user query to determine which agents are needed"""
    
    query_lower = query.lower()
    needed_agents = []
    
    # Database-related keywords
    db_keywords = ['data', 'users', 'orders', 'fetch', 'find', 'search', 'query', 'database', 'active', 'show', 'list', 'get']
    if any(keyword in query_lower for keyword in db_keywords):
        needed_agents.append('db')
    
    # Document-related keywords
    doc_keywords = ['pdf', 'document', 'report', 'extract', 'generate', 'template']
    if any(keyword in query_lower for keyword in doc_keywords):
        needed_agents.append('docs')
    
    # Communication-related keywords
    comm_keywords = ['email', 'send', 'notify', 'slack', 'message', 'alert']
    if any(keyword in query_lower for keyword in comm_keywords):
        needed_agents.append('comms')
    
    # Default to db if no specific agent identified
    if not needed_agents:
        needed_agents.append('db')
        print(f"⚠️ No specific agent keywords found, defaulting to: {needed_agents}")
    
    return needed_agents

def synthesize_multi_agent_results(results: Dict[str, Any], original_query: str) -> AIMessage:
    """Synthesize results from multiple agents into a cohesive response"""
    
    synthesized_content = f"Multi-agent response for: {original_query}\n\n"
    
    for agent_name, result in results.items():
        if 'messages' in result and result['messages']:
            last_message = result['messages'][-1]
            content = extract_message_content(last_message)
            synthesized_content += f"{agent_name.upper()} Agent Result:\n{content}\n\n"
    
    return AIMessage(content=synthesized_content)

def create_multi_agent_system():
    """Create the complete multi-agent system with supervisor"""
    return build_supervisor_agent()

if __name__ == "__main__":
    # Test the supervisor system
    supervisor_system = create_multi_agent_system()
    
    test_queries = [
        "Find active users",
        # "Show me all users with status active",  # More specific
        # "Get user data from the database"  # Very explicit
    ]
    
    for query in test_queries:
        print(f"\n" + "="*60)
        print(f"🔍 Testing Query: {query}")
        print("="*60)
        
        try:
            result = supervisor_system.invoke({
                "messages": [HumanMessage(content=query)]
            })
            
            if result and 'messages' in result and result['messages']:
                last_message = result['messages'][-1]
                content = extract_message_content(last_message)
                print(f"✅ Final Result: {content}")
            else:
                print("❌ No result returned")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
