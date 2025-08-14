# office.py — Module Cài đặt Office (mở qua main.py)
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
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, *parts)

# ===== Optional Pillow cho icon 20x20 =====
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
    global _AUTH_TOKEN
    _AUTH_TOKEN = token

# ===== Cấu hình & Hằng số =====
APP_PAGE_TITLE = "Cài đặt Office"
ODT_DOWNLOAD_URL = (
    "https://download.microsoft.com/download/"
    "6c1eeb25-cf8b-41d9-8d0d-cc1dbc032140/officedeploymenttool_18925-20138.exe"
)
ACTIVATION_SCRIPT_URL = (
    "https://raw.githubusercontent.com/massgravel/Microsoft-Activation-Scripts/"
    "master/MAS/Separate-Files-Version/Activators/Ohook_Activation_AIO.cmd"
)

TEMP_DIR = os.environ.get("TEMP", ".")
SOURCE_PATH = os.path.dirname(__file__)
ODT_EXTRACTOR_PATH = os.path.join(TEMP_DIR, "officedeploymenttool.exe")
ODT_SETUP_PATH     = os.path.join(SOURCE_PATH, "setup.exe")
CONFIG_FILE_PATH   = os.path.join(TEMP_DIR,  "config.xml")

OFFICE_APPS = ["Access", "Excel", "Word", "PowerPoint",
               "Outlook", "Publisher", "OneNote", "Teams"]

