# banquyen.py — Sao lưu bản quyền (module riêng)
# - authorize(token) + open_window(root)
# - Tạo gói "sao lưu an toàn" (không sao chép tokens), nén ZIP ra Desktop
# - Chạy script sao lưu/khôi phục cục bộ (.cmd/.bat/.ps1)
# - Log đen, khóa/mở nút, icon img/logo.ico, footer bản quyền

import os, sys, shutil, datetime, queue, threading, subprocess, tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

# ========= Guard: chỉ mở qua main.py =========
_AUTH_TOKEN = None
def authorize(token: str):
    global _AUTH_TOKEN
    _AUTH_TOKEN = token

# ========= Resource helper (hỗ trợ PyInstaller) =========
def res_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base, *parts)

# ========= Helpers chạy lệnh =========
def run_stream(cmd, q, shell=True):
    """Chạy lệnh và đẩy stdout/stderr theo dòng vào queue; khi xong gửi None."""
    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=shell,
            creationflags=subprocess.CREATE_NO_WINDOW
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

def run_cmd_capture(cmd: str) -> tuple[bool, str]:
    """Chạy lệnh và trả về (ok, output)."""
    try:
        out = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return True, out.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError as e:
        return False, (e.output or b"").decode("utf-8", errors="ignore")

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

def open_path(p: str):
    if not p: return
    if sys.platform == "win32":
        os.startfile(p)
    else:
        subprocess.Popen(["xdg-open", p])

