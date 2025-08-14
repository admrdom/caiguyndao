# network.py — Sửa lỗi mạng (mở qua main.py)
import os, sys, queue, threading, subprocess, datetime, tkinter as tk
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

# ===== Worker =====
class NetRepairWorker(threading.Thread):
    def __init__(self, opts, q):
        super().__init__(daemon=True)
        self.o = opts
        self.q = q

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
        self.report("Bắt đầu sửa lỗi...", "orange")

        if self.o["tcpip"]:
            ok, err = self.sh("netsh int ip reset")
            self.report("Reset Internet Protocols (TCP/IP)" if ok else f"Lỗi reset TCP/IP: {err}",
                        "green" if ok else "red")

        if self.o["winsock"]:
            ok, err = self.sh("netsh winsock reset")
            self.report("Repair Winsock" if ok else f"Lỗi Winsock: {err}",
                        "green" if ok else "red")

        if self.o["renew_conn"]:
            cmds = ["ipconfig /release", "ipconfig /renew"]
            ok = True; last = ""
            for c in cmds:
                ok_i, last = self.sh(c); ok = ok and ok_i
            self.report("Renew Internet Connections" if ok else f"Lỗi renew: {last}",
                        "green" if ok else "red")

        if self.o["flush_dns"]:
            ok, err = self.sh("ipconfig /flushdns")
            self.report("Flush DNS Resolver Cache" if ok else f"Lỗi flush DNS: {err}",
                        "green" if ok else "red")

        if self.o["flush_arp"]:
            ok, err = self.sh('arp -d *')
            self.report("Flush ARP Cache" if ok else f"Lỗi flush ARP: {err}",
                        "green" if ok else "red")

        if self.o["repair_ie"]:
            # Có thể không còn IE11, cứ thử và bỏ qua lỗi
            ok, _ = self.sh(r'rundll32.exe inetcpl.cpl,ResetIEtoDefaults')
            self.report("Repair Internet Explorer 11" if ok else "IE11 không khả dụng / bỏ qua", "grey" if not ok else "green")

        if self.o["clear_wu_history"]:
            ok = True; last = ""
            cmds = [
                "net stop wuauserv", "net stop bits", "net stop cryptsvc",
                r'cmd /c del /f /q "%WINDIR%\SoftwareDistribution\*.*" /s',
                r'cmd /c del /f /q "%WINDIR%\Logs\WindowsUpdate\*.*" /s',
                "net start cryptsvc", "net start bits", "net start wuauserv",
            ]
            for c in cmds:
                ok_i, last = self.sh(c); ok = ok and ok_i
            self.report("Clear Windows Update History" if ok else f"Lỗi clear WU history: {last}",
                        "green" if ok else "red")

        if self.o["repair_wu"]:
            ok = True; last = ""
            cmds = [
                "net stop wuauserv", "net stop bits", "net stop cryptsvc", "net stop msiserver",
                r'ren "%WINDIR%\SoftwareDistribution" "SoftwareDistribution.old"',
                r'ren "%WINDIR%\System32\catroot2" "catroot2.old"',
                "net start msiserver", "net start cryptsvc", "net start bits", "net start wuauserv",
            ]
            for c in cmds:
                ok_i, last = self.sh(c); ok = ok and ok_i
            self.report("Repair Windows / Automatic Updates" if ok else f"Lỗi repair Windows Update: {last}",
                        "green" if ok else "red")

        if self.o["repair_ssl"]:
            ok = True; last = ""
            cmds = [
                'certutil -urlcache * delete',
                'netsh winhttp reset proxy',
            ]
            for c in cmds:
                ok_i, last = self.sh(c); ok = ok and ok_i
            self.report("Repair SSL / HTTPS / Cryptography" if ok else f"Lỗi repair SSL: {last}",
                        "green" if ok else "red")

        if self.o["reset_proxy"]:
            ok = True; last = ""
            cmds = [
                'netsh winhttp reset proxy',
                r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f',
                r'reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /f',
            ]
            for c in cmds:
                ok_i, last = self.sh(c); ok = ok and ok_i
            self.report("Reset Proxy Server Configuration" if ok else f"Lỗi reset proxy: {last}",
                        "green" if ok else "red")

        if self.o["reset_firewall"]:
            ok, err = self.sh("netsh advfirewall reset")
            self.report("Reset Windows Firewall Configuration" if ok else f"Lỗi reset firewall: {err}",
                        "green" if ok else "red")

        if self.o["restore_hosts"]:
            try:
                etc = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "drivers", "etc")
                hosts = os.path.join(etc, "hosts")
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                if os.path.exists(hosts):
                    try: os.replace(hosts, hosts + f".bak_{ts}")
                    except: pass
                content = (
                    "# Default Microsoft Hosts\n"
                    "127.0.0.1 localhost\n"
                    "::1 localhost\n"
                )
                with open(hosts, "w", encoding="utf-8") as f:
                    f.write(content)
                self.report("Restore the default hosts file", "green")
            except Exception as e:
                self.report(f"Lỗi khôi phục hosts: {e}", "red")

        if self.o["renew_wins"]:
            ok = True; last = ""
            for c in ["nbtstat -RR", "ipconfig /registerdns"]:
                ok_i, last = self.sh(c); ok = ok and ok_i
            self.report("Renew Wins Client Registrations" if ok else f"Lỗi renew WINS: {last}",
                        "green" if ok else "red")

        if self.o["network_visible"]:
            ps = ('powershell -NoProfile -Command '
                  '"Set-NetFirewallRule -Group \\"Network Discovery\\" -Enabled True -Profile Any; '
                  'Start-Service fdrespub -ErrorAction SilentlyContinue; '
                  'Start-Service upnphost -ErrorAction SilentlyContinue; '
                  'Start-Service SSDPSRV -ErrorAction SilentlyContinue"')
            ok, err = self.sh(ps)
            self.report("Make Network Computers Visible in File Explorer" if ok else f"Lỗi bật Network Discovery: {err}",
                        "green" if ok else "red")

        self.report("Hoàn tất.", "green", done=True)

