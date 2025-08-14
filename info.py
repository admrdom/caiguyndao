# info.py — Thông tin hệ thống (mở qua main.py)
# Hiển thị CPU, Mainboard, RAM (hãng, số khe, bus, dung lượng, serial),
# Ổ đĩa (model/hãng, dung lượng, serial nếu có), VGA, Serial máy.
# Có nút "Kiểm tra driver" đến trang hỗ trợ theo hãng (Dell/HP/Lenovo/Acer/ASUS/MSI).
import os, sys, json, queue, threading, subprocess, tkinter as tk
from tkinter import ttk, messagebox, PhotoImage

# ========= Resource helper (PyInstaller) =========
def res_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, *parts)

# Optional Pillow để resize icon 20x20
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

# ========= Footer =========
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

# ========= Auth token =========
_AUTH_TOKEN = None
def authorize(token: str):
    global _AUTH_TOKEN
    _AUTH_TOKEN = token

# ========= PowerShell helpers =========
def ps_json(query: str):
    """Run PowerShell query and return JSON-decoded object (list or dict)."""
    cmd = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-Command", f"{query} | ConvertTo-Json -Depth 6"
    ]
    try:
        out = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        if not out:
            return None
        data = json.loads(out.decode("utf-8", errors="ignore") or "null")
        return data
    except Exception:
        return None

def ensure_list(obj):
    if obj is None: return []
    return obj if isinstance(obj, list) else [obj]

# ========= Collectors =========
def bytes_to_gb(n):
    try:
        return round((int(n) / (1024**3)), 2) if n else 0
    except Exception:
        return 0

def get_overview():
    cs  = ps_json("Get-CimInstance Win32_ComputerSystem")
    bios= ps_json("Get-CimInstance Win32_BIOS")
    prod= ps_json("Get-CimInstance Win32_ComputerSystemProduct")
    encl= ps_json("Get-CimInstance Win32_SystemEnclosure")

    cs  = ensure_list(cs)[0] if ensure_list(cs) else {}
    bios= ensure_list(bios)[0] if ensure_list(bios) else {}
    prod= ensure_list(prod)[0] if ensure_list(prod) else {}
    enc = ensure_list(encl)[0] if ensure_list(encl) else {}

    # loại máy (Laptop/Desktop) dựa vào ChassisTypes
    is_laptop = False
    try:
        types = enc.get("ChassisTypes") or []
        # notebook/portable/laptop = 8,9,10,14 theo SMBIOS
        is_laptop = any(int(x) in (8,9,10,14) for x in types)
    except Exception:
        pass

    total_ram = int(cs.get("TotalPhysicalMemory") or 0)
    serial = (prod.get("IdentifyingNumber") or bios.get("SerialNumber") or "").strip()

    return {
        "Manufacturer": cs.get("Manufacturer"),
        "Model": cs.get("Model"),
        "TotalRAM": total_ram,  # bytes
        "SerialNumber": serial,
        "IsLaptop": bool(is_laptop),
    }

def get_cpu():
    items = ensure_list(ps_json("Get-CimInstance Win32_Processor"))
    if not items: return {}
    c = items[0]
    return {
        "Name": c.get("Name"),
        "Cores": c.get("NumberOfCores"),
        "Threads": c.get("NumberOfLogicalProcessors"),
        "MaxClockMHz": c.get("MaxClockSpeed"),
        "Manufacturer": c.get("Manufacturer"),
        "ProcessorId": c.get("ProcessorId"),
    }

def get_baseboard():
    items = ensure_list(ps_json("Get-CimInstance Win32_BaseBoard"))
    if not items: return {}
    b = items[0]
    return {
        "Manufacturer": b.get("Manufacturer"),
        "Product": b.get("Product"),
        "Version": b.get("Version"),
        "SerialNumber": b.get("SerialNumber"),
    }

