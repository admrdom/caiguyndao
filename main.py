# main.py — Tiện ích cài Win Dạo V1.0.1
# - Không có menu
# - Đăng nhập bắt buộc (APP_PASSWORD) → cấp token cho module con (authorize + open_window)
# - Nút chức năng chính: Office, Phần mềm, Thiết lập Windows, Sửa lỗi mạng, Sao lưu/Khôi phục,
#   Xoá rác, Thông tin máy, Kích hoạt, Xoá bloatware, Sao lưu bản quyền
# - Tuỳ chọn nhanh (2 hàng): Hiện/Ẩn file ẩn, Hiện/Ẩn đuôi file, Bật/Tắt Update (on_off_win.py nếu có),
#   Tắt BitLocker
# - Icon tiêu đề: img/logo.ico ; Icon nút: PNG 20x20 trong img/
# - Khi mở: căn giữa màn hình với chút NGẪU NHIÊN (jitter)

import os
import sys
import random
import importlib
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, PhotoImage

APP_VER = "V2.0.1"                         # ← cập nhật mỗi lần bạn phát hành
APP_TITLE = f"Tiện ích cài Win Dạo {APP_VER}"
APP_PASSWORD = "1"                     # ← ĐỔI mật khẩu theo ý bạn

# ===== Optional Pillow để resize icon PNG về 20x20 =====
try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

