# Create test_tools.py
from common.tool_loader import load_tools_from_json

def test_db_tools():
    """Test database tools directly"""
    
    print("🧪 Testing database tools...")
    
    # Load tools
    tools = load_tools_from_json("/Users/arnavdewan/Desktop/Repos/scout/agents/db/tools.json")
    
    for tool in tools:
        print(f"\n🔧 Testing tool: {tool.name}")
        print(f"Description: {tool.description}")
        
        try:
            # Test with some parameters
            result = tool.invoke({
                "status": "ACTIVE",
            })
            print(f"✅ Tool result: {result[:200]}...")
            
        except Exception as e:
            print(f"❌ Tool error: {e}")

if __name__ == "__main__":
    test_db_tools()
