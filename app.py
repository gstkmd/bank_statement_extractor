import os
import sys
import json
import re
import uuid
import zipfile
import traceback
from flask import Flask, request, render_template, send_file, jsonify
from werkzeug.utils import secure_filename
from src.redact_documents import get_config, setup_analyzer, PseudoAnonymizer, process_file, analyze_file
from src.restore_documents import restore_file, restore_text_wrapper
from src.trial_manager import get_trial_status, increment_scan_count
from src.auto_updater import start_update_checker_background
from src.rename_documents import extract_first_page_text, generate_local_nlp_name, generate_ai_name
from src.pdf_utils import extract_text_from_file

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
import google.auth.transport.requests
import google.oauth2.id_token
from google_auth_oauthlib.flow import Flow
import webbrowser

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['UPLOAD_FOLDER'] = os.path.expanduser('~/.shielddocs/data/input')
app.config['OUTPUT_FOLDER'] = os.path.expanduser('~/.shielddocs/data/output')
app.config['MAPPING_FILE'] = os.path.expanduser('~/.shielddocs/data/mapping.json')

# SECURITY FIX: Block huge file uploads (Max 64 MB for batch)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024 

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File payload is too large. Maximum size is 64MB.'}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Internal server error occurred.'}), 500

# SECURITY FIX: Restrict allowed file types
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'docx', 'xlsx', 'csv', 'json', 'xml'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

from src.database import db

