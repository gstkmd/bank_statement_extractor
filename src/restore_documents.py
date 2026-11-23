import os
import json
import docx
import argparse
import sys

def load_mapping(mapping_file):
    from src.models import AnonymizerMapping
    try:
        # If running within a Flask app context, this will work.
        # Otherwise, if called as a script, it might fail, but this is used by app.py
        import re
        def score_original(text):
            t = text.lower()
            t = re.sub(r'[^a-z0-9\s]', ' ', t)
            words = t.split()
            generic = {'ms', 'm', 's', 'private', 'pvt', 'limited', 'ltd', 'llp', 'inc', 'corp', 'associates', 'co', 'the', 'and', 'of', 'for', 'in', 'india', 'address', 'name', 'pan', 'date', 'no', 'ack', 'phone', 'email', 'mob', 'mobile', 'tel', 'fax', 'pin', 'code', 'state', 'city', 'district', 'street', 'road', 'marg', 'nagar', 'colony', 'apartment', 'floor', 'block', 'building', 'tower', 'sector', 'phase', 'zone', 'ward', 'circle', 'tehsil', 'mandal', 'village', 'post', 'office', 'police', 'station', 'near', 'opp', 'opposite', 'behind', 'beside', 'above', 'below', 'ground', 'first', 'second', 'third', 'dr', 'mr', 'mrs', 'shri', 'smt', 'kumari'}
            sig_words = [w for w in words if w not in generic and len(w) > 1]
            return (len(sig_words), -len(text))

        records = AnonymizerMapping.query.all()
        reverse_mapping = {}
        for r in records:
            fake = r.fake_text
            orig = r.original_text
            if fake not in reverse_mapping:
                reverse_mapping[fake] = orig
            else:
                # Compare using the scoring heuristic:
                # 1. Highest number of significant (non-generic) words
                # 2. If tied, shortest string (fewer garbage/noisy characters attached)
                if score_original(orig) > score_original(reverse_mapping[fake]):
                    reverse_mapping[fake] = orig
        return reverse_mapping
    except Exception as e:
        print(f"Error loading mapping from DB: {e}")
        return {}

import re

def restore_text(text, reverse_mapping):
    restored_text = text
    # Sort reverse mapping keys by length descending to prevent partial replacements
    for fake_val in sorted(reverse_mapping.keys(), key=len, reverse=True):
        # Case insensitive replacement for LLM generated text that might alter casing
        pattern = re.compile(r'(?<!\w)' + re.escape(fake_val) + r'(?!\w)', re.IGNORECASE)
        restored_text = pattern.sub(lambda m: reverse_mapping[fake_val], restored_text)
    return restored_text

def restore_text_wrapper(text, mapping_file):
    reverse_mapping = load_mapping(mapping_file)
    if not reverse_mapping:
        return text
    return restore_text(text, reverse_mapping)

def process_txt(filepath, reverse_mapping, output_path):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
            
        restored = restore_text(text, reverse_mapping)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(restored)
        print(f"Restored TXT saved to {output_path}")
    except Exception as e:
        print(f"Error processing TXT {filepath}: {e}")

def process_docx(filepath, reverse_mapping, output_path):
    try:
        doc = docx.Document(filepath)
        for para in doc.paragraphs:
            if para.text.strip():
                para.text = restore_text(para.text, reverse_mapping)
                
        # Also process tables if present
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        cell.text = restore_text(cell.text, reverse_mapping)
                        
        doc.save(output_path)
        print(f"Restored DOCX saved to {output_path}")
    except Exception as e:
        print(f"Error processing DOCX {filepath}: {e}")

def restore_file(input_path, mapping_file, output_dir=None):
    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        return None
        
    reverse_mapping = load_mapping(mapping_file)
    if not reverse_mapping:
        print("No mappings to restore. Returning original text.")
        reverse_mapping = {}
        
    if output_dir is None:
        output_dir = os.path.dirname(input_path)
    base_name = os.path.basename(input_path)
    name, ext = os.path.splitext(base_name)
    output_path = os.path.join(output_dir, f"{name}_restored{ext}")
    
    print(f"Restoring {input_path}...")
    
    if ext.lower() == '.txt':
        process_txt(input_path, reverse_mapping, output_path)
    elif ext.lower() == '.docx':
        process_docx(input_path, reverse_mapping, output_path)
    else:
        print(f"Unsupported file format: {ext}. Only .txt and .docx are supported for restoration.")
        return None
        
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Restore anonymized documents using mapping.json")
    parser.add_argument("input_file", help="Path to the document to restore (.txt or .docx)")
    parser.add_argument("--mapping", default="./data/mapping.json", help="Path to mapping.json")
    
    args = parser.parse_args()
    restore_file(args.input_file, args.mapping)

if __name__ == "__main__":
    main()
