import customtkinter
import os
import sys
import threading
import requests
import subprocess
from tkinter import messagebox

# --- Cấu hình và Hằng số ---
OHOOK_SCRIPT_URL = "https://raw.githubusercontent.com/massgravel/Microsoft-Activation-Scripts/master/MAS/Separate-Files-Version/Activators/Ohook_Activation_AIO.cmd"
HWID_SCRIPT_URL = "https://raw.githubusercontent.com/massgravel/Microsoft-Activation-Scripts/master/MAS/Separate-Files-Version/Activators/HWID_Activation.cmd"
TEMP_DIR = os.environ.get("TEMP", ".")

# --- Hàm tiện ích ---
def res_path(*parts):
    """Lấy đường dẫn tài nguyên an toàn cho cả môi trường dev và PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, *parts)

def open_link(url: str):
    """Mở một URL trong trình duyệt mặc định."""
    if sys.platform == "win32":
        os.startfile(url)
    else:
        subprocess.Popen(["xdg-open", url])

def add_footer(parent_frame):
    """Thêm footer vào cuối cửa sổ."""
    footer_frame = customtkinter.CTkFrame(parent_frame, fg_color="transparent")
    footer_frame.grid(row=4, column=0, padx=10, pady=(5, 10), sticky="ew")
    
    author_label = customtkinter.CTkLabel(footer_frame, text="Tiện ích này được phát triển bởi Trần Hà", text_color="gray")
    author_label.pack()

    link_label = customtkinter.CTkLabel(footer_frame, text="Liên Hệ: facebook.com/DomBM.Rika/", text_color=("#3a7ebf", "#1f6aa5"), cursor="hand2")
    link_label.pack()
    link_label.bind("<Button-1>", lambda e: open_link("https://www.facebook.com/DomBM.Rika/"))

def create_activation_widgets(parent_frame):
    """Tạo giao diện cho chức năng kích hoạt, giữ lại layout gốc đơn giản."""

    parent_frame.grid_rowconfigure(3, weight=1)
    parent_frame.grid_columnconfigure(0, weight=1)

    # --- Tiêu đề chính ---
    main_title_label = customtkinter.CTkLabel(parent_frame, text="Kích hoạt Bản quyền Windows & Office", font=customtkinter.CTkFont(size=20, weight="bold"))
    main_title_label.grid(row=0, column=0, padx=10, pady=(10, 0))

    # --- Tiêu đề phụ ---
    title_label = customtkinter.CTkLabel(parent_frame, text="Chọn phương thức kích hoạt", font=customtkinter.CTkFont(size=16))
    title_label.grid(row=1, column=0, padx=10, pady=(0, 10))

    # --- Khung chứa các nút ---
    button_frame = customtkinter.CTkFrame(parent_frame, fg_color="transparent")
    button_frame.grid(row=2, column=0, padx=10, pady=5)
    button_frame.grid_columnconfigure((0, 1, 2), weight=1)

    # --- Ô văn bản hiển thị log ---
    log_textbox = customtkinter.CTkTextbox(parent_frame, wrap="word", font=("Courier New", 11), text_color=("gray90", "gray90"), fg_color="black")
    log_textbox.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")
    log_textbox.insert("end", "Chào mừng đến với công cụ kích hoạt.\n\n"
                              "Chọn một chức năng để bắt đầu.\n"
                              "Một cửa sổ dòng lệnh sẽ hiện ra, vui lòng làm theo hướng dẫn trong đó.\n")

    # --- Thêm Footer ---
    add_footer(parent_frame)

    # --- Hàm xử lý logic ---
    def activation_logic(log_widget, buttons, task):
        """Hàm chứa logic tải và chạy script, được thực thi trong một luồng riêng."""
        
        def log(message):
            log_widget.after(0, lambda: log_widget.insert("end", f"{message}\n"))

        if task == "activate_windows":
            url = HWID_SCRIPT_URL
            script_filename = "HWID_Activation.cmd"
            param = ""
            title = "Kich hoat Windows (HWID)"
        else:
            url = OHOOK_SCRIPT_URL
            script_filename = "Ohook_Activation_AIO.cmd"
            param = "/Ohook" if task == "activate_office" else "/UnOhook"
            title = "Kich hoat Office" if task == "activate_office" else "Go bo Kich hoat Office"

        script_path = os.path.join(TEMP_DIR, script_filename)
        
        try:
            log("Đang tải script... Vui Lòng Chờ!")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(script_path, "wb") as f:
                f.write(response.content)
            
            log("-> Đang mở cửa sổ dòng lệnh. Vui lòng làm theo hướng dẫn...")
            
            command = f'start "ADMRDOM - {title}" /wait cmd.exe /c "chcp 65001 > nul & \"{script_path}\" {param} & pause"'
            subprocess.run(command, shell=True, check=True, creationflags=0x08000000)

            log(f"\n-> Quá trình '{title}' đã kết thúc.")
            messagebox.showinfo("Hoàn tất", f"Quá trình '{title}' đã kết thúc.")

        except requests.exceptions.RequestException as e:
            log(f"!!! LỖI: Không thể tải công cụ.\nChi tiết: {e}")
            messagebox.showerror("Lỗi Mạng", f"Không thể tải công cụ kích hoạt.\nChi tiết: {e}")
        except subprocess.CalledProcessError:
            log("!!! LỖI: Quá trình bị hủy hoặc có lỗi trong script.")
            messagebox.showwarning("Cảnh báo", "Quá trình đã bị hủy hoặc có lỗi xảy ra.")
        except Exception as e:
            log(f"!!! LỖI KHÔNG XÁC ĐỊNH: {e}")
            messagebox.showerror("Lỗi không xác định", f"Đã xảy ra lỗi không mong muốn: {e}")
        finally:
            if os.path.exists(script_path):
                try: os.remove(script_path)
                except OSError: pass
            for btn in buttons:
                btn.configure(state="normal")

    def start_task(task):
        """Hàm được gọi khi nhấn nút, để bắt đầu luồng."""
        log_textbox.delete("1.0", "end")
        all_buttons = [win_activate_button, office_activate_button, office_uninstall_button]
        for btn in all_buttons:
            btn.configure(state="disabled")
        
        thread = threading.Thread(target=activation_logic, args=(log_textbox, all_buttons, task))
        thread.daemon = True
        thread.start()

    # --- Các nút bấm ---
    win_activate_button = customtkinter.CTkButton(
        button_frame,
        text="Kích hoạt Windows (HWID)",
        command=lambda: start_task("activate_windows")
    )
    win_activate_button.grid(row=0, column=0, padx=5)

    office_activate_button = customtkinter.CTkButton(
        button_frame,
        text="Kích hoạt Office",
        command=lambda: start_task("activate_office")
    )
    office_activate_button.grid(row=0, column=1, padx=5)

    office_uninstall_button = customtkinter.CTkButton(
        button_frame,
        text="Gỡ bỏ Kích hoạt Office",
        command=lambda: start_task("unactivate_office")
    )
    office_uninstall_button.grid(row=0, column=2, padx=5)


# ===== API cho main.py =====
def open_window(root):
    """Hàm được gọi từ main.py để mở cửa sổ kích hoạt."""
    window = customtkinter.CTkToplevel(root)
    window.title("Kích hoạt Bản quyền Windows & Office")
    window.geometry("700x500")
    window.transient(root)
    window.grab_set()

    # Thêm icon cho cửa sổ
    icon_path = res_path("img", "logo.ico")
    if os.path.exists(icon_path):
        try:
            window.iconbitmap(icon_path)
        except Exception:
            pass # Bỏ qua nếu không set được icon

    create_activation_widgets(window)
