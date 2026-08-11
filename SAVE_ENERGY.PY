import sys
import os
import time
import ctypes
import tkinter as tk
import multiprocessing

# --- WINDOWS API STRUCTURES ---
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
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
                        found_media[0] = True
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
                        found_copy_dialog[0] = True
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

    # Size calculation for 90% of screen
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
    
    # Styled to mimic the red digital LED layout
    timer_label = tk.Label(container, text="09:00:00", font=("DS-Digital", 200, "bold"), fg="#FF0000", bg="#000000")
    timer_label.pack()

    # Countdown for 9 minutes (540 seconds)
    COUNTDOWN_SECONDS = 9 * 60
    start_time = time.time()

    def update_window():
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()
        
        os_idle = get_raw_os_idle_time()
        
        # Abort if user activity detected (mouse, keyboard, media, or file copy)
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
    # Trigger popup after exactly 60 seconds (1 minute) of true idle
    IDLE_WAIT_BEFORE_POPUP = 1 * 60  
    last_activity_timestamp = time.time()
    
    # Print custom banner
    print("=" * 70)
    print("                           SAVE ENERGY")
    print("=" * 70)
    print("for customization / buy me a coffee please reach us out at ")
    print("-DXEVOLUTION.AB@GMAIL.COM")
    print("=" * 70)
    print(f"[{time.strftime('%H:%M:%S')}] Monitoring active. Waiting for system to idle...\n")

    while True:
        try:
            os_idle_seconds = get_raw_os_idle_time()
            current_time = time.time()
            python_idle_seconds = current_time - last_activity_timestamp
            
            # Reset idle timers if media/copying is active, or if OS detects movement
            if is_file_copy_active() or is_media_playing():
                last_activity_timestamp = current_time
            elif os_idle_seconds < python_idle_seconds:
                last_activity_timestamp = current_time - os_idle_seconds
            
            effective_idle_seconds = current_time - last_activity_timestamp
            remaining_seconds = max(0, int(IDLE_WAIT_BEFORE_POPUP - effective_idle_seconds))

            # Real-time console countdown
            sys.stdout.write(f"\r[STATUS] Idle countdown before Save Energy: {remaining_seconds:02d} seconds remaining...   ")
            sys.stdout.flush()

            # Launch UI if we hit the idle threshold
            if effective_idle_seconds >= IDLE_WAIT_BEFORE_POPUP:
                sys.stdout.write(f"\n\n[{time.strftime('%H:%M:%S')}] Idle threshold reached! Launching countdown window...\n")
                sys.stdout.flush()
                
                p = multiprocessing.Process(target=show_countdown_window)
                p.start()
                p.join()  
                
                # If we get here, it means the window closed due to user activity
                sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] Activity detected. Shutdown aborted. Resetting timer...\n\n")
                sys.stdout.flush()
                last_activity_timestamp = time.time()
                
        except Exception:
            pass
        
        time.sleep(1)

if __name__ == "__main__":
    # Set custom title for the terminal window
    ctypes.windll.kernel32.SetConsoleTitleW("Save Energy")
    # Required for multiprocessing safely on Windows
    multiprocessing.freeze_support()
    shutdown_monitor_worker()
