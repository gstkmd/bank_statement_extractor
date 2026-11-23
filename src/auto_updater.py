import os
import sys
import json
import urllib.request
import threading
import time
import subprocess
import tempfile

# NOTE: This matches the repository you just created in the screenshot!
GITHUB_REPO = "gstkmd/ShieldDocs-Releases"
UPDATE_CHECK_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CURRENT_VERSION = "v1.1.41"

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        pass

def parse_version(v_str):
    import re
    parts = re.findall(r'\d+', str(v_str))
    return tuple(map(int, parts)) if parts else (0,)

def check_for_updates():
    """
    Checks the GitHub public repository for a new version.
    Returns (True, latest_version_string, download_url) if an update is available.
    """
    try:
        req = urllib.request.Request(UPDATE_CHECK_URL, headers={'User-Agent': 'ShieldDocs-Updater'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        latest_version = data.get("tag_name", "")
        
        # Robust numeric version comparison (e.g. (1, 1, 42) > (1, 1, 41))
        if latest_version and parse_version(latest_version) > parse_version(CURRENT_VERSION):
            # Find the Inno Setup installer .exe asset (must contain 'setup' to ensure all dependencies are bundled)
            download_url = None
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith(".exe") and "setup" in name:
                    download_url = asset.get("browser_download_url")
                    break
            
            if download_url:
                return True, latest_version, download_url
                
        return False, CURRENT_VERSION, None
    except Exception as e:
        safe_print(f"Update check failed: {e}")
        return False, CURRENT_VERSION, None

def perform_update(download_url, new_version):
    """
    Downloads the new installer, shows a non-blocking UI, and runs it with visible progress.
    """
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title("ShieldDocs Update")
        root.attributes('-topmost', True)
        
        # Center the window
        window_width = 400
        window_height = 250
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = int((screen_width / 2) - (window_width / 2))
        y = int((screen_height / 2) - (window_height / 2))
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        label = tk.Label(root, text=f"ShieldDocs Version {new_version} found!\n\nDownloading update in the background...", font=("Arial", 12), justify="center", wraplength=350)
        label.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Update the UI without blocking
        root.update()

        safe_print(f"Downloading update from {download_url}...")
        
        # Download the .exe to a temporary directory
        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, "ShieldDocs_Update.exe")
        
        start_time = time.time()
        
        def reporthook(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(int((downloaded / total_size) * 100), 100)
                
                elapsed = time.time() - start_time
                if elapsed > 0 and downloaded > 0:
                    speed = downloaded / elapsed
                    remaining_bytes = max(0, total_size - downloaded)
                    est_time_sec = remaining_bytes / speed if speed > 0 else 0
                    
                    if est_time_sec < 10:
                        msg = "Almost done!"
                    elif est_time_sec < 60:
                        msg = "Hold tight, it's going fast!"
                    elif est_time_sec < 300:
                        msg = "Grabbing a coffee might be a good idea..."
                    else:
                        msg = "This might take a while depending on your connection."
                        
                    mins, secs = divmod(int(est_time_sec), 60)
                    time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                    
                    label.config(text=f"ShieldDocs Version {new_version} found!\n\nDownloading update: {percent}%\nEstimated time left: {time_str}\n{msg}")
                else:
                    label.config(text=f"ShieldDocs Version {new_version} found!\n\nDownloading update: {percent}%")
                    
                root.update()

        urllib.request.urlretrieve(download_url, installer_path, reporthook=reporthook)
        
        # Update label text to let the user know it's closing
        label.config(text="Download complete!\n\nShieldDocs will now close to apply the update.")
        root.update()
        
        # Wait 3 seconds so the user can read the message before closing
        time.sleep(3)
        
        safe_print(f"Download complete. Running installer: {installer_path}")
        
        # Launch the Inno Setup installer with visible progress
        # /SILENT: Shows progress bar but skips setup wizard questions
        # /FORCECLOSEAPPLICATIONS: Force close the current app if locked
        subprocess.Popen([installer_path, '/SILENT', '/FORCECLOSEAPPLICATIONS'])
        
        safe_print("Update applied. Shutting down for installation...")
        
        # Terminate immediately so the installer can overwrite the .exe
        os._exit(0)
        
    except Exception as e:
        safe_print(f"Update failed: {e}")
        try:
            label.config(text=f"An error occurred while updating:\n{e}")
            root.update()
            time.sleep(5)
            root.destroy()
        except:
            pass

def start_update_checker_background():
    """
    Runs the update checker in a background thread so it doesn't block the UI.
    """
    def task():
        # Wait a few seconds after startup before checking
        time.sleep(5)
        has_update, new_version, url = check_for_updates()
        if has_update:
            safe_print(f"*** New version {new_version} available! ***")
            # Usually we would send a signal to the frontend UI here to prompt the user
            # For automatic updates in the background, we notify the user and run it:
            perform_update(url, new_version)

    thread = threading.Thread(target=task, daemon=True)
    thread.start()
