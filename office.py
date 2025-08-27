# office.py — Module Cài đặt Office (giữ nguyên giao diện gốc và cải tiến logic nền)
import os
import sys
import time
import queue
import shutil
import threading
import subprocess
import requests
import tkinter as tk
from tkinter import ttk, messagebox, PhotoImage

# ===== Resource helper (PyInstaller) =====
def res_path(*parts):
    """Lấy đường dẫn tài nguyên an toàn cho cả môi trường dev và PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, *parts)

# ===== Optional Pillow cho icon 20x20 =====
try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

def load_icon_png(name, size=(20, 20)):
    """Tải icon từ thư mục img."""
    path = res_path("img", name)
    if not os.path.exists(path):
        return None
    try:
        if HAVE_PIL:
            img = Image.open(path).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        return PhotoImage(file=path)
    except Exception:
        return None

# ===== Footer & link helpers =====
def open_link(url: str):
    """Mở một URL trong trình duyệt mặc định."""
    if sys.platform == "win32":
        os.startfile(url)
    else:
        subprocess.Popen(["xdg-open", url])

def add_footer(window: tk.Misc):
    """Thêm footer vào cuối cửa sổ."""
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
    """Hàm này phải được gọi từ main.py để cho phép mở cửa sổ."""
    global _AUTH_TOKEN
    _AUTH_TOKEN = token

# ===== Cấu hình & Hằng số =====
APP_PAGE_TITLE = "Cài đặt Office"
ODT_DOWNLOAD_URL = "https://download.microsoft.com/download/2/7/A/27AF1BE6-DD20-4CB4-B154-EBAB8A7D4A7E/officedeploymenttool_16731-20358.exe"
ACTIVATION_SCRIPT_URL = "https://raw.githubusercontent.com/massgravel/Microsoft-Activation-Scripts/master/MAS/Separate-Files-Version/Activators/Ohook_Activation_AIO.cmd"

TEMP_DIR = os.environ.get("TEMP", ".")
ODT_EXTRACTOR_PATH = os.path.join(TEMP_DIR, "officedeploymenttool.exe")
ODT_SETUP_PATH     = os.path.join(TEMP_DIR, "setup.exe")
CONFIG_FILE_PATH   = os.path.join(TEMP_DIR, "config.xml")

OFFICE_APPS = ["Access", "Excel", "Word", "PowerPoint", "Outlook", "Publisher", "OneNote", "Teams"]
LANGUAGES = {"English (Mỹ)": "en-us", "Vietnamese (Việt Nam)": "vi-vn", "Chinese (Trung Quốc)": "zh-cn"}

# ===== UI chính =====
class OfficeInstallerApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(APP_PAGE_TITLE)
        self.geometry("620x470")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except tk.TclError: pass

        self.icons = {}
        self._load_icons()

        self.version_var  = tk.StringVar(value="2021")
        self.lang_var     = tk.StringVar(value="Vietnamese (Việt Nam)")
        self.bitness_var  = tk.StringVar(value="64-bit")
        self.app_vars     = {app: tk.BooleanVar(value=True) for app in OFFICE_APPS}
        self.project_var  = tk.BooleanVar(value=False)
        self.visio_var    = tk.BooleanVar(value=False)
        self.is_all_selected = True

        self.q = queue.Queue()
        self.action_buttons = []

        self._build_ui()
        self._pump_queue()

    def _load_icons(self):
        for name in ["install", "activate", "language", "shortcut", "select_all", "download"]:
            self.icons[name] = load_icon_png(f"{name}.png")

    def _build_ui(self):
        main = ttk.Frame(self, padding="10")
        main.pack(fill="both", expand=True)
        self._version_group(main)
        self._options_group(main)
        self._apps_group(main)
        self._action_buttons(main)
        self._status_area(main)
        add_footer(self)

    def _version_group(self, parent):
        f = ttk.LabelFrame(parent, text="Chọn phiên bản Office", padding="10")
        f.pack(fill="x", pady=5)
        versions = [("Office 2016", "2016"), ("Office 2019", "2019"), ("Office 2021", "2021"), ("Office 365", "365")]
        for text, val in versions:
            ttk.Radiobutton(f, text=text, variable=self.version_var, value=val).pack(side="left", padx=5)

    def _options_group(self, parent):
        f = ttk.LabelFrame(parent, text="Tùy chọn", padding="10")
        f.pack(fill="x", pady=5)
        ttk.Label(f, text="Ngôn ngữ:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Combobox(f, textvariable=self.lang_var, values=list(LANGUAGES.keys()), state="readonly").grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(f, text="Cấu trúc:").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Combobox(f, textvariable=self.bitness_var, values=["64-bit", "32-bit"], state="readonly", width=7).grid(row=0, column=3, sticky="w", padx=5)
        f.columnconfigure(1, weight=1)
        
        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=(10, 0))
        ttk.Button(btn_frame, text=" Chọn tất cả", image=self.icons.get("select_all"),
                   compound="left", command=self._toggle_all).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=" Tải tùy chọn", image=self.icons.get("download"),
                   compound="left", command=lambda: self._start("download")).pack(side="left", padx=5)


    def _apps_group(self, parent):
        area = ttk.Frame(parent)
        area.pack(fill="x", pady=5)
        apps = ttk.LabelFrame(area, text="Chọn ứng dụng cần cài", padding="10")
        apps.pack(side="left", fill="both", expand=True, padx=(0, 5))
        col1, col2 = ttk.Frame(apps), ttk.Frame(apps)
        col1.pack(side="left", padx=10); col2.pack(side="left", padx=10)
        for i, app in enumerate(OFFICE_APPS):
            target = col1 if i < len(OFFICE_APPS)/2 else col2
            ttk.Checkbutton(target, text=app, variable=self.app_vars[app]).pack(anchor="w")
        prod = ttk.LabelFrame(area, text="Sản phẩm riêng", padding="10")
        prod.pack(side="left", fill="both")
        ttk.Checkbutton(prod, text="Project", variable=self.project_var).pack(anchor="w")
        ttk.Checkbutton(prod, text="Visio", variable=self.visio_var).pack(anchor="w")

    def _action_buttons(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=10)
        
        def placeholder_command():
            messagebox.showinfo("Thông báo", "Tính năng đang được phát triển.")

        actions = [
            (" Cài đặt", "install", lambda: self._start("configure")),
            (" Kích hoạt", "activate", lambda: self._start("activate")),
            (" Cài Ngôn Ngữ", "language", placeholder_command), # Cập nhật ở đây
            (" Tạo shortcut", "shortcut", lambda: self._start("shortcut"))
        ]
        for text, icon, cmd in actions:
            btn = ttk.Button(f, text=text, image=self.icons.get(icon), compound="left", command=cmd)
            btn.pack(side="left", padx=5, expand=True, fill="x")
            self.action_buttons.append(btn)

    def _status_area(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=(0, 5))
        self.status = ttk.Label(f, text="Trạng thái: Sẵn sàng.", foreground="green")
        self.status.pack(fill="x")

    def _build_config(self, lang_only=False):
        products = {
            "2021": {"ID": "ProPlus2021Volume", "Channel": "PerpetualVL2021"},
            "2019": {"ID": "ProPlus2019Volume", "Channel": "PerpetualVL2019"},
            "2016": {"ID": "ProPlusVolume", "Channel": "PerpetualVL2019"},
            "365": {"ID": "O365ProPlusRetail", "Channel": "Monthly"}
        }
        ver_info = products.get(self.version_var.get())
        bit = self.bitness_var.get().split("-")[0]
        lang = LANGUAGES.get(self.lang_var.get(), "en-us")
        xml = f'<Configuration><Add OfficeClientEdition="{bit}" Channel="{ver_info["Channel"]}">'
        if lang_only:
            xml += f'<Product ID="LanguagePack"><Language ID="{lang}" /></Product>'
        else:
            excluded = "".join(f'<ExcludeApp ID="{app}" />' for app, var in self.app_vars.items() if not var.get())
            xml += f'<Product ID="{ver_info["ID"]}"><Language ID="{lang}" />{excluded}</Product>'
            if self.project_var.get(): xml += f'<Product ID="ProjectProRetail"><Language ID="{lang}" /></Product>'
            if self.visio_var.get(): xml += f'<Product ID="VisioProRetail"><Language ID="{lang}" /></Product>'
        xml += '</Add><Display Level="Full" AcceptEULA="TRUE" /></Configuration>'
        return xml
        
    def _toggle_all(self):
        self.is_all_selected = not self.is_all_selected
        for v in self.app_vars.values():
            v.set(self.is_all_selected)
        self.project_var.set(self.is_all_selected)
        self.visio_var.set(self.is_all_selected)

    def _start(self, task):
        self._set_enabled(False)
        worker = None
        if task in ("configure", "download"):
            worker = OdtWorker(task, self._build_config(), self.q)
        elif task == "install_lang":
            worker = OdtWorker("configure", self._build_config(lang_only=True), self.q)
        elif task == "activate":
            worker = ActivationWorker(self.q)
        elif task == "shortcut":
            selected_apps = [name for name, var in self.app_vars.items() if var.get()]
            if self.project_var.get(): selected_apps.append("Project")
            if self.visio_var.get(): selected_apps.append("Visio")
            worker = ShortcutWorker(self.q, selected_apps)
        
        if worker:
            threading.Thread(target=worker.run, daemon=True).start()
        else:
            self._set_enabled(True)

    def _pump_queue(self):
        try:
            msg, color, done, popup = self.q.get_nowait()
            self.status.config(text=f"Trạng thái: {msg}", foreground=color)
            if popup: messagebox.showinfo("Hoàn tất", msg, parent=self)
            if done: self._set_enabled(True)
        except queue.Empty:
            pass
        self.after(100, self._pump_queue)

    def _set_enabled(self, enable: bool):
        state = "normal" if enable else "disabled"
        for b in self.action_buttons: b.config(state=state)

# ===== Workers =====
class BaseWorker:
    def __init__(self, q: queue.Queue): self.q = q
    def report(self, msg, color, done=False, popup=False): self.q.put((msg, color, done, popup))

class OdtWorker(BaseWorker):
    def __init__(self, action, config_xml, q):
        super().__init__(q)
        self.action, self.config_xml = action, config_xml

    def run(self):
        try:
            self.report("📥 Đang tải công cụ ODT...", "blue")
            r = requests.get(ODT_DOWNLOAD_URL, stream=True, timeout=30)
            r.raise_for_status()
            with open(ODT_EXTRACTOR_PATH, "wb") as f: shutil.copyfileobj(r.raw, f)
            self.report("⚙️ Đang giải nén setup.exe...", "blue")
            subprocess.run(f'"{ODT_EXTRACTOR_PATH}" /extract:"{TEMP_DIR}" /quiet /norestart', shell=True, check=True, creationflags=0x08000000)
            if not os.path.exists(ODT_SETUP_PATH): raise FileNotFoundError("Không thể giải nén setup.exe.")
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f: f.write(self.config_xml)
            text = "Cài đặt" if self.action == "configure" else "Tải xuống"
            self.report(f"⏳ Đang {text} Office, vui lòng chờ...", "orange")
            subprocess.run(f'"{ODT_SETUP_PATH}" /{self.action} "{CONFIG_FILE_PATH}"', shell=True, check=True, creationflags=0x08000000)
            self.report(f"✅ Đã {text} xong!", "green", popup=True)
        except Exception as e:
            self.report(f"❌ Lỗi: {e}", "red")
        finally:
            for path in [CONFIG_FILE_PATH, ODT_SETUP_PATH, ODT_EXTRACTOR_PATH]:
                if os.path.exists(path):
                    try: os.remove(path)
                    except OSError: pass
            self.report("Sẵn sàng.", "green", done=True)

class ActivationWorker(BaseWorker):
    def __init__(self, q: queue.Queue):
        super().__init__(q)

    def run(self):
        self.report("Đang tải công cụ kích hoạt...", "blue")
        script_path = os.path.join(TEMP_DIR, "MAS_AIO.cmd")
        try:
            r = requests.get(ACTIVATION_SCRIPT_URL, timeout=30)
            r.raise_for_status()
            
            self.report("Tải thành công. Chuẩn bị chạy...", "blue")
            with open(script_path, "wb") as f:
                f.write(r.content)
            
            self.report("Đang mở cửa sổ kích hoạt. Vui lòng làm theo hướng dẫn...", "orange")
            
            command = f'start "Kich hoat Office" /wait cmd.exe /c ""{script_path}" /Ohook & pause"'
            subprocess.run(command, shell=True, check=True, creationflags=0x08000000)

            self.report("Kích hoạt hoàn tất!", "green", popup=True)
        except requests.exceptions.RequestException as e:
            self.report(f"Lỗi tải công cụ kích hoạt: {e}", "red")
        except subprocess.CalledProcessError:
            self.report("Quá trình kích hoạt bị hủy hoặc có lỗi.", "red")
        except Exception as e:
            self.report(f"Lỗi không xác định: {e}", "red")
        finally:
            if os.path.exists(script_path):
                try: os.remove(script_path)
                except OSError: pass
            self.report("Sẵn sàng.", "green", done=True)

class ShortcutWorker(BaseWorker):
    def __init__(self, q: queue.Queue, selected_apps: list):
        super().__init__(q)
        self.selected_apps = selected_apps

    def run(self):
        if not self.selected_apps:
            self.report("Vui lòng chọn ít nhất một ứng dụng để tạo shortcut.", "orange", done=True)
            return

        self.report("🔍 Đang tìm kiếm shortcut...", "blue")
        start_menu_path = os.path.join(os.environ['PROGRAMDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs')
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        found_count = 0
        
        try:
            if not os.path.exists(start_menu_path):
                self.report(f"❌ Không tìm thấy thư mục Start Menu.", "red", done=True)
                return

            # Quét thư mục Start Menu và các thư mục con
            for root, dirs, files in os.walk(start_menu_path):
                for filename in files:
                    if filename.endswith(".lnk"):
                        if any(app_name.lower() in filename.lower() for app_name in self.selected_apps):
                            source_path = os.path.join(root, filename)
                            dest_path = os.path.join(desktop_path, filename)
                            try:
                                shutil.copy2(source_path, dest_path)
                                found_count += 1
                            except Exception: 
                                pass
            
            if found_count > 0:
                msg = f"✅ Hoàn tất! Đã tạo {found_count} shortcut cho các ứng dụng đã chọn."
                self.report(msg, "green", popup=True)
            else:
                msg = "ℹ️ Không tìm thấy shortcut nào cho các ứng dụng đã chọn."
                self.report(msg, "grey", popup=True)

        except Exception as e:
            self.report(f"❌ Lỗi không xác định: {e}", "red")
        finally:
            self.report("Sẵn sàng.", "green", done=True)

# ===== API cho main.py =====
def open_window(root: tk.Tk):
    """API để main.py gọi. Sẽ kiểm tra token trước khi mở."""
    if not _AUTH_TOKEN:
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở ứng dụng từ file main.py.")
        return
    OfficeInstallerApp(root)

# ===== Chặn chạy trực tiếp =====
if __name__ == "__main__":
    # Ẩn cửa sổ tkinter gốc không cần thiết
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Từ chối truy cập", "Vui lòng chạy ứng dụng từ file main.py.")
