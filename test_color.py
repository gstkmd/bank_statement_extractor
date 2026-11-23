import webview
import pywinstyles
import threading
import time
import ctypes

def change(window):
    time.sleep(2)
    hwnd = ctypes.windll.user32.FindWindowW(None, 'My Test Window')
    print(f'HWND: {hwnd}')
    if hwnd:
        try:
            pywinstyles.change_header_color(hwnd, color='#10b981')
            print('pywinstyles success')
        except Exception as e:
            print(f'Error: {e}')
    time.sleep(1)
    window.destroy()

window = webview.create_window('My Test Window', html='<h1>Test</h1>')
t = threading.Thread(target=change, args=(window,))
t.start()
webview.start()
