import threading
from src.redact_documents import setup_analyzer

_analyzer_instance = None
_ocr_reader_instance = None
_ocr_initialized = False

_analyzer_lock = threading.Lock()
_ocr_lock = threading.Lock()

def get_analyzer():
    global _analyzer_instance
    if _analyzer_instance is None:
        with _analyzer_lock:
            if _analyzer_instance is None:
                print("Lazy loading NLP Analyzer...")
                _analyzer_instance = setup_analyzer()
    return _analyzer_instance

def reload_analyzer():
    global _analyzer_instance
    with _analyzer_lock:
        _analyzer_instance = setup_analyzer()

def get_ocr_reader():
    global _ocr_reader_instance, _ocr_initialized
    if not _ocr_initialized:
        with _ocr_lock:
            if not _ocr_initialized:
                print("Lazy loading EasyOCR...")
                try:
                    import easyocr
                    _ocr_reader_instance = easyocr.Reader(['en'], download_enabled=False)
                except Exception as e:
                    print(f"Failed to load OCR: {e}")
                    _ocr_reader_instance = None
                finally:
                    _ocr_initialized = True
    return _ocr_reader_instance
