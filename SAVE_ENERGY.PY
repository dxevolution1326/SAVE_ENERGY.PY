import sys
import os
import time
import ctypes
from ctypes import wintypes
import tkinter as tk
import multiprocessing
import threading

# --- LOW-LEVEL WINDOWS HOOKS ---
user32 = ctypes.WinDLL('user32', use_last_error=True)

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
LLKHF_INJECTED = 0x10
LLMHF_INJECTED = 0x01

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD), 
        ("scanCode", wintypes.DWORD), 
        ("flags", wintypes.DWORD), 
        ("time", wintypes.DWORD), 
        ("dwExtraInfo", wintypes.PULONG)
    ]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT), 
        ("mouseData", wintypes.DWORD), 
        ("flags", wintypes.DWORD), 
        ("time", wintypes.DWORD), 
        ("dwExtraInfo", wintypes.PULONG)
    ]

# Define LRESULT explicitly for 64-bit compatibility
LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

# =====================================================================
# THE FIX: Explicitly define argtypes so lParam doesn't overflow
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
# =====================================================================

shared_activity_time = None
cmp_kb = None
cmp_ms = None

def keyboard_handler(nCode, wParam, lParam):
    if nCode >= 0:
        info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if not (info.flags & LLKHF_INJECTED):
            shared_activity_time.value = time.time()
    return user32.CallNextHookEx(None, nCode, wParam, lParam)

def mouse_handler(nCode, wParam, lParam):
    if nCode >= 0:
        info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        if not (info.flags & LLMHF_INJECTED):
            shared_activity_time.value = time.time()
    return user32.CallNextHookEx(None, nCode, wParam, lParam)

def start_input_hooks(shared_val):
    global shared_activity_time, cmp_kb, cmp_ms
    shared_activity_time = shared_val
    
    cmp_kb = HOOKPROC(keyboard_handler)
    cmp_ms = HOOKPROC(mouse_handler)
    
    user32.SetWindowsHookExW(WH_KEYBOARD_LL, cmp_kb, None, 0)
    user32.SetWindowsHookExW(WH_MOUSE_LL, cmp_ms, None, 0)
    
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


# --- HELPER FUNCTIONS ---
def is_media_playing():
    try:
        found_media = [False]
        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_windows_callback(hwnd, extra):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    
                    media_keywords = [
                        "youtube", "netflix", "prime video", "hotstar", "vlc",
                        "potplayer", "kmplayer", "spotify", "twitch", "disney+",
                        "jio cinema", "discord", "zoom", "teams", "steam", "game",
                        "media player", "movies & tv", "g-force"
                    ]
                    if any(keyword in title for keyword in media_keywords):
                        found_media[0] = title 
                        return False
            return True
        ctypes.windll.user32.EnumWindows(enum_windows_callback, 0)
        return found_media[0]
    except Exception:
        return False

def is_file_copy_active():
    try:
        found_copy_dialog = [False]
        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_windows_callback(hwnd, extra):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    if any(
                        keyword in title
                        for keyword in [
                            "copying", "moving", "deleting",
                            "items remaining", "calculating",
                        ]
                    ):
                        found_copy_dialog[0] = title
                        return False
            return True
        ctypes.windll.user32.EnumWindows(enum_windows_callback, 0)
        return found_copy_dialog[0]
    except Exception:
        return False


