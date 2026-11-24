import os
import sys
import subprocess
import shutil
import ast
import glob

def get_hidden_imports():
    """Parse original source files to find all imports so PyInstaller bundles them."""
    imports = set()
    # Read app.py and all src/*.py files
    files = ['app.py'] + glob.glob('src/*.py')
    for f in files:
        if not os.path.exists(f): continue
        with open(f, 'r', encoding='utf-8') as file:
            try:
                tree = ast.parse(file.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module.split('.')[0])
            except Exception as e:
                print(f"Warning: Could not parse imports from {f}: {e}")
                
    # Ensure the local src package and its modules are included
    imports.add('src')
    imports.add('src.redact_documents')
    imports.add('src.restore_documents')
    imports.add('src.trial_manager')
    imports.add('src.auto_updater')
    imports.add('src.pseudo_anonymizer')
    imports.add('src.pdf_utils')
    imports.add('src.rename_documents')
    imports.add('src.extractors')
    imports.add('src.extractors.aadhaar_extractor')
    imports.add('src.extractors.pan_extractor')
    imports.add('src.pdf_routes')
    imports.add('src.services')
    imports.add('src.services.analyze_service')
    imports.add('src.services.extract_service')
    imports.add('src.services.model_service')
    imports.add('src.services.rename_service')

    imports.add('flask_sqlalchemy')
    imports.add('sqlalchemy')
    imports.add('src.database')
    imports.add('src.models')
    imports.add('pywinstyles')
    
    # Always include standard ones that might be dynamically loaded
    imports.update(['json', 'os', 'sys', 'datetime', 'time', 'urllib', 'threading', 'random', 'string', 'uuid', 're'])
    
    return list(imports)

def run_command(command, error_msg):
    print(f"\n>>> Running: {command}")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        print(f"\n[ERROR] {error_msg}")
        sys.exit(1)

