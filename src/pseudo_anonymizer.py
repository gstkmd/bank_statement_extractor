import os
import json
import random
import string
import re
from faker import Faker

from src.database import db
from src.models import AnonymizerMapping

class PseudoAnonymizer:
    def __init__(self, mapping_file=None):
        self.faker = Faker('en_IN')
        self.mapping = {}
        self.reverse_mapping = {}
        self.load_mapping()
        
    def load_mapping(self):
        try:
            records = AnonymizerMapping.query.all()
            for r in records:
                self.mapping[r.original_text] = r.fake_text
                self.reverse_mapping[r.fake_text] = r.original_text
        except Exception as e:
            print(f"Error loading mapping from DB: {e}")
            
    def save_mapping(self):
        try:
            for original, fake in self.mapping.items():
                record = AnonymizerMapping.query.get(original)
                if not record:
                    record = AnonymizerMapping(original_text=original, fake_text=fake)
                    db.session.add(record)
                else:
                    # Update existing mapping if it has changed (e.g., user edited it in the UI)
                    record.fake_text = fake
            db.session.commit()
        except Exception as e:
            print(f"Error saving mapping to DB: {e}")
            db.session.rollback()
    def _get_significant_words(self, text):
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        words = text.split()
        generic = {'ms', 'm', 's', 'private', 'pvt', 'limited', 'ltd', 'llp', 'inc', 'corp', 'associates', 'co', 'the', 'and', 'of', 'for', 'in', 'india'}
        sig_words = set([w for w in words if w not in generic and len(w) > 2])
        return sig_words
    def get_fake_value(self, original_text, entity_type):
        original_text = original_text.strip()
        if not original_text: return ""
        if original_text in self.mapping:
            return self.mapping[original_text]
            
        DUMMY_PERSONS = [
            "Rajesh Kumar Sharma", "K. S. Venkatesh Iyer", "Bikramjit Das", "Jayesh R. Patil",
            "Sunita Rani Mehra", "P. Lakshmi Narayanan", "Aditya Baruah", "Meenal S. Deshmukh",
            "Vikram Singh Rathore", "R. Nandini Krishnan", "Deepanjali Bora", "Dinesh K. Shah",
            "Anil K. Gupta", "S. Ramakrishnan Pillai", "Prabhat Ranjan Thakur", "Sandhya P. Mhatre",
            "Neha Wadhwa", "S. V. Anantharaman", "Dawa Lhendup Bhutia", "Harish K. Chavan",
            "Yogesh Chandna", "V. K. Natarajan", "L. Thangmawia", "Falguni N. Mehta",
            "Priyanka Goyal", "A. R. Shankar Iyengar", "Bobby Lyngdoh", "Prakash R. Shetty",
            "Col. (Retd.) H.S. Sandhu", "M. S. Swaminathan", "Kanaklata Devi", "Imran A. Siddiqui",
            "Sangeeta B. Joshi", "T. S. Rajeshwari", "Momita Choudhury", "Rohit M. Gokhale",
            "Arvind D. Tandon", "C. K. Raveendran", "Nongthombam Biren", "Abbas H. Tyabji"
        ]
        
        DUMMY_ORGANIZATIONS = [
            "Aryavrat Engineering Pvt Ltd", "Ganga Infrastructure & Developers LLP", "Sahyadri Agrotech Private Limited", 
            "Vijayalakshmi Spinning Mills Pvt Ltd", "Emerald City Realty Solutions LLP", "Navkar Logistics & Supply Chain Pvt Ltd", 
            "Shree Ganpati Auto Components Pvt Ltd", "Aster Medcity Healthcare Private Limited", "Adroit IT Solutions & Consulting LLP", 
            "Akar Fintech Services Pvt Ltd", "Bharat Biologics Research Centre Pvt Ltd", "Sagar Marine Exports Private Limited", 
            "Trident Facility Management LLP", "Vasundhara Green Energy Pvt Ltd", "Kalinga Aerospace & Defence Private Limited",
            "Hinduja Global Metals Limited", "Rajasthan Petrochemicals Corp. Ltd.", "Sundaram Finserv Holdings Ltd.", 
            "Godavari Fertilizers & Chemicals Ltd.", "Konkan Railway Infrastructure Corp. Ltd.", "Narmada Clean Tech Limited", 
            "Ujjivan Small Finance Bank Ltd.", "Malabar Gold & Diamond Limited", "Indus Valley Cement Corp. Ltd.", 
            "Punjab Agro-Industries Corporation Ltd.", "Eastern Power Grid Solutions Ltd.", "Gujarat Fluoropolymers Ltd.", 
            "Kaveri Delta Seeds & Biotech Ltd.", "Himalayan Breweries & Distilleries Ltd.", "Coromandel Paints & Coatings Ltd.",
            "Annapoorna Mess & Tiffin Centre", "Kumar & Sons Hardware Mart", "Rajdhani Pustak Bhandar", 
            "Meena Bazaar - Ethnic Wear & Textiles", "Balaji Mobile Point & Repairs", "Saini Kirana & General Stores", 
            "Rameshwaram Cafe & Bakery", "Laxmi Narayan Traders", "City Hospital Pharmacy & Medicals", 
            "Guru Nanak Auto Garage & Tyres", "Kerala Blasters Sports Academy", "Banaras Handloom Emporium", 
            "Poona Packers & Movers", "Jaipur Jewellers & Gem House", "Coastal Aqua Farms & Exports"
        ]

        if entity_type in ('ORGANIZATION', 'PERSON'):
            orig_sig_words = self._get_significant_words(original_text)
            if orig_sig_words:
                for existing_orig, existing_fake in self.mapping.items():
                    existing_sig_words = self._get_significant_words(existing_orig)
                    if existing_sig_words:
                        intersection = orig_sig_words.intersection(existing_sig_words)
                        min_len = min(len(orig_sig_words), len(existing_sig_words))
                        if min_len > 0 and (len(intersection) / min_len) >= 0.6:
                            self.mapping[original_text] = existing_fake
                            self.save_mapping()
                            return existing_fake
                            
        if entity_type == 'PERSON':
            fake_val = random.choice(DUMMY_PERSONS)
        elif entity_type == 'ORGANIZATION':
            fake_val = random.choice(DUMMY_ORGANIZATIONS)
        elif entity_type == 'IN_PAN':
            fake_val = f"{''.join(random.choices(string.ascii_uppercase, k=5))}{''.join(random.choices(string.digits, k=4))}{random.choice(string.ascii_uppercase)}"
        elif entity_type == 'IN_GST':
            fake_val = f"{random.randint(10,37)}{''.join(random.choices(string.ascii_uppercase, k=5))}{''.join(random.choices(string.digits, k=4))}{random.choice(string.ascii_uppercase)}1Z{random.choice(string.ascii_uppercase)}"
        elif entity_type == 'IN_AADHAAR':
            fake_val = f"{random.randint(2,9)}{''.join(random.choices(string.digits, k=3))} {''.join(random.choices(string.digits, k=4))} {''.join(random.choices(string.digits, k=4))}"
        elif entity_type == 'ACK_NO':
            prefix = re.match(r"(?i)\b(?:Ack No|Acknowledgement No|Ack\. No\.)[\s:]+", original_text)
            fake_num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))
            fake_val = (prefix.group(0) if prefix else "Ack No: ") + fake_num
        elif entity_type == 'DATE_TIME':
            fake_val = self.faker.date('%d/%m/%Y')
        elif entity_type == 'PHONE_NUMBER':
            fake_val = self.faker.phone_number()
        elif entity_type == 'EMAIL_ADDRESS':
            fake_val = self.faker.email()
        elif entity_type == 'LOCATION':
            fake_val = self.faker.city()
        elif entity_type == 'FRN':
            prefix = re.match(r"(?i)\b(?:FRN|Firm Regn\. No\.|Firm Registration Number)[\s:]+", original_text)
            fake_num = f"{''.join(random.choices(string.digits, k=6))}{random.choice(string.ascii_uppercase)}"
            fake_val = (prefix.group(0) if prefix else "FRN: ") + fake_num
        elif entity_type == 'MEMBERSHIP_NO':
            prefix = re.match(r"(?i)\b(?:M\. No\.|Membership No\.)[\s:]+", original_text)
            fake_num = f"{''.join(random.choices(string.digits, k=6))}"
            fake_val = (prefix.group(0) if prefix else "M. No.: ") + fake_num
        elif entity_type == 'UDIN':
            prefix = re.match(r"(?i)\b(?:UDIN)[\s:]+", original_text)
            fake_num = f"{''.join(random.choices(string.digits + string.ascii_uppercase, k=18))}"
            fake_val = (prefix.group(0) if prefix else "UDIN: ") + fake_num
        else:
            fake_val = f"[REDACTED_{entity_type}_{random.randint(1000,9999)}]"
        self.mapping[original_text] = fake_val
        self.reverse_mapping[fake_val] = original_text
        self.save_mapping()
        return fake_val
    def anonymize_text(self, text, analyzer_results):
        results = sorted(analyzer_results, key=lambda x: x.start, reverse=True)
        anonymized_text = text
        for res in results:
            original = text[res.start:res.end]
            fake_val = self.get_fake_value(original, res.entity_type)
            anonymized_text = anonymized_text[:res.start] + fake_val + anonymized_text[res.end:]
        return anonymized_text
