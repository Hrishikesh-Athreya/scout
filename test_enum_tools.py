# test_enum_tools.py
from common.tool_loader import load_tools_from_json

def test_enum_validation():
    """Test that enum validation works correctly"""
    
    tools = load_tools_from_json("/Users/arnavdewan/Desktop/Repos/scout/agents/db/tools.json")
    
    for tool in tools:
        if tool.name == "db_get_users":
            print(f"Testing {tool.name}")
            
            # Test valid enum values
            valid_tests = [
                {"status": "ACTIVE", "businessUnit": "engineering"},
                {"status": "INACTIVE", "businessUnit": "sales"},
                {}  # empty parameters
            ]
            
            for test_params in valid_tests:
                try:
                    result = tool.invoke(test_params)
                    print(f"✅ Valid params {test_params}: Success")
                except Exception as e:
                    print(f"❌ Valid params {test_params}: {e}")
            
            # Test invalid enum values
            invalid_tests = [
                {"status": "unknown"},  # invalid status
                {"businessUnit": "invalid_dept"}  # invalid business unit
            ]
            
            for test_params in invalid_tests:
                try:
                    result = tool.invoke(test_params)
                    print(f"⚠️ Invalid params {test_params}: Should have failed but didn't")
                except Exception as e:
                    print(f"✅ Invalid params {test_params}: Correctly rejected - {e}")

if __name__ == "__main__":
    test_enum_validation()
