import os
import yaml
import glob
import json
import random
import string
# from faker import Faker (removed)
# presidio_analyzer imports moved inside setup_analyzer
import re
import fitz  # PyMuPDF
import docx
import csv
import xml.etree.ElementTree as ET
import hashlib
ocr_cache = {}
def get_cached_ocr(img_bytes, ocr_reader):
    img_hash = hashlib.md5(img_bytes).hexdigest()
    if img_hash in ocr_cache:
        return ocr_cache[img_hash]
    results = ocr_reader.readtext(img_bytes)
    ocr_cache[img_hash] = results
    return results
from src.pseudo_anonymizer import PseudoAnonymizer
def _check_ocr():
    import importlib.util
    return importlib.util.find_spec("easyocr") is not None
OCR_AVAILABLE = _check_ocr()
def get_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
# CaseSensitiveCompanyRecognizer moved inside setup_analyzer for lazy loading
def load_custom_rules():
    rules_path = os.path.expanduser('~/.shielddocs/data/custom_rules.json')
    if os.path.exists(rules_path):
        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading custom rules: {e}")
    return {"words": [], "regexes": []}
def setup_analyzer():
    from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, EntityRecognizer, RecognizerResult
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    import spacy

    class CaseSensitiveCompanyRecognizer(EntityRecognizer):
        def __init__(self):
            super().__init__(supported_entities=["ORGANIZATION"])
            self.pattern = re.compile(r"\b(?:(?:[A-Z][A-Za-z0-9&.,-]*|[a-z]|&)[ \t]+){1,10}(?:Private Limited|PRIVATE LIMITED|Pvt Ltd|PVT LTD|Pvt\. Ltd\.|PVT\. LTD\.|Limited|LIMITED|Ltd\.|LTD\.|LLP|Inc|Corp|INC|CORP|Associates|ASSOCIATES|& Co\.|& CO\.|& Co|& CO|Bank Ltd\.?|Bank Limited)\b|\bM/s\.?[ \t]+(?:[A-Z][A-Za-z0-9&.,-]*[ \t]*){1,10}\b")
        def analyze(self, text, entities, nlp_artifacts=None):
            results = []
            for match in self.pattern.finditer(text):
                results.append(RecognizerResult(
                    entity_type="ORGANIZATION",
                    start=match.start(),
                    end=match.end(),
                    score=0.9
                ))
            return results

    # Prefer local offline models without attempting network download
    model_name = "en_core_web_lg"
    try:
        spacy.load(model_name)
    except Exception:
        try:
            spacy.load("en_core_web_sm")
            model_name = "en_core_web_sm"
        except Exception:
            pass

    try:
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": model_name}]
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
    except Exception as e:
        print(f"Fallback AnalyzerEngine initialization: {e}")
        analyzer = AnalyzerEngine()
    custom_rules = load_custom_rules()
    if custom_rules.get("words"):
        escaped_words = [re.escape(w.strip()) for w in custom_rules["words"] if w.strip()]
        if escaped_words:
            regex_str = r"(?i)\b(?:" + "|".join(escaped_words) + r")\b"
            custom_word_pattern = Pattern(name="custom_words_pattern", regex=regex_str, score=1.0)
            custom_word_recognizer = PatternRecognizer(supported_entity="CUSTOM_WORD", patterns=[custom_word_pattern])
            analyzer.registry.add_recognizer(custom_word_recognizer)
    if custom_rules.get("regexes"):
        for i, rx in enumerate(custom_rules["regexes"]):
            pattern_str = rx.get("pattern", "").strip()
            name = rx.get("name", f"custom_regex_{i}").strip()
            if pattern_str:
                pat = Pattern(name=f"rx_{i}", regex=pattern_str, score=1.0)
                entity_type = "CUSTOM_REGEX"
                if name:
                    entity_type = "CUSTOM_" + re.sub(r'[^A-Z0-9_]', '', name.upper().replace(' ', '_'))
                rec = PatternRecognizer(supported_entity=entity_type, patterns=[pat])
                analyzer.registry.add_recognizer(rec)
    gst_pattern_strict = Pattern(
        name="gst_pattern_strict",
        regex=r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}[Zz][0-9A-Z]{1}\b",
        score=0.9
    )
    gst_pattern_ocr = Pattern(
        name="gst_pattern_ocr",
        regex=r"(?i)\b(?=\w*[0-9])[0-9OoSsUuIlZzGgAaBbq]{2}[A-Za-z0125864]{5}[0-9OoSsUuIlZzGgAaBbq]{4}[A-Za-z0125864]{1}[A-Za-z0-9]{1}[Zz2S5]{1}[A-Za-z0-9]{1}\b",
        score=0.6
    )
    gst_recognizer = PatternRecognizer(supported_entity="IN_GST", patterns=[gst_pattern_strict, gst_pattern_ocr])
    analyzer.registry.add_recognizer(gst_recognizer)
    pan_pattern_strict = Pattern(
        name="pan_pattern_strict",
        regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
        score=0.9
    )
    pan_pattern_ocr = Pattern(
        name="pan_pattern_ocr",
        regex=r"(?i)\b(?=\w*[0-9])[A-Za-z0125864]{5}[0-9OoSsUuIlZzGgAaBbq]{4}[A-Za-z0125864]{1}\b",
        score=0.6
    )
    pan_recognizer = PatternRecognizer(supported_entity="IN_PAN", patterns=[pan_pattern_strict, pan_pattern_ocr])
    analyzer.registry.add_recognizer(pan_recognizer)
    dob_pattern = Pattern(
        name="dob_pattern",
        regex=r"(?i)(?:DOB|Date of Birth|D\.O\.B)[\s:-]*\d{2}[-/]\d{2}[-/]\d{4}",
        score=0.9
    )
    dob_recognizer = PatternRecognizer(supported_entity="DATE_TIME", patterns=[dob_pattern])
    analyzer.registry.add_recognizer(dob_recognizer)
    auth_person_pattern = Pattern(
        name="auth_person_pattern",
        regex=r"(?i)(?<=Authorised Signatory: )[^\n]+|(?<=Authorised Person: )[^\n]+|(?<=Authorised Signatory:)[^\n]+|(?<=Authorised Person:)[^\n]+|(?<=Authorised Signatory )[^\n]+|(?<=Authorised Person )[^\n]+",
        score=0.9
    )
    auth_person_recognizer = PatternRecognizer(supported_entity="PERSON", patterns=[auth_person_pattern])
    analyzer.registry.add_recognizer(auth_person_recognizer)
    name_field_pattern = Pattern(
        name="name_field_pattern",
        regex=r"(?i)(?<=Name: )[^\n]+|(?<=Name:)[^\n]+",
        score=0.9
    )
    name_field_recognizer = PatternRecognizer(supported_entity="PERSON", patterns=[name_field_pattern])
    analyzer.registry.add_recognizer(name_field_recognizer)
    company_recognizer = CaseSensitiveCompanyRecognizer()
    analyzer.registry.add_recognizer(company_recognizer)
    aadhaar_pattern_strict = Pattern(
        name="aadhaar_pattern_strict",
        regex=r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b",
        score=0.9
    )
    aadhaar_pattern_ocr = Pattern(
        name="aadhaar_pattern_ocr",
        regex=r"(?i)\b(?=.*[0-9])[2-9ZzSsBbq]{1}[0-9OoSsUuIlZzGgAaBbq]{3}\s?[0-9OoSsUuIlZzGgAaBbq]{4}\s?[0-9OoSsUuIlZzGgAaBbq]{4}\b",
        score=0.6
    )
    aadhaar_recognizer = PatternRecognizer(supported_entity="IN_AADHAAR", patterns=[aadhaar_pattern_strict, aadhaar_pattern_ocr])
    analyzer.registry.add_recognizer(aadhaar_recognizer)
    ack_no_pattern = Pattern(
        name="ack_no_pattern",
        regex=r"(?i)\b(?:Ack No|Acknowledgement No|Ack\. No\.)[\s:]+[A-Za-z0-9]+\b",
        score=0.9
    )
    ack_no_recognizer = PatternRecognizer(supported_entity="ACK_NO", patterns=[ack_no_pattern])
    analyzer.registry.add_recognizer(ack_no_recognizer)
    frn_pattern = Pattern(
        name="frn_pattern",
        regex=r"(?i)\b(?:FRN|Firm Regn\. No\.|Firm Registration Number)[\s:]+[A-Za-z0-9]+\b",
        score=0.9
    )
    frn_recognizer = PatternRecognizer(supported_entity="FRN", patterns=[frn_pattern])
    analyzer.registry.add_recognizer(frn_recognizer)
    mno_pattern = Pattern(
        name="mno_pattern",
        regex=r"(?i)\b(?:M\. No\.|Membership No\.)[\s:]+[0-9]+\b",
        score=0.9
    )
    mno_recognizer = PatternRecognizer(supported_entity="MEMBERSHIP_NO", patterns=[mno_pattern])
    analyzer.registry.add_recognizer(mno_recognizer)
    udin_pattern = Pattern(
        name="udin_pattern",
        regex=r"(?i)\b(?:UDIN)[\s:]+[A-Za-z0-9]+\b",
        score=0.9
    )
    udin_recognizer = PatternRecognizer(supported_entity="UDIN", patterns=[udin_pattern])
    analyzer.registry.add_recognizer(udin_recognizer)
    return analyzer