def res_path(*parts):
    """Hỗ trợ PyInstaller lấy resource."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, *parts)

def load_icon_png(name, size=(20, 20)):
    """Load PNG từ ./img và resize về 20x20 nếu có Pillow."""
    p = res_path("img", name)
    if not os.path.exists(p):
        return None
    try:
        if HAVE_PIL:
            img = Image.open(p).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        return PhotoImage(file=p)
    except Exception:
        return None

def run_cmd(cmd: str) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return True, out.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        return False, (e.output or b"").decode("utf-8", errors="ignore")

def open_link(url: str):
    if sys.platform == "win32":
        os.startfile(url)
    else:
        subprocess.Popen(["xdg-open", url])

def center_on_screen(win, jitter=0):
    """
    Đặt cửa sổ ra giữa màn hình, có dao động ngẫu nhiên ±jitter pixel (nếu >0).
    Gọi sau khi đã set geometry/build UI để lấy đúng kích thước.
    """
    win.update_idletasks()
    try:
        size = win.geometry().split('+')[0]  # "WxH+X+Y"
        w, h = map(int, size.split('x'))
    except Exception:
        w = win.winfo_width() or win.winfo_reqwidth()
        h = win.winfo_height() or win.winfo_reqheight()

    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2

    if jitter:
        x += random.randint(-jitter, jitter)
        y += random.randint(-jitter, jitter)

    x = max(0, min(x, sw - w))
    y = max(0, min(y, sh - h))
    win.geometry(f"+{x}+{y}")

# ======================= ĐĂNG NHẬP =======================
class LoginDialog(tk.Toplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success
        self.title(APP_TITLE)
        self.geometry("420x200")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(bg="#f0f0f0")

        # Icon tiêu đề
        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        # Chỉ hiển thị dòng hướng dẫn (bỏ tiêu đề lớn bên trong hộp)
        hint = tk.Label(self, text="Vui lòng nhập mật khẩu để tiếp tục",
                        bg="#f0f0f0", fg="#444", font=("Segoe UI", 11, "bold"))
        hint.pack(pady=(16, 8))

        frm = tk.Frame(self, bg="#f0f0f0"); frm.pack(pady=6)
        tk.Label(frm, text="Mật khẩu:", bg="#f0f0f0").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.var_pw = tk.StringVar()
        self.ent_pw = tk.Entry(frm, textvariable=self.var_pw, show="*")
        self.ent_pw.grid(row=0, column=1, padx=5, pady=5)
        self.ent_pw.focus_set()

        btns = tk.Frame(self, bg="#f0f0f0"); btns.pack(pady=6)
        ttk.Button(btns, text="Đăng nhập", command=self._login).pack(side="left", padx=6)
        ttk.Button(btns, text="Thoát", command=self._quit).pack(side="left", padx=6)

        # Footer bản quyền
        sep = ttk.Separator(self); sep.pack(side="bottom", fill="x", pady=(8,0))
        box = ttk.Frame(self); box.pack(side="bottom", fill="x", pady=(4,6))
        ttk.Label(box, text="Tiện ích này được phát triển bởi Trần Hà",
                  foreground="grey", anchor="center").pack(fill="x")
        link = ttk.Label(box, text="Liên Hệ: facebook.com/DomBM.Rika/",
                         foreground="blue", cursor="hand2", anchor="center")
        link.pack(fill="x")
        link.bind("<Button-1>", lambda e: open_link("https://www.facebook.com/DomBM.Rika/"))

        self.bind("<Return>", lambda e: self._login())

        # Căn giữa + ngẫu nhiên khi mở
        self.after(0, lambda: center_on_screen(self, jitter=20))

    def _login(self):
        pw = self.var_pw.get().strip()
        if pw == APP_PASSWORD:  # BẮT BUỘC đúng mật khẩu
            token = "OK-" + pw
            self.on_success(token)
            self.destroy()
        else:
            messagebox.showerror("Sai mật khẩu", "Mật khẩu không đúng. Vui lòng thử lại.")
            self.ent_pw.select_range(0, 'end')
            self.ent_pw.focus_set()

    def _quit(self):
        self.master.destroy()

# ======================= ỨNG DỤNG CHÍNH =======================
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x680")
        self.resizable(False, False)
        self.configure(bg="#f8f8f8")

        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.auth_token = None
        self.icons = self._load_icons()

        # Hiển thị login
        self.withdraw()
        LoginDialog(self, self._on_login_success)

    # --------- Icon set ----------
    def _load_icons(self):
        return {
            "office":    load_icon_png("office.png"),
            "soft":      load_icon_png("soft.png"),
            "system":    load_icon_png("system.png"),
            "internet":  load_icon_png("internet.png"),
            "backup":    load_icon_png("backup.png"),
            "clean":     load_icon_png("clean.png"),
            "info":      load_icon_png("info.png"),
            "activate":  load_icon_png("activate.png"),
            "bloat":     load_icon_png("bloat.png"),
            "license":   load_icon_png("license.png"),
            "hidden_on": load_icon_png("hidden_on.png"),
            "hidden_off":load_icon_png("hidden_off.png"),
            "ext_on":    load_icon_png("ext_on.png"),
            "ext_off":   load_icon_png("ext_off.png"),
            "update":    load_icon_png("update.png"),
            "bitlocker": load_icon_png("bitlocker.png"),
        }

    def _on_login_success(self, token: str):
        self.auth_token = token
        self.deiconify()
        self._build_ui()
        # Căn giữa + ngẫu nhiên cửa sổ chính
        center_on_screen(self, jitter=40)

    # --------- Build UI ----------
    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#f8f8f8"); header.pack(fill="x", padx=12, pady=(12,6))
        tk.Label(header, text=APP_TITLE, font=("Segoe UI", 14, "bold"), bg="#f8f8f8").pack(side="left")
        tk.Label(header, text="© Trần Hà", bg="#f8f8f8", fg="#666").pack(side="right")

        # Nội dung chia 2 cột
        body = tk.Frame(self, bg="#f8f8f8"); body.pack(fill="both", expand=True, padx=12, pady=6)
        left = tk.Frame(body, bg="#f8f8f8"); left.pack(side="left", fill="both", expand=True, padx=(0,6))
        right = tk.Frame(body, bg="#f8f8f8"); right.pack(side="left", fill="both", expand=True, padx=(6,0))

        # --- KHU VỰC CHÍNH: DANH MỤC ---
        lf = ttk.LabelFrame(left, text="Danh mục", padding=10)
        lf.pack(fill="both", expand=True)

        grid = tk.Frame(lf, bg="#ffffff"); grid.pack(fill="both", expand=True)

        items = [
            (" Cài Office",             self.icons["office"],   lambda: self._open_module("office", "Cài Office")),
            (" Cài Phần Mềm",           self.icons["soft"],     lambda: self._open_module("phanmem", "Cài Phần Mềm")),
            (" Thiết lập Windows",      self.icons["system"],   lambda: self._open_module("setup", "Thiết lập Windows")),
            (" Sửa Lỗi Mạng",           self.icons["internet"], lambda: self._open_module("network", "Sửa Lỗi Mạng")),
            (" Sao lưu / Khôi phục",    self.icons["backup"],   lambda: self._open_module("backup", "Sao lưu / Khôi phục")),
            (" Xoá rác (Cleanup)",      self.icons["clean"],    lambda: self._open_module("cleanup", "Xoá rác")),
            (" Thông tin máy",          self.icons["info"],     lambda: self._open_module("info", "Thông tin máy")),
            (" Kích hoạt Win - Office", self.icons["activate"], lambda: self._open_module("kichhoat", "Kích hoạt Win - Office")),
            (" Xoá bloatware",          self.icons["bloat"],    lambda: self._open_module("bloatware", "Xoá bloatware")),
            (" Sao lưu bản quyền",      self.icons["license"],  lambda: self._open_module("banquyen", "Sao lưu bản quyền")),
        ]

        cols = 2
        for i, (text, icon, cmd) in enumerate(items):
            r, c = divmod(i, cols)
            btn = ttk.Button(grid, text=text, image=icon, compound="left", command=cmd)
            btn.grid(row=r, column=c, sticky="ew", padx=6, pady=6, ipadx=8, ipady=8)
        for c in range(cols):
            grid.grid_columnconfigure(c, weight=1)

        # --- KHU VỰC PHẢI: TUỲ CHỌN NHANH ---
        rf = ttk.LabelFrame(right, text="Tuỳ chọn nhanh", padding=10)
        rf.pack(fill="x")

        row1 = tk.Frame(rf, bg="#ffffff"); row1.pack(fill="x")
        row2 = tk.Frame(rf, bg="#ffffff"); row2.pack(fill="x", pady=(4,0))

        ttk.Button(row1, text=" Hiện file ẩn", image=self.icons["hidden_on"], compound="left",
                   command=self.show_hidden).pack(side="left", expand=True, fill="x", padx=4, pady=4)
        ttk.Button(row1, text=" Ẩn file ẩn", image=self.icons["hidden_off"], compound="left",
                   command=self.hide_hidden).pack(side="left", expand=True, fill="x", padx=4, pady=4)
        ttk.Button(row1, text=" Hiện đuôi file", image=self.icons["ext_on"], compound="left",
                   command=self.show_extensions).pack(side="left", expand=True, fill="x", padx=4, pady=4)
        ttk.Button(row1, text=" Ẩn đuôi file", image=self.icons["ext_off"], compound="left",
                   command=self.hide_extensions).pack(side="left", expand=True, fill="x", padx=4, pady=4)

        ttk.Button(row2, text=" Bật/Tắt Windows Update", image=self.icons["update"], compound="left",
                   command=self.toggle_windows_update).pack(side="left", expand=True, fill="x", padx=4, pady=4)
        ttk.Button(row2, text=" Tắt BitLocker (ổ hệ thống)", image=self.icons["bitlocker"], compound="left",
                   command=self.turn_off_bitlocker).pack(side="left", expand=True, fill="x", padx=4, pady=4)

        # --- KHUNG GỢI Ý ---
        tips = ttk.LabelFrame(right, text="Ghi chú", padding=10)
        tips.pack(fill="both", expand=True, pady=(8,0))
        tk.Label(tips, bg="#ffffff", justify="left", anchor="w",
                 text=(
                    "• Tiện ích hỗ trợ cài Office/Phần mềm, thiết lập và sửa lỗi Windows nhanh.\n"
                    "• Một số tác vụ cần quyền Admin (BitLocker, Windows Update, dọn rác hệ thống).\n"
                    "• Mỗi chức năng mở trong cửa sổ riêng; hãy chạy từ main.py sau khi đăng nhập.\n"
                    "• Thay đổi Hiện/Ẩn file/đuôi cần mở lại File Explorer để áp dụng."
                    "• Hỗ trợ sửa lỗi mạng, lỗi do treo mạng..."
                    "• Tính năng sắp tới, sửa lỗi chia sẻ máy in, chia sẻ file qua mạng...."                        
                 )).pack(fill="both", expand=True)

        # Footer
        sep = ttk.Separator(self); sep.pack(side="bottom", fill="x", pady=(6,0))
        box = ttk.Frame(self); box.pack(side="bottom", fill="x", pady=(4,8))
        ttk.Label(box, text="Tiện ích này được phát triển bởi Trần Hà",
                  foreground="grey", anchor="center").pack(fill="x")
        link = ttk.Label(box, text="Liên Hệ: facebook.com/DomBM.Rika/",
                         foreground="blue", cursor="hand2", anchor="center")
        link.pack(fill="x")
        link.bind("<Button-1>", lambda e: open_link("https://www.facebook.com/DomBM.Rika/"))

    # --------- OPEN MODULE ----------
    def _open_module(self, modname: str, pretty: str):
        try:
            m = importlib.import_module(modname)
        except Exception as e:
            messagebox.showerror("Không tìm thấy module",
                                 f"Chưa có file {modname}.py hoặc lỗi import.\n{e}")
            return
        try:
            if hasattr(m, "authorize"):
                m.authorize(self.auth_token or "")
            if hasattr(m, "open_window"):
                m.open_window(self)
            else:
                messagebox.showerror("Module không hợp lệ",
                                     f"{modname}.py thiếu hàm open_window(root)")
        except Exception as e:
            messagebox.showerror(f"Lỗi mở {pretty}", str(e))

    # ==================== QUICK ACTIONS ====================
    # Ẩn/Hiện file ẩn
    def show_hidden(self):
        cmds = [
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v Hidden /t REG_DWORD /d 1 /f',
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v ShowSuperHidden /t REG_DWORD /d 1 /f',
        ]
        ok = self._run_many(cmds)
        if ok:
            messagebox.showinfo("Thành công", "Đã bật hiển thị file ẩn & hệ thống.\nMở lại cửa sổ Explorer để thấy thay đổi.")

    def hide_hidden(self):
        cmds = [
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v Hidden /t REG_DWORD /d 2 /f',
            r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v ShowSuperHidden /t REG_DWORD /d 0 /f',
        ]
        ok = self._run_many(cmds)
        if ok:
            messagebox.showinfo("Thành công", "Đã ẩn file ẩn & hệ thống.")

    # Ẩn/Hiện đuôi file
    def show_extensions(self):
        cmd = r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v HideFileExt /t REG_DWORD /d 0 /f'
        ok, out = run_cmd(cmd)
        if ok:
            messagebox.showinfo("Thành công", "Đã bật hiển thị đuôi mở rộng của tệp.")
        else:
            messagebox.showerror("Lỗi", out)

    def hide_extensions(self):
        cmd = r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v HideFileExt /t REG_DWORD /d 1 /f'
        ok, out = run_cmd(cmd)
        if ok:
            messagebox.showinfo("Thành công", "Đã ẩn đuôi mở rộng của tệp.")
        else:
            messagebox.showerror("Lỗi", out)

    # Bật/Tắt Windows Update → mở module on_off_win.py nếu có, nếu không thì fallback
    def toggle_windows_update(self):
        try:
            m = importlib.import_module("on_off_win")  # module đề nghị: on_off_win.py
            if hasattr(m, "authorize"): m.authorize(self.auth_token or "")
            if hasattr(m, "open_window"): m.open_window(self); return
        except Exception:
            pass

        ans = messagebox.askyesno("Bật/Tắt Windows Update",
                                  "Không tìm thấy module on_off_win.py.\n"
                                  "Bạn có muốn TẮT Windows Update tạm thời không?\n"
                                  "(Stop wuauserv + bits)")
        if ans:
            cmds = [
                r'net stop wuauserv',
                r'net stop bits',
                r'reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoUpdate /t REG_DWORD /d 1 /f'
            ]
            ok = self._run_many(cmds, admin=True)
            if ok: messagebox.showinfo("Xong", "Đã tắt tạm thời Windows Update.")
        else:
            ans2 = messagebox.askyesno("Bật Update", "Bật lại Windows Update?")
            if ans2:
                cmds = [
                    r'reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoUpdate /t REG_DWORD /d 0 /f',
                    r'net start wuauserv',
                    r'net start bits'
                ]
                ok = self._run_many(cmds, admin=True)
                if ok: messagebox.showinfo("Xong", "Đã bật lại Windows Update.")

    # Tắt BitLocker ổ hệ thống
    def turn_off_bitlocker(self):
        if not messagebox.askyesno("Tắt BitLocker", "Giải mã BitLocker cho ổ C:? (cần quyền Admin)"):
            return
        ps = 'Start-Process powershell -Verb runAs -ArgumentList "manage-bde -off C:"'
        ok, out = run_cmd(f'powershell -NoProfile -Command "{ps}"')
        if ok:
            messagebox.showinfo("Đã thực thi", "Đã gửi lệnh tắt BitLocker. Quá trình giải mã sẽ chạy nền.")
        else:
            messagebox.showerror("Lỗi", out)

    # --------- helpers ----------
    def _run_many(self, cmds, admin=False) -> bool:
        if admin:
            ps_body = "; ".join([c.replace('"', '\\"') for c in cmds])
            ps = f'Start-Process powershell -Verb runAs -ArgumentList \\"-NoProfile -Command {ps_body}\\"'
            ok, out = run_cmd(f'powershell -NoProfile -Command "{ps}"')
            if not ok: messagebox.showerror("Lỗi", out)
            return ok
        else:
            for c in cmds:
                ok, out = run_cmd(c)
                if not ok:
                    messagebox.showerror("Lỗi", f"Lệnh thất bại:\n{c}\n\n{out}")
                    return False
            return True

# ======================= ENTRY =======================
if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
