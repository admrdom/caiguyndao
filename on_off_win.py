# on_off_win.py — Bật/Tắt Windows Update (mở từ main.py)
import os, sys, queue, threading, subprocess, tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, PhotoImage

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

TARGET_SERVICES = ["wuauserv", "bits", "DoSvc"]

def run_cmd(cmd: str) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
        return True, out.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        return False, (e.output or b"").decode("utf-8", errors="ignore")

def service_running(name: str) -> bool:
    ok, out = run_cmd(f'sc query "{name}"')
    return ok and ("RUNNING" in out.upper())

class UpdateToggleApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Bật/Tắt Windows Update")
        self.geometry("600x420")
        self.resizable(False, False)
        self.transient(parent); self.grab_set()

        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.icon = load_icon_png("update.png", (20,20))
        self.q = queue.Queue()
        self._build_ui()
        self.refresh_status()
        self._pump()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10); outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="⚙️  Điều khiển dịch vụ Windows Update",
                  font=("Segoe UI", 12, "bold"), foreground="red").pack(anchor="w", pady=(0,8))

        row = ttk.Frame(outer); row.pack(fill="x", pady=(0,8))
        self.btn_on  = ttk.Button(row, text=" Bật dịch vụ Update ", command=self.enable_update)
        self.btn_off = ttk.Button(row, text=" Tắt dịch vụ Update ", command=self.disable_update)
        self.btn_on.pack(side="left", padx=6); self.btn_off.pack(side="left", padx=6)

        self.status = ttk.Label(outer, text="Trạng thái: …", foreground="green")
        self.status.pack(anchor="w", pady=(0,6))

        logf = ttk.LabelFrame(outer, text="Nhật ký", padding=10)
        logf.pack(fill="both", expand=True)
        self.out = scrolledtext.ScrolledText(logf, wrap="word", height=12, font=("Consolas", 10))
        self.out.pack(fill="both", expand=True)
        bar = ttk.Frame(outer); bar.pack(fill="x", pady=(6,0))
        ttk.Button(bar, text="Sao chép log", command=self.copy_log).pack(side="left", padx=4)
        ttk.Button(bar, text="Xoá log", command=lambda: self._set_log("")).pack(side="left", padx=4)

        add_footer(self)

    def _append(self, text: str):
        self.out.configure(state="normal")
        self.out.insert("end", text + ("\n" if not text.endswith("\n") else ""))
        self.out.see("end")
        self.out.configure(state="disabled")

    def _set_log(self, text: str):
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.insert("1.0", text)
        self.out.configure(state="disabled")

    def copy_log(self):
        txt = self.out.get("1.0", "end").strip()
        self.clipboard_clear(); self.clipboard_append(txt)
        messagebox.showinfo("Sao chép", "Đã sao chép nhật ký.")

    def set_buttons(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_on.configure(state=state)
        self.btn_off.configure(state=state)

    def refresh_status(self):
        runs = [s for s in TARGET_SERVICES if service_running(s)]
        if runs:
            self.status.config(text=f"Trạng thái: ĐANG BẬT — chạy: {', '.join(runs)}", foreground="green")
        else:
            self.status.config(text="Trạng thái: ĐÃ TẮT (disabled hoặc stopped)", foreground="orange")

    def _pump(self):
        try:
            while True:
                line = self.q.get_nowait()
                if line is None:
                    self.set_buttons(True)
                    self.refresh_status()
                    self.bell()
                    break
                self._append(line)
        except queue.Empty:
            pass
        self.after(120, self._pump)

    def _thread_do(self, enable: bool):
        if enable:
            self.q.put("== BẬT Windows Update ==")
            for s in TARGET_SERVICES:
                self.q.put(f"sc config {s} start= demand")
                run_cmd(f'sc config "{s}" start= demand')
                self.q.put(f"sc start {s}")
                run_cmd(f'sc start "{s}"')
            self.q.put("Hoàn tất bật dịch vụ.")
        else:
            self.q.put("== TẮT Windows Update ==")
            for s in TARGET_SERVICES:
                self.q.put(f"sc stop {s}")
                run_cmd(f'sc stop "{s}"')
                self.q.put(f"sc config {s} start= disabled")
                run_cmd(f'sc config "{s}" start= disabled')
            self.q.put("Hoàn tất tắt dịch vụ.")
        self.q.put(None)

    def enable_update(self):
        self._set_log("")
        self.set_buttons(False)
        self.status.config(text="Trạng thái: Đang bật dịch vụ…", foreground="orange")
        threading.Thread(target=self._thread_do, args=(True,), daemon=True).start()

    def disable_update(self):
        self._set_log("")
        self.set_buttons(False)
        self.status.config(text="Trạng thái: Đang tắt dịch vụ…", foreground="orange")
        threading.Thread(target=self._thread_do, args=(False,), daemon=True).start()

def open_window(root, **kwargs):
    if not _AUTH_TOKEN:
        tk.Tk().withdraw()
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    UpdateToggleApp(root)

if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy ứng dụng từ main.py.")
