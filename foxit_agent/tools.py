import base64
import os
import requests
from config import FOXIT_CLIENT_ID, FOXIT_CLIENT_SECRET, FOXIT_DOCGEN_URL, FOXIT_PDF_SERVICES_URL

def doc_gen_generate_pdf(data, template_path):
    with open(template_path, "rb") as f:
        template_b64 = base64.b64encode(f.read()).decode()
    payload = {
        "outputFormat": "pdf",
        "documentValues": data,
        "base64FileString": template_b64
    }
    headers = {
        "client_id": FOXIT_CLIENT_ID,
        "client_secret": FOXIT_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    resp = requests.post(FOXIT_DOCGEN_URL, json=payload, headers=headers)
    resp.raise_for_status()
    pdf_b64 = resp.json()["document"]
    out_path = "output/generated_report.pdf"
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(pdf_b64))
    return out_path

def insert_image(pdf_path, image_path, position, size):
    # This is a placeholder.
    # Foxit PDF Services API may not have "insert image" as a direct call.
    # Instead, you would use Foxit PDF SDK or pre-compose template with images or annotations.
    # This function emulates the feature by returning the path unchanged.
    print(f"Inserting image {image_path} at {position} with size {size} into {pdf_path} (simulated)")
    return pdf_path

def merge_pdfs(pdf_paths):
    # Chain merge API - upload all docs and merge
    # For demonstration, simulate with first PDF
    print(f"Merging PDFs: {pdf_paths} (simulated)")
    return pdf_paths[0]

def watermark_pdf(pdf_path, text="CONFIDENTIAL"):
    with open(pdf_path, "rb") as f:
        files = {'file': ('file.pdf', f, 'application/pdf')}
        data = {"text": text}
        headers = {"client_id": FOXIT_CLIENT_ID, "client_secret": FOXIT_CLIENT_SECRET}
        resp = requests.post(f"{FOXIT_PDF_SERVICES_URL}/watermark", files=files, data=data, headers=headers)
        resp.raise_for_status()
        pdf_data = resp.content
    out_path = "output/watermarked_report.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_data)
    return out_path

def compress_pdf(pdf_path):
    with open(pdf_path, "rb") as f:
        files = {'file': ('file.pdf', f, 'application/pdf')}
        headers = {"client_id": FOXIT_CLIENT_ID, "client_secret": FOXIT_CLIENT_SECRET}
        resp = requests.post(f"{FOXIT_PDF_SERVICES_URL}/compress", files=files, headers=headers)
        resp.raise_for_status()
        pdf_data = resp.content
    out_path = "output/compressed_report.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_data)
    return out_path
