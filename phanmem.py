# phanmem.py — Trình cài đặt phần mềm (mở qua main.py)
import os
import sys
import queue
import shutil
import threading
import subprocess
import urllib.request
import zipfile
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, PhotoImage

# ===== Resource helper (hỗ trợ PyInstaller --onefile) =====
def res_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, *parts)

# ===== Optional Pillow để resize icon 20x20 =====
try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

def load_icon_png(name, size=(20, 20)):
    path = res_path("img", name)
    if not os.path.exists(path):
        return None
    try:
        if HAVE_PIL:
            img = Image.open(path).convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        return PhotoImage(file=path)
    except Exception:
        return None

# ===== Footer & link helpers =====
def open_link(url: str):
    if sys.platform == "win32":
        os.startfile(url)
    else:
        subprocess.Popen(["xdg-open", url])

def add_footer(window: tk.Misc):
    sep = ttk.Separator(window)
    sep.pack(side="bottom", fill="x", pady=(8, 0))
    box = ttk.Frame(window)
    box.pack(side="bottom", fill="x", pady=(4, 6))
    ttk.Label(
        box, text="Tiện ích này được phát triển bởi Trần Hà",
        foreground="grey", anchor="center"
    ).pack(fill="x")
    link = ttk.Label(
        box, text="Liên Hệ: facebook.com/DomBM.Rika/",
        foreground="blue", cursor="hand2", anchor="center"
    )
    link.pack(fill="x")
    link.bind("<Button-1>", lambda e: open_link("https://www.facebook.com/DomBM.Rika/"))

# ===== Auth token (nhận từ main.py) =====
_AUTH_TOKEN = None
def authorize(token: str):
    """Được main.py cấp quyền sau khi đăng nhập."""
    global _AUTH_TOKEN
    _AUTH_TOKEN = token

# ===== Liên kết gói font theo yêu cầu =====
CHINESE_FONT_ZIP_URL = "https://archive.org/download/font-tieng-trung-dac-biet-rika/Font-tieng-trung-dac-biet-rika.zip"
VNI_FONT_ZIP_URL     = "https://archive.org/download/vni-full-rika/VNI-Full-Rika.zip"

# ===== Danh sách app và mã gói winget =====
APPS = [
    {"label": "UniKey",        "winget_id": "UniKey.UniKey",                      "icon": "unikey.png"},
    {"label": "Google Chrome", "winget_id": "Google.Chrome",                      "icon": "chrome.png"},
    {"label": "EVKey",         "winget_id": "lamquangminh.EVKey",                 "icon": "evkey.png"},
    {"label": "UltraViewer",   "winget_id": "UltraViewer.UltraViewer",            "icon": "ultraviewer.png"},

    # Nút Font -> bật popup chọn "Tiếng Trung" hoặc "VNI Time"
    {"label": "Font chữ",      "special":   "fonts",                              "icon": "font.png"},

    {"label": "Zalo PC",       "winget_id": "VNG.Zalo",                           "icon": "zalo.png"},   # nếu sai, thử VNGCorp.Zalo
    {"label": "Foxit Reader",  "winget_id": "Foxit.FoxitReader",                  "icon": "foxit.png"},
    {"label": "K-Lite Codec",  "winget_id": "CodecGuide.K-LiteCodecPack.Full",    "icon": "klite.png"},
    {"label": "WinRAR",
     "winget_id": "RARLab.WinRAR",
     "icon": "winrar.png",
     "key_url": "https://raw.githubusercontent.com/admrdom/SoftDao/refs/heads/main/rarreg.key"},
    {"label": "Full Visual C++", "special":  "vcredist",                          "icon": "vcredist.png"},
    {"label": ".NET 3.5",      "special":   "dotnet35",                           "icon": "dotnet35.png"},
    {"label": ".NET 4.8",      "winget_id": "Microsoft.DotNet.Framework.DeveloperPack_4.8",
                                                                             "icon": "dotnet48.png"},
]

