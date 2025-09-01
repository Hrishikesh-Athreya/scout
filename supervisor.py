from typing import Dict, List, Any
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain.globals import set_debug, set_verbose
import time
import dotenv

from agents.db.agent import build_db_agent
from agents.docs.agent import build_docs_agent  
from agents.comms.agent import build_comms_agent
from common.prompts import get_agent_prompt

dotenv.load_dotenv()

def measure_invoke(agent, inputs, config=None):
    """Wrapper to measure tokens and execution time"""
    start_time = time.time()
    
    if config is not None:
        result = agent.invoke(inputs, config)
    else:
        result = agent.invoke(inputs)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Try to extract token usage from different possible locations
    tokens_used = None
    if hasattr(result, 'llm_output') and result.llm_output:
        token_info = result.llm_output.get('token_usage', {})
        tokens_used = token_info.get('total_tokens')
    
    # Print metrics
    if tokens_used:
        print(f"🪙 Tokens: {tokens_used}")
    print(f"⏱️ Time: {duration:.2f}s")
    
    return result

def build_supervisor_agent():
    """Build the supervisor agent that coordinates other agents"""
    
    # Disable verbose debugging for cleaner output
    set_debug(False)
    set_verbose(False)
    
    # Build specialized agents
    agents = {
        "db": build_db_agent(),
        "docs": build_docs_agent(), 
        "comms": build_comms_agent()
    }
    
    def supervisor_node(state: MessagesState):
        """Main supervisor logic"""
        
        last_message = state["messages"][-1]
        user_query = extract_message_content(last_message)
        
        # Analyze query to determine which agents to use
        agent_plan = analyze_query_for_agents(user_query)
        
        if len(agent_plan) == 1:
            # Single agent workflow
            agent_name = agent_plan[0]
            agent = agents[agent_name]
            
            # Enhanced query with specific instructions
            enhanced_query = f"""
            Please use your available tools to find information about: {user_query}
            
            Requirements:
            1. Use appropriate filters and parameters
            2. Return structured data if possible
            3. If no data found, explain what was searched
            4. For status queries, use exact values: active, inactive, pending, suspended
            5. For business units, use: engineering, sales, marketing, hr, finance
            """
            
            result = measure_invoke(agent, {
                "messages": [HumanMessage(content=enhanced_query)]
            })
            
            return {"messages": result["messages"]}
        else:
            # Multi-agent workflow
            results = {}
            for agent_name in agent_plan:
                agent = agents[agent_name]
                result = measure_invoke(agent, {"messages": state["messages"]})
                results[agent_name] = result
            
            # Synthesize results
            synthesized_response = synthesize_multi_agent_results(results, user_query)
            return {"messages": state["messages"] + [synthesized_response]}
    
    # Create supervisor graph
    builder = StateGraph(MessagesState)
    builder.add_node("supervisor", supervisor_node)
    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", END)
    
    # Compile the graph
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
    """Analyze user query to determine which agents are needed using llm"""
    
    needed_agents = []

    # Use a language model to determine the agents needed
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    prompt = f"""
    You are an expert at classifying user queries into relevant specialized agents.
    The available agents are:
    - db: Database agent for fetching and retrieving data
    - docs: Document agent for PDF and document processing
    - comms: Communications agent for email and messaging operations
    Analyze the following user query and determine which agents are needed to fulfill the request.
    User Query: "{query}"
    Respond with a comma-separated list of agent names (db, docs, comms) that are relevant.
    If unsure, default to 'db'.
    """
    response = llm.predict_messages([HumanMessage(content=prompt)])
    response_text = extract_message_content(response).strip().lower()
    for agent in ['db', 'docs', 'comms']:
        if agent in response_text:
            needed_agents.append(agent)
    if not needed_agents:
        needed_agents.append('db')
    # # Simple keyword-based approach (commented out in favor of llm-based)
    
    # # Database-related keywords
    # db_keywords = ['data', 'users', 'orders', 'fetch', 'find', 'search', 'query', 
    #                'database', 'active', 'show', 'list', 'get', 'sales', 'customers']
    # if any(keyword in query_lower for keyword in db_keywords):
    #     needed_agents.append('db')
    #
    # # Document-related keywords
    # doc_keywords = ['pdf', 'document', 'report', 'extract', 'generate', 'template']
    # if any(keyword in query_lower for keyword in doc_keywords):
    #     needed_agents.append('docs')
    #
    # # Communication-related keywords
    # comm_keywords = ['email', 'send', 'notify', 'slack', 'message', 'alert']
    # if any(keyword in query_lower for keyword in comm_keywords):
    #     needed_agents.append('comms')
    #
    # # Default to db if no specific agent identified
    # if not needed_agents:
    #     needed_agents.append('db')
    
    return needed_agents

def synthesize_multi_agent_results(results: Dict[str, Any], original_query: str) -> AIMessage:
    """Synthesize results from multiple agents into a cohesive response"""
    
    synthesized_content = f"Multi-agent response for: {original_query}\n\n"
    
    for agent_name, result in results.items():
        if 'messages' in result and result['messages']:
            last_message = result['messages'][-1]
            content = extract_message_content(last_message)
            synthesized_content += f"{agent_name.upper()} Agent:\n{content}\n\n"
    
    return AIMessage(content=synthesized_content)

def create_multi_agent_system():
    """Create the complete multi-agent system with supervisor"""
    return build_supervisor_agent()

if __name__ == "__main__":
    supervisor_system = create_multi_agent_system()
    
    test_queries = [
        # "Find active users and give me their emails",
        "Show me all users with status active",
        # "Get user data from engineering department",
        # "List recent orders"
    ]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"🔍 Query: {query}")
        print('='*50)
        
        try:
            result = measure_invoke(supervisor_system, {
                "messages": [HumanMessage(content=query)]
            })
            
            if result and 'messages' in result and result['messages']:
                last_message = result['messages'][-1]
                content = extract_message_content(last_message)
                print(f"\n✅ Response:\n{content}")
            else:
                print("\n❌ No response received")
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