LANGUAGES = {
    "English (Mỹ)": "en-us",
    "Vietnamese (Việt Nam)": "vi-vn",
    "Chinese (Trung Quốc)": "zh-cn",
}

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
            try:
                self.iconbitmap(ico)
            except tk.TclError:
                pass

        self.icons = {}
        self._load_icons()

        # State
        self.version_var  = tk.StringVar(value="2024")
        self.lang_var     = tk.StringVar(value="English (Mỹ)")
        self.bitness_var  = tk.StringVar(value="64-bit")
        self.app_vars     = {app: tk.BooleanVar(value=True) for app in OFFICE_APPS}
        self.project_var  = tk.BooleanVar(value=False)
        self.visio_var    = tk.BooleanVar(value=False)
        self.is_all_selected = True

        self.q = queue.Queue()
        self.action_buttons = []

        self._build_ui()
        self._pump_queue()

    # ---------- UI helpers ----------
    def _load_icons(self):
        for name in ["install", "activate", "language", "shortcut", "select_all", "download"]:
            self.icons[name] = load_icon_png(f"{name}.png", (20, 20))

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
        for text, val in [("Office 2016","2016"),("Office 2019","2019"),
                          ("Office 2021","2021"),("Office 2024","2024"),("Office 365","365")]:
            ttk.Radiobutton(f, text=text, variable=self.version_var, value=val)\
                .pack(side="left", padx=5)

    def _options_group(self, parent):
        f = ttk.LabelFrame(parent, text="Tùy chọn thư viện Offline", padding="10")
        f.pack(fill="x", pady=5)

        ttk.Label(f, text="Ngôn ngữ:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Combobox(f, textvariable=self.lang_var, values=list(LANGUAGES.keys()),
                     state="readonly").grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(f, text="Cấu trúc:").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Combobox(f, textvariable=self.bitness_var, values=["64-bit","32-bit"],
                     state="readonly", width=7).grid(row=0, column=3, sticky="w", padx=5)

        f.columnconfigure(1, weight=1)

        btn = ttk.Frame(f)
        btn.grid(row=1, column=0, columnspan=4, pady=(10, 0))
        ttk.Button(btn, text=" Chọn tất cả", image=self.icons.get("select_all"),
                   compound="left", command=self._toggle_all).pack(side="left", padx=5)
        ttk.Button(btn, text=" Tải tùy chọn", image=self.icons.get("download"),
                   compound="left", command=lambda: self._start("download")).pack(side="left", padx=5)

    def _apps_group(self, parent):
        area = ttk.Frame(parent)
        area.pack(fill="x", pady=5)

        apps = ttk.LabelFrame(area, text="Chọn ứng dụng cần cài", padding="10")
        apps.pack(side="left", fill="both", expand=True, padx=(0, 5))

        col1 = ttk.Frame(apps); col1.pack(side="left", padx=10)
        col2 = ttk.Frame(apps); col2.pack(side="left", padx=10)
        for i, app in enumerate(OFFICE_APPS):
            target = col1 if i < len(OFFICE_APPS)/2 else col2
            ttk.Checkbutton(target, text=app, variable=self.app_vars[app]).pack(anchor="w")

        prod = ttk.LabelFrame(area, text="Sản phẩm riêng", padding="10")
        prod.pack(side="left", fill="both")
        ttk.Checkbutton(prod, text="Project", variable=self.project_var).pack(anchor="w")
        ttk.Checkbutton(prod, text="Visio",   variable=self.visio_var).pack(anchor="w")

    def _action_buttons(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=10)

        b1 = ttk.Button(f, text=" Cài đặt", image=self.icons.get("install"),
                        compound="left", command=lambda: self._start("configure"))
        b2 = ttk.Button(f, text=" Kích hoạt", image=self.icons.get("activate"),
                        compound="left", command=lambda: self._start("activate"))
        b3 = ttk.Button(f, text=" Cài Ngôn Ngữ", image=self.icons.get("language"),
                        compound="left", command=lambda: self._start("install_lang"))
        b4 = ttk.Button(f, text=" Tạo shortcut", image=self.icons.get("shortcut"),
                        compound="left", command=lambda: self._start("shortcut"))

        for b in (b1, b2, b3, b4):
            b.pack(side="left", padx=5, expand=True, fill="x")

        self.action_buttons = [b1, b2, b3, b4]

    def _status_area(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=(0, 5))
        self.status = ttk.Label(f, text="Trạng thái: Sẵn sàng.", foreground="green")
        self.status.pack(fill="x")

    # ---------- Logic ----------
    def _product_id(self):
        mapping = {
            "2016": "ProPlusRetail",
            "2019": "ProPlus2019Retail",
            "2021": "ProPlus2021Retail",
            "2024": "ProPlus2024Retail",
            "365":  "O365ProPlusRetail",
        }
        return mapping.get(self.version_var.get(), "ProPlus2024Retail")

    def _build_config(self, lang_only=False):
        pid  = self._product_id()
        bit  = self.bitness_var.get().split("-")[0]
        lang = LANGUAGES.get(self.lang_var.get(), "en-us")

        if lang_only:
            return (
                f'<Configuration><Add OfficeClientEdition="{bit}" Channel="Current">'
                f'<Product ID="{pid}"><Language ID="{lang}" /></Product></Add></Configuration>'
            )

        excluded = "".join(
            f'      <ExcludeApp ID="{app}" />\n'
            for app, var in self.app_vars.items() if not var.get()
        )
        excluded += '      <ExcludeApp ID="OneDrive" />\n      <ExcludeApp ID="Lync" />\n'

        proj = f'<Product ID="ProjectProRetail"><Language ID="{lang}" /></Product>\n' if self.project_var.get() else ""
        vis  = f'<Product ID="VisioProRetail"><Language ID="{lang}" /></Product>\n'   if self.visio_var.get()   else ""

        return (
            f'<Configuration><Add OfficeClientEdition="{bit}" Channel="Current">'
            f'<Product ID="{pid}"><Language ID="{lang}" />{excluded}</Product>'
            f'{proj}{vis}</Add></Configuration>'
        )

    def _start(self, task):
        self._set_enabled(False)
        if task in ("configure", "download"):
            worker = OdtWorker(task, self._build_config(), self.q)
        elif task == "install_lang":
            worker = OdtWorker("configure", self._build_config(lang_only=True), self.q)
        elif task == "activate":
            worker = ActivationWorker(self.q)
        elif task == "shortcut":
            worker = ShortcutWorker(self.q)
        else:
            return
        threading.Thread(target=worker.run, daemon=True).start()

    def _pump_queue(self):
        try:
            msg, color, done, popup = self.q.get_nowait()
            self.status.config(text=f"Trạng thái: {msg}", foreground=color)
            if popup:
                messagebox.showinfo("Thành công", msg, parent=self)
            if done:
                self._set_enabled(True)
        except queue.Empty:
            pass
        self.after(100, self._pump_queue)

    def _set_enabled(self, enable: bool):
        state = "normal" if enable else "disabled"
        for b in self.action_buttons:
            b.config(state=state)

    def _toggle_all(self):
        self.is_all_selected = not self.is_all_selected
        for v in self.app_vars.values():
            v.set(self.is_all_selected)
        self.project_var.set(self.is_all_selected)
        self.visio_var.set(self.is_all_selected)

# ===== Workers =====
class BaseWorker:
    def __init__(self, q: queue.Queue):
        self.q = q
    def report(self, msg, color, done=False, popup=False):
        self.q.put((msg, color, done, popup))

