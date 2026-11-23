import os
import uuid
import traceback
from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from src.pdf_utils import merge_pdfs, split_resequence_pdf, compress_pdf

pdf_bp = Blueprint('pdf_bp', __name__)

@pdf_bp.route('/api/merge_pdf', methods=['POST'])
def merge_pdf_route():
    try:
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files uploaded'}), 400
            
        saved_paths = []
        for f in files:
            if f.filename.lower().endswith('.pdf'):
                unique_id = uuid.uuid4().hex[:8]
                filename = f"merge_{unique_id}_{secure_filename(f.filename)}"
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                f.save(filepath)
                saved_paths.append(filepath)
                
        if not saved_paths:
            return jsonify({'error': 'No valid PDF files provided'}), 400
            
        output_filename = f"Merged_Document_{uuid.uuid4().hex[:8]}.pdf"
        output_path = os.path.join(current_app.config['OUTPUT_FOLDER'], output_filename)
        
        merge_pdfs(saved_paths, output_path)
        
        return send_file(output_path, as_attachment=True, download_name="Merged_Document.pdf")
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@pdf_bp.route('/api/split_pdf', methods=['POST'])
def split_pdf_route():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        sequence = request.form.get('sequence', '')
        if not sequence:
            return jsonify({'error': 'No sequence provided'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported'}), 400
            
        unique_id = uuid.uuid4().hex[:8]
        filename = f"split_{unique_id}_{secure_filename(file.filename)}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        output_filename = f"Split_Document_{unique_id}.pdf"
        output_path = os.path.join(current_app.config['OUTPUT_FOLDER'], output_filename)
        
        split_resequence_pdf(filepath, sequence, output_path)
        
        return send_file(output_path, as_attachment=True, download_name="Split_Document.pdf")
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@pdf_bp.route('/api/compress_pdf', methods=['POST'])
def compress_pdf_route():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported'}), 400
            
        unique_id = uuid.uuid4().hex[:8]
        filename = f"compress_{unique_id}_{secure_filename(file.filename)}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        output_filename = f"Compressed_{unique_id}.pdf"
        output_path = os.path.join(current_app.config['OUTPUT_FOLDER'], output_filename)
        
        compress_pdf(filepath, output_path)
        
        return send_file(output_path, as_attachment=True, download_name="Compressed_Document.pdf")
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
