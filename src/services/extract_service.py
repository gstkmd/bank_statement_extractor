import json
import os
from src.pdf_utils import extract_text_from_file
from src.trial_manager import increment_scan_count
from src.services.model_service import get_analyzer, get_ocr_reader

def generate_extract_stream(saved_files_info, doc_type):
    yield f"data: {json.dumps({'status': 'progress', 'message': 'Warming up machine learning models (this happens once)...'})}\n\n"
    current_analyzer = get_analyzer()
    current_ocr = get_ocr_reader()
    extracted_data = []
    filenames = []
    
    for info in saved_files_info:
        filepath = info['filepath']
        orig_name = info['original_filename']
        filenames.append(info['server_filename'])
        
        yield f"data: {json.dumps({'status': 'progress', 'message': f'Analyzing {orig_name}...'})}\n\n"
        
        text_content = extract_text_from_file(filepath, current_ocr)
        
        if text_content.strip():
            if doc_type == 'pan':
                from src.extractors.pan_extractor import extract_pan_details
                pan_details = extract_pan_details(text_content, current_analyzer)
                for pd in pan_details:
                    extracted_data.append({
                        'file': orig_name,
                        'type': pd['type'],
                        'original': pd['original'],
                        'cleaned': pd['cleaned']
                    })
            elif doc_type == 'aadhaar':
                from src.extractors.aadhaar_extractor import extract_aadhaar_details
                aadhaar_details = extract_aadhaar_details(text_content)
                for ad in aadhaar_details:
                    extracted_data.append({
                        'file': orig_name,
                        'type': ad['type'],
                        'original': ad['original'],
                        'cleaned': ad['cleaned']
                    })
            elif doc_type == 'voter_id':
                extracted_data.append({
                    'file': orig_name,
                    'type': 'Voter ID Document',
                    'original': 'Full extraction engine coming soon',
                    'cleaned': 'Not fully supported yet'
                })
        
        increment_scan_count()
    
    yield f"data: {json.dumps({'status': 'done', 'filenames': filenames, 'extracted_data': extracted_data})}\n\n"