class OdtWorker(BaseWorker):
    def __init__(self, action, config_xml, q):
        super().__init__(q)
        self.action = action
        self.config_xml = config_xml
        self._own_setup = False

    def ensure_setup(self):
        if os.path.exists(ODT_SETUP_PATH):
            return True
        self._own_setup = True
        self.report("📥 Đang tải công cụ triển khai Office...", "blue")
        r = requests.get(ODT_DOWNLOAD_URL, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        r.raise_for_status()
        with open(ODT_EXTRACTOR_PATH, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        self.report("⚙️ Đang giải nén setup.exe...", "blue")
        subprocess.run(
            f'"{ODT_EXTRACTOR_PATH}" /extract:"{SOURCE_PATH}" /quiet /norestart',
            shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        time.sleep(2)
        if not os.path.exists(ODT_SETUP_PATH):
            raise FileNotFoundError("Không thể giải nén setup.exe.")
        return True

    def run(self):
        try:
            self.ensure_setup()
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                f.write(self.config_xml)
            cmd = f'"{ODT_SETUP_PATH}" /{self.action} "{CONFIG_FILE_PATH}"'
            text = "Cài đặt" if self.action == "configure" else "Tải xuống"
            self.report(f"⏳ Đang {text} Office, vui lòng chờ...", "orange")
            subprocess.run(cmd, shell=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            self.report(f"✅ Đã {text} xong!", "green")
        except Exception as e:
            self.report(f"❌ Lỗi: {e}", "red")
        finally:
            if os.path.exists(CONFIG_FILE_PATH):
                os.remove(CONFIG_FILE_PATH)
            if self._own_setup:
                if os.path.exists(ODT_SETUP_PATH):
                    os.remove(ODT_SETUP_PATH)
                for fn in os.listdir(SOURCE_PATH):
                    if fn.startswith("configuration-") and fn.endswith(".xml"):
                        try:
                            os.remove(os.path.join(SOURCE_PATH, fn))
                        except Exception:
                            pass
            if os.path.exists(ODT_EXTRACTOR_PATH):
                os.remove(ODT_EXTRACTOR_PATH)
            self.report("🗑️ Đã dọn dẹp file tạm.", "grey", done=True)

class ActivationWorker(BaseWorker):
    def run(self):
        self.report("Đang tải công cụ kích hoạt Ohook...", "blue")
        script = os.path.join(TEMP_DIR, "Ohook_Activation_AIO.cmd")
        try:
            r = requests.get(ACTIVATION_SCRIPT_URL, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            with open(script, "wb") as f:
                f.write(r.content)
            self.report("Đang chạy kích hoạt tự động...", "orange")
            subprocess.run(f'"{script}" /Ohook', shell=True, check=True,
                           creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.report("Kích hoạt hoàn tất!", "green", popup=True)
        except Exception as e:
            self.report(f"Lỗi kích hoạt: {e}", "red")
        finally:
            if os.path.exists(script):
                try:
                    os.remove(script)
                except OSError:
                    pass
            self.report("Sẵn sàng.", "green", done=True)

class ShortcutWorker(BaseWorker):
    def run(self):
        self.report("🔍 Đang tìm kiếm shortcut...", "blue")
        start_menu = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                                  "Microsoft", "Windows", "Start Menu", "Programs")
        desktop = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")
        names = ["Word","Excel","PowerPoint","Outlook","Access","Publisher","OneNote","Project","Visio"]
        found = 0
        try:
            if not os.path.exists(start_menu):
                self.report("❌ Không tìm thấy thư mục Start Menu.", "red")
                return
            for item in os.listdir(start_menu):
                if item.endswith(".lnk"):
                    for n in names:
                        if n.lower() in item.lower():
                            try:
                                shutil.copy2(os.path.join(start_menu, item),
                                             os.path.join(desktop, item))
                                found += 1
                            except Exception:
                                pass
                            break
            if found:
                self.report(f"✅ Hoàn tất! Đã tạo {found} shortcut.", "green")
            else:
                self.report("ℹ️ Không tìm thấy shortcut nào của Office.", "grey")
        except Exception as e:
            self.report(f"❌ Lỗi không xác định: {e}", "red")
        finally:
            self.report("Sẵn sàng.", "green", done=True)

# ===== API cho main.py =====
def open_window(root: tk.Tk):
    if not _AUTH_TOKEN:
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    OfficeInstallerApp(root)

# ===== Chặn chạy trực tiếp =====
if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy ứng dụng từ main.py.")