def auto_increment_version():
    if '--no-increment' in sys.argv:
        print("[INFO] Skipping version auto-increment (--no-increment specified)")
        return
    import re
    updater_file = os.path.join('src', 'auto_updater.py')
    if not os.path.exists(updater_file):
        return
        
    with open(updater_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    match = re.search(r'CURRENT_VERSION\s*=\s*"v(\d+)\.(\d+)\.(\d+)"', content)
    if match:
        major, minor, patch = match.groups()
        new_patch = int(patch) + 1
        old_version_str = f'v{major}.{minor}.{patch}'
        new_version_str = f'v{major}.{minor}.{new_patch}'
        
        new_content = content.replace(f'CURRENT_VERSION = "{old_version_str}"', f'CURRENT_VERSION = "{new_version_str}"', 1)
        
        with open(updater_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"Auto-incremented version: {old_version_str} -> {new_version_str}")

        # Auto-update installer.iss
        iss_file = 'installer.iss'
        if os.path.exists(iss_file):
            with open(iss_file, 'r', encoding='utf-8') as f:
                iss_content = f.read()
            
            iss_content = re.sub(r'AppVersion=.*', f'AppVersion={new_version_str}', iss_content)
            iss_content = re.sub(r'OutputBaseFilename=.*', f'OutputBaseFilename=ShieldDocs_Setup_{new_version_str}', iss_content)
            
            with open(iss_file, 'w', encoding='utf-8') as f:
                f.write(iss_content)
            print(f"Updated installer.iss with version {new_version_str}")

def main():
    print("========================================")
    print(" ShieldDocs Secure Build Pipeline")
    print("========================================\n")
    
    # 0. Auto-increment version
    auto_increment_version()
    
    # 1. Check dependencies
    print("Checking dependencies...")
    run_command(f'"{sys.executable}" -m pip install pyarmor pyinstaller', "Failed to install build dependencies.")
    
    # 2. Clean previous builds
    print("\nCleaning previous builds...")
    for folder in ['build', 'dist', 'obfuscated_src']:
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)
            
    env_dir = os.path.dirname(sys.executable)

    # 3. Obfuscate code with PyArmor
    print("\nStep 1: Obfuscating Python code to prevent reverse engineering...")
    run_command(
        f'"{sys.executable}" -m pyarmor.cli gen -O obfuscated_src app.py src',
        "Failed to obfuscate code. Check if PyArmor is installed correctly."
    )
    
    # Check if obfuscation succeeded
    if not os.path.exists('obfuscated_src/app.py'):
        print("\n[ERROR] Obfuscation failed: obfuscated_src/app.py not found.")
        sys.exit(1)
        
    # 4. Copy necessary asset folders to the obfuscated directory
    print("\nStep 2: Copying HTML templates and static assets...")
    shutil.copytree('templates', 'obfuscated_src/templates', dirs_exist_ok=True)
    shutil.copytree('static', 'obfuscated_src/static', dirs_exist_ok=True)
    if os.path.exists('data'):
        shutil.copytree('data', 'obfuscated_src/data', dirs_exist_ok=True)
    if os.path.exists('config.yml'):
        shutil.copy2('config.yml', 'obfuscated_src/config.yml')
    if os.path.exists('firebase-adminsdk.json'):
        shutil.copy2('firebase-adminsdk.json', 'obfuscated_src/firebase-adminsdk.json')
    if os.path.exists('client_secret.json'):
        shutil.copy2('client_secret.json', 'obfuscated_src/client_secret.json')
    
    # 5. Build executable with PyInstaller
    # Get the current version for display purposes
    sys.path.insert(0, os.path.abspath('src'))
    try:
        from auto_updater import CURRENT_VERSION
        version_str = CURRENT_VERSION
    except ImportError:
        version_str = "unknown"
    finally:
        sys.path.pop(0)

    print(f"\nStep 3: Packaging ShieldDocs {version_str}...")
    
    # Gather hidden imports from original unencrypted files
    print("\nAnalyzing original source code for dependencies...")
    # We must do this BEFORE changing directory
    hidden_imports = get_hidden_imports()
    hidden_import_args = " ".join([f'--hidden-import {mod}' for mod in hidden_imports])
    # We change directory into obfuscated_src so PyInstaller builds from the encrypted files
    os.chdir('obfuscated_src')
    
    # Dynamically find the pyarmor runtime package injected by PyArmor v8
    runtime_pkg_args = ""
    for d in os.listdir('.'):
        if d.startswith('pyarmor_runtime_') and os.path.isdir(d):
            hidden_imports.append(d)
            runtime_pkg_args += f'--collect-all {d} --add-data "{d};{d}" '
            
    hidden_import_args = " ".join([f'--hidden-import {mod}' for mod in hidden_imports])
    
    pyinstaller_cmd = (
        f'"{sys.executable}" -m PyInstaller --noconfirm --onedir --noconsole --name "ShieldDocs" '
        '--add-data "templates;templates" '
        '--add-data "static;static" '
        '--add-data "config.yml;." '
        '--add-data "firebase-adminsdk.json;." '
        '--add-data "client_secret.json;." '
        '--collect-all flask_sqlalchemy '
        '--collect-all sqlalchemy '
        '--collect-all presidio_analyzer '
        '--collect-all easyocr '
        '--collect-all faker '
        '--collect-all webview '
        '--collect-all firebase_admin '
        '--collect-all google_auth_oauthlib '
        '--collect-all google '
        '--collect-all en_core_web_lg '
        '--hidden-import en_core_web_lg '
        '--collect-all en_core_web_sm '
        '--hidden-import en_core_web_sm '
        f'{runtime_pkg_args}'
        f'{hidden_import_args} '
        'app.py'
    )
    
    run_command(pyinstaller_cmd, "Failed to build executable with PyInstaller.")
    
    # Workaround: PyInstaller sometimes leaves the main executable in 'build' when obfuscating
    exe_dist_path = os.path.abspath("dist/ShieldDocs/ShieldDocs.exe")
    exe_build_path = os.path.abspath("build/ShieldDocs/ShieldDocs.exe")
    if not os.path.exists(exe_dist_path):
        if os.path.exists(exe_build_path):
            print("\n[INFO] ShieldDocs.exe not found in dist. Copying from build folder...")
            shutil.copy2(exe_build_path, exe_dist_path)
        else:
            print("\n[WARNING] ShieldDocs.exe not found in build or dist folders.")

    print("\n========================================")
    print(" BUILD SUCCESSFUL!")
    print("========================================")
    print("Your secure, encrypted application is located at:")
    print(exe_dist_path)

    # 6. Automatically compile Inno Setup installer
    iscc_candidates = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        shutil.which("ISCC.exe"),
    ]
    iscc_path = next((p for p in iscc_candidates if p and os.path.exists(p)), None)
    iss_file = os.path.abspath("../installer.iss")

    if iscc_path and os.path.exists(iss_file):
        print("\nStep 4: Compiling Inno Setup installer...")
        os.chdir(os.path.dirname(iss_file))
        run_command(f'"{iscc_path}" "{iss_file}"', "Failed to compile Inno Setup installer.")
        print("\n========================================")
        print(" INSTALLER BUILD COMPLETE!")
        print("========================================")
        print(f"Installer generated: obfuscated_src/dist/ShieldDocs_Setup_{version_str}.exe")
        print("\n[IMPORTANT] Always upload 'ShieldDocs_Setup_{version_str}.exe' to GitHub Releases.")
        print("[IMPORTANT] Do NOT upload 'ShieldDocs.exe' alone, as it requires the _internal bundle!")
    else:
        print("\n[NOTE] Inno Setup compiler (ISCC.exe) not found.")
        print("You can manually open 'installer.iss' in Inno Setup to generate the Setup executable.")

if __name__ == "__main__":
    main()