# Initialize Database
db_path = os.path.expanduser('~/.shielddocs/data/shielddocs.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Initialize global components (fast ones)
config = get_config()

with app.app_context():
    db.create_all()
    anonymizer = PseudoAnonymizer(app.config['MAPPING_FILE'])

from src.services.model_service import get_analyzer, get_ocr_reader, reload_analyzer

# Start auto-updater background thread
start_update_checker_background()

def preload_models():
    print("Preloading ML models in the background...")
    try:
        get_analyzer()
        get_ocr_reader()
        print("ML models preloaded successfully.")
    except Exception as e:
        print(f"Error preloading models: {e}")

import threading
threading.Thread(target=preload_models, daemon=True).start()

# --- Firebase Custom Auth ---
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
global_custom_token = None
global_oauth_flow = None

try:
    cred_path = os.path.join(os.path.dirname(__file__), 'firebase-adminsdk.json')
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully.")
    else:
        print("firebase-adminsdk.json not found. Custom auth will fail.")
except Exception as e:
    print(f"Failed to initialize Firebase Admin SDK: {e}")

@app.route('/auth/login')
def auth_login():
    global global_oauth_flow
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    client_secret_path = os.path.join(base_path, 'client_secret.json')
    
    try:
        global_oauth_flow = Flow.from_client_secrets_file(
            client_secret_path,
            scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile'],
            redirect_uri='http://127.0.0.1:5055/auth/callback'
        )
        auth_url, _ = global_oauth_flow.authorization_url(prompt='consent')
        webbrowser.open(auth_url)
        return jsonify({"status": "browser_opened"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/auth/callback')
def auth_callback():
    global global_custom_token, global_oauth_flow
    try:
        if not global_oauth_flow:
            return "OAuth flow state not found.", 400
            
        global_oauth_flow.fetch_token(authorization_response=request.url)
        creds = global_oauth_flow.credentials
        
        request_session = google.auth.transport.requests.Request()
        id_info = google.oauth2.id_token.verify_oauth2_token(
            creds.id_token, request_session, audience=global_oauth_flow.client_config['client_id'], clock_skew_in_seconds=60
        )
        
        uid = id_info['sub']
        email = id_info.get('email')
        name = id_info.get('name')
        
        try:
            user = firebase_auth.get_user(uid)
        except firebase_admin.auth.UserNotFoundError:
            user = firebase_auth.create_user(uid=uid, email=email, display_name=name)
            
        custom_token = firebase_auth.create_custom_token(uid)
        global_custom_token = custom_token.decode('utf-8') if isinstance(custom_token, bytes) else custom_token
        
        # Bring the desktop window to the front automatically
        try:
            import ctypes
            hwnd = ctypes.windll.user32.FindWindowW(None, "ShieldDocs")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
                
                # SwitchToThisWindow aggressively brings the window to the front
                ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
                
                # Windows prevents background apps from stealing focus, causing the taskbar icon to flash instead.
                # We bypass this by temporarily making the window "Always on Top" and then immediately reverting it.
                HWND_TOPMOST = -1
                HWND_NOTOPMOST = -2
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                
                ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        except Exception:
            pass
        
        return "<h2 style='font-family: sans-serif; text-align: center; margin-top: 50px; color: #4CAF50;'>Authentication successful!</h2><p style='text-align: center; font-family: sans-serif; font-size: 1.2rem; margin-top: 20px;'>Please return to the <b>ShieldDocs app</b> (blinking in your taskbar below) to continue.</p><p style='text-align: center; font-family: sans-serif; color: #666; font-size: 0.9rem; margin-top: 30px;'>(You may safely close this browser window)</p><script>window.close();</script>"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Authentication failed: {e}", 400

@app.route('/auth/status')
def auth_status():
    global global_custom_token
    if global_custom_token:
        token = global_custom_token
        global_custom_token = None
        return jsonify({"status": "success", "token": token})
    return jsonify({"status": "waiting"})
# ----------------------------

@app.route('/')
@app.route('/redact')
@app.route('/restore')
@app.route('/merge-pdf')
@app.route('/split-pdf')
@app.route('/account')
@app.route('/dictionary')
def index():
    from src.auto_updater import CURRENT_VERSION
    import socket
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = 'localhost'
    return render_template('index.html', version=CURRENT_VERSION, local_ip=hostname)

@app.route('/api/trial_status', methods=['GET'])
def trial_status():
    status = get_trial_status()
    return jsonify(status)

@app.route('/api/custom_rules', methods=['GET'])
def get_custom_rules():
    from src.redact_documents import load_custom_rules
    return jsonify(load_custom_rules())

@app.route('/api/custom_rules', methods=['POST'])
def save_custom_rules():
    try:
        rules = request.json
        if not rules:
            return jsonify({'success': False, 'error': 'No rules provided'}), 400
        
        rules_path = os.path.expanduser('~/.shielddocs/data/custom_rules.json')
        os.makedirs(os.path.dirname(rules_path), exist_ok=True)
        with open(rules_path, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=4)
            
        # Reload the NLP engine with the new rules
        reload_analyzer()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/analyze_file', methods=['POST'])
def analyze_file_route():
    try:
        if 'files' not in request.files and 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
            
        files = request.files.getlist('files')
        if not files:
            files = request.files.getlist('file')
            
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No file selected'}), 400

        valid_files = [f for f in files if allowed_file(f.filename)]
        if not valid_files:
            return jsonify({'error': 'File types not allowed. Please upload PDF, DOCX, TXT, or Image.'}), 400
            
        import uuid
        import json
        from flask import Response, stream_with_context
        
        local_anonymizer = PseudoAnonymizer(app.config['MAPPING_FILE'])

        saved_files_info = []
        for file in valid_files:
            original_ext = os.path.splitext(file.filename)[1]
            base_filename = secure_filename(file.filename)
            if not base_filename or not base_filename.endswith(original_ext):
                base_filename = f"document{original_ext}"
            name_part = os.path.splitext(base_filename)[0]
            unique_id = uuid.uuid4().hex[:8]
            filename = f"{name_part}_{unique_id}{original_ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            saved_files_info.append({
                'original_filename': file.filename,
                'server_filename': filename,
                'filepath': filepath
            })

        from src.services.analyze_service import generate_analyze_stream
        return Response(stream_with_context(generate_analyze_stream(saved_files_info, local_anonymizer, config)), mimetype='text/event-stream')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/extract_info', methods=['POST'])
def extract_info_route():
    try:
        if 'files' not in request.files and 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
            
        files = request.files.getlist('files')
        if not files:
            files = request.files.getlist('file')
            
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No file selected'}), 400

        valid_files = [f for f in files if allowed_file(f.filename)]
        if not valid_files:
            return jsonify({'error': 'File types not allowed.'}), 400
            
        import uuid
        import json
        from flask import Response, stream_with_context
        
        saved_files_info = []
        for file in valid_files:
            original_ext = os.path.splitext(file.filename)[1]
            base_filename = secure_filename(file.filename)
            if not base_filename or not base_filename.endswith(original_ext):
                base_filename = f"document{original_ext}"
            name_part = os.path.splitext(base_filename)[0]
            unique_id = uuid.uuid4().hex[:8]
            filename = f"extract_{name_part}_{unique_id}{original_ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            saved_files_info.append({
                'original_filename': file.filename,
                'server_filename': filename,
                'filepath': filepath
            })

        from src.services.extract_service import generate_extract_stream
        doc_type = request.form.get('doc_type', 'pan')
        return Response(stream_with_context(generate_extract_stream(saved_files_info, doc_type)), mimetype='text/event-stream')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/apply_redaction', methods=['POST'])
