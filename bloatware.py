# bloatware.py — Gỡ bloatware Windows (UWP, OneDrive, Teams…)
# Mẫu module: authorize(token) + open_window(root)
# UI: checkbox chọn hạng mục, nút "Bắt đầu gỡ", log đen, nút khôi phục Store, tắt quảng cáo…
# Chạy PowerShell nền, có log, khoá/mở nút, footer bản quyền.

import os, sys, queue, threading, subprocess, tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# ===== Guard mở qua main.py =====
_AUTH_TOKEN = None
def authorize(token: str):
    global _AUTH_TOKEN
    _AUTH_TOKEN = token

# ===== Resource helper (icon .ico) =====
def res_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, *parts)

# ===== Chạy lệnh stream log =====
def run_stream(cmd, q, shell=True):
    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            shell=shell, creationflags=subprocess.CREATE_NO_WINDOW
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

# ===== PowerShell snippets =====
def ps_remove_template(patterns: list[str]) -> str:
    # Hàm Remove-Appx theo tên (provisioned + app hiện hữu)
    base = r'''
function Remove-AppxByName($name){
  try{
    Write-Output ">> Gỡ provisioned: $name"
    $prov = Get-AppxProvisionedPackage -Online | Where-Object { $_.DisplayName -like $name }
    foreach($p in $prov){ Remove-AppxProvisionedPackage -Online -PackageName $p.PackageName -ErrorAction SilentlyContinue | Out-Null }

    Write-Output ">> Gỡ appx hiện hữu: $name"
    $apps = Get-AppxPackage -AllUsers -Name $name
    foreach($a in $apps){ Remove-AppxPackage -AllUsers -Package $a.PackageFullName -ErrorAction SilentlyContinue | Out-Null }
  } catch { Write-Output "[Lỗi] $($_.Exception.Message)" }
}
'''
    body = "".join([f'Remove-AppxByName "{p}"\n' for p in patterns])
    return base + "\n" + body

def ps_onedrive_uninstall() -> str:
    return r'''
Write-Output ">> Dừng OneDrive..."
taskkill /f /im OneDrive.exe *>$null

$syswow = "$env:SystemRoot\SysWOW64\OneDriveSetup.exe"
$sys32  = "$env:SystemRoot\System32\OneDriveSetup.exe"
$exe = $(if (Test-Path $syswow) { $syswow } elseif (Test-Path $sys32) { $sys32 } else { $null })
if($exe){
  Write-Output ">> Gỡ OneDrive..."
  & $exe /uninstall | Out-Null
}else{
  Write-Output ">> Không tìm thấy OneDriveSetup.exe"
}

Write-Output ">> Xoá thư mục còn sót..."
Remove-Item "$env:USERPROFILE\OneDrive" -Force -Recurse -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\Microsoft\OneDrive" -Force -Recurse -ErrorAction SilentlyContinue
Remove-Item "$env:PROGRAMDATA\Microsoft OneDrive" -Force -Recurse -ErrorAction SilentlyContinue
'''

def ps_disable_consumer_features() -> str:
    return r'''
Write-Output ">> Tắt quảng cáo/Consumer features..."
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\CloudContent" /v DisableConsumerFeatures /t REG_DWORD /d 1 /f | Out-Null
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v ContentDeliveryAllowed /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v OemPreInstalledAppsEnabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v PreInstalledAppsEnabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v PreInstalledAppsEverEnabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v SilentInstalledAppsEnabled /t REG_DWORD /d 0 /f | Out-Null
'''

def ps_restore_store() -> str:
    return r'''
Write-Output ">> Khôi phục Microsoft Store & công cụ cốt lõi..."
$targets = @("Microsoft.WindowsStore","Microsoft.StorePurchaseApp","Microsoft.DesktopAppInstaller")
foreach($n in $targets){
  $p = Get-AppxPackage -AllUsers -Name $n
  if($p){ Add-AppxPackage -DisableDevelopmentMode -Register "$($p.InstallLocation)\AppxManifest.xml" -ErrorAction SilentlyContinue | Out-Null
          Write-Output "   - Đã đăng ký lại: $n" }
  else { Write-Output "   - Không thấy gói: $n" }
}
Write-Output ">> Chạy wsreset..."
Start-Process -FilePath "wsreset.exe" -WindowStyle Hidden
'''

