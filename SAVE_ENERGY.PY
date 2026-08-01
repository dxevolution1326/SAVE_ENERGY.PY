import ctypes
import os
import sys
import time
import tkinter as tk
from datetime import datetime

# Set Console Title
ctypes.windll.kernel32.SetConsoleTitleW(
    "Auto Shutdown Monitor"
)

# Windows API Constants
SW_HIDE = 0
SW_MINIMIZE = 6
SW_RESTORE = 9


def log_debug(message):
    """Outputs timestamped debug info to console only."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        print(formatted_msg)
    except Exception as e:
        print(f"Logging error: {e}")


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def get_idle_time():
    """Returns system-wide idle time in seconds."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)

    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        current_ticks = ctypes.windll.kernel32.GetTickCount()
        idle_ticks = (current_ticks - lii.dwTime) & 0xFFFFFFFF
        return idle_ticks / 1000.0
    return 0.0


def is_media_playing():
    """Checks if active media/video playback, streaming, or media players are running."""
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

    except Exception as e:
        log_debug(f"Media check error: {e}")
        return False


def is_file_copy_active():
    """Checks if an active File Explorer copy, move, or delete dialog is open."""
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


def show_countdown_window():
    """Launches a dedicated Tkinter popup window forced on top dynamically centered on any global screen resolution."""
    log_debug("Idle threshold reached. Launching countdown popup overlay.")
    root = tk.Tk()
    root.title("System Shutdown Warning")

    root.attributes("-topmost", True)
    root.overrideredirect(True)

    # Dynamically fetch actual primary monitor screen dimensions for global multi-resolution support
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    
    win_w = int(screen_w * 0.80)
    win_h = int(screen_h * 0.80)

    pos_x = (screen_w - win_w) // 2
    pos_y = (screen_h - win_h) // 2

    root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
    root.configure(bg="#000000")

    container = tk.Frame(root, bg="#000000")
    container.pack(expand=True)

    msg_label = tk.Label(
        container,
        text="To stop shutdown, please press any key or move your mouse!",
        font=("Consolas", 24, "bold"),
        fg="#ff5555",
        bg="#000000",
    )
    msg_label.pack(pady=20)

    timer_label = tk.Label(
        container,
        text="00:00.00",
        font=("Consolas", 110, "bold"),
        fg="#00e5ff",
        bg="#000000",
    )
    timer_label.pack()

    SHUTDOWN_THRESHOLD = 10 * 60

    def update_window():
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()

        if is_file_copy_active() or is_media_playing():
            log_debug("Activity detected during countdown. Aborting popup and resetting.")
            root.destroy()
            return

        idle_seconds = get_idle_time()
        remaining_time = SHUTDOWN_THRESHOLD - idle_seconds

        if remaining_time <= 0:
            root.destroy()
            log_debug("Countdown expired! Initiating system shutdown.")
            os.system("shutdown /s /f /t 1")
            sys.exit(0)
        elif idle_seconds < 59:
            log_debug("User activity detected. Closing popup.")
            root.destroy()
            return

        total_centis = int(max(0, remaining_time) * 100)
        mins, rem_centis = divmod(total_centis, 6000)
        secs, centis = divmod(rem_centis, 100)

        timer_label.config(text=f"{mins:02d}:{secs:02d}.{centis:02d}")
        root.after(30, update_window)

    root.after(30, update_window)
    root.mainloop()


def main():
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()

    print("================================================================")
    print(" SHUTDOWN MONITOR ACTIVE                                        ")
    print(" This script monitors your system activity and idle time.       ")
    print(" If you are inactive for 59 seconds, a countdown will begin     ")
    print(" and shut down the system unless activity resumes.             ")
    print(" Minimizing this window in 10 seconds...                        ")
    print("================================================================")
    
    # Give user 10 seconds to read the information
    time.sleep(10)

    # Minimize window automatically
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)

    log_debug("=== SHUTDOWN MONITOR SERVICE STARTED & WINDOW MINIMIZED ===")
    SHOW_CONSOLE_THRESHOLD = 59
    user_manually_restored = False

    while True:
        # Check if the user manually restored/maximized the window back up
        if hwnd:
            is_minimized = ctypes.windll.user32.IsIconic(hwnd)
            if not is_minimized and not user_manually_restored:
                user_manually_restored = True
                log_debug("User maximized/restored the window. Keeping it visible.")
            elif is_minimized and user_manually_restored:
                user_manually_restored = False

        idle_seconds = get_idle_time()
        file_copy = is_file_copy_active()
        media_playing = is_media_playing()

        log_debug(
            f"Monitor State -> Idle: {idle_seconds:.1f}s | FileCopy: {file_copy} | Media/Audio: {media_playing}"
        )

        if not file_copy and not media_playing:
            if idle_seconds >= SHOW_CONSOLE_THRESHOLD:
                show_countdown_window()

        time.sleep(1)


if __name__ == "__main__":
    main()