import json
from typing import Optional, Dict
from openai import OpenAI
import requests
from config import OPENAI_API_KEY

class BasePlanner:
    def plan(self, instructions: str, template_descriptions: Optional[Dict[str, str]] = None) -> Optional[str]:
        raise NotImplementedError

class OpenAIPlanner(BasePlanner):
    def __init__(self, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = model

    def plan(self, instructions: str, template_descriptions: Optional[Dict[str, str]] = None) -> str:
        if template_descriptions is None:
            template_descriptions = {}

        templates_info_str = "\n".join(
            f"Template '{name}':\n{desc}" for name, desc in template_descriptions.items()
        )

        prompt = f"""
You are a PDF workflow planner working with the following templates:
{templates_info_str}

Given user instructions, return a JSON array of step objects including the template name.
Each step contains an action and parameters (template name, image path, watermark text, etc.).

Instructions:
\"\"\"{instructions}\"\"\"

Only output valid JSON.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Received empty response from OpenAI planner.")
        return content.strip()

class GeminiPlanner(BasePlanner):
    def __init__(self, api_key: str, endpoint: str):
        self.api_key = api_key
        self.endpoint = endpoint

    def plan(self, instructions: str, template_descriptions: Optional[Dict[str, str]] = None) -> str:
        if template_descriptions is None:
            template_descriptions = {}

        templates_info_str = "\n".join(
            f"Template '{name}':\n{desc}" for name, desc in template_descriptions.items()
        )

        prompt = f"""
You are a PDF workflow planner working with the following templates:
{templates_info_str}

Given user instructions, return a JSON array of step objects including the template name.
Each step contains an action and parameters (template name, image path, watermark text, etc.).

Instructions:
\"\"\"{instructions}\"\"\"

Only output valid JSON.
"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {
            "model": "gemini-1",
            "prompt": prompt,
            "temperature": 0,
        }

        r = requests.post(self.endpoint, json=data, headers=headers)
        r.raise_for_status()

        text = r.json().get("text")
        if text is None:
            raise ValueError("Received empty response from Gemini planner.")
        return text.strip()
