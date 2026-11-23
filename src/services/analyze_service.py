import json
from src.redact_documents import analyze_file
from src.pdf_utils import extract_text_from_file
from src.trial_manager import increment_scan_count
from src.services.model_service import get_analyzer, get_ocr_reader

def generate_analyze_stream(saved_files_info, local_anonymizer, config):
    yield f"data: {json.dumps({'status': 'progress', 'message': 'Warming up machine learning models (this happens once)...'})}\n\n"
    current_analyzer = get_analyzer()
    current_ocr = get_ocr_reader()
    
    combined_mappings = {}
    combined_text = []
    filenames = []
    
    for info in saved_files_info:
        filepath = info['filepath']
        orig_name = info['original_filename']
        filenames.append(info['server_filename'])
        
        yield f"data: {json.dumps({'status': 'progress', 'message': f'Analyzing {orig_name}...'})}\n\n"
        
        for event_json in analyze_file(filepath, current_analyzer, local_anonymizer, config, current_ocr, original_filename=orig_name):
            event = json.loads(event_json)
            if event.get('status') == 'progress':
                msg = event.get('message')
                yield f"data: {json.dumps({'status': 'progress', 'message': f'[{orig_name}] {msg}'})}\n\n"
            elif event.get('status') == 'complete':
                combined_mappings.update(event.get('mappings', {}))
        
        yield f"data: {json.dumps({'status': 'progress', 'message': f'Extracting raw text from {orig_name}...'})}\n\n"
        text = extract_text_from_file(filepath, current_ocr)
        combined_text.append(f"--- Document {len(combined_text) + 1} ---\n{text}")
        
        increment_scan_count()
    
    yield f"data: {json.dumps({'status': 'progress', 'message': 'Combining results...'})}\n\n"
    final_text = "\n\n".join(combined_text)
    
    yield f"data: {json.dumps({'status': 'done', 'filenames': filenames, 'extracted_text': final_text, 'mappings': combined_mappings, 'file_info_list': saved_files_info})}\n\n"