def get_ram():
    sticks = ensure_list(ps_json("Get-CimInstance Win32_PhysicalMemory"))
    arrs   = ensure_list(ps_json("Get-CimInstance Win32_PhysicalMemoryArray"))
    slot_count = None
    max_cap    = None
    if arrs:
        try: slot_count = int(arrs[0].get("MemoryDevices") or 0)
        except Exception: pass
        try:
            # MaxCapacityEx (KB) hoặc MaxCapacity (KB)
            max_cap = int(arrs[0].get("MaxCapacityEx") or arrs[0].get("MaxCapacity") or 0) * 1024
        except Exception: pass

    modules = []
    total = 0
    for s in sticks:
        cap = int(s.get("Capacity") or 0)
        total += cap
        modules.append({
            "Slot": s.get("DeviceLocator") or s.get("BankLabel"),
            "Manufacturer": s.get("Manufacturer"),
            "PartNumber": (s.get("PartNumber") or "").strip(),
            "Serial": (s.get("SerialNumber") or "").strip(),
            "SpeedMHz": s.get("ConfiguredClockSpeed") or s.get("Speed"),
            "CapacityB": cap
        })
    return {
        "SlotCount": slot_count,
        "MaxCapacityB": max_cap,
        "TotalB": total,
        "Modules": modules
    }

def get_disks():
    disks = ensure_list(ps_json("Get-CimInstance Win32_DiskDrive"))
    medias= ensure_list(ps_json("Get-CimInstance Win32_PhysicalMedia"))
    # map PhysicalMedia.Tag (\\.\PHYSICALDRIVE0) -> SerialNumber
    media_serial = {}
    for m in medias:
        tag = (m.get("Tag") or "").lower()  # \\.\PHYSICALDRIVE0
        media_serial[tag] = (m.get("SerialNumber") or "").strip()

    items = []
    for d in disks:
        dev = (d.get("DeviceID") or "").lower()
        items.append({
            "Model": d.get("Model"),
            "Interface": d.get("InterfaceType"),
            "SizeB": d.get("Size"),
            "Serial": (d.get("SerialNumber") or "").strip() or media_serial.get(dev, "")
        })
    return items

def get_gpus():
    vids = ensure_list(ps_json("Get-CimInstance Win32_VideoController"))
    items = []
    for v in vids:
        ram = v.get("AdapterRAM")
        vram_mb = None
        try:
            vram_mb = round((int(ram)/1024/1024), 0) if ram else None
        except Exception:
            pass
        items.append({
            "Name": v.get("Name"),
            "Vendor": v.get("AdapterCompatibility"),
            "DriverVersion": v.get("DriverVersion"),
            "DriverDate": v.get("DriverDate"),
            "VRAM_MB": vram_mb
        })
    return items

def has_intel_me():
    # best-effort: tìm thiết bị có chuỗi "Management Engine"
    ent = ensure_list(ps_json(r'Get-CimInstance Win32_PnPEntity | Where-Object {$_.Name -like "*Management Engine*"}'))
    return bool(ent)

# ========= Vendor support links =========
def vendor_support_url(manu: str, serial: str):
    m = (manu or "").lower()
    s = (serial or "").strip().upper()
    if "dell" in m:
        # theo yêu cầu: dùng path productsmfe + locale en-vn
        return (f"https://www.dell.com/support/productsmfe/en-vn/productdetails?selection={s}"
                if s else "https://www.dell.com/support/home/en-vn")
    if "hp" in m or "hewlett" in m:
        return f"https://support.hp.com/checkwarranty?serialNumber={s}" if s else "https://support.hp.com/"
    if "lenovo" in m:
        return f"https://pcsupport.lenovo.com/products?serialNumber={s}" if s else "https://pcsupport.lenovo.com/"
    if "acer" in m:
        return f"https://www.acer.com/support?sn={s}" if s else "https://www.acer.com/support"
    if "asus" in m:
        return f"https://www.asus.com/support/warranty-status?serialno={s}" if s else "https://www.asus.com/support"
    if "msi" in m:
        return "https://www.msi.com/support"
    # mặc định
    return "https://www.google.com/search?q=driver+" + ((manu or "laptop").replace(" ", "+"))

