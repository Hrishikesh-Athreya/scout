TEMPLATES = {
    "report_template.docx": """
    Template fields:
    - date: string (e.g., 2025-08-24)
    - region: string (e.g., West)
    - sales: number (total sales amount)
    - items: list of objects with fields:
        - name: string
        - units: integer
        - revenue: number
    """,

    "invoice_template.docx": """
    Template fields:
    - invoice_number: string
    - date: string
    - customer_name: string
    - items: list of objects with:
        - description: string
        - quantity: integer
        - price: number
    - total: number
    """,

    # Add more templates as needed
}
