# kichhoat.py — Kích hoạt Win/Office (UI tối giản, downloader robust)
# - 3 nút: Kích hoạt Windows, Kích hoạt Office, Gỡ kích hoạt Office
# - Tải & chạy script HỢP PHÁP từ URL (PowerShell: IWR → BITS → WebClient), tự xoá file tạm
# - Không dùng 'requests'; log tải chỉ: "Đang tải script. Vui lòng chờ…"
# - Nếu không cấu hình URL: yêu cầu Product Key hợp pháp (Windows/Office) hoặc gỡ key Office
# - Mở qua main.py: authorize(token) + open_window(root)

import os, sys, queue, threading, subprocess, tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext

# ====== (Tuỳ chọn) URL script HỢP PHÁP của bạn ======
# Để trống => dùng phương án hợp pháp bằng Product Key
WINDOWS_ACTIVATE_URL         = "https://raw.githubusercontent.com/massgravel/Microsoft-Activation-Scripts/refs/heads/master/MAS/Separate-Files-Version/Activators/HWID_Activation.cmd"  # ví dụ: "https://raw.githubusercontent.com/your-org/your-repo/main/activate_win.cmd"
OFFICE_ACTIVATE_URL          = "https://raw.githubusercontent.com/massgravel/Microsoft-Activation-Scripts/refs/heads/master/MAS/Separate-Files-Version/Activators/Ohook_Activation_AIO.cmd"  # ví dụ: "https://raw.githubusercontent.com/your-org/your-repo/main/activate_office.cmd"
OFFICE_UNINSTALL_LICENSE_URL = "https://raw.githubusercontent.com/massgravel/Microsoft-Activation-Scripts/refs/heads/master/MAS/Separate-Files-Version/Activators/Ohook_Activation_AIO.cmd"  # ví dụ: "https://raw.githubusercontent.com/your-org/your-repo/main/uninstall_office_license.cmd"

TEMP_WIN_FILE   = "win_activate.cmd"
TEMP_OFF_FILE   = "office_activate.cmd"
TEMP_OFF_UNFILE = "office_uninstall.cmd"

# ====== Guard: chỉ mở từ main.py ======
_AUTH_TOKEN = None
def authorize(token: str):
    global _AUTH_TOKEN
    _AUTH_TOKEN = token

# ====== Resource helper (hỗ trợ PyInstaller) ======
def res_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, *parts)

# ====== Tiện ích shell ======
def run_stream(cmd, q, shell=True):
    """Chạy lệnh và đẩy stdout/stderr theo dòng vào queue; khi xong gửi None."""
    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            shell=shell,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        for line in iter(p.stdout.readline, ''):
            q.put(line)
        p.stdout.close()
        p.wait()
        q.put(f"\n--- Hoàn tất. Mã thoát: {p.returncode} ---\n")
    except Exception as e:
        q.put(f"[Lỗi] {e}\n")
    finally:
        q.put(None)

def run_cmd(cmd: str) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return True, out.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        return False, (e.output or b"").decode("utf-8", errors="ignore")

def _to_raw_url(url: str) -> str:
    """Chuyển link GitHub dạng blob -> raw (nếu cần)."""
    try:
        if "github.com" in url and "/blob/" in url:
            url = url.replace("github.com/", "raw.githubusercontent.com/").replace("/blob/", "/")
    except Exception:
        pass
    return url

def _ps_save_and_run(ps_code: str) -> tuple[bool, str]:
    """Ghi 1 script PowerShell tạm rồi chạy nó (tránh one-liner khó quote)."""
    import tempfile
    tmp_dir = os.environ.get("TEMP", tempfile.gettempdir())
    ps_path = os.path.join(tmp_dir, f"_dl_{os.getpid()}.ps1")
    with open(ps_path, "w", encoding="utf-8") as f:
        f.write(ps_code)
    ok, out = run_cmd(f'powershell -NoProfile -ExecutionPolicy Bypass -File "{ps_path}"')
    try:
        if os.path.isfile(ps_path):
            os.remove(ps_path)
    except Exception:
        pass
    return ok, out

def run_script_from_url_to_temp(url: str, filename: str, args: list[str], q):
    """
    Tải script HỢP PHÁP về %TEMP% (IWR → BITS → WebClient), chạy, xong tự xoá.
    Log khi tải chỉ hiển thị: 'Đang tải script. Vui lòng chờ…'
    """
    import tempfile
    tmp_dir = os.environ.get("TEMP", tempfile.gettempdir())
    # Bảo vệ: nếu filename rỗng => dùng tên mặc định an toàn
    safe_filename = filename or f"script_{os.getpid()}.cmd"
    path = os.path.join(tmp_dir, safe_filename)

    # PowerShell script đa phương án tải
    raw = _to_raw_url(url).replace("'", "''")
    outp = path.replace("'", "''")
    ps = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try {{
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
}} catch {{ }}

$u = '{raw}'
$o = '{outp}'
$ua = 'Mozilla/5.0'

