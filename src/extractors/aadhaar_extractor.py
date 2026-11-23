import re

def clean_ocr_aadhaar(num_str):
    if len(num_str) != 12:
        return num_str
        
    verhoeff_d = (
        (0,1,2,3,4,5,6,7,8,9), (1,2,3,4,0,6,7,8,9,5), (2,3,4,0,1,7,8,9,5,6), (3,4,0,1,2,8,9,5,6,7),
        (4,0,1,2,3,9,5,6,7,8), (5,9,8,7,6,0,4,3,2,1), (6,5,9,8,7,1,0,4,3,2), (7,6,5,9,8,2,1,0,4,3),
        (8,7,6,5,9,3,2,1,0,4), (9,8,7,6,5,4,3,2,1,0)
    )
    verhoeff_p = (
        (0,1,2,3,4,5,6,7,8,9), (1,5,7,6,2,8,3,0,9,4), (5,8,0,3,7,9,6,1,4,2), (8,9,1,6,0,4,3,5,2,7),
        (9,4,5,3,1,2,6,8,7,0), (4,2,8,6,5,7,3,9,0,1), (2,7,9,3,8,0,6,4,1,5), (7,0,4,6,9,1,3,2,5,8)
    )

    def is_valid(num):
        if not num.isdigit(): return False
        c = 0
        for i, item in enumerate(reversed(num)):
            c = verhoeff_d[c][verhoeff_p[i % 8][int(item)]]
        return c == 0

    if is_valid(num_str):
        return num_str
        
    # Common OCR mistakes mapping
    mistakes = {'2':'7', '7':'2', '0':'O', 'O':'0', '5':'S', 'S':'5', '8':'B', 'B':'8', '1':'I', 'I':'1', '1':'7', '7':'1'}
    
    # Try single character substitutions
    for i in range(12):
        char = num_str[i]
        if char in mistakes:
            test_str = num_str[:i] + mistakes[char] + num_str[i+1:]
            if is_valid(test_str):
                return test_str
                
    return num_str

