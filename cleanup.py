# cleanup.py — Dọn dẹp hệ thống (tương tự Disk Cleanup) — mở qua main.py
import os, sys, re, queue, shutil, ctypes, threading, subprocess, datetime, math, tkinter as tk
from tkinter import ttk, messagebox, PhotoImage

# ===== Resource & icon loader =====
def res_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, *parts)

try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

def load_icon_png(name, size=(20, 20)):
    p = res_path("img", name)
    if not os.path.exists(p):
        return None
    try:
        if HAVE_PIL:
            img = Image.open(p).convert("RGBA"); img = img.resize(size, Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        return PhotoImage(file=p)
    except Exception:
        return None

# ===== Footer =====
def open_link(url: str):
    if sys.platform == "win32": os.startfile(url)
    else: subprocess.Popen(["xdg-open", url])

def add_footer(win: tk.Misc):
    sep = ttk.Separator(win); sep.pack(side="bottom", fill="x", pady=(8,0))
    box = ttk.Frame(win); box.pack(side="bottom", fill="x", pady=(4,6))
    ttk.Label(box, text="Tiện ích này được phát triển bởi Trần Hà",
              foreground="grey", anchor="center").pack(fill="x")
    link = ttk.Label(box, text="Liên Hệ: facebook.com/DomBM.Rika/",
                     foreground="blue", cursor="hand2", anchor="center")
    link.pack(fill="x")
    link.bind("<Button-1>", lambda e: open_link("https://www.facebook.com/DomBM.Rika/"))

# ===== Auth token =====
_AUTH_TOKEN = None
def authorize(token: str):
    global _AUTH_TOKEN
    _AUTH_TOKEN = token

# ===== Helpers =====
WINDIR   = os.environ.get("WINDIR", r"C:\Windows")
LOCAL    = os.environ.get("LOCALAPPDATA", "")
APPDATA  = os.environ.get("APPDATA", "")
PROGRAMD = os.environ.get("ProgramData", "")
USER     = os.environ.get("USERPROFILE", "")
TEMP     = os.environ.get("TEMP", os.path.join(LOCAL, "Temp"))

def human_size(nbytes: int) -> str:
    if nbytes <= 0: return "0 B"
    units = ["B","KB","MB","GB","TB"]
    i = min(int(math.log(nbytes, 1024)), len(units)-1)
    return f"{nbytes / (1024**i):.2f} {units[i]}"

def fn_to_rx(pat: str) -> str:
    pat = re.escape(pat).replace(r"\*", ".*").replace(r"\?", ".")
    return "^" + pat + "$"

def walk_size(path, patterns=None):
    total = 0
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        if not os.path.isdir(path):
            return 0
        rx = [re.compile(fn_to_rx(pat), re.I) for pat in patterns] if patterns else None
        for root, _, files in os.walk(path, topdown=True):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    if rx:
                        name = os.path.basename(fp)
                        if not any(r.match(name) for r in rx):
                            continue
                    total += os.path.getsize(fp)
                except Exception:
                    pass
    except Exception:
        pass
    return total

def remove_path(path):
    try:
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path); return True
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True); return True
    except Exception:
        return False
    return False

def clear_dir_contents(path, patterns=None):
    ok = True
    if not os.path.isdir(path): return True
    try:
        entries = os.listdir(path)
    except Exception:
        return False
    rx = [re.compile(fn_to_rx(p), re.I) for p in patterns] if patterns else None
    for name in entries:
        fp = os.path.join(path, name)
        if rx and not any(r.match(name) for r in rx): 
            continue
        ok = remove_path(fp) and ok
    return ok