# --- UI COUNTDOWN LOGIC ---
def show_countdown_window(shared_val):
    root = tk.Tk()
    root.title("Save Energy Mode")
    root.attributes("-topmost", True)
    root.overrideredirect(True)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    win_w, win_h = int(screen_w * 0.90), int(screen_h * 0.90)
    pos_x, pos_y = (screen_w - win_w) // 2, (screen_h - win_h) // 2

    root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
    root.configure(bg="#000000")

    container = tk.Frame(root, bg="#000000")
    container.pack(expand=True)

    tk.Label(container, text="System idle. Press any key or move mouse to abort shutdown.",
             font=("Consolas", 24, "bold"), fg="#ff5555", bg="#000000").pack(pady=40)
    
    timer_label = tk.Label(container, text="09:00:00", font=("DS-Digital", 200, "bold"), fg="#FF0000", bg="#000000")
    timer_label.pack()

    COUNTDOWN_SECONDS = 9 * 60 
    start_time = time.time()

    def update_window():
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
        
        real_idle_seconds = time.time() - shared_val.value
        
        if real_idle_seconds < 2 or is_file_copy_active() or is_media_playing():
            root.destroy()
            return

        elapsed = time.time() - start_time
        remaining_time = COUNTDOWN_SECONDS - elapsed

        if remaining_time <= 0:
            root.destroy()
            os.system("shutdown /s /f /t 1")
            sys.exit(0)

        total_centis = int(max(0, remaining_time) * 100)
        mins, rem_centis = divmod(total_centis, 6000)
        secs, centis = divmod(rem_centis, 100)
        
        timer_label.config(text=f"{mins:02d}:{secs:02d}:{centis:02d}")
        root.after(30, update_window)

    root.after(30, update_window)
    root.mainloop()


# --- MAIN WORKER ---
def shutdown_monitor_worker():
    IDLE_WAIT_BEFORE_POPUP = 60  
    
    shared_val = multiprocessing.Value('d', time.time())
    
    hook_thread = threading.Thread(target=start_input_hooks, args=(shared_val,), daemon=True)
    hook_thread.start()
    
    previous_effective_idle = 0
    
    print("=" * 70)
    print("                           SAVE ENERGY")
    print("=" * 70)
    print(" An auto-shutdown Python script that saves energy by turning off")
    print(" your PC after 10 minutes of inactivity.")
    print("=" * 70)
    print(" For customization / buy me a coffee please reach us out at:")
    print(" - DXEVOLUTION.AB@GMAIL.COM")
    print("=" * 70)
    print(f"[{time.strftime('%H:%M:%S')}] Monitoring active. Waiting for system to idle...\n")

    while True:
        try:
            current_time = time.time()
            
            copy_window_title = is_file_copy_active()
            media_window_title = is_media_playing()
            
            detailed_reset_reason = None
            
            if copy_window_title:
                shared_val.value = current_time
                detailed_reset_reason = f"[Software] File Transfer Active: '{copy_window_title}'"
            elif media_window_title:
                shared_val.value = current_time
                detailed_reset_reason = f"[Software] Media/App Running: '{media_window_title}'"
            
            effective_idle_seconds = current_time - shared_val.value
            
            if not detailed_reset_reason and effective_idle_seconds < previous_effective_idle - 1:
                detailed_reset_reason = "[Hardware] Physical Mouse or Keyboard Input Detected"
            
            if detailed_reset_reason and previous_effective_idle > 3.0 and effective_idle_seconds < previous_effective_idle:
                sys.stdout.write("\r" + " " * 80 + "\r")
                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ TIMER RESET TRIGGERED!")
                print(f"[{time.strftime('%H:%M:%S')}] Cause: {detailed_reset_reason}")
                print("-" * 70)
                sys.stdout.flush()

            previous_effective_idle = effective_idle_seconds
            remaining_seconds = max(0, int(IDLE_WAIT_BEFORE_POPUP - effective_idle_seconds))

            sys.stdout.write(f"\r[STATUS] No activity counter, countdown will begin in {remaining_seconds:02d} seconds...   ")
            sys.stdout.flush()

            if effective_idle_seconds >= IDLE_WAIT_BEFORE_POPUP:
                sys.stdout.write(f"\n\n[{time.strftime('%H:%M:%S')}] Idle threshold reached! Launching countdown window...\n")
                sys.stdout.flush()
                
                p = multiprocessing.Process(target=show_countdown_window, args=(shared_val,))
                p.start()
                p.join()  
                
                sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] Activity detected. Aborted. Resetting timer...\n\n")
                sys.stdout.flush()
                
                shared_val.value = time.time()
                previous_effective_idle = 0
                
        except Exception as e:
            pass
        
        time.sleep(1)

if __name__ == "__main__":
    ctypes.windll.kernel32.SetConsoleTitleW("Save Energy")
    multiprocessing.freeze_support()
    shutdown_monitor_worker()
