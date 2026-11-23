import os
import json
from src.rename_documents import extract_first_page_text, generate_local_nlp_name
from src.redact_documents import get_config
from src.services.model_service import get_analyzer, get_ocr_reader

def generate_rename_stream(valid_files, ai_provider, api_key, id_token, local_anonymizer):
    yield f"data: {json.dumps({'status': 'start', 'total': len(valid_files)})}\n\n"
    yield f"data: {json.dumps({'status': 'progress', 'message': 'Warming up machine learning models (this happens once)...'})}\n\n"
    current_analyzer = get_analyzer()
    current_ocr = get_ocr_reader()
    
    results = []
    batch_size = 10
    current_batch = []
    
    for i, filepath in enumerate(valid_files):
        filename = os.path.basename(filepath)
        orig_ext = os.path.splitext(filename)[1]
        yield f"data: {json.dumps({'status': 'progress', 'message': f'Reading {filename}...', 'current': i+1})}\n\n"
        
        # Extract text
        text = extract_first_page_text(filepath, current_ocr)
        
        # Local NLP Name
        local_name = generate_local_nlp_name(text, current_analyzer)
        
        redacted_text = ""
        if (ai_provider and api_key) or id_token:
            config = get_config()
            lang = config.get('nlp', {}).get('language', 'en')
            # Do not redact DATE_TIME so the AI can read the actual financial year/period!
            entities = config.get('nlp', {}).get('entities', ['PERSON', 'ORGANIZATION', 'IN_PAN', 'IN_GST', 'IN_AADHAAR', 'PHONE_NUMBER', 'EMAIL_ADDRESS', 'LOCATION', 'ACK_NO', 'FRN', 'MEMBERSHIP_NO', 'UDIN'])
            if 'DATE_TIME' in entities:
                entities.remove('DATE_TIME')
            
            results_analyzer = current_analyzer.analyze(text=text, entities=entities, language=lang)
            redacted_text = local_anonymizer.anonymize_text(text, results_analyzer)
        
        current_batch.append({
            'id': i,
            'filename': filename,
            'filepath': filepath,
            'orig_ext': orig_ext,
            'local_name': local_name,
            'text': redacted_text
        })
        
        # If batch is full or we are at the last file, process AI
        if len(current_batch) == batch_size or i == len(valid_files) - 1:
            yield f"data: {json.dumps({'status': 'progress', 'message': f'Requesting AI names for {len(current_batch)} files...', 'current': i+1})}\n\n"
            
            ai_names_dict = {}
            if (ai_provider and api_key) or id_token:
                from src.rename_documents import generate_ai_name_batch
                ai_names_dict = generate_ai_name_batch(current_batch, ai_provider, api_key, id_token)
                with open("debug_rename.log", "a") as f:
                    f.write(f"Provider: {ai_provider}, HasKey: {bool(api_key)}, HasToken: {bool(id_token)}\n")
                    f.write(f"Input batch size: {len(current_batch)}\n")
                    f.write(f"Returned dict: {ai_names_dict}\n\n")
            
            for item in current_batch:
                ai_name = ai_names_dict.get(item['id']) or ai_names_dict.get(str(item['id']), "")
                
                if ai_name and local_anonymizer:
                    import re
                    # Sort mapping by length of fake_val descending to match longest first
                    sorted_mapping = sorted(local_anonymizer.reverse_mapping.items(), key=lambda x: len(x[0]), reverse=True)
                    
                    for fake_val, original_val in sorted_mapping:
                        replaced = False
                        
                        # 1. Try full exact match
                        stripped_fake = re.sub(r'[^a-zA-Z0-9_\-]', '', fake_val)
                        underscore_fake = re.sub(r'[^a-zA-Z0-9_\-]', '', fake_val.replace(' ', '_'))
                        
                        if underscore_fake:
                            new_ai_name = re.sub(re.escape(underscore_fake), original_val.replace(' ', '_'), ai_name, flags=re.IGNORECASE)
                            if new_ai_name != ai_name:
                                ai_name = new_ai_name
                                replaced = True
                        if not replaced and stripped_fake:
                            new_ai_name = re.sub(re.escape(stripped_fake), original_val.replace(' ', '_'), ai_name, flags=re.IGNORECASE)
                            if new_ai_name != ai_name:
                                ai_name = new_ai_name
                                replaced = True
                                
                        # 2. Try match without corporate suffixes (AI often drops them)
                        if not replaced:
                            core_fake = re.sub(r'\b(Corp|Inc|LLC|Ltd|Private Limited|LLP)\b', '', fake_val, flags=re.IGNORECASE).strip()
                            if core_fake and core_fake != fake_val:
                                underscore_core = re.sub(r'[^a-zA-Z0-9_\-]', '', core_fake.replace(' ', '_'))
                                if underscore_core and len(underscore_core) > 4:
                                    ai_name = re.sub(re.escape(underscore_core), original_val.replace(' ', '_'), ai_name, flags=re.IGNORECASE)
                
                l_name = item['local_name']
                result = {
                    'original_name': item['filename'],
                    'original_path': item['filepath'],
                    'local_name': f"{l_name}{item['orig_ext']}" if l_name else "",
                    'ai_name': f"{ai_name}{item['orig_ext']}" if ai_name else ""
                }
                results.append(result)
                
            current_batch = []
        
    yield f"data: {json.dumps({'status': 'done', 'results': results})}\n\n"

def process_apply_rename(renames):
    success_count = 0
    errors = []
    
    for item in renames:
        orig_path = item.get('original_path')
        new_name = item.get('new_name')
        
        if not orig_path or not new_name or not os.path.exists(orig_path):
            errors.append(f"Invalid path or name for {orig_path}")
            continue
            
        folder = os.path.dirname(orig_path)
        new_path = os.path.join(folder, new_name)
        
        # Handle conflicts
        if os.path.exists(new_path) and orig_path != new_path:
            name, ext = os.path.splitext(new_name)
            counter = 1
            while os.path.exists(new_path):
                new_path = os.path.join(folder, f"{name}_{counter}{ext}")
                counter += 1
                
        try:
            os.rename(orig_path, new_path)
            success_count += 1
        except Exception as e:
            errors.append(f"Failed to rename {os.path.basename(orig_path)}: {e}")
            
    return success_count, errors
