def validate_data_keys(data, required_keys):
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ValueError(f"Missing required keys: {missing}")

def safety_check_instructions(instructions):
    forbidden = ["delete", "drop", "format disk"]
    for term in forbidden:
        if term in instructions.lower():
            raise ValueError(f"Unsafe term detected in instructions: {term}")
