import os
import json
import fitz
import re
import urllib.request
import urllib.parse
from src.redact_documents import get_cached_ocr

def extract_first_page_text(filepath, ocr_reader=None):
    text_content = ""
    try:
        ext = filepath.lower().rsplit('.', 1)[-1]
        if ext == 'pdf':
            doc = fitz.open(filepath)
            try:
                if len(doc) > 0:
                    page = doc[0]
                    text_content = page.get_text()
                    if len(text_content.strip()) < 50 and ocr_reader:
                        pix = page.get_pixmap()
                        img_bytes = pix.tobytes("png")
                        results = get_cached_ocr(img_bytes, ocr_reader)
                        ocr_text_list = [ocr_text for bbox, ocr_text, prob in results if prob > 0.2]
                        text_content = "\n".join(ocr_text_list)
            finally:
                doc.close()
        elif ext == 'docx':
            import docx
            doc = docx.Document(filepath)
            lines = [para.text for para in doc.paragraphs if para.text.strip()]
            text_content = "\n".join(lines[:20]) # First 20 paragraphs
        elif ext == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                text_content = "".join(lines[:50]) # First 50 lines
        elif ext == 'xlsx':
            import openpyxl
            wb = openpyxl.load_workbook(filepath, data_only=True)
            lines = []
            if wb.worksheets:
                for row in wb.worksheets[0].iter_rows(values_only=True, max_row=20):
                    row_text = " ".join([str(cell) for cell in row if cell is not None])
                    if row_text.strip(): lines.append(row_text)
            text_content = "\n".join(lines)
        elif ext == 'csv':
            import csv
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                lines = []
                for i, row in enumerate(reader):
                    if i >= 20: break
                    lines.append(" ".join(row))
                text_content = "\n".join(lines)
        elif ext == 'json':
            import json
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text_content = f.read()
        elif ext == 'xml':
            import xml.etree.ElementTree as ET
            tree = ET.parse(filepath)
            lines = []
            for i, elem in enumerate(tree.getroot().iter()):
                if i >= 50: break
                if elem.text and elem.text.strip():
                    lines.append(elem.text.strip())
            text_content = "\n".join(lines)
        elif ext in ['jpg', 'jpeg', 'png'] and ocr_reader:
            with open(filepath, 'rb') as f:
                img_bytes = f.read()
            results = get_cached_ocr(img_bytes, ocr_reader)
            ocr_text_list = [ocr_text for bbox, ocr_text, prob in results if prob > 0.2]
            text_content = "\n".join(ocr_text_list)
    except Exception as e:
        print(f"Extraction error in smart rename: {e}")
        
    return text_content[:2000] # Limit to 2000 chars to avoid huge payloads

