import time
from src.redact_documents import get_config, setup_analyzer

analyzer = setup_analyzer()
t = open('js_diff.txt', 'r', encoding='utf-8').read()

entities=['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'IN_GST', 'IN_PAN', 'DATE_TIME', 'IN_AADHAAR', 'ACK_NO', 'FRN', 'MEMBERSHIP_NO', 'UDIN', 'ORGANIZATION']

for ent in entities:
    t0 = time.time()
    try:
        analyzer.analyze(text=t, entities=[ent], language='en')
        print(f'{ent}: {time.time()-t0}')
    except Exception as e:
        print(f'{ent} failed: {e}')