def extract_aadhaar_details(text_content):
    import re
    details = []
    
    lines = [line.strip() for line in text_content.split('\n') if line.strip() and len(line.strip()) > 2]
    
    # 1. Aadhaar Number
    aadhaar_num = None
    for line in lines:
        cleaned_line = re.sub(r'\s+', '', line).upper()
        # Sometimes O is read instead of 0, so we just check length 12
        if len(cleaned_line) == 12 and bool(re.match(r'^[0-9OISB]+$', cleaned_line)):
            # Convert obvious letter typos to numbers before validation
            typo_map = {'O':'0', 'I':'1', 'S':'5', 'B':'8', 'L':'1', 'Z':'2'}
            fixed_line = "".join(typo_map.get(c, c) for c in cleaned_line)
            
            aadhaar_num = clean_ocr_aadhaar(fixed_line)
            details.append({'type': 'Aadhaar Number', 'cleaned': f"{aadhaar_num[:4]} {aadhaar_num[4:8]} {aadhaar_num[8:]}", 'original': line})
            break
            
    # 2. DOB or YOB
    dob_idx = -1
    for i, line in enumerate(lines):
        dob_match = re.search(r'\d{2}[-/. ]\d{2}[-/. ]\d{4}', line)
        if dob_match:
            details.append({'type': 'Date of Birth', 'cleaned': dob_match.group(0), 'original': line})
            dob_idx = i
            break
        yob_match = re.search(r'\b(19|20)\d{2}\b', line)
        if yob_match:
            if not (len(re.sub(r'\s+', '', line)) == 12):
                details.append({'type': 'Year of Birth', 'cleaned': yob_match.group(0), 'original': line})
                dob_idx = i
                break
                
    # 3. Gender
    gender_idx = -1
    for i, line in enumerate(lines):
        upper_line = line.upper()
        if 'FEMALE' in upper_line:
            details.append({'type': 'Gender', 'cleaned': 'Female', 'original': line})
            gender_idx = i
            break
        elif 'MALE' in upper_line:
            details.append({'type': 'Gender', 'cleaned': 'Male', 'original': line})
            gender_idx = i
            break
        elif 'TRANSGENDER' in upper_line:
            details.append({'type': 'Gender', 'cleaned': 'Transgender', 'original': line})
            gender_idx = i
            break
                
    # 4. Name
    # Name is typically immediately preceding DOB or Gender. We scan upwards from DOB.
    name = None
    anchor_idx = dob_idx if dob_idx != -1 else gender_idx
    if anchor_idx != -1:
        for i in range(anchor_idx - 1, -1, -1):
            line = lines[i]
            upper_line = line.upper()
            if 'INDIA' in upper_line or 'GOVERNMENT' in upper_line or 'GOVT' in upper_line:
                continue
            if any(char.isdigit() for char in line):
                continue
            if 'FATHER' in upper_line or 'ADDRESS' in upper_line:
                continue
            if 'YEAR' in upper_line or 'BIRTH' in upper_line or 'DOB' in upper_line or 'YOB' in upper_line:
                continue
            if 'MALE' in upper_line or 'FEMALE' in upper_line or 'TRANSGENDER' in upper_line:
                continue
            if 'WIFE' in upper_line or 'HUSBAND' in upper_line or 'SON' in upper_line or 'DAUGHTER' in upper_line:
                continue
            if 'W/O' in upper_line or 'S/O' in upper_line or 'D/O' in upper_line or 'C/O' in upper_line:
                continue
            
            clean_name = re.sub(r'[^a-zA-Z\s]', '', line).strip()
            # A valid name should have at least 4 chars and ideally a space
            if len(clean_name) > 4 and ' ' in clean_name:
                name = line
                break
                
    if name:
        details.append({'type': 'Name', 'cleaned': name, 'original': name})
        
    # 5. Address
    # Addresses on Aadhaar almost always contain a 6-digit PIN code. We use this as an anchor.
    address_lines = []
    pin_idx = -1
    for i, line in enumerate(lines):
        if re.search(r'\b\d{6}\b', line):
            # Ensure it's not the Aadhaar number
            clean_num = re.sub(r'\s+', '', line).upper()
            if not (len(clean_num) == 12 and bool(re.match(r'^[0-9OISB]+$', clean_num))):
                pin_idx = i
                break
                
    if pin_idx != -1:
        # Scan upwards from the PIN code line to capture the address block
        for i in range(pin_idx, max(-1, pin_idx - 7), -1):
            line = lines[i]
            upper_line = line.upper()
            
            # Stop if we bleed into other known fields
            clean_num = re.sub(r'\s+', '', line).upper()
            if len(clean_num) == 12 and bool(re.match(r'^[0-9OISB]+$', clean_num)):
                break
            if 'MALE' in upper_line or 'FEMALE' in upper_line or 'TRANSGENDER' in upper_line:
                break
            if re.search(r'\d{2}[-/. ]\d{2}[-/. ]\d{4}', line) or 'YOB' in upper_line:
                break
                
            # Clean off the "Address:" prefix if it exists
            clean_line = re.sub(r'(?i)^address[:\s]*', '', line).strip()
            clean_line = re.sub(r'^पता[:\s]*', '', clean_line).strip()
            
            if clean_line:
                address_lines.insert(0, clean_line)
                
            # If we hit the 'Address' or 'S/O' header, stop going up
            if 'ADDRESS' in upper_line or 'पता' in line or bool(re.match(r'^[SDWC][|/I1L\\]?[O0]\b', upper_line)):
                break

    if address_lines:
        full_address = ", ".join(address_lines)
        
        # Strip out "Unique Identification Authority of India" (handling OCR typos)
        full_address = re.sub(r'(?i)unique\s+iden[a-z]+\s+authority\s+of\s+india,?\s*', '', full_address).strip()
        
        # Normalize S/o, W/o, D/o, C/o (handling OCR typos like SIO, S1O)
        full_address = re.sub(r'\b[sS][|/lI1\\]?[oO0]\b[:\s]*', 'S/o: ', full_address)
        full_address = re.sub(r'\b[wW][|/lI1\\]?[oO0]\b[:\s]*', 'W/o: ', full_address)
        full_address = re.sub(r'\b[dD][|/lI1\\]?[oO0]\b[:\s]*', 'D/o: ', full_address)
        full_address = re.sub(r'\b[cC][|/lI1\\]?[oO0]\b[:\s]*', 'C/o: ', full_address)
        
        # Clean up any leading commas or spaces
        full_address = re.sub(r'^[,:\s]+', '', full_address)
        
        details.append({'type': 'Address', 'cleaned': full_address, 'original': "\n".join(address_lines)})
        
    return details