def generate_local_nlp_name(text, analyzer):
    """Option A: Use local NLP and Regex to intelligently name the file"""
    if not text.strip():
        return ""
        
    doc_type = ""
    entity_name = ""
    period = ""
    
    # 1. Extract Document Type
    doc_type_mapping = {
        r"(?i)balance\s*sheet": "BalanceSheet",
        r"(?i)profit\s*(&|and)\s*loss": "ProfitAndLoss",
        r"(?i)tax\s*return|itr[-\s]*[1-7]?": "IncomeTaxReturn",
        r"(?i)gstr[-\s]*3b|gst\s*return|gstr[-\s]*1": "GSTReturn",
        r"(?i)net\s*worth\s*certificate": "NetWorthCertificate",
        r"(?i)no\s*due\s*certificate": "NoDueCertificate",
        r"(?i)bank\s*statement": "BankStatement",
        r"(?i)audit\s*report": "AuditReport",
        r"(?i)partnership\s*deed": "PartnershipDeed",
        r"(?i)incorporation\s*certificate": "IncorporationCertificate",
        r"(?i)pan\s*card": "PANCard",
        r"(?i)aadhaar\s*card": "AadhaarCard",
        r"(?i)rent\s*agreement": "RentAgreement",
        r"(?i)loan\s*sanction\s*letter": "LoanSanctionLetter",
        r"(?i)purchase\s*invoice|tax\s*invoice": "Invoice",
        r"(?i)form\s*16": "Form16",
        r"(?i)form\s*26as": "Form26AS",
        r"(?i)mca\s*circular|general\s*circular": "MCACircular",
        r"(?i)project\s*report": "ProjectReport",
        r"(?i)leave\s*application": "LeaveApplication",
        r"(?i)production\s*certificate": "ProductionCertificate"
    }
    
    for pattern, name in doc_type_mapping.items():
        # Only search for document type in the first 500 characters (the title/header area)
        # This prevents false positives from body text (e.g., "please submit your bank statement")
        if re.search(pattern, text[:500]):
            doc_type = name
            break
            
    # 2. Extract Entity Name
    results = analyzer.analyze(text=text, entities=['ORGANIZATION', 'PERSON'], language='en')
    # Filter to high confidence, sort by score then early appearance
    results = [r for r in results if r.score >= 0.5]
    results = sorted(results, key=lambda x: (x.score, -x.start), reverse=True)
    
    for res in results:
        extracted = text[res.start:res.end].strip()
        clean_name = re.sub(r'[^a-zA-Z0-9_\- ]', '', extracted)
        clean_name = clean_name.replace(' ', '_')
        # Require at least one letter so we don't accidentally pick a string of numbers
        if clean_name and len(clean_name) > 2 and re.search(r'[a-zA-Z]', clean_name):
            entity_name = clean_name
            break
            
    # 3. Extract Period
    # Look for FY / AY
    fy_match = re.search(r"(?i)(?:FY|F\.Y\.|AY|A\.Y\.)\s*20\d{2}[-\s]*\d{2}", text)
    if fy_match:
        period = re.sub(r'[^a-zA-Z0-9_\-]', '', fy_match.group(0).replace(' ', ''))
    else:
        # Look for months / date ranges
        date_match = re.search(r"(?i)(?:january|february|march|april|may|june|july|august|september|october|november|december)\s*20\d{2}", text)
        if date_match:
            period = date_match.group(0).replace(' ', '')
        else:
            # Check NLP dates
            date_results = analyzer.analyze(text=text, entities=['DATE_TIME'], language='en')
            if date_results:
                best_date = max(date_results, key=lambda x: x.score)
                extracted_date = text[best_date.start:best_date.end].strip()
                period = re.sub(r'[^a-zA-Z0-9_\-]', '', extracted_date.replace(' ', ''))
                
    # Combine
    parts = [p for p in [doc_type, entity_name, period] if p]
    if parts:
        return "_".join(parts)
        
    # Fallback
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        first_line = lines[0][:30]
        clean_name = re.sub(r'[^a-zA-Z0-9_\- ]', '', first_line).replace(' ', '_')
        if clean_name:
            return clean_name
            
    return ""

