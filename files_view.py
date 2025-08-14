# files_view.py — Ẩn/Hiện thư mục & đuôi file (mở từ main.py)
import os, sys, subprocess, tkinter as tk
from tkinter import ttk, messagebox, PhotoImage

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
    if not os.path.exists(p): return None
    try:
        if HAVE_PIL:
            img = Image.open(p).convert("RGBA"); img = img.resize(size, Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        return PhotoImage(file=p)
    except Exception:
        return None

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

_AUTH_TOKEN = None
def authorize(token: str):
    global _AUTH_TOKEN; _AUTH_TOKEN = token

REG_KEY = r'HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'

def run_cmd(cmd: str) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
        return True, out.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        return False, (e.output or b"").decode("utf-8", errors="ignore")

def get_reg_dword(name: str, default: int | None):
    ok, out = run_cmd(f'reg query "{REG_KEY}" /v {name}')
    if not ok: return default
    for line in out.splitlines():
        if name in line:
            parts = line.split()
            try:
                return int(parts[-1], 16)
            except Exception:
                return default
    return default

def set_reg(name: str, val: int):
    run_cmd(f'reg add "{REG_KEY}" /v {name} /t REG_DWORD /d {val} /f')

def restart_explorer():
    run_cmd('taskkill /F /IM explorer.exe')
    run_cmd('start explorer.exe')

class FilesViewApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Ẩn/Hiện thư mục & đuôi file")
        self.geometry("520x280"); self.resizable(False, False)
        self.transient(parent); self.grab_set()
        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.var_hidden = tk.BooleanVar()
        self.var_ext    = tk.BooleanVar()
        self.var_sys    = tk.BooleanVar()

        self._build_ui()
        self.load_state()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12); outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="👁  Tùy chọn hiển thị Explorer",
                  font=("Segoe UI", 12, "bold"), foreground="red").pack(anchor="w", pady=(0,8))

        frm = ttk.LabelFrame(outer, text="Tùy chọn", padding=10); frm.pack(fill="x")
        ttk.Checkbutton(frm, text="Hiện file/thư mục ẩn", variable=self.var_hidden).grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Checkbutton(frm, text="Hiện đuôi mở rộng của file", variable=self.var_ext).grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Checkbutton(frm, text="Hiện file hệ thống (Super Hidden)", variable=self.var_sys).grid(row=2, column=0, sticky="w", padx=6, pady=6)

        btns = ttk.Frame(outer); btns.pack(pady=10)
        ttk.Button(btns, text="Áp dụng (khởi động lại Explorer)", command=self.apply).pack(side="left", padx=6)
        ttk.Button(btns, text="Khôi phục mặc định", command=self.restore_default).pack(side="left", padx=6)

        self.status = ttk.Label(outer, text="Trạng thái: Sẵn sàng.", foreground="green")
        self.status.pack(anchor="w", pady=(4,0))

        add_footer(self)

    def load_state(self):
        # Hidden: 1=show, 2=do not show
        hidden = get_reg_dword("Hidden", 2)
        ext    = get_reg_dword("HideFileExt", 1)     # 1=hide, 0=show
        superh = get_reg_dword("ShowSuperHidden", 0) # 1=show, 0=hide

        self.var_hidden.set(hidden == 1)
        self.var_ext.set(ext == 0)
        self.var_sys.set(superh == 1)

    def apply(self):
        set_reg("Hidden", 1 if self.var_hidden.get() else 2)
        set_reg("HideFileExt", 0 if self.var_ext.get() else 1)
        set_reg("ShowSuperHidden", 1 if self.var_sys.get() else 0)
        self.status.config(text="Trạng thái: Đã ghi Registry, đang khởi động lại Explorer...", foreground="orange")
        restart_explorer()
        self.status.config(text="Trạng thái: Hoàn tất.", foreground="green")
        self.bell(); messagebox.showinfo("Xong", "Đã áp dụng cài đặt hiển thị.")

    def restore_default(self):
        self.var_hidden.set(False)  # Hidden=2
        self.var_ext.set(False)     # HideFileExt=1
        self.var_sys.set(False)     # ShowSuperHidden=0
        self.apply()

def open_window(root, **kwargs):
    if not _AUTH_TOKEN:
        tk.Tk().withdraw()
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    FilesViewApp(root)

if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy ứng dụng từ main.py.")