Write-Output 'Đang tải script. Vui lòng chờ…'

function Try-IWR {{
  try {{
    Invoke-WebRequest -Uri $u -Headers @{{'User-Agent'=$ua}} -UseBasicParsing -OutFile $o -TimeoutSec 90
    return $true
  }} catch {{ Write-Output ('IWR: ' + $_.Exception.Message); return $false }}
}}

function Try-BITS {{
  try {{
    Start-BitsTransfer -Source $u -Destination $o -ErrorAction Stop
    return $true
  }} catch {{ Write-Output ('BITS: ' + $_.Exception.Message); return $false }}
}}

function Try-WebClient {{
  try {{
    $wc = New-Object Net.WebClient
    $wc.Headers['User-Agent'] = $ua
    $wc.DownloadFile($u, $o)
    return $true
  }} catch {{ Write-Output ('WebClient: ' + $_.Exception.Message); return $false }}
}}

$ok = $false
if (-not $ok) {{ $ok = Try-IWR }}
if (-not $ok) {{ $ok = Try-BITS }}
if (-not $ok) {{ $ok = Try-WebClient }}

if (-not $ok) {{
  Write-Output '[Lỗi] Không tải được file.'
  exit 1
}}

if (!(Test-Path $o)) {{
  Write-Output '[Lỗi] File không tồn tại sau khi tải.'
  exit 1
}}

$len = (Get-Item $o).Length
if ($len -lt 16) {{
  Write-Output '[Lỗi] File rỗng hoặc quá nhỏ.'
  exit 1
}}