def generate_ai_name(text, ai_provider, api_key=None):
    """Option C: Send text to AI provider to summarize a short name"""
    if not text.strip():
        return ""
    prompt = f"""You are an expert document classification and naming assistant.

Your task is to analyze OCR text extracted from a document and determine:
1. The nature/type of the document.
2. The primary entity, company, or person's name.
3. The financial year, assessment year, date, or period mentioned (if any).
4. A concise and standardized file name suitable for document management systems.

Possible document types include but are not limited to:
* Balance Sheet, Profit & Loss Account, Income Tax Return, GST Return, Net Worth Certificate, No Due Certificate, Bank Statement, Audit Report, Partnership Deed, Incorporation Certificate, PAN Card, Aadhaar Card, Rent Agreement, Loan Sanction Letter, Purchase Invoice, Sale Invoice, Form 16, Form 26AS, Property Documents, ROC Filing, Other

Rules:
* Extract the most relevant person/company name that is the SUBJECT of the document.
* IMPORTANT: If the document is a letterhead, certificate, or report issued by a Chartered Accountant, Auditor, or Bank, DO NOT use the CA firm or Bank's name as the entity. Find the client or subject's name.
* Ignore OCR noise, page numbers, headers, footers, and repeated text.
* If a financial year is found, include it in the filename.
* Create a short filename using the format: <Document Type>_<Entity Name>_<Period>

Return ONLY valid JSON in the following format:
{{
"document_type": "",
"entity_name": "",
"period": "",
"suggested_file_name": "",
"confidence": 0,
"reasoning": ""
}}

OCR TEXT:
{text[:1500]}
"""

    def parse_ai_json(content):
        import json, re
        content = content.strip()
        if content.startswith("```json"): content = content[7:]
        elif content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        try:
            parsed = json.loads(content.strip())
            return parsed.get("suggested_file_name", "").strip()
        except Exception as e:
            print("Failed to parse JSON:", e, content)
            return ""

    try:
        if ai_provider == 'openai' and api_key:
            req = urllib.request.Request(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                data=json.dumps({
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }).encode('utf-8')
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                content = result['choices'][0]['message']['content']
                name = parse_ai_json(content)
                return re.sub(r'[^a-zA-Z0-9_\-]', '', name)
                
        elif ai_provider == 'google' and api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps({
                    "contents": [{"parts": [{"text": prompt}]}]
                }).encode('utf-8')
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                content = result['candidates'][0]['content']['parts'][0]['text']
                name = parse_ai_json(content)
                return re.sub(r'[^a-zA-Z0-9_\-]', '', name)
    except Exception as e:
        print(f"AI Naming Error: {e}")
        
    return ""

def generate_ai_name_batch(batch, ai_provider, api_key=None, id_token=None):
    """Send an array of text snippets to the AI and get back a dictionary of ID -> Suggested Name"""
    import json
    if not batch:
        return {}
        
    # Construct the JSON input for the prompt
    documents_json = []
    for item in batch:
        documents_json.append({
            "id": item['id'],
            # Increased to 1000 characters
            "text": item['text'][:1000] 
        })
        
    prompt = f"""You are an expert document classification and naming assistant.

Your task is to analyze an array of OCR text snippets extracted from multiple documents. For each document, determine:
1. The nature/type of the document.
2. The primary entity, company, or person's name.
3. The financial year, assessment year, date, or period mentioned (if any).
4. A concise and standardized file name suitable for document management systems.

Possible document types include but are not limited to:
* Balance Sheet, Profit & Loss Account, Income Tax Return, GST Return, Net Worth Certificate, No Due Certificate, Bank Statement, Audit Report, Partnership Deed, Incorporation Certificate, PAN Card, Aadhaar Card, Rent Agreement, Loan Sanction Letter, Purchase Invoice, Sale Invoice, Form 16, Form 26AS, Property Documents, ROC Filing, Other

Rules:
* Extract the most relevant person/company name that is the SUBJECT of the document.
* IMPORTANT: If the document is a letterhead, certificate, or report issued by a Chartered Accountant, Auditor, or Bank, DO NOT use the CA firm or Bank's name as the entity. Find the client or subject's name.
* Ignore OCR noise, page numbers, headers, footers, and repeated text.
* If a financial year is found, include it in the filename.
* Create a short filename using the format: <Document Type>_<Entity Name>_<Period>

Return ONLY a valid JSON ARRAY of objects in the following format:
[
  {{
    "id": 0,
    "suggested_file_name": ""
  }}
]

Documents to Process:
{json.dumps(documents_json)}
"""

    def parse_ai_json_batch(content):
        import json, re
        content = content.strip()
        if content.startswith("```json"): content = content[7:]
        elif content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        results_dict = {}
        try:
            parsed_array = json.loads(content.strip())
            for obj in parsed_array:
                name = obj.get("suggested_file_name", "").strip()
                clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '', name)
                results_dict[obj.get("id")] = clean_name
        except Exception as e:
            print("Failed to parse JSON array:", e, content)
        return results_dict

    try:
        import urllib.request
        import json
        
        # 1. Use Firebase Cloud Function if ID token is provided
        if id_token:
            url = 'https://us-central1-shielddocs-1f6cd.cloudfunctions.net/generateSmartRenameBatch'
            req = urllib.request.Request(
                url,
                headers={'Authorization': f'Bearer {id_token}', 'Content-Type': 'application/json'},
                data=json.dumps({"data": {"batch": documents_json}}).encode('utf-8')
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                
                # Firebase onCall returns { "result": { success, results, costCharged } }
                if 'result' in result and result['result'].get('success'):
                    return result['result'].get('results', {})
                else:
                    err_msg = result.get('error', {}).get('message', 'Unknown Firebase Error')
                    print("Firebase Rename Error:", result)
                    return {doc['id']: f"ERROR: {err_msg}" for doc in documents_json}
                    
        # 2. Direct OpenAI Fallback
        elif ai_provider == 'openai' and api_key:
            req = urllib.request.Request(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                data=json.dumps({
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }).encode('utf-8')
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                content = result['choices'][0]['message']['content']
                return parse_ai_json_batch(content)
                
        elif ai_provider == 'google' and api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps({
                    "contents": [{"parts": [{"text": prompt}]}]
                }).encode('utf-8')
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                content = result['candidates'][0]['content']['parts'][0]['text']
                return parse_ai_json_batch(content)
    except Exception as e:
        err_msg = str(e)
        if hasattr(e, 'read'):
            err_msg += " Body: " + e.read().decode('utf-8')
        print(f"AI Batch Naming Error: {err_msg}")
        with open("firebase_error.log", "w") as f:
            f.write(err_msg)
        
    return {}