def process_pdf(filepath, analyzer, anonymizer, config, out_path, ocr_reader=None, mappings_to_apply=None):
    if mappings_to_apply is None: mappings_to_apply = anonymizer.mapping
    try:
        doc = fitz.open(filepath)
        try:
            entities = config.get('redaction', {}).get('entities', ['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER'])
            lang = config.get('redaction', {}).get('language', 'en')
            for page in doc:
                text = page.get_text()
                if len(text.strip()) < 50 and ocr_reader:
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    ocr_results = get_cached_ocr(img_bytes, ocr_reader)
                    scale_x = page.rect.width / pix.width
                    scale_y = page.rect.height / pix.height
                    redacted_rects = []
                    for bbox, ocr_text, prob in ocr_results:
                        if prob < 0.2:
                            continue
                        for orig, fake_val in sorted(mappings_to_apply.items(), key=lambda x: len(x[0]), reverse=True):
                            import re
                            match = re.search(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', ocr_text, re.IGNORECASE)
                            if match:
                                start_idx = match.start()
                                end_idx = match.end()
                                start_frac = start_idx / max(1, len(ocr_text))
                                end_frac = end_idx / max(1, len(ocr_text))
                                x0 = min(p[0] for p in bbox)
                                y0 = min(p[1] for p in bbox)
                                x1 = max(p[0] for p in bbox)
                                y1 = max(p[1] for p in bbox)
                                box_width = x1 - x0
                                pii_x0 = x0 + box_width * start_frac
                                pii_x1 = x0 + box_width * end_frac
                                rect = fitz.Rect(pii_x0 * scale_x, y0 * scale_y, pii_x1 * scale_x, y1 * scale_y)
                                
                                overlaps = False
                                for r in redacted_rects:
                                    if rect.intersects(r):
                                        overlaps = True
                                        break
                                if not overlaps:
                                    page.add_redact_annot(rect, text=fake_val, fill=(1, 1, 1))
                                    redacted_rects.append(rect)
                else:
                    if not text.strip(): continue
                    redacted_rects = []
                    for orig, fake_val in sorted(mappings_to_apply.items(), key=lambda x: len(x[0]), reverse=True):
                        rects = page.search_for(orig)
                        for rect in rects:
                            overlaps = False
                            for r in redacted_rects:
                                if rect.intersects(r):
                                    overlaps = True
                                    break
                            if not overlaps:
                                page.add_redact_annot(rect, text=fake_val, fill=(1, 1, 1))
                                redacted_rects.append(rect)
                page.apply_redactions()
            doc.save(out_path)
        finally:
            doc.close()
    except Exception as e:
        print(f"Error processing PDF {filepath}: {e}")
def process_docx(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply=None):
    if mappings_to_apply is None: mappings_to_apply = anonymizer.mapping
    try:
        doc = docx.Document(filepath)
        entities = config.get('redaction', {}).get('entities', ['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER'])
        lang = config.get('redaction', {}).get('language', 'en')
        for para in doc.paragraphs:
            if not para.text.strip(): continue
            import re
            for orig in sorted(mappings_to_apply.keys(), key=len, reverse=True):
                new_fake = mappings_to_apply[orig]
                pattern = re.compile(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', re.IGNORECASE)
                para.text = pattern.sub(lambda m: new_fake, para.text)
        doc.save(out_path)
    except Exception as e:
        print(f"Error processing DOCX {filepath}: {e}")
def process_txt(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply=None):
    if mappings_to_apply is None: mappings_to_apply = anonymizer.mapping
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        if not text.strip(): return
        import re
        for orig in sorted(mappings_to_apply.keys(), key=len, reverse=True):
            new_fake = mappings_to_apply[orig]
            pattern = re.compile(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', re.IGNORECASE)
            text = pattern.sub(lambda m: new_fake, text)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)
    except Exception as e:
        print(f"Error processing TXT {filepath}: {e}")
def process_excel(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply=None):
    if mappings_to_apply is None: mappings_to_apply = anonymizer.mapping
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath)
        import re
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        text = cell.value
                        for orig in sorted(mappings_to_apply.keys(), key=len, reverse=True):
                            new_fake = mappings_to_apply[orig]
                            pattern = re.compile(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', re.IGNORECASE)
                            text = pattern.sub(lambda m: new_fake, text)
                        cell.value = text
        wb.save(out_path)
    except Exception as e:
        print(f"Error processing Excel {filepath}: {e}")
def process_csv(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply=None):
    if mappings_to_apply is None: mappings_to_apply = anonymizer.mapping
    try:
        import re
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as infile:
            reader = csv.reader(infile)
            rows = list(reader)
        for i in range(len(rows)):
            for j in range(len(rows[i])):
                if rows[i][j]:
                    text = rows[i][j]
                    for orig in sorted(mappings_to_apply.keys(), key=len, reverse=True):
                        new_fake = mappings_to_apply[orig]
                        pattern = re.compile(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', re.IGNORECASE)
                        text = pattern.sub(lambda m: new_fake, text)
                    rows[i][j] = text
        with open(out_path, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile)
            writer.writerows(rows)
    except Exception as e:
        print(f"Error processing CSV {filepath}: {e}")
def process_json(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply=None):
    if mappings_to_apply is None: mappings_to_apply = anonymizer.mapping
    try:
        import re
        def redact_data(data):
            if isinstance(data, dict):
                for k, v in data.items():
                    data[k] = redact_data(v)
                return data
            elif isinstance(data, list):
                return [redact_data(item) for item in data]
            elif isinstance(data, str):
                text = data
                for orig in sorted(mappings_to_apply.keys(), key=len, reverse=True):
                    new_fake = mappings_to_apply[orig]
                    pattern = re.compile(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', re.IGNORECASE)
                    text = pattern.sub(lambda m: new_fake, text)
                return text
            else:
                return data
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
        data = redact_data(data)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error processing JSON {filepath}: {e}")
def process_xml(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply=None):
    if mappings_to_apply is None: mappings_to_apply = anonymizer.mapping
    try:
        import re
        tree = ET.parse(filepath)
        root = tree.getroot()
        def apply_redaction(text):
            if not text: return text
            for orig in sorted(mappings_to_apply.keys(), key=len, reverse=True):
                new_fake = mappings_to_apply[orig]
                pattern = re.compile(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', re.IGNORECASE)
                text = pattern.sub(lambda m: new_fake, text)
            return text
        for elem in root.iter():
            if elem.text:
                elem.text = apply_redaction(elem.text)
            if elem.tail:
                elem.tail = apply_redaction(elem.tail)
            for k, v in elem.attrib.items():
                elem.attrib[k] = apply_redaction(v)
        tree.write(out_path, encoding='utf-8', xml_declaration=True)
    except Exception as e:
        print(f"Error processing XML {filepath}: {e}")
def process_image(filepath, analyzer, anonymizer, config, out_path, ocr_reader=None, mappings_to_apply=None):
    if mappings_to_apply is None: mappings_to_apply = anonymizer.mapping
    if not ocr_reader:
        print("OCR reader is required to process images.")
        return
    try:
        img_doc = fitz.open(filepath)
        pdf_bytes = img_doc.convert_to_pdf()
        img_doc.close()
        doc = fitz.open("pdf", pdf_bytes)
        page = doc[0]
        pix = page.get_pixmap()
        img_bytes = pix.tobytes("png")
        ocr_results = get_cached_ocr(img_bytes, ocr_reader)
        scale_x = page.rect.width / pix.width
        scale_y = page.rect.height / pix.height
        redacted_rects = []
        for bbox, ocr_text, prob in ocr_results:
            if prob < 0.2:
                continue
            for orig, fake_val in sorted(mappings_to_apply.items(), key=lambda x: len(x[0]), reverse=True):
                import re
                match = re.search(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', ocr_text, re.IGNORECASE)
                if match:
                    start_idx = match.start()
                    end_idx = match.end()
                    start_frac = start_idx / max(1, len(ocr_text))
                    end_frac = end_idx / max(1, len(ocr_text))
                    x0 = min(p[0] for p in bbox)
                    y0 = min(p[1] for p in bbox)
                    x1 = max(p[0] for p in bbox)
                    y1 = max(p[1] for p in bbox)
                    box_width = x1 - x0
                    pii_x0 = x0 + box_width * start_frac
                    pii_x1 = x0 + box_width * end_frac
                    rect = fitz.Rect(pii_x0 * scale_x, y0 * scale_y, pii_x1 * scale_x, y1 * scale_y)
                    
                    overlaps = False
                    for r in redacted_rects:
                        if rect.intersects(r):
                            overlaps = True
                            break
                    if not overlaps:
                        page.add_redact_annot(rect, text=fake_val, fill=(1, 1, 1))
                        redacted_rects.append(rect)
        page.apply_redactions()
        out_pix = page.get_pixmap()
        out_pix.save(out_path)
        doc.close()
    except Exception as e:
        print(f"Error processing image {filepath}: {e}")
def analyze_file(filepath, analyzer, anonymizer, config, ocr_reader=None, original_filename=None):
    import json
    ext = os.path.splitext(filepath)[1].lower()
    entities = config.get('redaction', {}).get('entities', ['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER'])
    lang = config.get('redaction', {}).get('language', 'en')
    found_mappings = {}
    def add_to_mappings(original, entity_type):
        original = original.strip()
        if not original: return
        import re
        if re.search(r'[\u0900-\u097F]', original): return
        if re.match(r'^[\d\s.,/\-₹$€£%]+$', original): return
        ignore_list = {
            'mens rea', 'mens', 'rea', 'inter alia', 'sc', 'hc', 'scn', 'fir', 'ipc', 'crpc', 'roc', 'mca',
            'gst', 'cgst', 'sgst', 'igst', 'tds', 'tcs', 'vat', 'tin', 'din', 'dpin', 'pan', 'tan',
            'nclt', 'nclat', 'itat', 'drt', 'drat', 'sebi', 'rbi', 'irdai', 'fema', 'pmla',
            'date', 'page', 'ref', 'no', 'sr', 'sl', 'amount', 'total', 'tax', 'rupees', 'rs', 'inr',
            'appellant', 'respondent', 'plaintiff', 'defendant', 'petitioner', 'applicant', 'counsel',
            'advocate', 'judge', 'justice', 'sir', 'madam', 'passed', 'filed', 'order', 'judgment',
            'annexure', 'exhibit', 'paragraph', 'section', 'rule', 'act', 'article', 'court', 'tribunal',
            'company', 'director', 'manager', 'partner', 'proprietor', 'authorized', 'signatory',
            'cgst commissionerate', 'assessing officer', 'assissing officer', 'proper officer', 
            'poper office', 'proper office', 'inspector', 'commissioner', 'superintendent'
        }
        if original.lower() in ignore_list: return
        if entity_type in ('PERSON', 'LOCATION') and original.isupper() and len(original) <= 4:
            return
        fake_val = anonymizer.get_fake_value(original, entity_type)
        found_mappings[original] = fake_val
    if original_filename:
        name_no_ext = os.path.splitext(original_filename)[0]
    else:
        base_name = os.path.basename(filepath)
        name_no_ext = os.path.splitext(base_name)[0]
        import re
        name_no_ext = re.sub(r'_[0-9a-f]{8}$', '', name_no_ext)
    if name_no_ext.strip():
        filename_results = analyzer.analyze(text=name_no_ext, entities=entities, language=lang)
        for result in filename_results:
            add_to_mappings(name_no_ext[result.start:result.end], result.entity_type)
    if ext == '.pdf':
        doc = fitz.open(filepath)
        try:
            total_pages = len(doc)
            for i, page in enumerate(doc):
                yield json.dumps({"status": "progress", "message": f"Analyzing page {i+1} of {total_pages}..."})
                text = page.get_text()
                if len(text.strip()) < 50 and ocr_reader:
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    ocr_results = get_cached_ocr(img_bytes, ocr_reader)
                    full_ocr_text = "\n".join([t[1] for t in ocr_results if t[2] > 0.2])
                    results = analyzer.analyze(text=full_ocr_text, entities=entities, language=lang)
                    for result in results:
                        add_to_mappings(full_ocr_text[result.start:result.end], result.entity_type)
                else:
                    if not text.strip(): continue
                    results = analyzer.analyze(text=text, entities=entities, language=lang)
                    for result in results:
                        add_to_mappings(text[result.start:result.end], result.entity_type)
        finally:
            doc.close()
    elif ext == '.docx':
        doc = docx.Document(filepath)
        total_paras = len(doc.paragraphs)
        for i, para in enumerate(doc.paragraphs):
            if i % 10 == 0:
                yield json.dumps({"status": "progress", "message": f"Analyzing paragraph {i+1} of {total_paras}..."})
            if not para.text.strip(): continue
            results = analyzer.analyze(text=para.text, entities=entities, language=lang)
            for result in results:
                add_to_mappings(para.text[result.start:result.end], result.entity_type)
    elif ext == '.txt':
        yield json.dumps({"status": "progress", "message": "Analyzing text document..."})
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        if text.strip():
            results = analyzer.analyze(text=text, entities=entities, language=lang)
            for result in results:
                add_to_mappings(text[result.start:result.end], result.entity_type)
    elif ext == '.xlsx':
        yield json.dumps({"status": "progress", "message": "Analyzing Excel document..."})
        import openpyxl
        wb = openpyxl.load_workbook(filepath, data_only=True)
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                for cell in row:
                    if cell and isinstance(cell, str):
                        results = analyzer.analyze(text=cell, entities=entities, language=lang)
                        for result in results:
                            add_to_mappings(cell[result.start:result.end], result.entity_type)
    elif ext == '.csv':
        yield json.dumps({"status": "progress", "message": "Analyzing CSV document..."})
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            for row in reader:
                for cell in row:
                    if cell:
                        results = analyzer.analyze(text=cell, entities=entities, language=lang)
                        for result in results:
                            add_to_mappings(cell[result.start:result.end], result.entity_type)
    elif ext == '.json':
        yield json.dumps({"status": "progress", "message": "Analyzing JSON document..."})
        def analyze_data(data):
            if isinstance(data, dict):
                for k, v in data.items(): analyze_data(v)
            elif isinstance(data, list):
                for item in data: analyze_data(item)
            elif isinstance(data, str):
                results = analyzer.analyze(text=data, entities=entities, language=lang)
                for result in results:
                    add_to_mappings(data[result.start:result.end], result.entity_type)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            analyze_data(json.load(f))
    elif ext == '.xml':
        yield json.dumps({"status": "progress", "message": "Analyzing XML document..."})
        tree = ET.parse(filepath)
        for elem in tree.getroot().iter():
            for text_part in [elem.text, elem.tail] + list(elem.attrib.values()):
                if text_part and isinstance(text_part, str):
                    results = analyzer.analyze(text=text_part, entities=entities, language=lang)
                    for result in results:
                        add_to_mappings(text_part[result.start:result.end], result.entity_type)
    elif ext in ['.jpg', '.jpeg', '.png']:
        yield json.dumps({"status": "progress", "message": "Analyzing image file..."})
        if ocr_reader:
            with open(filepath, 'rb') as f:
                img_bytes = f.read()
            ocr_results = get_cached_ocr(img_bytes, ocr_reader)
            full_ocr_text = "\n".join([t[1] for t in ocr_results if t[2] > 0.2])
            results = analyzer.analyze(text=full_ocr_text, entities=entities, language=lang)
            for result in results:
                add_to_mappings(full_ocr_text[result.start:result.end], result.entity_type)
        else:
            yield json.dumps({"status": "progress", "message": "OCR reader not initialized. Cannot analyze image."})
    yield json.dumps({"status": "complete", "mappings": found_mappings})
def process_file(filepath, analyzer, anonymizer, config, ocr_reader=None, mappings_to_apply=None, original_filename=None):
    print(f"Processing {filepath}...")
    ext = os.path.splitext(filepath)[1].lower()
    output_dir = os.path.expanduser(config.get('paths', {}).get('output_dir', '~/.shielddocs/data/output/'))
    os.makedirs(output_dir, exist_ok=True)
    if original_filename:
        name, original_ext = os.path.splitext(original_filename)
    else:
        base_name = os.path.basename(filepath)
        name, original_ext = os.path.splitext(base_name)
        import re
        name = re.sub(r'_[0-9a-f]{8}$', '', name)
    if mappings_to_apply:
        for orig in sorted(mappings_to_apply.keys(), key=len, reverse=True):
            new_fake = mappings_to_apply[orig]
            import re
            pattern = re.compile(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', re.IGNORECASE)
            name = pattern.sub(lambda m: new_fake, name)
    from werkzeug.utils import secure_filename
    name = secure_filename(name)
    out_path = os.path.join(output_dir, f"{name}_redacted_ocr{original_ext}")
    if ext == '.pdf':
        process_pdf(filepath, analyzer, anonymizer, config, out_path, ocr_reader, mappings_to_apply)
        print(f"Saved redacted PDF to {out_path}\n")
    elif ext == '.docx':
        process_docx(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply)
        print(f"Saved redacted DOCX to {out_path}\n")
    elif ext == '.txt':
        process_txt(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply)
        print(f"Saved redacted TXT to {out_path}\n")
    elif ext == '.xlsx':
        process_excel(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply)
        print(f"Saved redacted Excel to {out_path}\n")
    elif ext == '.csv':
        process_csv(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply)
        print(f"Saved redacted CSV to {out_path}\n")
    elif ext == '.json':
        process_json(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply)
        print(f"Saved redacted JSON to {out_path}\n")
    elif ext == '.xml':
        process_xml(filepath, analyzer, anonymizer, config, out_path, mappings_to_apply)
        print(f"Saved redacted XML to {out_path}\n")
    elif ext in ['.jpg', '.jpeg', '.png']:
        process_image(filepath, analyzer, anonymizer, config, out_path, ocr_reader, mappings_to_apply)
        print(f"Saved redacted image to {out_path}\n")
    else:
        print(f"Unsupported file type: {ext}")
        return None
    return out_path
def main():
    print("="*50)
    print("Starting Document PII Redactor")
    print("="*50)
    config = get_config()
    input_dir = os.path.expanduser(config.get('paths', {}).get('input_dir', '~/.shielddocs/data/input/'))
    if not os.path.exists(input_dir):
        print(f"Input directory not found. Creating {input_dir}")
        os.makedirs(input_dir, exist_ok=True)
        print("Please place your files (.pdf, .docx, .txt) in the input directory and run again.")
        return
    files = glob.glob(os.path.join(input_dir, '*.*'))
    if not files:
        print(f"No files found in {input_dir}.")
        return
    analyzer = setup_analyzer()
    output_dir = os.path.expanduser(config.get('paths', {}).get('output_dir', '~/.shielddocs/data/output/'))
    anonymizer = PseudoAnonymizer(os.path.join(output_dir, '..', 'mapping.json'))
    ocr_reader = None
    if OCR_AVAILABLE:
        print("Initializing EasyOCR (this may take a moment)...")
        try:
            import easyocr
            ocr_reader = easyocr.Reader(['en'], download_enabled=False)
        except Exception as e:
            print(f"Failed to initialize EasyOCR: {e}")
            ocr_reader = None
    else:
        print("EasyOCR not found. Image-based PDFs will not be properly redacted.")
    for file in files:
        process_file(file, analyzer, anonymizer, config, ocr_reader)
if __name__ == '__main__':
    main()
