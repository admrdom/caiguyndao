# backup.py — Sao lưu / Khôi phục (Browser + Zalo) — mở qua main.py
import os, sys, time, queue, threading, subprocess, zipfile, tempfile, shutil, datetime, tkinter as tk
from tkinter import ttk, messagebox, PhotoImage, filedialog

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

# ===== Browsers (Chromium-based) =====
LOCAL = os.environ.get("LOCALAPPDATA", "")
BROWSERS = {
    "Google Chrome": {
        "proc": "chrome.exe",
        "user_data": os.path.join(LOCAL, "Google", "Chrome", "User Data"),
        "key": "chrome",
    },
    "Microsoft Edge": {
        "proc": "msedge.exe",
        "user_data": os.path.join(LOCAL, "Microsoft", "Edge", "User Data"),
        "key": "edge",
    },
    "Cốc Cốc": {
        "proc": "browser.exe",
        "user_data": os.path.join(LOCAL, "CocCoc", "Browser", "User Data"),
        "key": "coccoc",
    },
}
EXCLUDE_DIRS = {
    "Cache", "Code Cache", "GPUCache", "Crashpad", "GrShaderCache", "DawnCache",
    "ShaderCache", "Temp", "BrowserMetrics", "OptimizationGuidePredictionModels",
}

# ===== Zalo paths =====
def get_zalo_paths():
    LOCAL = os.environ.get("LOCALAPPDATA", "")
    APPDATA = os.environ.get("APPDATA", "")
    USER = os.environ.get("USERPROFILE", "")
    return {
        "ProgramsZalo": os.path.join(LOCAL, "Programs", "Zalo"),
        "ZaloPC":       os.path.join(LOCAL, "ZaloPC"),
        "ZaloData":     os.path.join(APPDATA, "ZaloData"),
        "Received":     os.path.join(USER, "Documents", "Zalo Received Files"),
        "Updater":      os.path.join(APPDATA, "zalo-updater"),
    }

ZALO_PROC = ["Zalo.exe", "ZaloUpdate.exe", "zalo-updater.exe"]