def apply_redaction():
    try:
        data = request.json
        filenames = data.get('filenames')
        
        # Backwards compatibility
        if not filenames and data.get('filename'):
            filenames = [data.get('filename')]
            
        custom_mappings = data.get('mappings', {})
        file_info_list = data.get('file_info_list', [])
        
        if not filenames:
            return jsonify({'error': 'Filenames missing'}), 400
            
        local_anonymizer = PseudoAnonymizer(app.config['MAPPING_FILE'])
        local_anonymizer.mapping = custom_mappings
        local_anonymizer.save_mapping()
        
        current_analyzer = get_analyzer()
        current_ocr = get_ocr_reader()
        
        out_paths = []
        combined_preview_text = []
    
        for filename in filenames:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if not os.path.exists(filepath):
                continue
                
            orig_name = None
            for info in file_info_list:
                if info.get('server_filename') == filename:
                    orig_name = info.get('original_filename')
                    break
                    
            out_path = process_file(filepath, current_analyzer, local_anonymizer, config, current_ocr, custom_mappings, original_filename=orig_name)
            if out_path and os.path.exists(out_path):
                out_paths.append(out_path)
                
                try:
                    text_content = extract_text_from_file(filepath, current_ocr)
                    import re
                    for orig in sorted(custom_mappings.keys(), key=len, reverse=True):
                        new_fake = custom_mappings[orig]
                        pattern = re.compile(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', re.IGNORECASE)
                        text_content = pattern.sub(lambda m: new_fake, text_content)
                    
                    # Get the base name using the original filename
                    if orig_name:
                        name, ext = os.path.splitext(orig_name)
                    else:
                        name, ext = os.path.splitext(filename)
                        name = re.sub(r'_[0-9a-f]{8}$', '', name)
                        
                    redacted_name = name
                    for orig in sorted(custom_mappings.keys(), key=len, reverse=True):
                        new_fake = custom_mappings[orig]
                        pattern = re.compile(r'(?<![a-zA-Z0-9])' + re.escape(orig) + r'(?![a-zA-Z0-9])', re.IGNORECASE)
                        redacted_name = pattern.sub(lambda m: new_fake, redacted_name)
                        
                    # Sanitize it for display just like the saved file
                    from werkzeug.utils import secure_filename
                    redacted_name = secure_filename(redacted_name)
                        
                    combined_preview_text.append(f"--- Document {len(combined_preview_text) + 1} ---\n{text_content}")
                except Exception as e:
                    combined_preview_text.append(f"Could not extract text for preview: {e}")
                    
        if not out_paths:
            return jsonify({'error': 'Failed to process any files. Please try again.'}), 500
            
        if len(out_paths) == 1:
            download_url = f"/download/{os.path.basename(out_paths[0])}"
        else:
            zip_filename = f"redacted_files_{uuid.uuid4().hex[:8]}.zip"
            zip_filepath = os.path.join(app.config['OUTPUT_FOLDER'], zip_filename)
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for out_path in out_paths:
                    zipf.write(out_path, os.path.basename(out_path))
            download_url = f"/download/{zip_filename}"
            
        return jsonify({
            'success': True,
            'download_url': download_url,
            'text_content': "\n\n".join(combined_preview_text)
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Execution error: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    out_dir = app.config.get('OUTPUT_FOLDER', './data/output')
    safe_filename = secure_filename(filename)
    return send_file(os.path.join(out_dir, safe_filename), as_attachment=True)

@app.route('/upload_restore', methods=['POST'])
def upload_restore():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed.'}), 400
        
    if file:
        import uuid
        original_ext = os.path.splitext(file.filename)[1]
        base_filename = secure_filename(file.filename)
        if not base_filename or not base_filename.endswith(original_ext):
            base_filename = f"document{original_ext}"
        name_part = os.path.splitext(base_filename)[0]
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{name_part}_{unique_id}{original_ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Restore the file
        out_path = restore_file(filepath, app.config['MAPPING_FILE'], output_dir=app.config.get('OUTPUT_FOLDER', './data/output'))
        if out_path and os.path.exists(out_path):
            filename = os.path.basename(out_path)
            return jsonify({
                'success': True,
                'download_url': f'/download/{filename}',
                'filename': filename
            })
        else:
            return jsonify({'error': 'Failed to restore file'}), 500

@app.route('/restore_generated_text', methods=['POST'])
def restore_generated_text():
    data = request.json
    reply_content = data.get('reply_content')
    
    if not reply_content:
        return jsonify({'error': 'No text provided'}), 400
        
    try:
        # Restore original data into the AI reply
        restored_reply = restore_text_wrapper(reply_content, app.config['MAPPING_FILE'])
        
        return jsonify({
            'success': True,
            'reply': restored_reply
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/get_mapping', methods=['GET'])
def get_mapping():
    anonymizer.load_mapping()
    return jsonify(anonymizer.mapping)

@app.route('/api/select_folder', methods=['GET'])
def select_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        # Create hidden root window
        root = tk.Tk()
        root.withdraw()
        # Bring dialog to front
        root.attributes('-topmost', True)
        
        folder_path = filedialog.askdirectory(title="Select Folder to Smart Rename")
        root.destroy()
        
        if folder_path:
            return jsonify({'success': True, 'path': folder_path})
        else:
            return jsonify({'success': False, 'error': 'No folder selected'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scan_rename_folder', methods=['POST'])
def scan_rename_folder():
    data = request.json
    folder_path = data.get('folder_path')
    ai_provider = data.get('ai_provider')
    api_key = data.get('api_key')
    id_token = data.get('id_token')
    
    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({'error': 'Invalid folder path'}), 400
        
    from flask import Response, stream_with_context
    import glob
    
    from src.services.rename_service import generate_rename_stream
    from src.redact_documents import PseudoAnonymizer
    local_anonymizer = PseudoAnonymizer(app.config['MAPPING_FILE']) if ((ai_provider and api_key) or id_token) else None
    files = glob.glob(os.path.join(folder_path, '*.*'))
    valid_files = [f for f in files if allowed_file(f)]
    return Response(stream_with_context(generate_rename_stream(valid_files, ai_provider, api_key, id_token, local_anonymizer)), mimetype='text/event-stream')

@app.route('/api/apply_rename', methods=['POST'])
def apply_rename():
    data = request.json
    renames = data.get('renames', [])
    
    if not renames:
        return jsonify({'error': 'No renames provided'}), 400
        
    from src.services.rename_service import process_apply_rename
    success_count, errors = process_apply_rename(renames)
    
    return jsonify({
        'success': True,
        'renamed_count': success_count,
        'errors': errors
    })

from src.pdf_routes import pdf_bp
app.register_blueprint(pdf_bp)

if __name__ == '__main__':
    import webview
    import threading
    import socket

    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    port = 5055
    
    def start_server():
        print("Starting ShieldDocs Server...")
        # Bound to 0.0.0.0 to allow office LAN access
        app.run(host='0.0.0.0', debug=False, port=port, use_reloader=False)

    def apply_titlebar_color():
        import time, ctypes
        try:
            import pywinstyles
            # Try for up to 10 seconds to find the window
            for _ in range(10):
                time.sleep(1)
                hwnd = ctypes.windll.user32.FindWindowW(None, "ShieldDocs")
                if hwnd:
                    pywinstyles.change_header_color(hwnd, color="#0f172a") # Dark Slate Theme
                    try:
                        pywinstyles.apply_style(hwnd, "dark") # Make window buttons white
                    except:
                        pass
                    break
        except Exception as e:
            print("Style error:", e)

    class Api:
        def __init__(self):
            self._window = None

        def save_file(self, filename):
            import shutil
            out_dir = app.config.get('OUTPUT_FOLDER', './data/output')
            source_path = os.path.join(out_dir, filename)
            
            if not os.path.exists(source_path):
                return False

            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory='',
                save_filename=filename
            )
            
            if result:
                dest_path = result[0]
                shutil.copy2(source_path, dest_path)
                return True
            return False

    if is_port_in_use(port):
        print(f"Port {port} is already in use. Opening window connecting to existing instance.")
        api = Api()
        window = webview.create_window('ShieldDocs', f'http://127.0.0.1:{port}/', width=1200, height=800, maximized=True, js_api=api, text_select=True)
        api._window = window
        t_style = threading.Thread(target=apply_titlebar_color, daemon=True)
        t_style.start()
        webview.start(private_mode=False, storage_path=os.path.expanduser('~/.shielddocs/webview_data'))
    else:
        # Start Flask in a daemon thread
        t = threading.Thread(target=start_server)
        t.daemon = True
        t.start()
        
        # Start PyWebView desktop window
        api = Api()
        window = webview.create_window('ShieldDocs', f'http://127.0.0.1:{port}/', width=1200, height=800, maximized=True, js_api=api, text_select=True)
        api._window = window
        t_style = threading.Thread(target=apply_titlebar_color, daemon=True)
        t_style.start()
        webview.start(private_mode=False, storage_path=os.path.expanduser('~/.shielddocs/webview_data'))
