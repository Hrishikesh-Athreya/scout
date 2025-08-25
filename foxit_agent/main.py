from agent_manager import FoxitAgentManager

data = {
    "date": "2025-08-24",
    "region": "West",
    "sales": 99999,
    "items": [
        {"name": "Widget A", "units": 10, "revenue": 8000},
        {"name": "Widget B", "units": 20, "revenue": 19000}
    ]
}

instructions = """
Generate a report using the report_template.docx template,
insert the image assets/example_image.png at position [100,200] sized [250,150],
watermark the PDF with the text CONFIDENTIAL,
then compress the final PDF.
"""

agent = FoxitAgentManager(planner_type="gemini")

try:
    final_pdf_path = agent.run(data, instructions)
    print(f"Final PDF created: {final_pdf_path}")
except Exception as e:
    print(f"Error: {e}")
