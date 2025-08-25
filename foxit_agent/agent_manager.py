import json
from tools import doc_gen_generate_pdf, insert_image, merge_pdfs, watermark_pdf, compress_pdf
from guardrails import validate_data_keys, safety_check_instructions
from planners import OpenAIPlanner, GeminiPlanner
from config import GEMINI_API_KEY, GEMINI_ENDPOINT
from template_registry import TEMPLATES

class FoxitAgentManager:
    def __init__(self, planner_type="openai"):
        self.required_keys = ["date", "region", "sales", "items"]
        if planner_type=="openai":
            self.planner = OpenAIPlanner()
        elif planner_type=="gemini":
            self.planner = GeminiPlanner(GEMINI_API_KEY, GEMINI_ENDPOINT)
        else:
            raise ValueError("Unsupported planner type")

    def plan_workflow(self, instructions):
        return self.planner.plan(instructions, TEMPLATES)

    def execute_plan(self, data, plan, template_path="templates/report_template.docx"):
        validate_data_keys(data, self.required_keys)
        pdf_path = None
        plan_dict = json.loads(plan)
        for step in plan_dict.get("steps", []):
            action = step.get("action")
            if action == "generate":
                template = step.get("template", template_path)
                pdf_path = doc_gen_generate_pdf(data, template)
            elif action == "insert_image":
                if not pdf_path:
                    raise RuntimeError("PDF must be generated before inserting images")
                image_path = step.get("image_path")
                position = step.get("position")
                size = step.get("size")
                pdf_path = insert_image(pdf_path, image_path, position, size)
            elif action == "merge":
                pdfs = step.get("pdfs")
                pdf_path = merge_pdfs(pdfs)
            elif action == "watermark":
                if not pdf_path:
                    raise RuntimeError("PDF must be generated before watermarking")
                text = step.get("text", "CONFIDENTIAL")
                pdf_path = watermark_pdf(pdf_path, text)
            elif action == "compress":
                if not pdf_path:
                    raise RuntimeError("PDF must be generated before compressing")
                pdf_path = compress_pdf(pdf_path)
            else:
                raise RuntimeError(f"Unknown action: {action}")
        return pdf_path

    def run(self, data, instructions):
        safety_check_instructions(instructions)
        plan = self.plan_workflow(instructions)
        return self.execute_plan(data, plan)