# ===== UI =====
class NetRepairApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Sửa Lỗi Mạng"); self.geometry("560x520"); self.resizable(False, False)
        self.transient(parent); self.grab_set()
        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.q = queue.Queue()
        self.vars = {}
        self._build_ui()
        self._pump()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10); outer.pack(fill="both", expand=True)

        header = ttk.Label(outer, text="🌐  Sửa Lỗi Mạng", foreground="red", font=("Segoe UI", 12, "bold"))
        header.pack(anchor="w", pady=(0,8))

        # Nút chọn tất cả / bỏ chọn
        selbar = ttk.Frame(outer); selbar.pack(fill="x", pady=(0,6))
        self.select_all_state = tk.BooleanVar(value=True)
        ttk.Checkbutton(selbar, text="Chọn tất cả", variable=self.select_all_state, command=self.toggle_all)\
            .pack(side="left")

        # Danh sách tùy chọn (2 cột)
        box = ttk.LabelFrame(outer, text="Tùy chọn sửa chữa", padding=10)
        box.pack(fill="x", pady=4)

        items = [
            ("Reset Internet Protocols (TCP/IP)",      "tcpip",           True),
            ("Repair Winsock (Reset Catalog)",         "winsock",         True),
            ("Renew Internet Connections",             "renew_conn",      True),
            ("Flush DNS Resolver Cache",               "flush_dns",       True),
            ("Flush ARP Cache (Address Resolution)",   "flush_arp",       False),
            ("Repair Internet Explorer 11",            "repair_ie",       False),
            ("Clear Windows Update History",           "clear_wu_history",False),
            ("Repair Windows / Automatic Updates",     "repair_wu",       False),
            ("Repair SSL / HTTPS / Cryptography",      "repair_ssl",      True),
            ("Reset Proxy Server Configuration",       "reset_proxy",     True),
            ("Reset Windows Firewall Configuration",   "reset_firewall",  False),
            ("Restore the default hosts file",         "restore_hosts",   True),
            ("Renew Wins Client Registrations",        "renew_wins",      False),
            ("Make Network Computers Visible in Explorer", "network_visible", True),
        ]

        for idx, (label, key, default) in enumerate(items):
            self.vars[key] = tk.BooleanVar(value=default)
            r, c = divmod(idx, 2)
            ttk.Checkbutton(box, text=label, variable=self.vars[key])\
                .grid(row=r, column=c, sticky="w", padx=6, pady=3)
        box.columnconfigure(0, weight=1)
        box.columnconfigure(1, weight=1)

        self.status = ttk.Label(outer, text="Trạng thái: Sẵn sàng.", foreground="green")
        self.status.pack(anchor="w", pady=(8,10))

        ttk.Button(outer, text=" Go! ", command=self.start).pack()
        add_footer(self)

    def toggle_all(self):
        val = self.select_all_state.get()
        for v in self.vars.values():
            v.set(val)

    def start(self):
        opts = {k: v.get() for k, v in self.vars.items()}
        if not any(opts.values()):
            messagebox.showinfo("Thông báo", "Hãy chọn ít nhất một tùy chọn.")
            return
        if opts.get("reset_firewall"):
            if not messagebox.askyesno("Xác nhận", "Reset tường lửa sẽ khôi phục cấu hình về mặc định. Tiếp tục?"):
                return
        self.set_enabled(False)
        NetRepairWorker(opts, self.q).start()

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
    NetRepairApp(root)

# ===== Block chạy trực tiếp =====
if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy ứng dụng từ main.py.")
