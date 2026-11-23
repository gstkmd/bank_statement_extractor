import re

def clean_ocr_pan(dirty_pan):
    """
    Takes an OCR string that matched the loose PAN pattern and corrects common OCR errors
    based on positional constraints: [5 Letters][4 Digits][1 Letter].
    """
    dirty_pan = dirty_pan.upper()
    if len(dirty_pan) != 10:
        return dirty_pan
    
    clean = ""
    # Map numbers misread as letters
    num_to_let = {'0': 'O', '1': 'I', '2': 'Z', '4': 'A', '5': 'S', '8': 'B', '6': 'G'}
    # Map letters misread as numbers
    let_to_num = {'O': '0', 'I': '1', 'L': '1', 'Z': '2', 'A': '4', 'S': '5', 'B': '8', 'G': '6', 'Q': '9'}
    
    # First 5 characters must be letters
    for i in range(5):
        char = dirty_pan[i]
        clean += num_to_let.get(char, char)
        
    # Next 4 characters must be digits
    for i in range(5, 9):
        char = dirty_pan[i]
        clean += let_to_num.get(char, char)
        
    # Last character must be a letter
    char = dirty_pan[9]
    clean += num_to_let.get(char, char)
    
    return clean

def extract_pan_details(text_content, current_analyzer):
    import re
    details = []
    
    # Constitution Mapping based on 4th character of PAN
    constitution_map = {
        'C': 'Company',
        'P': 'Person',
        'H': 'Hindu Undivided Family (HUF)',
        'F': 'Firm',
        'A': 'Association of Persons (AOP)',
        'T': 'AOP (Trust)',
        'B': 'Body of Individuals (BOI)',
        'L': 'Local Authority',
        'J': 'Artificial Juridical Person',
        'G': 'Government'
    }

    # Extract PAN using the analyzer
    pan_number = None
    original_pan_str = None
    results = current_analyzer.analyze(text=text_content, entities=['IN_PAN'], language='en')
    for r in results:
        if r.entity_type == 'IN_PAN':
            original_pan_str = text_content[r.start:r.end]
            pan_number = clean_ocr_pan(original_pan_str)
            break
            
    if pan_number:
        details.append({'type': 'PAN Number', 'cleaned': pan_number, 'original': original_pan_str})
        
        # Extract Constitution
        if len(pan_number) == 10:
            fourth_char = pan_number[3].upper()
            constitution = constitution_map.get(fourth_char, 'Unknown')
            details.append({'type': 'Constitution', 'cleaned': constitution, 'original': fourth_char})
            
    # Heuristics for Name, Father Name, DOB
    lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 2]
    
    # 1. Date of Birth
    dob_idx = -1
    for i, line in enumerate(lines):
        if re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', line):
            dob_match = re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', line)
            details.append({'type': 'Date of Birth', 'cleaned': dob_match.group(0), 'original': line})
            dob_idx = i
            break
            
    # 2. Name & Father Name
    # Based on standard layout: Name is usually line above Father Name, and Father Name is line above DOB
    # We scan upwards from DOB, skipping known header lines.
    
    name = None
    father_name = None
    
    valid_names = []
    if dob_idx > 0:
        for i in range(dob_idx - 1, -1, -1):
            line = lines[i]
            upper_line = line.upper()
            
            # Skip known headers
            if 'DATE' in upper_line or 'BIRTH' in upper_line or 'DOB' in upper_line:
                continue
            if 'FATHER' in upper_line or upper_line == 'NAME' or 'NAME /' in upper_line or 'NAME/' in upper_line:
                continue
            # Handle "FAF" or "Faf" which is an OCR typo for Father, and other exact headers
            if upper_line == 'FAF' or upper_line == 'FATHERS NAME' or upper_line == "FATHER'S NAME" or upper_line == 'NAME':
                continue
            if 'GOVT' in upper_line or 'INDIA' in upper_line or 'INCOME' in upper_line or 'TAX' in upper_line or 'DEPARTMENT' in upper_line:
                continue
            if any(char.isdigit() for char in line):
                continue
            
            clean_name = re.sub(r'[^a-zA-Z\s]', '', line).strip()
            # A valid name should have at least 3 chars
            if len(clean_name) >= 3:
                valid_names.append(line)
                
            if len(valid_names) == 2:
                break
                
    if len(valid_names) >= 1:
        father_name = valid_names[0]
    if len(valid_names) >= 2:
        name = valid_names[1]
            
    if name:
        details.append({'type': 'Name', 'cleaned': name, 'original': name})
    if father_name:
        details.append({'type': "Father's Name", 'cleaned': father_name, 'original': father_name})
        
    return details
