import json
import os
import re
from typing import List, Dict, Any, Optional, Type
import requests
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model, validator

def load_tools_from_json(json_file_path: str) -> List[BaseTool]:
    """
    Load tools from JSON configuration file and create LangChain tools
    """
    
    # Load JSON configuration
    with open(json_file_path, 'r') as f:
        tools_config = json.load(f)
    
    tools = []
    
    for tool_config in tools_config:
        # Create tool from configuration
        langchain_tool = create_tool_from_config(tool_config)
        tools.append(langchain_tool)
    
    return tools

def create_tool_from_config(config: Dict[str, Any]) -> BaseTool:
    """
    Create a LangChain tool from JSON configuration
    """
    
    tool_name = config['name']
    tool_description = config['description']
    parameters_schema = config['parameters']
    execution_config = config['execution']
    
    # Create dynamic Pydantic model for parameters
    ParameterModel = create_parameter_model(tool_name, parameters_schema)
    
    # Create the tool function
    if execution_config['type'] == 'http':
        tool_func = create_http_tool_function(execution_config, tool_name)
    else:
        raise ValueError(f"Unsupported execution type: {execution_config['type']}")
    
    # Create the tool using StructuredTool
    structured_tool = StructuredTool.from_function(
        func=tool_func,
        name=tool_name,
        description=tool_description,
        args_schema=ParameterModel
    )
    
    return structured_tool

def create_parameter_model(tool_name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
    """
    Create a Pydantic model from JSON schema for tool parameters with enum support
    """
    
    properties = schema.get('properties', {})
    required_fields = set(schema.get('required', []))
    
    model_fields = {}
    validators = {}
    
    for field_name, field_config in properties.items():
        field_type = get_python_type_from_json_type(field_config['type'])
        description = field_config.get('description', '')
        
        # Handle enum fields
        if 'enum' in field_config:
            enum_values = field_config['enum']
            
            # Create custom validator for enum fields
            def create_enum_validator(allowed_values):
                def validate_enum(cls, v):
                    if v not in allowed_values:
                        raise ValueError(f"Value must be one of {allowed_values}")
                    return v
                return validate_enum
            
            validators[f'validate_{field_name}'] = validator(field_name, allow_reuse=True)(
                create_enum_validator(enum_values)
            )
        
        # Handle required vs optional fields
        if field_name in required_fields:
            model_fields[field_name] = (field_type, Field(description=description))
        else:
            model_fields[field_name] = (Optional[field_type], Field(default=None, description=description))
    
    # Create dynamic model with validators
    model_name = f"{tool_name.replace('_', ' ').title().replace(' ', '')}Parameters"
    
    # Create the model class with validators
    model_class = create_model(model_name, **model_fields)
    
    # Add validators to the model
    for validator_name, validator_func in validators.items():
        setattr(model_class, validator_name, validator_func)
    
    return model_class

def get_python_type_from_json_type(json_type):
    """
    Convert JSON schema type to Python type with enum support
    """
    if isinstance(json_type, list):
        # Handle union types like ["string", "null"]
        non_null_types = [t for t in json_type if t != "null"]
        if len(non_null_types) == 1:
            return get_single_python_type(non_null_types[0])
        else:
            # For multiple non-null types, default to str
            return str
    else:
        return get_single_python_type(json_type)

def get_single_python_type(json_type: str):
    """
    Map single JSON type to Python type
    """
    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict
    }
    return type_mapping.get(json_type, str)

def create_http_tool_function(execution_config: Dict[str, Any], tool_name: str):
    """
    Create HTTP execution function for the tool
    """
    
    method = execution_config['method'].upper()
    base_url = execution_config['url']
    headers = execution_config.get('headers', {})
    query_map = execution_config.get('query_map', {})
    timeout = execution_config.get('timeout', 30)
    
    def http_tool_function(**kwargs) -> str:
        """
        Execute HTTP request with provided parameters
        """
        
        # Prepare query parameters
        query_params = {}
        for param_name, param_value in kwargs.items():
            if param_value is not None:
                # Map parameter name to query parameter name
                query_key = query_map.get(param_name, param_name)
                query_params[query_key] = param_value
        
        # Interpolate environment variables in URL and headers
        url = safe_env_interpolation(base_url)
        processed_headers = {k: safe_env_interpolation(v) for k, v in headers.items()}
        
        try:
            # Make HTTP request
            response = requests.request(
                method=method,
                url=url,
                params=query_params if method == 'GET' else None,
                json=query_params if method in ['POST', 'PUT', 'PATCH'] else None,
                headers=processed_headers,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # Return response as JSON string or text
            try:
                result = response.json()
                return json.dumps(result, indent=2)
            except:
                return response.text
                
        except requests.RequestException as e:
            return f"Error executing {tool_name}: {str(e)}"
    
    return http_tool_function

def safe_env_interpolation(text: str) -> str:
    """
    Safely interpolate environment variables in text
    Supports ${VAR_NAME} and ${VAR_NAME:default_value} syntax
    """
    if not isinstance(text, str):
        return text
    
    # Pattern to match ${VAR_NAME} or ${VAR_NAME:default}
    pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
    
    def replacer(match):
        var_name = match.group(1)
        default_value = match.group(2) if match.group(2) is not None else ''
        return os.getenv(var_name, default_value)
    
    return re.sub(pattern, replacer, text)

# Utility function for testing tools
def test_tool_from_json(json_file_path: str, tool_name: str, **test_params):
    """
    Test a specific tool from JSON configuration
    """
    
    tools = load_tools_from_json(json_file_path)
    
    # Find the specific tool
    target_tool = None
    for tool in tools:
        if tool.name == tool_name:
            target_tool = tool
            break
    
    if not target_tool:
        print(f"Tool '{tool_name}' not found in {json_file_path}")
        return None
    
    print(f"Testing tool: {tool_name}")
    print(f"Description: {target_tool.description}")
    print(f"Parameters: {test_params}")
    
    try:
        result = target_tool.invoke(test_params)
        print(f"Result: {result}")
        return result
    except Exception as e:
        print(f"Error: {e}")
        return None