# ========= Worker =========
class InfoWorker(threading.Thread):
    def __init__(self, q):
        super().__init__(daemon=True)
        self.q = q
    def report(self, key, data): self.q.put((key, data))
    def run(self):
        self.report("overview", get_overview())
        self.report("cpu", get_cpu())
        self.report("base", get_baseboard())
        self.report("ram", get_ram())
        self.report("disks", get_disks())
        self.report("gpus", get_gpus())
        self.report("intel_me", has_intel_me())

# ========= UI =========
class InfoApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Thông tin hệ thống")
        self.geometry("860x660")
        self.resizable(False, False)
        self.transient(parent); self.grab_set()

        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.icon = load_icon_png("info.png", (20,20))

        self.q = queue.Queue()
        self.data = {}
        self.summary_text_cache = ""

        self._build_ui()
        self.refresh()

    # ---------- Clipboard ----------
    def copy_to_clipboard(self, text: str, toast: str = "Đã sao chép"):
        try:
            self.clipboard_clear(); self.clipboard_append(text or "")
            self.update()  # sync
            messagebox.showinfo("Sao chép", toast)
        except Exception:
            pass

    # ---------- Context menu for Treeview ----------
    def _bind_copy_context(self, tree: ttk.Treeview):
        menu = tk.Menu(tree, tearoff=0)
        menu.add_command(label="Copy dòng đã chọn", command=lambda: self._copy_selected_row(tree))

        def on_rclick(event):
            iid = tree.identify_row(event.y)
            if iid:
                tree.selection_set(iid)
                menu.tk_popup(event.x_root, event.y_root)

        tree.bind("<Button-3>", on_rclick)

    def _copy_selected_row(self, tree: ttk.Treeview):
        sel = tree.selection()
        if not sel: return
        iid = sel[0]
        vals = tree.item(iid, "values")
        self.copy_to_clipboard(" | ".join(str(v) for v in vals), "Đã sao chép dòng.")

    # ---------- UI build ----------
    def _build_ui(self):
        top = ttk.Frame(self, padding=10); top.pack(fill="both", expand=True)

        # ======= Header: Tổng quan =======
        header = ttk.LabelFrame(top, text="Tổng quan", padding=10)
        header.pack(fill="x")
        # Biến hiển thị
        self.var_manu   = tk.StringVar(value="—")
        self.var_model  = tk.StringVar(value="—")
        self.var_serial = tk.StringVar(value="—")
        self.var_ram    = tk.StringVar(value="—")
        self.var_type   = tk.StringVar(value="—")
        self.var_me     = tk.StringVar(value="—")

        # Hãng
        ttk.Label(header, text="Hãng:").grid(row=0, column=0, sticky="w", padx=(6,2), pady=2)
        e_manu = ttk.Entry(header, textvariable=self.var_manu, state="readonly", width=28)
        e_manu.grid(row=0, column=1, sticky="w", padx=(2,6), pady=2)
        ttk.Button(header, text="Copy", width=6, command=lambda: self.copy_to_clipboard(self.var_manu.get(), "Đã sao chép Hãng")).grid(row=0, column=2, padx=(0,8))

        # Model
        ttk.Label(header, text="Model:").grid(row=0, column=3, sticky="w", padx=(6,2), pady=2)
        e_model = ttk.Entry(header, textvariable=self.var_model, state="readonly", width=28)
        e_model.grid(row=0, column=4, sticky="w", padx=(2,6), pady=2)
        ttk.Button(header, text="Copy", width=6, command=lambda: self.copy_to_clipboard(self.var_model.get(), "Đã sao chép Model")).grid(row=0, column=5, padx=(0,8))

        # Serial
        ttk.Label(header, text="Serial:").grid(row=1, column=0, sticky="w", padx=(6,2), pady=2)
        e_serial = ttk.Entry(header, textvariable=self.var_serial, state="readonly", width=28)
        e_serial.grid(row=1, column=1, sticky="w", padx=(2,6), pady=2)
        ttk.Button(header, text="Copy", width=6, command=lambda: self.copy_to_clipboard(self.var_serial.get(), "Đã sao chép Serial")).grid(row=1, column=2, padx=(0,8))

        # RAM tổng
        ttk.Label(header, text="RAM:").grid(row=1, column=3, sticky="w", padx=(6,2), pady=2)
        e_ram = ttk.Entry(header, textvariable=self.var_ram, state="readonly", width=28)
        e_ram.grid(row=1, column=4, sticky="w", padx=(2,6), pady=2)

        # Loại thiết bị + Intel ME
        ttk.Label(header, text="Thiết bị:").grid(row=2, column=0, sticky="w", padx=(6,2), pady=2)
        e_type = ttk.Entry(header, textvariable=self.var_type, state="readonly", width=28)
        e_type.grid(row=2, column=1, sticky="w", padx=(2,6), pady=2)

        ttk.Label(header, text="Intel ME:").grid(row=2, column=3, sticky="w", padx=(6,2), pady=2)
        e_me = ttk.Entry(header, textvariable=self.var_me, state="readonly", width=28)
        e_me.grid(row=2, column=4, sticky="w", padx=(2,6), pady=2)

        header.columnconfigure(1, weight=1)
        header.columnconfigure(4, weight=1)

        # Nút actions
        btnbar = ttk.Frame(top); btnbar.pack(fill="x", pady=(6,8))
        ttk.Button(btnbar, text="Làm mới", command=self.refresh).pack(side="left")
        ttk.Button(btnbar, text="Sao chép tóm tắt", command=self.copy_summary).pack(side="left", padx=6)
        self.btn_support = ttk.Button(btnbar, text="Kiểm tra driver theo Serial", command=self.open_support)
        self.btn_support.pack(side="right")
        self.btn_support.configure(state="disabled")

        # ======= Tabs =======
        nb = ttk.Notebook(top); nb.pack(fill="both", expand=True)

        # CPU tab
        self.cpu_tree = self._mk_kv_tab(nb, "CPU")
        self._bind_copy_context(self.cpu_tree)

        # Mainboard tab
        self.base_tree = self._mk_kv_tab(nb, "Mainboard")
        self._bind_copy_context(self.base_tree)

        # RAM tab (table)
        ram_tab = ttk.Frame(nb); nb.add(ram_tab, text="RAM")
        cols = ("Slot","Hãng","Part","Serial","Bus (MHz)","Dung lượng (GB)")
        self.ram_tree = ttk.Treeview(ram_tab, columns=cols, show="headings", height=9)
        for c, w in zip(cols, (80,120,180,160,90,120)):
            self.ram_tree.heading(c, text=c); self.ram_tree.column(c, width=w, anchor="w")
        self.ram_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self._bind_copy_context(self.ram_tree)
        self.lbl_slots = ttk.Label(ram_tab, text="Số khe: —"); self.lbl_slots.pack(anchor="w", padx=10, pady=(0,6))

        # DISK tab
        disk_tab = ttk.Frame(nb); nb.add(disk_tab, text="Ổ đĩa")
        cols = ("Model","Giao tiếp","Dung lượng (GB)","Serial")
        self.disk_tree = ttk.Treeview(disk_tab, columns=cols, show="headings", height=9)
        for c, w in zip(cols, (280,110,130,240)):
            self.disk_tree.heading(c, text=c); self.disk_tree.column(c, width=w, anchor="w")
        self.disk_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self._bind_copy_context(self.disk_tree)

        # GPU tab
        gpu_tab = ttk.Frame(nb); nb.add(gpu_tab, text="Đồ họa")
        cols = ("Tên","Hãng","VRAM (MB)","Driver","Ngày driver")
        self.gpu_tree = ttk.Treeview(gpu_tab, columns=cols, show="headings", height=9)
        for c, w in zip(cols, (300,140,100,160,140)):
            self.gpu_tree.heading(c, text=c); self.gpu_tree.column(c, width=w, anchor="w")
        self.gpu_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self._bind_copy_context(self.gpu_tree)

        # Summary / Log tab
        sum_tab = ttk.Frame(nb); nb.add(sum_tab, text="Tóm tắt / Log")
        sum_btns = ttk.Frame(sum_tab); sum_btns.pack(fill="x", pady=(8,0), padx=8)
        ttk.Button(sum_btns, text="Làm mới tóm tắt", command=self.render_summary_text).pack(side="left")
        ttk.Button(sum_btns, text="Sao chép toàn bộ", command=lambda: self.copy_to_clipboard(self.summary_text_cache, "Đã sao chép tóm tắt")).pack(side="left", padx=6)
        self.sum_text = tk.Text(sum_tab, height=12, wrap="word")
        self.sum_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.sum_text.configure(state="disabled")

        # status + footer
        self.status = ttk.Label(top, text="Trạng thái: Sẵn sàng.", foreground="green")
        self.status.pack(anchor="w", pady=(2,0))
        add_footer(self)

    def _mk_kv_tab(self, nb: ttk.Notebook, title: str):
        frm = ttk.Frame(nb); nb.add(frm, text=title)
        tree = ttk.Treeview(frm, columns=("v",), show="headings", height=9)
        tree.heading("v", text="Giá trị")
        tree.column("v", width=800, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        return tree

    # ---------- Actions ----------
    def refresh(self):
        self.status.config(text="Trạng thái: Đang lấy thông tin...", foreground="orange")
        self.btn_support.configure(state="disabled")
        for t in (self.cpu_tree, self.base_tree, self.ram_tree, self.disk_tree, self.gpu_tree):
            t.delete(*t.get_children())
        self.lbl_slots.config(text="Số khe: —")
        InfoWorker(self.q).start()
        self.after(120, self._pump)

    def _pump(self):
        updated_any = False
        try:
            while True:
                key, data = self.q.get_nowait()
                self.data[key] = data
                updated_any = True
        except queue.Empty:
            pass

        if updated_any:
            self._render()
        # chờ đủ dữ liệu chính thì kết thúc
        required = {"overview","cpu","base","ram","disks","gpus"}
        if required.issubset(self.data.keys()):
            self.status.config(text="Trạng thái: Hoàn tất.", foreground="green")
            self.render_summary_text()
        else:
            self.after(120, self._pump)

    def _render(self):
        ov = self.data.get("overview") or {}
        ram = self.data.get("ram") or {}
        manu  = ov.get("Manufacturer") or "—"
        model = ov.get("Model") or "—"
        serial= ov.get("SerialNumber") or "—"
        total = bytes_to_gb(ov.get("TotalRAM"))
        me    = "Có" if self.data.get("intel_me") else "Không/Không rõ"
        devt  = "Laptop" if ov.get("IsLaptop") else "Desktop/Khác"

        self.var_manu.set(str(manu))
        self.var_model.set(str(model))
        self.var_serial.set(str(serial))
        self.var_ram.set(f"{total} GB")
        self.var_type.set(devt)
        self.var_me.set(me)

        # bật nút support nếu là laptop & có serial
        if ov.get("IsLaptop") and (ov.get("SerialNumber") or "").strip():
            self.btn_support.configure(state="normal")
        else:
            self.btn_support.configure(state="disabled")

        # CPU
        self.cpu_tree.delete(*self.cpu_tree.get_children())
        cpu = self.data.get("cpu") or {}
        for k in ("Name","Manufacturer","Cores","Threads","MaxClockMHz","ProcessorId"):
            v = cpu.get(k)
            if v is not None:
                self.cpu_tree.insert("", "end", values=(f"{k}: {v}",))

        # Baseboard
        self.base_tree.delete(*self.base_tree.get_children())
        base = self.data.get("base") or {}
        for k in ("Manufacturer","Product","Version","SerialNumber"):
            v = base.get(k)
            if v is not None:
                self.base_tree.insert("", "end", values=(f"{k}: {v}",))

        # RAM
        self.ram_tree.delete(*self.ram_tree.get_children())
        for m in (ram.get("Modules") or []):
            self.ram_tree.insert("", "end", values=(
                m.get("Slot") or "",
                m.get("Manufacturer") or "",
                m.get("PartNumber") or "",
                m.get("Serial") or "",
                m.get("SpeedMHz") or "",
                bytes_to_gb(m.get("CapacityB")) or "",
            ))
        slots = ram.get("SlotCount")
        self.lbl_slots.config(text=f"Số khe: {slots if slots is not None else '—'}")

        # DISKs
        self.disk_tree.delete(*self.disk_tree.get_children())
        for d in (self.data.get("disks") or []):
            self.disk_tree.insert("", "end", values=(
                d.get("Model") or "",
                d.get("Interface") or "",
                bytes_to_gb(d.get("SizeB")) or "",
                d.get("Serial") or "",
            ))

        # GPUs
        self.gpu_tree.delete(*self.gpu_tree.get_children())
        for g in (self.data.get("gpus") or []):
            self.gpu_tree.insert("", "end", values=(
                g.get("Name") or "",
                g.get("Vendor") or "",
                g.get("VRAM_MB") or "",
                g.get("DriverVersion") or "",
                g.get("DriverDate") or "",
            ))

    def build_summary(self) -> str:
        ov  = self.data.get("overview") or {}
        cpu = self.data.get("cpu") or {}
        base= self.data.get("base") or {}
        ram = self.data.get("ram") or {}
        gpus= self.data.get("gpus") or []
        disks=self.data.get("disks") or []

        lines = []
        lines.append(f"Hãng/Model: {ov.get('Manufacturer', '')} {ov.get('Model', '')}".strip())
        lines.append(f"Serial: {ov.get('SerialNumber', '')}")
        lines.append(f"Thiết bị: {'Laptop' if ov.get('IsLaptop') else 'Desktop/Khác'}")
        lines.append(f"RAM tổng: {bytes_to_gb(ov.get('TotalRAM'))} GB")
        lines.append("")
        if cpu:
            lines.append(f"CPU: {cpu.get('Name','')} | {cpu.get('Cores','?')}C/{cpu.get('Threads','?')}T | {cpu.get('MaxClockMHz','?')} MHz")
        if base:
            lines.append(f"Mainboard: {base.get('Manufacturer','')} {base.get('Product','')} (S/N: {base.get('SerialNumber','')})")
        lines.append(f"Số khe RAM: {ram.get('SlotCount')}")
        lines.append(f"Tổng RAM nhận: {bytes_to_gb(ram.get('TotalB'))} GB")
        for i, m in enumerate(ram.get("Modules") or [], 1):
            lines.append(f"  DIMM{i}: {m.get('Manufacturer','')} {m.get('PartNumber','')} | {bytes_to_gb(m.get('CapacityB'))}GB | {m.get('SpeedMHz')}MHz | S/N {m.get('Serial','')}")
        lines.append("")
        for d in disks:
            lines.append(f"Disk: {d.get('Model','')} | {bytes_to_gb(d.get('SizeB'))} GB | IF: {d.get('Interface','')} | S/N: {d.get('Serial','')}")
        for g in gpus:
            lines.append(f"GPU: {g.get('Name','')} | {g.get('Vendor','')} | VRAM: {g.get('VRAM_MB','')}MB | Driver: {g.get('DriverVersion','')}")
        return "\n".join(lines)

    def render_summary_text(self):
        text = self.build_summary()
        self.summary_text_cache = text
        self.sum_text.configure(state="normal")
        self.sum_text.delete("1.0", "end")
        self.sum_text.insert("1.0", text)
        self.sum_text.configure(state="disabled")

    def copy_summary(self):
        self.render_summary_text()
        self.copy_to_clipboard(self.summary_text_cache, "Đã sao chép tóm tắt.")

    def open_support(self):
        manu = self.var_manu.get()
        serial = self.var_serial.get()
        url = vendor_support_url(manu, serial)
        open_link(url)

# ========= Public API cho main.py =========
def open_window(root):
    if not _AUTH_TOKEN:
        tk.Tk().withdraw()
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    InfoApp(root)

# ========= Run direct guard =========
if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy ứng dụng từ main.py.")