def stop_services(*names):
    for s in names:
        try: subprocess.run(f'net stop {s}', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception: pass

def start_services(*names):
    for s in names:
        try: subprocess.run(f'net start {s}', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception: pass

def run_cmd(cmd):
    try:
        subprocess.run(cmd, shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True, None
    except subprocess.CalledProcessError as e:
        return False, str(e)

def kill_proc(image):
    try:
        subprocess.run(f'taskkill /F /T /IM "{image}"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass

# Recycle Bin via SHEmptyRecycleBin
SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI   = 0x00000002
SHERB_NOSOUND        = 0x00000004
def empty_recycle_bin():
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, SHERB_NOCONFIRMATION|SHERB_NOPROGRESSUI|SHERB_NOSOUND)
        return True, None
    except Exception as e:
        ok, err = run_cmd('powershell -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"')
        return (ok, err if not ok else None)

# ===== Chromium caches =====
def chrome_user_data():  return os.path.join(LOCAL, "Google", "Chrome", "User Data")
def edge_user_data():    return os.path.join(LOCAL, "Microsoft", "Edge", "User Data")
def coccoc_user_data():  return os.path.join(LOCAL, "CocCoc", "Browser", "User Data")

def chromium_cache_targets(root):
    targets = []
    if not os.path.isdir(root): return targets
    for entry in os.listdir(root):
        prof = os.path.join(root, entry)
        if not os.path.isdir(prof): continue
        for sub in ("Cache", "Code Cache", "GPUCache"):
            p = os.path.join(prof, sub)
            if os.path.isdir(p): targets.append(p)
    for sub in ("ShaderCache", "DawnCache"):
        p = os.path.join(root, sub)
        if os.path.isdir(p): targets.append(p)
    return targets

# ===== Categories =====
CATEGORIES = [
    {"key":"recycle", "label":"Thùng rác (Recycle Bin)", "type":"special"},
    {"key":"temp", "label":"Tệp tạm (TEMP người dùng + Windows)", "paths":[
        (TEMP, None), (os.path.join(WINDIR, "Temp"), None),
    ]},
    {"key":"prefetch", "label":"Prefetch", "paths":[(os.path.join(WINDIR, "Prefetch"), None)]},
    {"key":"recent", "label":"Recent Items", "paths":[
        (os.path.join(APPDATA, "Microsoft", "Windows", "Recent"), None),
        (os.path.join(APPDATA, "Microsoft", "Windows", "Recent", "AutomaticDestinations"), None),
        (os.path.join(APPDATA, "Microsoft", "Windows", "Recent", "CustomDestinations"), None),
    ]},
    {"key":"thumbs", "label":"Thumbnail/Icon cache", "paths":[
        (os.path.join(LOCAL, "Microsoft", "Windows", "Explorer"), ["thumbcache*.db","iconcache*.db"]),
    ]},
    {"key":"wer", "label":"Windows Error Reporting", "paths":[
        (os.path.join(LOCAL, "Microsoft", "Windows", "WER"), None),
    ]},
    {"key":"dxcache", "label":"DirectX Shader Cache", "paths":[
        (os.path.join(LOCAL, "D3DSCache"), None),
        (os.path.join(LOCAL, "NVIDIA", "DXCache"), None),
        (os.path.join(LOCAL, "NVIDIA", "GLCache"), None),
        (os.path.join(LOCAL, "AMD", "DxCache"), None),
    ]},
    {"key":"do", "label":"Delivery Optimization Files", "paths":[
        (os.path.join(PROGRAMD, "Microsoft", "Windows", "DeliveryOptimization"), None),
    ]},
    {"key":"swdistrib", "label":"Windows Update Cache (SoftwareDistribution\\Download)", "type":"special"},
    {"key":"catroot2", "label":"Reset Catroot2 (ký số cập nhật)", "type":"special"},
    {"key":"dism", "label":"Component Cleanup (DISM)", "type":"special"},
    {"key":"logs", "label":"Nhật ký Windows (CBS/WindowsUpdate)", "paths":[
        (os.path.join(WINDIR, "Logs", "CBS"), None),
        (os.path.join(WINDIR, "Logs", "WindowsUpdate"), None),
    ]},
    {"key":"dump", "label":"Memory Dump (MEMORY.DMP + Minidump)", "paths":[
        (os.path.join(WINDIR, "MEMORY.DMP"), None),
        (os.path.join(WINDIR, "Minidump"), None),
    ]},
    {"key":"cache_edge", "label":"Cache Microsoft Edge", "type":"chromium", "root": edge_user_data},
    {"key":"cache_chrome", "label":"Cache Google Chrome", "type":"chromium", "root": chrome_user_data},
    {"key":"cache_coccoc", "label":"Cache Cốc Cốc", "type":"chromium", "root": coccoc_user_data},
]

BROWSER_PROCS = {
    "cache_edge":   "msedge.exe",
    "cache_chrome": "chrome.exe",
    "cache_coccoc": "browser.exe",
}

# ===== Worker =====
class CleanupWorker(threading.Thread):
    def __init__(self, mode, selections, q):
        super().__init__(daemon=True)
        self.mode = mode  # "scan" | "clean"
        self.sel = selections  # dict key->bool
        self.q = q

    def report(self, msg, color="blue", done=False, data=None):
        self.q.put((msg, color, done, data))

    def run(self):
        if self.mode == "scan": self.do_scan()
        else: self.do_clean()

    def do_scan(self):
        total = 0
        results = []  # (label, size or None)
        self.report("Đang quét dung lượng...", "orange")
        for cat in CATEGORIES:
            key = cat["key"]
            if not self.sel.get(key, False): continue
            size = 0
            ctype = cat.get("type")
            if ctype == "special":
                if key == "recycle":
                    results.append((cat["label"], None)); continue
                elif key == "swdistrib":
                    p = os.path.join(WINDIR, "SoftwareDistribution", "Download")
                    size += walk_size(p)
                elif key == "catroot2":
                    p = os.path.join(WINDIR, "System32", "catroot2")
                    size += walk_size(p)
                elif key == "dism":
                    results.append((cat["label"], None)); continue
            elif ctype == "chromium":
                root = cat["root"]()
                for p in chromium_cache_targets(root):
                    size += walk_size(p)
            else:
                for p, patterns in cat.get("paths", []):
                    size += walk_size(p, patterns)
            total += size
            results.append((cat["label"], size))
        self.report(f"Quét xong. Ước tính thu hồi: {human_size(total)}", "green", True, results)

    def do_clean(self):
        self.report("Bắt đầu dọn dẹp...", "orange")
        for cat in CATEGORIES:
            key = cat["key"]
            if not self.sel.get(key, False): continue
            label = cat["label"]; ctype = cat.get("type")
            try:
                if ctype == "special":
                    if key == "recycle":
                        ok, err = empty_recycle_bin()
                        self.report("Dọn Thùng rác" if ok else f"Lỗi dọn Thùng rác: {err}",
                                    "green" if ok else "red")
                    elif key == "swdistrib":
                        self.clean_software_distribution()
                    elif key == "catroot2":
                        self.clean_catroot2()
                    elif key == "dism":
                        self.component_cleanup()
                elif ctype == "chromium":
                    proc = BROWSER_PROCS.get(key)
                    if proc: kill_proc(proc)
                    root = cat["root"]()
                    count = 0
                    for p in chromium_cache_targets(root):
                        if remove_path(p): count += 1
                    self.report(f"Dọn cache Chromium ({label}): {count} thư mục", "green")
                else:
                    for p, patterns in cat.get("paths", []):
                        if patterns: clear_dir_contents(p, patterns)
                        else:
                            if os.path.isdir(p): clear_dir_contents(p)
                            elif os.path.isfile(p): remove_path(p)
                    self.report(f"Dọn {label}", "green")
            except Exception as e:
                self.report(f"Lỗi dọn {label}: {e}", "red")
        self.report("Hoàn tất dọn dẹp.", "green", True)

    # ---- Special cleaners ----
    def clean_software_distribution(self):
        self.report("Dừng dịch vụ Windows Update...", "grey")
        stop_services("wuauserv", "bits", "cryptsvc")
        target = os.path.join(WINDIR, "SoftwareDistribution", "Download")
        ok = True
        if os.path.isdir(target):
            self.report("Xoá SoftwareDistribution\\Download ...", "grey")
            ok = clear_dir_contents(target)
        start_services("cryptsvc", "bits", "wuauserv")
        self.report("Dọn Windows Update cache" if ok else "Lỗi dọn Windows Update cache", "green" if ok else "red")

    def clean_catroot2(self):
        self.report("Dừng dịch vụ CryptSvc...", "grey")
        stop_services("cryptsvc")
        target = os.path.join(WINDIR, "System32", "catroot2")
        ok = True
        if os.path.isdir(target):
            self.report("Reset Catroot2 ...", "grey")
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            try: os.replace(target, target + f".bak_{ts}")
            except Exception: ok = False
        start_services("cryptsvc")
        self.report("Reset Catroot2" if ok else "Lỗi reset Catroot2", "green" if ok else "red")

    def component_cleanup(self):
        self.report("DISM StartComponentCleanup (có thể mất vài phút)...", "grey")
        ok, err = run_cmd(r'Dism.exe /Online /Cleanup-Image /StartComponentCleanup')
        self.report("Component Cleanup (DISM)" if ok else f"Lỗi DISM: {err}", "green" if ok else "red")

# ===== UI =====
class CleanupApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Dọn dẹp hệ thống")
        self.geometry("700x640")
        self.resizable(False, False)
        self.transient(parent); self.grab_set()

        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.q = queue.Queue()
        self.vars = {c["key"]: tk.BooleanVar(value=True) for c in CATEGORIES}
        self.vars["dism"].set(False)   # mặc định bỏ chọn DISM

        self.results_tree = None
        self.total_label = None
        self.current_mode = None  # "scan" | "clean"

        self._build_ui()
        self._pump()

    # ----- tiện ích log -----
    def log(self, text, color="black"):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n", color)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10); outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="🧹  Dọn dẹp hệ thống", foreground="red",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,8))

        # Chọn nhanh
        selbar = ttk.Frame(outer); selbar.pack(fill="x", pady=(0,4))
        self.select_all_state = tk.BooleanVar(value=True)
        ttk.Checkbutton(selbar, text="Chọn tất cả", variable=self.select_all_state, command=self.toggle_all)\
            .pack(side="left")

        # Lưới hạng mục 2 cột
        grid = ttk.LabelFrame(outer, text="Hạng mục dọn dẹp", padding=10)
        grid.pack(fill="x", pady=(2,8))
        for idx, cat in enumerate(CATEGORIES):
            r, c = divmod(idx, 2)
            ttk.Checkbutton(grid, text=cat["label"], variable=self.vars[cat["key"]])\
                .grid(row=r, column=c, sticky="w", padx=6, pady=3)
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)

        # === HÀNG NÚT ===
        btns = ttk.Frame(outer); btns.pack(pady=(8, 6))
        self.btn_scan    = ttk.Button(btns, text=" Quét dung lượng ", command=self.start_scan)
        self.btn_clean   = ttk.Button(btns, text=" Bắt đầu dọn dẹp ", command=self.start_clean)
        self.btn_cleanmgr= ttk.Button(btns, text=" Mở Disk Cleanup (cleanmgr) ", command=self.open_cleanmgr)
        self.btn_scan.pack(side="left", padx=6)
        self.btn_clean.pack(side="left", padx=6)
        self.btn_cleanmgr.pack(side="left", padx=6)

        # Khung kết quả quét
        res = ttk.LabelFrame(outer, text="Kết quả quét", padding=10)
        res.pack(fill="both", expand=True)
        self.results_tree = ttk.Treeview(res, columns=("size"), show="headings", height=8)
        self.results_tree.heading("size", text="Dung lượng")
        self.results_tree.column("size", width=180, anchor="center")
        self.results_tree.pack(fill="both", expand=True)
        self.total_label = ttk.Label(res, text="Tổng ước tính: 0 B", foreground="grey")
        self.total_label.pack(anchor="e", pady=(6,0))

        # Khung nhật ký
        logf = ttk.LabelFrame(outer, text="Nhật ký", padding=10)
        logf.pack(fill="both", expand=True, pady=(8,0))
        self.log_text = tk.Text(logf, height=8, wrap="word")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("green", foreground="green")
        self.log_text.tag_configure("red",   foreground="red")
        self.log_text.tag_configure("orange",foreground="orange")
        self.log_text.tag_configure("grey",  foreground="grey")
        self.log_text.configure(state="disabled")

        # Status
        self.status = ttk.Label(outer, text="Trạng thái: Sẵn sàng.", foreground="green")
        self.status.pack(anchor="w", pady=(6,0))

        add_footer(self)

    # ---- chỉ khóa/mở 3 nút điều khiển ----
    def set_buttons_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for b in (self.btn_scan, self.btn_clean, self.btn_cleanmgr):
            b.configure(state=state)

    def toggle_all(self):
        val = self.select_all_state.get()
        for v in self.vars.values(): v.set(val)
        if val and "dism" in self.vars:
            self.vars["dism"].set(False)

    def start_scan(self):
        sels = {k: v.get() for k, v in self.vars.items()}
        self.current_mode = "scan"
        self.set_buttons_enabled(False)
        self.status.config(text="Trạng thái: Đang quét...", foreground="orange")
        self.log("Đang quét dung lượng...", "orange")
        CleanupWorker("scan", sels, self.q).start()

    def start_clean(self):
        sels = {k: v.get() for k, v in self.vars.items()}
        if not any(sels.values()):
            messagebox.showinfo("Thông báo", "Hãy chọn ít nhất một hạng mục."); return
        risky = [k for k in ("prefetch","recent","swdistrib","catroot2","dism","dump") if sels.get(k)]
        if risky:
            if not messagebox.askyesno("Xác nhận",
                "Một số hạng mục có thể ảnh hưởng tới hệ thống (Prefetch/Update/DISM...).\nBạn có chắc muốn tiếp tục?"):
                return
        self.current_mode = "clean"
        self.set_buttons_enabled(False)
        self.status.config(text="Trạng thái: Đang dọn dẹp...", foreground="orange")
        self.log("Bắt đầu dọn dẹp...", "orange")
        CleanupWorker("clean", sels, self.q).start()

    def open_cleanmgr(self):
        try:
            subprocess.run("cleanmgr", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được cleanmgr: {e}")

    def _pump(self):
        try:
            msg, color, done, data = self.q.get_nowait()
            self.status.config(text=f"Trạng thái: {msg}", foreground=color)
            self.log(msg, color)
            if data is not None:
                self.results_tree.delete(*self.results_tree.get_children())
                total = 0
                for label, size in data:
                    disp = "?" if size is None else human_size(size)
                    self.results_tree.insert("", "end", values=(f"{label} — {disp}", disp))
                    if size: total += size
                self.total_label.config(text=f"Tổng ước tính: {human_size(total)}")
                if self.current_mode == "scan":
                    self.log(f"Quét xong. Ước tính thu hồi: {human_size(total)}", "green")
            if done:
                self.set_buttons_enabled(True)
                if self.current_mode == "clean":
                    self.bell()
                    messagebox.showinfo("Hoàn tất", "Đã dọn dẹp xong!")
        except queue.Empty:
            pass
        self.after(120, self._pump)

# ===== API cho main.py =====
def open_window(root):
    if not _AUTH_TOKEN:
        tk.Tk().withdraw()
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    CleanupApp(root)

# ===== Block chạy trực tiếp =====
if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy ứng dụng từ main.py.")