FALLBACK_ICON = "icon.png"  # icon mặc định khi không có icon riêng

# ===== Worker cài đặt qua winget/đặc thù =====
class InstallWorker(threading.Thread):
    def __init__(self, app_spec, q_status):
        super().__init__(daemon=True)
        self.app = app_spec
        self.q = q_status

    def report(self, msg, color="blue", done=False):
        self.q.put((msg, color, done))

    def run_cmd(self, cmd):
        try:
            subprocess.run(cmd, shell=True, check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            return True, None
        except subprocess.CalledProcessError as e:
            return False, str(e)

    def run(self):
        name = self.app["label"]
        self.report(f"Đang cài: {name} ...", "orange")

        # kiểm tra winget với các app thường
        need_winget = self.app.get("winget_id") or self.app.get("special") in {"vcredist"}
        if need_winget and shutil.which("winget") is None:
            self.report("Thiếu winget. Cài App Installer từ Microsoft Store rồi thử lại.", "red", True)
            return

        special = self.app.get("special")

        # ===== Fonts ZIP theo lựa chọn popup =====
        if special == "fonts_zip":
            url = self.app.get("zip_url")
            pack_name = self.app.get("pack_name", "Fonts")
            ok, msg = self.install_fonts_from_zip(url)
            if ok:
                self.report(f"✅ Đã cài {pack_name}.", "green", True)
            else:
                self.report(f"❌ Lỗi cài {pack_name}: {msg}", "red", True)
            return

        # ===== Fonts local folder (nếu bạn vẫn để thư mục fonts/) =====
        if special == "fonts":
            # Không cài trực tiếp ở thread này; phần popup chọn gói đã xử lý ở UI
            # Nếu tới đây tức là UI không bơm thông số -> báo và dừng
            self.report("Vui lòng chọn gói font trong popup.", "grey", True)
            return

        # ===== Visual C++ =====
        if special == "vcredist":
            self.install_vcredist(); return

        # ===== .NET 3.5 =====
        if special == "dotnet35":
            self.install_dotnet35(); return

        # ===== Cài qua winget =====
        winget_id = self.app.get("winget_id")
        if winget_id:
            cmd = f'winget install -e --id "{winget_id}" --silent --accept-package-agreements --accept-source-agreements'
            ok, err = self.run_cmd(cmd)
            if ok:
                # Hậu cài đặt WinRAR: chép key (nếu có key_url)
                if self.app.get("key_url") and "winrar" in name.lower():
                    self.report("Đang kích hoạt WinRAR...", "orange")
                    ok2, info = self.install_winrar_key(self.app["key_url"])
                    if ok2:
                        self.report(f"✅ Hoàn tất: WinRAR đã kích hoạt (đã chép key vào: {info})", "green", True)
                    else:
                        self.report(f"⚠️ Cài xong WinRAR nhưng chưa đặt được key: {info}", "orange", True)
                else:
                    self.report(f"✅ Hoàn tất: {name}", "green", True)
            else:
                self.report(f"❌ Lỗi cài {name}: {err}", "red", True)
        else:
            self.report("Không có cấu hình cài đặt cho app này.", "red", True)

    # --- Cài Fonts từ ZIP URL ---
    def install_fonts_from_zip(self, url: str):
        if not url:
            return False, "Thiếu URL ZIP."
        try:
            self.report("🔽 Đang tải gói font...", "orange")
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
        except Exception as e:
            return False, f"Tải ZIP lỗi: {e}"

        # Lưu tạm & giải nén
        try:
            tmp_dir = tempfile.mkdtemp(prefix="fonts_")
            zip_path = os.path.join(tmp_dir, "fonts.zip")
            with open(zip_path, "wb") as f:
                f.write(data)
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(tmp_dir)
        except Exception as e:
            return False, f"Giải nén lỗi: {e}"

        # Copy .ttf/.otf vào Windows\Fonts
        win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        if not os.path.isdir(win_fonts):
            return False, "Không tìm thấy thư mục Fonts của Windows."

        copied = 0
        for root, _, files in os.walk(tmp_dir):
            for fn in files:
                if fn.lower().endswith((".ttf", ".otf")):
                    src = os.path.join(root, fn)
                    dst = os.path.join(win_fonts, fn)
                    try:
                        shutil.copy2(src, dst)
                        copied += 1
                    except Exception:
                        pass

        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

        if copied == 0:
            return False, "ZIP không chứa file .ttf/.otf phù hợp."
        return True, None

    # --- Cài các gói Visual C++ phổ biến ---
    def install_vcredist(self):
        packages = [
            "Microsoft.VCRedist.2015+.x64",
            "Microsoft.VCRedist.2015+.x86",
            "Microsoft.VCRedist.2013.x64",
            "Microsoft.VCRedist.2013.x86",
            "Microsoft.VCRedist.2012.x64",
            "Microsoft.VCRedist.2012.x86",
            "Microsoft.VCRedist.2010.x64",
            "Microsoft.VCRedist.2010.x86",
        ]
        failed = []
        for pid in packages:
            self.report(f"Cài {pid} ...")
            cmd = f'winget install -e --id "{pid}" --silent --accept-package-agreements --accept-source-agreements'
            ok, err = self.run_cmd(cmd)
            if not ok:
                failed.append(pid)
        if failed:
            self.report("Một số gói VC++ cài không thành công:\n" + "\n".join(failed), "red", True)
        else:
            self.report("✅ Hoàn tất Full Visual C++", "green", True)

    # --- Bật .NET Framework 3.5 (DISM) ---
    def install_dotnet35(self):
        cmd = r'DISM /Online /Enable-Feature /FeatureName:NetFx3 /All /NoRestart'
        ok, err = self.run_cmd(cmd)
        if ok:
            self.report("✅ Đã bật .NET Framework 3.5", "green", True)
        else:
            self.report(f"❌ Lỗi bật .NET 3.5: {err}", "red", True)

    # --- Chép key WinRAR ---
    def install_winrar_key(self, url):
        try:
            data = urllib.request.urlopen(url, timeout=20).read()
        except Exception as e:
            return False, f"Tải key lỗi: {e}"

        targets = []
        pf  = os.environ.get("ProgramFiles")
        pf86 = os.environ.get("ProgramFiles(x86)")
        if pf:   targets.append(os.path.join(pf,  "WinRAR"))
        if pf86: targets.append(os.path.join(pf86, "WinRAR"))
        appdata = os.environ.get("APPDATA")
        if appdata:
            user_dir = os.path.join(appdata, "WinRAR")
            os.makedirs(user_dir, exist_ok=True)
            targets.append(user_dir)

        last_err = None
        for d in targets:
            if not os.path.isdir(d):
                continue
            try:
                with open(os.path.join(d, "rarreg.key"), "wb") as f:
                    f.write(data)
                return True, d
            except Exception as e:
                last_err = e
                continue
        return False, f"Không ghi được key (lỗi: {last_err})"

# ===== UI chính =====
class PhanMemApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Trình cài đặt phần mềm")
        self.geometry("420x500")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

        self.q = queue.Queue()
        self.buttons = []
        self.icons = {}
        self._build_ui()
        self._pump()

    # ---- Popup chọn gói font ----
    def choose_font_pack(self):
        win = tk.Toplevel(self)
        win.title("Chọn gói Font"); win.resizable(False, False)
        win.transient(self); win.grab_set()

        ttk.Label(win, text="Chọn gói font cần cài:", font=("Segoe UI", 10, "bold")).pack(padx=12, pady=(12, 8))
        ttk.Label(win, text="• Font Tiếng Trung\n• Font VNI Time").pack(padx=12, pady=(0, 8))

        choice = {"name": None, "url": None}

        def pick_cn():
            choice["name"] = "Font Tiếng Trung"
            choice["url"] = CHINESE_FONT_ZIP_URL
            win.destroy()

        def pick_vni():
            choice["name"] = "Font VNI Time"
            choice["url"] = VNI_FONT_ZIP_URL
            win.destroy()

        btns = ttk.Frame(win); btns.pack(padx=12, pady=(6, 12), fill="x")
        ttk.Button(btns, text="Cài Font Tiếng Trung", command=pick_cn).pack(side="left", expand=True, fill="x", padx=(0,6))
        ttk.Button(btns, text="Cài Font VNI Time", command=pick_vni).pack(side="left", expand=True, fill="x", padx=(6,0))

        # Căn giữa
        win.update_idletasks()
        ww, wh = win.winfo_width(), win.winfo_height()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")

        self.wait_window(win)
        if choice["name"] and choice["url"]:
            return choice["name"], choice["url"]
        return None, None

    def _build_ui(self):
        header = ttk.Label(self, text="🧰  Chọn phần mềm cần cài", foreground="red", font=("Segoe UI", 12, "bold"))
        header.pack(anchor="w", padx=10, pady=(8, 6))

        grid = ttk.Frame(self)
        grid.pack(fill="both", expand=True, padx=8, pady=4)

        def icon_for(app):
            fn = app.get("icon") or FALLBACK_ICON
            if fn not in self.icons:
                self.icons[fn] = load_icon_png(fn, (20, 20)) or load_icon_png(FALLBACK_ICON, (20, 20))
            return self.icons[fn]

        cols = 2  # đổi 3/4 nếu muốn nhiều cột hơn
        for i, app in enumerate(APPS):
            r, c = divmod(i, cols)

            # Đặc biệt cho nút Font: gắn handler để bật popup chọn gói
            if app.get("special") == "fonts":
                def make_cmd_font():
                    def _cmd():
                        name, url = self.choose_font_pack()
                        if not url:
                            return
                        spec = {
                            "label": name,
                            "special": "fonts_zip",
                            "zip_url": url,
                            "icon": app.get("icon") or FALLBACK_ICON,
                        }
                        self.start_install(spec)
                    return _cmd
                cmd = make_cmd_font()
            else:
                cmd = (lambda spec=app: self.start_install(spec))

            btn = ttk.Button(
                grid,
                text=" " + app["label"],
                image=icon_for(app),
                compound="left",
                command=cmd
            )
            btn.grid(row=r, column=c, padx=6, pady=6, sticky="ew")
            self.buttons.append(btn)

        for c in range(cols):
            grid.columnconfigure(c, weight=1)

        self.status = ttk.Label(self, text="Trạng thái: Sẵn sàng cài đặt", foreground="green")
        self.status.pack(anchor="w", padx=10, pady=(6, 6))

        add_footer(self)

    def start_install(self, app_spec):
        if (app_spec.get("winget_id") or app_spec.get("special") in {"vcredist"}) and shutil.which("winget") is None:
            if messagebox.askyesno("Thiếu winget", "Máy chưa có winget (App Installer). Mở trang cài đặt Microsoft Store?"):
                open_link("https://apps.microsoft.com/detail/9nblggh4nns1")
            return
        self.set_enabled(False)
        worker = InstallWorker(app_spec, self.q)
        worker.start()

    def _pump(self):
        try:
            msg, color, done = self.q.get_nowait()
            self.status.config(text=f"Trạng thái: {msg}", foreground=color)
            if done:
                self.set_enabled(True)
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for b in self.buttons:
            b.config(state=state)

# ===== API cho main.py =====
def open_window(root):
    if not _AUTH_TOKEN:
        tk.Tk().withdraw()
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    PhanMemApp(root)

# ===== Chặn chạy trực tiếp =====
if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy ứng dụng từ main.py.")
