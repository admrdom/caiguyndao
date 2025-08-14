# setup.py — Thiết lập Windows (mở qua main.py)
import os, sys, queue, threading, subprocess, tkinter as tk
from tkinter import ttk, messagebox, PhotoImage

# ===== Resource & icon loader (20x20) =====
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

# ===== Worker thực thi các thiết lập =====
class SetupWorker(threading.Thread):
    def __init__(self, opts, q):
        super().__init__(daemon=True)
        self.o = opts
        self.q = q
        self.restart_needed = False

    def report(self, msg, color="blue", done=False):
        self.q.put((msg, color, done))

    def sh(self, cmd):
        try:
            subprocess.run(cmd, shell=True, check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            return True, None
        except subprocess.CalledProcessError as e:
            return False, str(e)

    def run(self):
        self.report("Bắt đầu áp dụng thiết lập...", "orange")

        # --- Nhóm tùy chọn nhanh ---
        if self.o["tz_gmt7"]:
            ok, err = self.sh(r'tzutil /s "SE Asia Standard Time"')
            self.report("Đặt múi giờ GMT+7" if ok else f"Lỗi đặt múi giờ: {err}",
                        "green" if ok else "red")

        if self.o["disable_notifications"]:
            ok, err = self.sh(r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\PushNotifications" /v ToastEnabled /t REG_DWORD /d 0 /f')
            self.report("Tắt thông báo Windows" if ok else f"Lỗi tắt thông báo: {err}",
                        "green" if ok else "red")

        if self.o["disable_uac"]:
            cmds = [
                r'reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v EnableLUA /t REG_DWORD /d 0 /f',
                r'reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 0 /f',
            ]
            ok = True; last = ""
            for c in cmds:
                ok_i, last = self.sh(c); ok = ok and ok_i
            self.report("Tắt UAC" if ok else f"Lỗi tắt UAC: {last}",
                        "green" if ok else "red")
            if ok: self.restart_needed = True

        if self.o["disable_smartscreen"]:
            cmds = [
                r'reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v EnableSmartScreen /t REG_DWORD /d 0 /f',
                r'reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v ShellSmartScreenLevel /t REG_SZ /d Off /f',
                r'reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" /v SmartScreenEnabled /t REG_SZ /d Off /f',
            ]
            ok = True; last = ""
            for c in cmds:
                ok_i, last = self.sh(c); ok = ok and ok_i
            self.report("Tắt SmartScreen" if ok else f"Lỗi tắt SmartScreen: {last}",
                        "green" if ok else "red")

        if self.o["open_thispc"]:
            ok, err = self.sh(r'reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v LaunchTo /t REG_DWORD /d 1 /f')
            self.report("Mở File Explorer: This PC" if ok else f"Lỗi đặt This PC: {err}",
                        "green" if ok else "red")

        if self.o["disable_secwarn"]:
            cmds = [
                r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Attachments" /v SaveZoneInformation /t REG_DWORD /d 2 /f',
                r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\Associations" /v LowRiskFileTypes /t REG_SZ /d ".exe;.bat;.reg;.vbs;.ps1;.msi;.cmd;" /f',
            ]
            ok = True; last = ""
            for c in cmds:
                ok_i, last = self.sh(c); ok = ok and ok_i
            self.report("Tắt Security Warning khi mở file tải về" if ok else f"Lỗi đặt cảnh báo: {last}",
                        "green" if ok else "red")

        if self.o["date_ddmmyyyy"]:
            ok, err = self.sh(r'reg add "HKCU\Control Panel\International" /v sShortDate /t REG_SZ /d dd/MM/yyyy /f')
            self.report("Đặt định dạng ngày dd/MM/yyyy" if ok else f"Lỗi đặt định dạng ngày: {err}",
                        "green" if ok else "red")

        if self.o["disable_bitlocker"]:
            # Thử dùng PowerShell trước
            ps = ('powershell -NoProfile -Command '
                  '"$v=Get-BitLockerVolume -ErrorAction SilentlyContinue; '
                  'if($v){$v | Disable-BitLocker -Confirm:$false; exit 0} '
                  'else{exit 2}"')
            ok, _ = self.sh(ps)
            if not ok:
                # Fallback manage-bde cho tất cả ổ C..Z
                cmd = r'cmd /c for %d in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do manage-bde -off %d:'
                ok2, err2 = self.sh(cmd)
                if ok2:
                    self.report("Đã gửi lệnh tắt BitLocker cho các ổ đĩa (giải mã sẽ chạy nền).", "green")
                else:
                    self.report(f"Lỗi tắt BitLocker: {err2}", "red")
            else:
                self.report("Đã gửi lệnh tắt BitLocker (giải mã sẽ chạy nền).", "green")

        # --- Nâng cao ---
        if self.o["sleep_mins"] is not None:
            m = self.o["sleep_mins"]
            ok1, e1 = self.sh(f'powercfg /change standby-timeout-ac {m}')
            ok2, e2 = self.sh(f'powercfg /change standby-timeout-dc {m}')
            ok = ok1 and ok2; last = e1 or e2
            self.report(f"Đặt Sleep {m} phút" if ok else f"Lỗi đặt Sleep: {last}",
                        "green" if ok else "red")

        if self.o["display_off_mins"] is not None:
            m = self.o["display_off_mins"]
            ok1, e1 = self.sh(f'powercfg /change monitor-timeout-ac {m}')
            ok2, e2 = self.sh(f'powercfg /change monitor-timeout-dc {m}')
            ok = ok1 and ok2; last = e1 or e2
            self.report(f"Tắt màn hình sau {m} phút" if ok else f"Lỗi đặt tắt màn hình: {last}",
                        "green" if ok else "red")

        if self.o["rename_pc"]:
            new = self.o["rename_pc"]
            ok, err = self.sh(f'powershell -NoProfile -Command "Rename-Computer -NewName \'{new}\' -Force -PassThru"')
            self.report(f"Đã đổi tên PC thành {new}" if ok else f"Lỗi đổi tên PC: {err}",
                        "green" if ok else "red")
            if ok: self.restart_needed = True

        if self.o["workgroup"]:
            wg = self.o["workgroup"]
            ok, err = self.sh(f'powershell -NoProfile -Command "Add-Computer -WorkGroupName \'{wg}\' -Force -PassThru"')
            self.report(f"Đã đổi Workgroup thành {wg}" if ok else f"Lỗi Workgroup: {err}",
                        "green" if ok else "red")
            if ok: self.restart_needed = True

        if self.o["rename_user"]:
            newu = self.o["rename_user"]
            ok, err = self.sh(f'powershell -NoProfile -Command "Rename-LocalUser -Name $env:USERNAME -NewName \'{newu}\'"')
            self.report(f"Đã đổi tên User thành {newu}" if ok else f"Lỗi đổi tên User: {err}",
                        "green" if ok else "red")

        if self.restart_needed:
            self.report("Một số thay đổi cần khởi động lại để áp dụng.", "orange")
        self.report("Hoàn tất.", "green", done=True)

# ===== Giao diện =====
class SetupWindowsApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Thiết lập Windows"); self.geometry("520x470"); self.resizable(False, False)
        self.transient(parent); self.grab_set()
        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.q = queue.Queue()
        self._build_ui()
        self._pump()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10); outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="🖥️  Thiết lập Windows", foreground="red",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,6))

        # ---- Tùy chọn nhanh (2 cột x 4 hàng) ----
        quick = ttk.LabelFrame(outer, text="Tùy chọn nhanh", padding=10)
        quick.pack(fill="x", pady=6)

        self.var_tz          = tk.BooleanVar(value=True)
        self.var_notif       = tk.BooleanVar(value=False)
        self.var_uac         = tk.BooleanVar(value=False)
        self.var_smartscreen = tk.BooleanVar(value=False)
        self.var_thispc      = tk.BooleanVar(value=True)
        self.var_secwarn     = tk.BooleanVar(value=False)
        self.var_datefmt     = tk.BooleanVar(value=True)
        self.var_bitlocker   = tk.BooleanVar(value=False)

        items = [
            ("Đặt múi giờ GMT+7",         self.var_tz),
            ("Tắt thông báo Windows",      self.var_notif),
            ("Tắt UAC",                    self.var_uac),
            ("Tắt SmartScreen",            self.var_smartscreen),
            ("Thiết lập mở This PC",       self.var_thispc),
            ("Tắt Security Warning",       self.var_secwarn),
            ("Đặt định dạng ngày dd/MM/yyyy", self.var_datefmt),
            ("Tắt BitLocker",              self.var_bitlocker),
        ]

        # Grid 2 cột cân xứng
        for idx, (txt, var) in enumerate(items):
            r, c = divmod(idx, 2)
            ttk.Checkbutton(quick, text=txt, variable=var).grid(row=r, column=c, sticky="w", padx=6, pady=2)
        quick.columnconfigure(0, weight=1)
        quick.columnconfigure(1, weight=1)

        # ---- Thiết lập nâng cao ----
        adv = ttk.LabelFrame(outer, text="Thiết lập nâng cao", padding=10)
        adv.pack(fill="x", pady=6)

        frm1 = ttk.Frame(adv); frm1.pack(fill="x", pady=2)
        ttk.Label(frm1, text="Sleep (phút):").pack(side="left")
        self.ent_sleep = ttk.Entry(frm1, width=6); self.ent_sleep.pack(side="left", padx=(4,12))
        ttk.Label(frm1, text="Tắt màn hình (phút):").pack(side="left")
        self.ent_disp = ttk.Entry(frm1, width=6); self.ent_disp.pack(side="left", padx=(4,0))

        frm2 = ttk.Frame(adv); frm2.pack(fill="x", pady=2)
        ttk.Label(frm2, text="Đổi tên User:").pack(side="left", padx=(0,6))
        self.ent_user = ttk.Entry(frm2, width=24); self.ent_user.pack(side="left", fill="x", expand=True)

        frm3 = ttk.Frame(adv); frm3.pack(fill="x", pady=2)
        ttk.Label(frm3, text="Đổi tên PC:").pack(side="left", padx=(0,6))
        self.ent_pc = ttk.Entry(frm3, width=24); self.ent_pc.pack(side="left", fill="x", expand=True)

        frm4 = ttk.Frame(adv); frm4.pack(fill="x", pady=2)
        ttk.Label(frm4, text="Đổi tên Workgroup:").pack(side="left", padx=(0,6))
        self.ent_wg = ttk.Entry(frm4, width=24); self.ent_wg.pack(side="left", fill="x", expand=True)

        self.status = ttk.Label(outer, text="Trạng thái: Sẵn sàng.", foreground="green")
        self.status.pack(anchor="w", pady=(4,8))

        ttk.Button(outer, text=" Bắt đầu ", command=self.start).pack()
        add_footer(self)

    def start(self):
        def parse_int(s):
            s = s.strip()
            if not s: return None
            if not s.isdigit(): return None
            return max(0, int(s))

        opts = {
            "tz_gmt7": self.var_tz.get(),
            "disable_notifications": self.var_notif.get(),
            "disable_uac": self.var_uac.get(),
            "disable_smartscreen": self.var_smartscreen.get(),
            "open_thispc": self.var_thispc.get(),
            "disable_secwarn": self.var_secwarn.get(),
            "date_ddmmyyyy": self.var_datefmt.get(),
            "disable_bitlocker": self.var_bitlocker.get(),

            "sleep_mins": parse_int(self.ent_sleep.get()),
            "display_off_mins": parse_int(self.ent_disp.get()),
            "rename_user": self.ent_user.get().strip() or None,
            "rename_pc": self.ent_pc.get().strip() or None,
            "workgroup": self.ent_wg.get().strip() or None,
        }

        if opts["disable_uac"] or opts["disable_smartscreen"] or opts["disable_secwarn"] or opts["disable_bitlocker"]:
            if not messagebox.askyesno("Xác nhận",
                "Một số thiết lập sẽ ảnh hưởng đến bảo mật hệ thống (UAC/SmartScreen/BitLocker).\nBạn có chắc muốn tiếp tục?"):
                return

        self.set_enabled(False)
        SetupWorker(opts, self.q).start()

    def _pump(self):
        try:
            msg, color, done = self.q.get_nowait()
            self.status.config(text=f"Trạng thái: {msg}", foreground=color)
            if done:
                self.set_enabled(True)
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
    SetupWindowsApp(root)

# ===== Block chạy trực tiếp =====
if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy ứng dụng từ main.py.")
