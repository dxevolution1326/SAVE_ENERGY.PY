import sys
import os
import time
import ctypes
import tkinter as tk
import multiprocessing
import subprocess

# --- WINDOWS API STRUCTURES ---
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]

class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]

# --- HELPER FUNCTIONS ---
def get_raw_os_idle_time():
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        current_ticks = ctypes.windll.kernel32.GetTickCount()
        idle_ticks = (current_ticks - lii.dwTime) & 0xFFFFFFFF
        return idle_ticks / 1000.0
    return 0.0

def get_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)

def check_power_requests():
    """Queries Windows powercfg to find out exactly which app is blocking idle."""
    try:
        result = subprocess.run(
            ['powercfg', '/requests'], 
            capture_output=True, 
            text=True, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        lines = result.stdout.split('\n')
        
        active_blockers = []
        current_category = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.isupper() and line.endswith(":"):
                current_category = line[:-1]
            elif "None." not in line and current_category:
                active_blockers.append(f"[{current_category}] {line}")
                
        if active_blockers:
            return " | ".join(active_blockers)
        return "No explicit power requests found (Could be a raw virtual keystroke)"
    except Exception as e:
        return f"Could not check powercfg: {e}"

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
def show_countdown_window():
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

    # Remaining 9 minutes for the popup to complete the full 10 minutes
    COUNTDOWN_SECONDS = 9 * 60 
    start_time = time.time()

    def update_window():
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
        
        os_idle = get_raw_os_idle_time()
        
        if os_idle < 2 or is_file_copy_active() or is_media_playing():
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
    # Only wait 60 seconds in the console before launching the UI
    IDLE_WAIT_BEFORE_POPUP = 60  
    
    last_activity_timestamp = time.time()
    previous_effective_idle = 0
    last_cursor_pos = get_cursor_pos()
    
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
            os_idle_seconds = get_raw_os_idle_time()
            current_time = time.time()
            python_idle_seconds = current_time - last_activity_timestamp
            current_cursor_pos = get_cursor_pos()
            
            detailed_reset_reason = None
            power_request_info = None
            
            copy_window_title = is_file_copy_active()
            media_window_title = is_media_playing()
            
            if copy_window_title:
                last_activity_timestamp = current_time
                detailed_reset_reason = f"[Software] File Transfer Active: '{copy_window_title}'"
            elif media_window_title:
                last_activity_timestamp = current_time
                detailed_reset_reason = f"[Software] Media/App Running: '{media_window_title}'"
            elif os_idle_seconds < python_idle_seconds:
                last_activity_timestamp = current_time - os_idle_seconds
                
                if current_cursor_pos != last_cursor_pos:
                    detailed_reset_reason = f"[Hardware] Mouse Movement (Coordinates changed from {last_cursor_pos} to {current_cursor_pos})"
                else:
                    detailed_reset_reason = "[Virtual/Keyboard] Phantom keypress or background app detected."
                    power_request_info = check_power_requests()
            
            effective_idle_seconds = current_time - last_activity_timestamp
            
            if detailed_reset_reason and effective_idle_seconds < previous_effective_idle and previous_effective_idle > 3.0:
                sys.stdout.write("\r" + " " * 80 + "\r")
                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ TIMER RESET TRIGGERED!")
                print(f"[{time.strftime('%H:%M:%S')}] Cause: {detailed_reset_reason}")
                
                if power_request_info:
                    print(f"[{time.strftime('%H:%M:%S')}] App Culprit: {power_request_info}")
                    
                print("-" * 70)
                sys.stdout.flush()

            previous_effective_idle = effective_idle_seconds
            remaining_seconds = max(0, int(IDLE_WAIT_BEFORE_POPUP - effective_idle_seconds))
            last_cursor_pos = current_cursor_pos

            # Strictly 2-digit format counting down from 60 in-place
            sys.stdout.write(f"\r[STATUS] No activity counter, countdown will begin in {remaining_seconds:02d} seconds...   ")
            sys.stdout.flush()

            if effective_idle_seconds >= IDLE_WAIT_BEFORE_POPUP:
                sys.stdout.write(f"\n\n[{time.strftime('%H:%M:%S')}] Idle threshold reached! Launching countdown window...\n")
                sys.stdout.flush()
                
                p = multiprocessing.Process(target=show_countdown_window)
                p.start()
                p.join()  
                
                sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] Activity detected. Aborted. Resetting timer...\n\n")
                sys.stdout.flush()
                
                last_activity_timestamp = time.time()
                previous_effective_idle = 0
                
        except Exception:
            pass
        
        time.sleep(1)

if __name__ == "__main__":
    ctypes.windll.kernel32.SetConsoleTitleW("Save Energy")
    multiprocessing.freeze_support()
    shutdown_monitor_worker()