# ========= UI =========
class LicenseBackupApp(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Sao lưu bản quyền")
        self.geometry("820x600")
        self.resizable(False, False)
        self.transient(parent); self.grab_set()
        self.configure(bg="#f0f0f0")

        # icon
        ico = res_path("img", "logo.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except Exception: pass

        self.q = queue.Queue()
        self.last_output_dir = ""
        self._build_ui()
        self._pump()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=10); outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Sao lưu bản quyền", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0,8))

        # Hàng nút chính
        bar1 = ttk.Frame(outer); bar1.pack(fill="x", pady=(0,6))
        self.btn_safe = ttk.Button(bar1, text=" Sao lưu thông tin (AN TOÀN) ", command=self.backup_safe)
        self.btn_run_bk = ttk.Button(bar1, text=" Chạy script sao lưu… ", command=lambda: self.run_script(kind="backup"))
        self.btn_run_rs = ttk.Button(bar1, text=" Chạy script khôi phục… ", command=lambda: self.run_script(kind="restore"))
        self.btn_safe.pack(side="left", padx=4)
        self.btn_run_bk.pack(side="left", padx=4)
        self.btn_run_rs.pack(side="left", padx=4)

        # Hàng nút tiện ích trên thư mục đầu ra
        bar2 = ttk.Frame(outer); bar2.pack(fill="x", pady=(0,8))
        self.btn_open = ttk.Button(bar2, text=" Mở thư mục lưu ", command=self.open_last_dir, state="disabled")
        self.btn_copy = ttk.Button(bar2, text=" Sao chép đường dẫn ", command=self.copy_last_dir, state="disabled")
        self.btn_open.pack(side="left", padx=4)
        self.btn_copy.pack(side="left", padx=4)

        # Log
        logf = ttk.LabelFrame(outer, text="Nhật ký", padding=8); logf.pack(fill="both", expand=True)
        self.out = scrolledtext.ScrolledText(logf, wrap="word", font=("Consolas", 10),
                                             height=16, bg="black", fg="white")
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
        link.bind("<Button-1>", lambda e: open_path("https://www.facebook.com/DomBM.Rika/"))

    # ----- UI helpers -----
    def _log_set(self, s: str):
        self.out.configure(state="normal"); self.out.delete("1.0", "end"); self.out.insert("1.0", s)
        self.out.configure(state="disabled")

    def _log_append(self, s: str):
        self.out.configure(state="normal"); self.out.insert("end", s if s.endswith("\n") else s+"\n")
        self.out.see("end"); self.out.configure(state="disabled")

    def _set_buttons(self, enabled: bool):
        st = "normal" if enabled else "disabled"
        for b in (self.btn_safe, self.btn_run_bk, self.btn_run_rs, self.btn_open, self.btn_copy):
            # open/copy chỉ enable khi đã có last dir
            if b in (self.btn_open, self.btn_copy) and not self.last_output_dir:
                b.config(state="disabled")
            else:
                b.config(state=st)

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

    def open_last_dir(self):
        if self.last_output_dir and os.path.isdir(self.last_output_dir):
            open_path(self.last_output_dir)
        else:
            messagebox.showinfo("Thông báo", "Chưa có thư mục đầu ra nào.")

    def copy_last_dir(self):
        if not self.last_output_dir:
            messagebox.showinfo("Thông báo", "Chưa có thư mục đầu ra để sao chép.")
            return
        self.clipboard_clear(); self.clipboard_append(self.last_output_dir)
        messagebox.showinfo("Sao chép", "Đã sao chép đường dẫn thư mục đầu ra.")

    # ----- Actions -----
    def backup_safe(self):
        # Chọn nơi lưu
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_dir = os.path.join(desktop, f"LicenseBackup_{ts}")

        outdir = filedialog.askdirectory(
            title="Chọn thư mục lưu (Bỏ qua để dùng Desktop mặc định)"
        )
        if not outdir:
            outdir = default_dir
        os.makedirs(outdir, exist_ok=True)
        self.last_output_dir = outdir
        self.btn_open.config(state="normal"); self.btn_copy.config(state="normal")

        self._log_set(f"Sao lưu thông tin bản quyền (an toàn) vào:\n{outdir}\n")
        self._set_buttons(False)
        self.status.config(text="Trạng thái: Đang sao lưu…", foreground="orange")

        def worker():
            try:
                # Windows status
                ok1, out1 = run_cmd_capture(r'cscript //Nologo "%SystemRoot%\System32\slmgr.vbs" /dli')
                ok2, out2 = run_cmd_capture(r'cscript //Nologo "%SystemRoot%\System32\slmgr.vbs" /xpr')
                with open(os.path.join(outdir, "windows_status.txt"), "w", encoding="utf-8") as f:
                    f.write("=== slmgr /dli ===\n" + (out1 or "") + "\n\n")
                    f.write("=== slmgr /xpr ===\n" + (out2 or "") + "\n")

                # Windows OEM key (có thể trống)
                ok3, out3 = run_cmd_capture(
                    'powershell -NoProfile -Command "(Get-WmiObject -Query \\"select * from SoftwareLicensingService\\").OA3xOriginalProductKey"'
                )
                with open(os.path.join(outdir, "windows_oem_key.txt"), "w", encoding="utf-8") as f:
                    f.write((out3 or "").strip() or "Không tìm thấy key OEM.")

                # Office status
                ospp = find_ospp_vbs()
                if ospp:
                    ok4, out4 = run_cmd_capture(f'cscript //Nologo "{ospp}" /dstatus')
                    with open(os.path.join(outdir, "office_status.txt"), "w", encoding="utf-8") as f:
                        f.write(out4 or "")
                else:
                    with open(os.path.join(outdir, "office_status.txt"), "w", encoding="utf-8") as f:
                        f.write("Không tìm thấy OSPP.VBS (Office Click-to-Run/Office16).")

                # README
                with open(os.path.join(outdir, "README.txt"), "w", encoding="utf-8") as f:
                    f.write(
                        "Sao lưu thông tin bản quyền (AN TOÀN)\n"
                        "- Không sao chép token/activation store.\n"
                        "- Lưu trạng thái Windows/Office và key OEM (nếu có).\n"
                        "- Dùng lại key hợp pháp hoặc đăng nhập MS Account để kích hoạt sau cài mới.\n"
                    )

                # ZIP ra Desktop
                zip_base = os.path.join(desktop, os.path.basename(outdir))
                zip_path = shutil.make_archive(zip_base, "zip", outdir)
                self.q.put(f"Đã sao lưu xong. File ZIP: {zip_path}")

            except Exception as e:
                self.q.put(f"[Lỗi] {e}")
            finally:
                self.q.put(None)

        threading.Thread(target=worker, daemon=True).start()

    def run_script(self, kind: str):
        """Chạy script sao lưu/khôi phục cục bộ (.cmd/.bat/.ps1)."""
        path = filedialog.askopenfilename(
            title=("Chọn script sao lưu" if kind=="backup" else "Chọn script khôi phục"),
            filetypes=[("Scripts", "*.cmd;*.bat;*.ps1"), ("All files", "*.*")]
        )
        if not path:
            return
        args = ""
        # nếu cần hỏi tham số:
        # from tkinter import simpledialog
        # args = simpledialog.askstring("Tham số (tùy chọn)", "Nhập tham số dòng lệnh:") or ""

        self._log_set(f"Đang chạy script {'sao lưu' if kind=='backup' else 'khôi phục'}…")
        self._set_buttons(False)
        self.status.config(text=f"Trạng thái: Đang chạy script {kind}…", foreground="orange")

        if path.lower().endswith(".ps1"):
            cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{path}" {args}'
        else:
            cmd = f'cmd.exe /d /c "{path}" {args}'

        threading.Thread(target=run_stream, args=(cmd, self.q), daemon=True).start()

# ========= Public API =========
def open_window(root, **kwargs):
    if not _AUTH_TOKEN:
        tk.Tk().withdraw()
        messagebox.showerror("Từ chối truy cập", "Vui lòng mở từ main.py sau khi đăng nhập.")
        return
    LicenseBackupApp(root)

if __name__ == "__main__":
    tk.Tk().withdraw()
    messagebox.showerror("Từ chối truy cập", "Hãy chạy tiện ích này từ main.py.")