Write-Output 'Đã tải xong script.'
"""

    def worker():
        try:
            ok, out = _ps_save_and_run(ps)
            if not ok:
                q.put(out.strip() or "[Lỗi] Không tải được file."); q.put(None); return

            # Chạy script vừa tải
            if path.lower().endswith(".ps1"):
                cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{path}" {" ".join(args)}'
            else:
                # thêm chcp 65001 để log Unicode đẹp hơn (không bắt buộc)
                cmd = f'cmd.exe /d /c chcp 65001>nul & "{path}" {" ".join(args)}'
            run_stream(cmd, q)
        except Exception as e:
            q.put(f"[Lỗi] {e}")
        finally:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    q.put("Đã xoá file tạm.")
            except Exception as e:
                q.put(f"[Cảnh báo] Không xoá được file tạm: {e}")
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

def find_ospp_vbs() -> str | None:
    """Tìm OSPP.VBS (Office16/Click-to-Run)."""
    cands = [
        r"C:\Program Files\Microsoft Office\Office16\OSPP.VBS",
        r"C:\Program Files (x86)\Microsoft Office\Office16\OSPP.VBS",
        r"C:\Program Files\Microsoft Office\root\Office16\OSPP.VBS",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\OSPP.VBS",
    ]
    for p in cands:
        if os.path.exists(p): return p
    return None

def normalize_key(raw: str) -> str:
    """Chuẩn hoá key 25 ký tự -> XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"""
    if not raw: return ""
    k = raw.replace("-", "").replace(" ", "").upper()
    if len(k) == 25 and k.isalnum():
        return "-".join([k[i:i+5] for i in range(0,25,5)])
    return ""

# ====== UI ======
class KichHoatUI(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Kích hoạt Win - Office")
        self.geometry("760x520")
        self.resizable(False, False)
        self.transient(parent); self.grab_set()
        self.configure(bg="#f0f0f0")

        # icon tiêu đề
        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.q = queue.Queue()
        self._build_ui()
        self._pump()

    def _build_ui(self):
        tk.Label(self, text="Chọn phương thức kích hoạt",
                 font=("Segoe UI", 12, "bold"), bg="#f0f0f0").pack(pady=10)

        row = tk.Frame(self, bg="#f0f0f0"); row.pack(pady=(0,8))
        self.btn_w_activate = tk.Button(row, text="Kích hoạt Windows", command=self.on_win_activate)
        self.btn_o_activate = tk.Button(row, text="Kích hoạt Office",  command=self.on_office_activate)
        self.btn_o_uninst   = tk.Button(row, text="Gỡ kích hoạt Office", command=self.on_office_uninstall)
        self.btn_w_activate.pack(side="left", padx=6)
        self.btn_o_activate.pack(side="left", padx=6)
        self.btn_o_uninst.pack(side="left", padx=6)

        self.out = scrolledtext.ScrolledText(self, wrap=tk.WORD, state="disabled",
                                             font=("Consolas", 10), bg="black", fg="white")
        self.out.pack(fill="both", expand=True, padx=8, pady=8)

        # footer bản quyền
        sep = ttk.Separator(self); sep.pack(side="bottom", fill="x", pady=(6,0))
        box = ttk.Frame(self); box.pack(side="bottom", fill="x", pady=(4,6))
        ttk.Label(box, text="Tiện ích này được phát triển bởi Trần Hà",
                  foreground="grey", anchor="center").pack(fill="x")
        link = ttk.Label(box, text="Liên Hệ: facebook.com/DomBM.Rika/",
                         foreground="blue", cursor="hand2", anchor="center")
        link.pack(fill="x")
        link.bind("<Button-1>", lambda e: self._open("https://www.facebook.com/DomBM.Rika/"))

    # ---- helpers ----
    def _open(self, url):
        if sys.platform == "win32": os.startfile(url)
        else: subprocess.Popen(["xdg-open", url])

    def _append(self, s: str):
        self.out.config(state="normal")
        self.out.insert("end", s if s.endswith("\n") else s + "\n")
        self.out.see("end")
        self.out.config(state="disabled")

    def _set_log(self, s: str):
        self.out.config(state="normal"); self.out.delete("1.0", "end"); self.out.insert("1.0", s); self.out.config(state="disabled")

    def _set_btns(self, enabled: bool):
        st = "normal" if enabled else "disabled"
        self.btn_w_activate.config(state=st)
        self.btn_o_activate.config(state=st)
        self.btn_o_uninst.config(state=st)

    def _pump(self):
        try:
            while True:
                line = self.q.get_nowait()
                if line is None:
                    self._set_btns(True)
                    self.bell()
                    break
                self._append(line)
        except queue.Empty:
            pass
        self.after(120, self._pump)

    # ---- actions ----
    def on_win_activate(self):
        if WINDOWS_ACTIVATE_URL:
            # KHÔNG set log ở đây để tránh trùng dòng; worker sẽ in "Đang tải script..."
            self._set_btns(False)
            run_script_from_url_to_temp(WINDOWS_ACTIVATE_URL, TEMP_WIN_FILE, [], self.q)
        else:
            key = simpledialog.askstring("Nhập key Windows", "Nhập Product Key 25 ký tự:", parent=self)
            key = normalize_key(key or "")
            if not key:
                messagebox.showerror("Lỗi", "Key không hợp lệ."); return
            if not messagebox.askyesno("Xác nhận", f"Cài key & kích hoạt Windows với key:\n{key}?"): return
            self._set_log(f"Đang cài key Windows: {key}\n"); self._set_btns(False)
            ps = r'[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; ' \
                 r'& {cscript //Nologo "$env:SystemRoot\System32\slmgr.vbs" /ipk ' + key + r'; ' \
                 r'cscript //Nologo "$env:SystemRoot\System32\slmgr.vbs" /ato }'
            cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -Command ' + ps
            threading.Thread(target=run_stream, args=(cmd, self.q), daemon=True).start()

    def on_office_activate(self):
        if OFFICE_ACTIVATE_URL:
            self._set_btns(False)
            run_script_from_url_to_temp(OFFICE_ACTIVATE_URL, TEMP_OFF_FILE, [], self.q)
        else:
            ospp = find_ospp_vbs()
            if not ospp:
                messagebox.showerror("Không tìm thấy OSPP.VBS", "Không xác định được đường dẫn OSPP.VBS (Office16)."); return
            key = simpledialog.askstring("Nhập key Office", "Nhập Product Key 25 ký tự:", parent=self)
            key = normalize_key(key or "")
            if not key:
                messagebox.showerror("Lỗi", "Key không hợp lệ."); return
            if not messagebox.askyesno("Xác nhận", f"Cài key & kích hoạt Office với key:\n{key}?"): return
            self._set_log(f"OSPP: {ospp}\nĐang cài key Office: {key}\n"); self._set_btns(False)
            ps = f'[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; & {{cscript //Nologo "{ospp}" /inpkey:{key}; cscript //Nologo "{ospp}" /act }}'
            cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -Command ' + ps
            threading.Thread(target=run_stream, args=(cmd, self.q), daemon=True).start()

    def on_office_uninstall(self):
        if OFFICE_UNINSTALL_LICENSE_URL:
            self._set_btns(False)
            run_script_from_url_to_temp(OFFICE_UNINSTALL_LICENSE_URL, TEMP_OFF_UNFILE, [], self.q)
        else:
            ospp = find_ospp_vbs()
            if not ospp:
                messagebox.showerror("Không tìm thấy OSPP.VBS", "Không xác định được đường dẫn OSPP.VBS (Office16)."); return
            last5 = simpledialog.askstring("Gỡ key Office", "Nhập 5 ký tự cuối của key:", parent=self)
            if not last5: return
            last5 = last5.strip().upper()
            if len(last5) != 5:
                messagebox.showerror("Lỗi", "Cần đúng 5 ký tự cuối."); return
            self._set_log(f"OSPP: {ospp}\nĐang gỡ key Office có đuôi: {last5}\n"); self._set_btns(False)
            cmd = f'cscript //Nologo "{ospp}" /unpkey:{last5}'
            threading.Thread(target=run_stream, args=(cmd, self.q), daemon=True).start()

# ====== Public API ======
def open_window(root, **kwargs):
    if not _AUTH_TOKEN:
        tk.Tk().withdraw()
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    KichHoatUI(root)

if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy tiện ích này từ main.py.")
