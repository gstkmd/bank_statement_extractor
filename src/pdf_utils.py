import fitz
import os

def merge_pdfs(pdf_paths, output_path):
    """
    Merge multiple PDFs into a single PDF.
    pdf_paths: list of paths to PDF files in the desired order.
    output_path: path to save the merged PDF.
    """
    merged_doc = fitz.open()
    try:
        for path in pdf_paths:
            if os.path.exists(path):
                with fitz.open(path) as doc:
                    merged_doc.insert_pdf(doc)
        merged_doc.save(output_path, garbage=4, deflate=True)
    finally:
        merged_doc.close()
    return output_path

def parse_sequence(seq_str, total_pages):
    """
    Parse a sequence string like '1,3,4-6,2' into a list of 0-indexed page numbers.
    """
    pages = []
    if not seq_str:
        return pages
        
    parts = seq_str.split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            ranges = part.split('-')
            if len(ranges) == 2 and ranges[0].isdigit() and ranges[1].isdigit():
                start = int(ranges[0])
                end = int(ranges[1])
                # Pages are 1-indexed for the user, 0-indexed internally
                # Allow backward ranges like 6-4
                if start <= end:
                    for p in range(start, end + 1):
                        if 1 <= p <= total_pages:
                            pages.append(p - 1)
                else:
                    for p in range(start, end - 1, -1):
                        if 1 <= p <= total_pages:
                            pages.append(p - 1)
        elif part.isdigit():
            p = int(part)
            if 1 <= p <= total_pages:
                pages.append(p - 1)
    return pages

def split_resequence_pdf(pdf_path, sequence, output_path):
    """
    Split and resequence a PDF based on a sequence string (1-indexed).
    e.g., '1,3,4-6,2'
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")
        
    doc = fitz.open(pdf_path)
    new_doc = fitz.open()
    try:
        total_pages = doc.page_count
        pages_to_keep = parse_sequence(sequence, total_pages)
        
        for p_idx in pages_to_keep:
            new_doc.insert_pdf(doc, from_page=p_idx, to_page=p_idx)
            
        if len(pages_to_keep) > 0:
            new_doc.save(output_path, garbage=4, deflate=True)
        else:
            raise ValueError("No valid pages found in the sequence.")
    finally:
        doc.close()
        new_doc.close()
        
    return output_path

def compress_pdf(pdf_path, output_path):
    """
    Compress a PDF file heavily using PyMuPDF options.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")
        
    doc = fitz.open(pdf_path)
    try:
        # garbage=4: removes unused objects, compacts xref table
        # deflate=True: compresses uncompressed streams
        # clean=True: clean content streams
        doc.save(output_path, garbage=4, deflate=True, clean=True)
    finally:
        doc.close()
        
    return output_path

def extract_text_from_file(filepath, ocr_reader=None):
    text_content = ""
    try:
        if filepath.lower().endswith('.pdf'):
            import fitz
            doc = fitz.open(filepath)
            try:
                text_content = "\n".join([page.get_text() for page in doc])
                if len(text_content.strip()) < 50 and ocr_reader:
                    ocr_text_list = []
                    from src.redact_documents import get_cached_ocr
                    for page in doc:
                        pix = page.get_pixmap()
                        img_bytes = pix.tobytes("png")
                        results = get_cached_ocr(img_bytes, ocr_reader)
                        for bbox, ocr_text, prob in results:
                            if prob > 0.2:
                                ocr_text_list.append(ocr_text)
                    text_content = "\n".join(ocr_text_list)
            finally:
                doc.close()
        elif filepath.lower().endswith('.docx'):
            import docx
            doc = docx.Document(filepath)
            text_content = "\n".join([para.text for para in doc.paragraphs])
        elif filepath.lower().endswith('.txt'):
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text_content = f.read()
        elif filepath.lower().endswith('.xlsx'):
            import openpyxl
            wb = openpyxl.load_workbook(filepath, data_only=True)
            lines = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    row_text = " ".join([str(cell) for cell in row if cell is not None])
                    if row_text.strip():
                        lines.append(row_text)
            text_content = "\n".join(lines)
        elif filepath.lower().endswith('.csv'):
            import csv
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                lines = []
                for row in reader:
                    lines.append(" ".join(row))
                text_content = "\n".join(lines)
        elif filepath.lower().endswith('.json'):
            import json
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
                text_content = json.dumps(data, indent=2)
        elif filepath.lower().endswith('.xml'):
            import xml.etree.ElementTree as ET
            tree = ET.parse(filepath)
            root = tree.getroot()
            lines = []
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    lines.append(elem.text.strip())
            text_content = "\n".join(lines)
        elif filepath.lower().endswith(('.jpg', '.jpeg', '.png')):
            if ocr_reader:
                from src.redact_documents import get_cached_ocr
                with open(filepath, 'rb') as f:
                    img_bytes = f.read()
                results = get_cached_ocr(img_bytes, ocr_reader)
                text_content = "\n".join([t[1] for t in results if t[2] > 0.2])
    except Exception as e:
        print(f"Extraction error: {e}")
    return text_content