# ===== Helpers =====
def kill_process(image_name: str):
    try:
        subprocess.run(f'taskkill /F /T /IM "{image_name}"',
                       shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass

def zip_folder(src_dir: str, ziph: zipfile.ZipFile, prefix: str = "", skip_dirs: set = None, status_cb=None):
    skip_dirs = skip_dirs or set()
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        rel_root = os.path.relpath(root, os.path.dirname(src_dir))
        for f in files:
            p = os.path.join(root, f)
            arc = os.path.join(prefix, rel_root, f)
            try:
                ziph.write(p, arcname=arc)
            except Exception:
                pass
        if status_cb:
            status_cb(f"Nén: {os.path.relpath(root, src_dir)}")

def safe_backup_exist(path: str):
    if os.path.exists(path):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        try: os.replace(path, path + f".bak_{ts}")
        except Exception: pass

# ===== Workers =====
class BrowserWorker(threading.Thread):
    def __init__(self, mode, selections, dest_dir=None, zip_files=None, q=None):
        super().__init__(daemon=True)
        self.mode = mode  # "backup" or "restore"
        self.selections = selections or []
        self.dest_dir = dest_dir
        self.zip_files = zip_files or []
        self.q = q

    def report(self, msg, color="blue", done=False):
        if self.q: self.q.put((msg, color, done))

    def run(self):
        if self.mode == "backup": self.do_backup()
        else: self.do_restore()

    def do_backup(self):
        if not self.selections:
            self.report("Chưa chọn trình duyệt để sao lưu.", "red", True); return
        if not self.dest_dir:
            self.report("Thiếu thư mục lưu file sao lưu.", "red", True); return

        for name in self.selections:
            spec = BROWSERS.get(name)
            if not spec: continue
            kill_process(spec["proc"])
            src = spec["user_data"]
            if not os.path.isdir(src):
                self.report(f"⚠️ Không thấy dữ liệu {name}: {src}", "orange"); continue
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_zip = os.path.join(self.dest_dir, f'{spec["key"]}_UserData_{ts}.zip')
            self.report(f"Sao lưu {name}...", "orange")
            try:
                os.makedirs(self.dest_dir, exist_ok=True)
                with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                    zip_folder(src, z, prefix=f'{spec["key"]}', skip_dirs=EXCLUDE_DIRS,
                               status_cb=lambda m: self.report(m, "grey"))
                self.report(f"✅ Đã lưu: {out_zip}", "green")
            except Exception as e:
                self.report(f"❌ Lỗi sao lưu {name}: {e}", "red")
        self.report("Hoàn tất sao lưu trình duyệt.", "green", True)

    def do_restore(self):
        if not self.zip_files:
            self.report("Chưa chọn file ZIP để khôi phục.", "red", True); return
        for zip_path in self.zip_files:
            bname = os.path.basename(zip_path).lower()
            target = None
            for name, spec in BROWSERS.items():
                if spec["key"] in bname or name.lower().split()[0] in bname:
                    target = (name, spec); break
            if not target:
                self.report(f"⚠️ Không xác định trình duyệt từ: {os.path.basename(zip_path)}", "orange"); continue
            name, spec = target
            kill_process(spec["proc"])
            self.report(f"Khôi phục {name}...", "orange")
            try:
                tmp = tempfile.mkdtemp(prefix="brow_")
                with zipfile.ZipFile(zip_path, "r") as z: z.extractall(tmp)
                # tìm thư mục có prefix spec["key"]
                src = os.path.join(tmp, spec["key"])
                if not os.path.isdir(src):
                    # có thể lưu kèm phụ thuộc; tìm đệ quy
                    for d in os.listdir(tmp):
                        cand = os.path.join(tmp, d, "User Data")
                        if os.path.isdir(cand): src = os.path.dirname(cand); break
                safe_backup_exist(spec["user_data"])
                shutil.move(src, spec["user_data"])
                shutil.rmtree(tmp, ignore_errors=True)
                self.report(f"✅ Đã khôi phục {name}.", "green")
            except Exception as e:
                self.report(f"❌ Lỗi khôi phục {name}: {e}", "red")
        self.report("Hoàn tất khôi phục trình duyệt.", "green", True)

class ZaloWorker(threading.Thread):
    def __init__(self, mode, selections, dest_dir=None, zip_path=None, q=None):
        super().__init__(daemon=True)
        self.mode = mode  # "backup" or "restore"
        self.selections = selections or {}  # dict[key->bool]
        self.dest_dir = dest_dir
        self.zip_path = zip_path
        self.q = q

    def report(self, msg, color="blue", done=False):
        if self.q: self.q.put((msg, color, done))

    def run(self):
        if self.mode == "backup": self.do_backup()
        else: self.do_restore()

    def do_backup(self):
        paths = get_zalo_paths()
        if not self.dest_dir:
            self.report("Thiếu thư mục lưu file sao lưu.", "red", True); return
        for p in ZALO_PROC: kill_process(p)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_zip = os.path.join(self.dest_dir, f"ZaloBackup_{ts}.zip")
        os.makedirs(self.dest_dir, exist_ok=True)

        self.report("Đang sao lưu Zalo...", "orange")
        try:
            with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for key, abs_path in paths.items():
                    if not self.selections.get(key, False): continue
                    if os.path.isdir(abs_path):
                        self.report(f"Đang nén: {key}", "grey")
                        zip_folder(abs_path, z, prefix=f"Zalo/{key}")
                    else:
                        self.report(f"⚠️ Bỏ qua {key} (không tồn tại: {abs_path})", "orange")
            self.report(f"✅ Đã lưu: {out_zip}", "green", True)
        except Exception as e:
            self.report(f"❌ Lỗi sao lưu Zalo: {e}", "red", True)

    def do_restore(self):
        if not self.zip_path or not os.path.isfile(self.zip_path):
            self.report("Chưa chọn file ZIP khôi phục.", "red", True); return
        for p in ZALO_PROC: kill_process(p)

        paths = get_zalo_paths()
        self.report("Đang khôi phục Zalo...", "orange")
        try:
            tmp = tempfile.mkdtemp(prefix="zalo_")
            with zipfile.ZipFile(self.zip_path, "r") as z:
                z.extractall(tmp)
            src_root = os.path.join(tmp, "Zalo")
            for key, target in paths.items():
                if not self.selections.get(key, False): continue
                src = os.path.join(src_root, key)
                if not os.path.isdir(src): 
                    self.report(f"⚠️ Không thấy dữ liệu {key} trong ZIP.", "orange"); continue
                safe_backup_exist(target)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                # di chuyển nguyên thư mục
                if os.path.exists(target): shutil.rmtree(target, ignore_errors=True)
                shutil.move(src, target)
                self.report(f"Khôi phục: {key}", "grey")
            shutil.rmtree(tmp, ignore_errors=True)
            self.report("✅ Đã khôi phục Zalo.", "green", True)
        except Exception as e:
            self.report(f"❌ Lỗi khôi phục Zalo: {e}", "red", True)

# ===== UI =====
class BackupApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Sao lưu / Khôi phục")
        self.geometry("620x560")
        self.resizable(False, False)
        self.transient(parent); self.grab_set()

        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.q = queue.Queue()
        self.vars = {name: tk.BooleanVar(value=True) for name in BROWSERS.keys()}
        self.dest_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop", "Backup"))
        self.selected_zips = []

        # Zalo vars
        self.zalo_sel = {k: tk.BooleanVar(value=(k in ["ZaloPC", "ZaloData", "Received"])) for k in get_zalo_paths().keys()}
        self.zalo_dest = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Desktop", "Backup"))
        self.zalo_zip = tk.StringVar(value="")

        self._build_ui()
        self._pump()

    def _build_ui(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=10)

        # ----- TAB: Trình duyệt -----
        tab_b = ttk.Frame(nb); nb.add(tab_b, text="Trình duyệt")
        grp_sel = ttk.LabelFrame(tab_b, text="Chọn trình duyệt", padding=10); grp_sel.pack(fill="x", pady=6)
        names = list(BROWSERS.keys())
        for i, name in enumerate(names):
            r, c = divmod(i, 2)
            ttk.Checkbutton(grp_sel, text=name, variable=self.vars[name]).grid(row=r, column=c, sticky="w", padx=6, pady=4)
        grp_sel.columnconfigure(0, weight=1); grp_sel.columnconfigure(1, weight=1)

        grp_dest = ttk.LabelFrame(tab_b, text="Thư mục lưu file sao lưu (.zip)", padding=10)
        grp_dest.pack(fill="x", pady=6)
        ttk.Entry(grp_dest, textvariable=self.dest_dir).pack(side="left", fill="x", expand=True, padx=(0,6))
        ttk.Button(grp_dest, text="Chọn...", command=self.pick_dest_dir).pack(side="left")

        row_btns = ttk.Frame(tab_b); row_btns.pack(pady=6)
        ttk.Button(row_btns, text=" Bắt đầu sao lưu ", command=self.start_backup).pack(side="left", padx=4)

        ttk.Label(tab_b, text="Khôi phục (chọn một hoặc nhiều file ZIP)").pack(anchor="w", padx=6, pady=(12,2))
        btns = ttk.Frame(tab_b); btns.pack(fill="x", padx=6, pady=(0,6))
        ttk.Button(btns, text=" Thêm ZIP... ", command=self.add_zip_files).pack(side="left")
        ttk.Button(btns, text=" Xóa danh sách ", command=self.clear_zip_list).pack(side="left", padx=6)
        self.listbox = tk.Listbox(tab_b, height=8); self.listbox.pack(fill="both", expand=True, padx=6, pady=(0,8))
        ttk.Button(tab_b, text=" Khôi phục ", command=self.start_restore).pack()

        # ----- TAB: Zalo -----
        tab_z = ttk.Frame(nb); nb.add(tab_z, text="Zalo")
        ttk.Label(tab_z, text="Chọn thành phần Zalo cần sao lưu/khôi phục:").pack(anchor="w", padx=6, pady=(8,4))

        grid = ttk.LabelFrame(tab_z, text="Thư mục dữ liệu", padding=10); grid.pack(fill="x", pady=6)
        items = list(get_zalo_paths().items())
        for i, (key, path) in enumerate(items):
            r, c = divmod(i, 2)
            ttk.Checkbutton(grid, text=f"{key}", variable=self.zalo_sel[key]).grid(row=r, column=c, sticky="w", padx=6, pady=4)
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)

        # Đích backup
        dest = ttk.LabelFrame(tab_z, text="Thư mục lưu (backup Zalo)", padding=10); dest.pack(fill="x", pady=6)
        ttk.Entry(dest, textvariable=self.zalo_dest).pack(side="left", fill="x", expand=True, padx=(0,6))
        ttk.Button(dest, text="Chọn...", command=self.pick_zalo_dest).pack(side="left")
        ttk.Button(tab_z, text=" Sao lưu Zalo ", command=self.zalo_backup).pack(pady=(6,10))

        # ZIP để khôi phục
        rest = ttk.LabelFrame(tab_z, text="File ZIP để khôi phục Zalo", padding=10); rest.pack(fill="x", pady=6)
        ttk.Entry(rest, textvariable=self.zalo_zip).pack(side="left", fill="x", expand=True, padx=(0,6))
        ttk.Button(rest, text="Chọn ZIP...", command=self.pick_zalo_zip).pack(side="left")
        ttk.Button(tab_z, text=" Khôi phục Zalo ", command=self.zalo_restore).pack(pady=(6,6))

        # ----- Status + footer -----
        self.status = ttk.Label(self, text="Trạng thái: Sẵn sàng.", foreground="green")
        self.status.pack(anchor="w", padx=12, pady=(0,8))
        add_footer(self)

    # ==== Browser handlers ====
    def pick_dest_dir(self):
        d = filedialog.askdirectory(initialdir=self.dest_dir.get() or os.path.expanduser("~"))
        if d: self.dest_dir.set(d)

    def add_zip_files(self):
        paths = filedialog.askopenfilenames(title="Chọn file sao lưu (.zip)", filetypes=[("ZIP files", "*.zip")])
        if not paths: return
        for p in paths:
            if p not in self.selected_zips:
                self.selected_zips.append(p); self.listbox.insert("end", p)

    def clear_zip_list(self):
        self.selected_zips.clear(); self.listbox.delete(0, "end")

    def start_backup(self):
        sels = [name for name, var in self.vars.items() if var.get()]
        if not sels:
            messagebox.showinfo("Thông báo", "Hãy chọn ít nhất một trình duyệt."); return
        self.set_enabled(False)
        BrowserWorker("backup", sels, dest_dir=self.dest_dir.get(), q=self.q).start()

    def start_restore(self):
        if not self.selected_zips:
            messagebox.showinfo("Thông báo", "Hãy chọn ít nhất một file ZIP để khôi phục."); return
        if not messagebox.askyesno("Xác nhận", "Khôi phục sẽ ghi đè dữ liệu (thư mục cũ sẽ được backup .bak). Tiếp tục?"):
            return
        self.set_enabled(False)
        BrowserWorker("restore", [], zip_files=self.selected_zips, q=self.q).start()

    # ==== Zalo handlers ====
    def pick_zalo_dest(self):
        d = filedialog.askdirectory(initialdir=self.zalo_dest.get() or os.path.expanduser("~"))
        if d: self.zalo_dest.set(d)

    def pick_zalo_zip(self):
        p = filedialog.askopenfilename(title="Chọn file sao lưu Zalo (.zip)", filetypes=[("ZIP files", "*.zip")])
        if p: self.zalo_zip.set(p)

    def zalo_backup(self):
        sels = {k: v.get() for k, v in self.zalo_sel.items()}
        if not any(sels.values()):
            messagebox.showinfo("Thông báo", "Hãy chọn ít nhất một thành phần Zalo."); return
        self.set_enabled(False)
        ZaloWorker("backup", sels, dest_dir=self.zalo_dest.get(), q=self.q).start()

    def zalo_restore(self):
        sels = {k: v.get() for k, v in self.zalo_sel.items()}
        if not any(sels.values()):
            messagebox.showinfo("Thông báo", "Hãy chọn ít nhất một thành phần Zalo."); return
        if not self.zalo_zip.get():
            messagebox.showinfo("Thông báo", "Hãy chọn file ZIP để khôi phục."); return
        if not messagebox.askyesno("Xác nhận", "Khôi phục Zalo sẽ ghi đè dữ liệu hiện tại (thư mục cũ sẽ được backup .bak). Tiếp tục?"):
            return
        self.set_enabled(False)
        ZaloWorker("restore", sels, zip_path=self.zalo_zip.get(), q=self.q).start()

    # ==== status loop ====
    def _pump(self):
        try:
            msg, color, done = self.q.get_nowait()
            self.status.config(text=f"Trạng thái: {msg}", foreground=color)
            if done: self.set_enabled(True)
        except queue.Empty:
            pass
        self.after(120, self._pump)

    def set_enabled(self, ok: bool):
        state = "normal" if ok else "disabled"
        for child in self.winfo_children():
            try: child.configure(state=state)
            except: pass

# ===== API cho main.py =====
def open_window(root):
    if not _AUTH_TOKEN:
        tk.Tk().withdraw()
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    BackupApp(root)

# ===== Block chạy trực tiếp =====
if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy ứng dụng từ main.py.")
