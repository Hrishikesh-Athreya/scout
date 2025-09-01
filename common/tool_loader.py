# common/tool_loader.py
import json
from typing import List, Dict, Any

def load_tools_from_json(filepath: str) -> List[Dict[str, Any]]:
    """Load tool configurations as dictionaries for API execution"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Tools file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in tools file: {e}")
        return []
    except Exception as e:
        print(f"❌ Error loading tools: {e}")
        return []