def ps_restore_core_apps() -> str:
    # Đăng ký lại phần lớn UWP (có thể ra cảnh báo ở một số gói => bỏ qua)
    return r'''
Write-Output ">> Khôi phục cơ bản các ứng dụng UWP (re-register manifests)..."
Get-AppxPackage -AllUsers | ForEach-Object {
  try { Add-AppxPackage -DisableDevelopmentMode -Register "$($_.InstallLocation)\AppxManifest.xml" -ErrorAction SilentlyContinue | Out-Null }
  catch {}
}
Write-Output ">> Hoàn tất khôi phục cơ bản."
'''

# ===== UI =====
class BloatwareApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Xóa Bloatware")
        self.geometry("820x600")
        self.resizable(False, False)
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

        ttk.Label(outer, text="Chọn hạng mục bloatware cần gỡ", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,8))

        # Nhóm lựa chọn (2 cột)
        opts = ttk.Frame(outer); opts.pack(fill="x")
        col1 = ttk.Frame(opts); col1.pack(side="left", expand=True, fill="x", padx=(0,8))
        col2 = ttk.Frame(opts); col2.pack(side="left", expand=True, fill="x")

        self.v_xbox     = tk.BooleanVar(value=True)
        self.v_onedrive = tk.BooleanVar(value=False)
        self.v_consumer = tk.BooleanVar(value=True)
        self.v_teams    = tk.BooleanVar(value=True)
        self.v_oem      = tk.BooleanVar(value=False)
        self.v_disableads = tk.BooleanVar(value=True)

        ttk.Checkbutton(col1, text="Gỡ ứng dụng Xbox/Gaming", variable=self.v_xbox).pack(anchor="w", pady=2)
        ttk.Checkbutton(col1, text="Gỡ Microsoft Teams (consumer)", variable=self.v_teams).pack(anchor="w", pady=2)
        ttk.Checkbutton(col1, text="Gỡ OneDrive", variable=self.v_onedrive).pack(anchor="w", pady=2)

        ttk.Checkbutton(col2, text="Gỡ app giải trí (News, Weather, 3D…)", variable=self.v_consumer).pack(anchor="w", pady=2)
        ttk.Checkbutton(col2, text="Gỡ app OEM (Dell/HP/Lenovo)", variable=self.v_oem).pack(anchor="w", pady=2)
        ttk.Checkbutton(col2, text="Tắt quảng cáo/Consumer features", variable=self.v_disableads).pack(anchor="w", pady=2)

        # Hàng nút hành động
        bar = ttk.Frame(outer); bar.pack(fill="x", pady=(10,6))
        self.btn_run  = ttk.Button(bar, text=" Bắt đầu gỡ bloatware ", command=self.start_remove)
        self.btn_rest = ttk.Button(bar, text=" Khôi phục Microsoft Store ", command=self.restore_store)
        self.btn_core = ttk.Button(bar, text=" Khôi phục UWP cơ bản ", command=self.restore_core)
        self.btn_run.pack(side="left", padx=4)
        self.btn_rest.pack(side="left", padx=4)
        self.btn_core.pack(side="left", padx=4)

        # Log
        logf = ttk.LabelFrame(outer, text="Nhật ký", padding=8); logf.pack(fill="both", expand=True, pady=(6,0))
        self.out = scrolledtext.ScrolledText(logf, wrap="word", font=("Consolas", 10), height=16, bg="black", fg="white")
        self.out.pack(fill="both", expand=True)

        # Trạng thái
        self.status = ttk.Label(outer, text="Trạng thái: Sẵn sàng.", foreground="green")
        self.status.pack(anchor="w", pady=(6,0))

        # Footer
        sep = ttk.Separator(self); sep.pack(side="bottom", fill="x", pady=(6,0))
        box = ttk.Frame(self); box.pack(side="bottom", fill="x", pady=(4,6))
        ttk.Label(box, text="Tiện ích này được phát triển bởi Trần Hà",
                  foreground="grey", anchor="center").pack(fill="x")
        link = ttk.Label(box, text="Liên Hệ: facebook.com/DomBM.Rika/",
                         foreground="blue", cursor="hand2", anchor="center")
        link.pack(fill="x")
        link.bind("<Button-1>", lambda e: self._open("https://www.facebook.com/DomBM.Rika/"))

    # ---- helpers UI ----
    def _open(self, url):
        if sys.platform == "win32": os.startfile(url)
        else: subprocess.Popen(["xdg-open", url])

    def _log_set(self, s: str):
        self.out.configure(state="normal"); self.out.delete("1.0", "end"); self.out.insert("1.0", s); self.out.configure(state="disabled")

    def _log_append(self, s: str):
        self.out.configure(state="normal"); self.out.insert("end", s if s.endswith("\n") else s+"\n"); self.out.see("end"); self.out.configure(state="disabled")

    def _set_buttons(self, enabled: bool):
        st = "normal" if enabled else "disabled"
        self.btn_run.configure(state=st); self.btn_rest.configure(state=st); self.btn_core.configure(state=st)

    def _pump(self):
        try:
            while True:
                line = self.q.get_nowait()
                if line is None:
                    self._set_buttons(True)
                    self.status.config(text="Trạng thái: Hoàn tất.", foreground="green")
                    self.bell()
                    break
                self._log_append(line)
        except queue.Empty:
            pass
        self.after(120, self._pump)

    # ---- Compose & run PowerShell ----
    def _make_ps_script(self) -> str:
        parts = []

        if self.v_xbox.get():
            xbox = [
                "Microsoft.XboxApp*",
                "Microsoft.Xbox.TCUI*",
                "Microsoft.XboxGamingOverlay*",
                "Microsoft.XboxGameOverlay*",
                "Microsoft.XboxIdentityProvider*",
                "Microsoft.GamingApp*",
                "Microsoft.GamingServices*"
            ]
            parts.append(ps_remove_template(xbox))

        if self.v_teams.get():
            teams = ["MicrosoftTeams*","MSTeams*"]
            parts.append(ps_remove_template(teams))

        if self.v_consumer.get():
            consumer = [
                "Microsoft.3DBuilder*",
                "Microsoft.Microsoft3DViewer*",
                "Microsoft.Print3D*",
                "Microsoft.SkypeApp*",
                "Microsoft.GetHelp*",
                "Microsoft.BingNews*",
                "Microsoft.BingWeather*",
                "Microsoft.ZuneMusic*",
                "Microsoft.ZuneVideo*",
                "Microsoft.MicrosoftSolitaireCollection*",
                "Microsoft.MixedReality.Portal*",
                "Microsoft.People*",
                "Microsoft.YourPhone*",
                "Microsoft.OneConnect*",
                "Microsoft.Todos*",
            ]
            parts.append(ps_remove_template(consumer))

        if self.v_oem.get():
            oem = ["*Dell*","*Alienware*","*HP*","*HewlettPackard*","*Lenovo*","*McAfee*","*Norton*"]
            parts.append(ps_remove_template(oem))

        if self.v_onedrive.get():
            parts.append(ps_onedrive_uninstall())

        if self.v_disableads.get():
            parts.append(ps_disable_consumer_features())

        if not parts:
            return 'Write-Output "Không có mục nào được chọn. Dừng lại."'

        return "\n".join(parts) + '\nWrite-Output ">> Hoàn tất các tác vụ đã chọn."'

    # ---- Actions ----
    def start_remove(self):
        ps = self._make_ps_script()
        self._log_set("Bắt đầu gỡ bloatware...\n")
        self._set_buttons(False)
        self.status.config(text="Trạng thái: Đang gỡ bloatware…", foreground="orange")

        # Chạy PowerShell
        cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -Command ' + f'"& {{ {ps} }}"'
        threading.Thread(target=run_stream, args=(cmd, self.q), daemon=True).start()

    def restore_store(self):
        ps = ps_restore_store()
        self._log_set("Khôi phục Microsoft Store...\n")
        self._set_buttons(False)
        self.status.config(text="Trạng thái: Đang khôi phục Store…", foreground="orange")
        cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -Command ' + f'"& {{ {ps} }}"'
        threading.Thread(target=run_stream, args=(cmd, self.q), daemon=True).start()

    def restore_core(self):
        ps = ps_restore_core_apps()
        self._log_set("Khôi phục UWP cơ bản...\n")
        self._set_buttons(False)
        self.status.config(text="Trạng thái: Đang khôi phục UWP…", foreground="orange")
        cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -Command ' + f'"& {{ {ps} }}"'
        threading.Thread(target=run_stream, args=(cmd, self.q), daemon=True).start()

# ===== Public API =====
def open_window(root, **kwargs):
    if not _AUTH_TOKEN:
        tk.Tk().withdraw()
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    BloatwareApp(root)

if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy tiện ích này từ main.py.")
