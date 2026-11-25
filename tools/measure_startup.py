import ctypes
import ctypes.wintypes as wt
import subprocess
import time

user32 = ctypes.windll.user32
exe = r"dist\WorldDataComparison\WorldDataComparison.exe"
p = subprocess.Popen([exe])
t0 = time.time()
found = None

for _ in range(120):
    titles = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def callback(hwnd, lparam, titles=titles):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == p.pid and user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                titles.append(buffer.value)
        return True

    user32.EnumWindows(callback, 0)
    if titles:
        found = time.time() - t0
        print("window titles:", titles, "after", round(found, 1), "s")
        break
    time.sleep(0.5)
if found is None:
    print("no window after 60s")
p.terminate()
