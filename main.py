import tkinter as tk
from tkinter import messagebox
import threading
import os
import sys
import cv2
import numpy as np
import mss
import keyboard
import time
import ctypes
import pydirectinput

pydirectinput.PAUSE = 0

# ==========================================
# FIX LỖI TỌA ĐỘ BỊ LỆCH DO WINDOWS SCALE
# ==========================================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# --- CẤU HÌNH ĐƯỜNG DẪN & ẢNH ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def load_image(filename):
    path = os.path.join(ASSETS_DIR, filename)
    img = cv2.imread(path, 0)
    if img is None:
        print(f"[LỖI] Không tìm thấy: {filename}")
    return img

tpl_cham_than = load_image('cham_than.png')
tpl_w = load_image('nut_w.png')
tpl_a = load_image('nut_a.png')
tpl_d = load_image('nut_d.png')
tpl_thanh_mau = load_image('thanh_mau.png')

CONFIDENCE_QTE = 0.7
CONFIDENCE_MAU = 0.65
bot_is_running = False

REGION_MAU = None
REGION_NHAN_VAT = None

sct = mss.MSS()

# --- HÀM TÌM ẢNH ĐƯỢC BỔ SUNG TÍNH NĂNG CHỤP LỖI (DEBUG) ---
def find_image(template_img, region, confidence, debug_filename=None):
    if template_img is None or region is None:
        return False
    
    sct_img = np.array(sct.grab(region))
    gray_screen = cv2.cvtColor(sct_img, cv2.COLOR_BGRA2GRAY)
    
    # Lưu lại ảnh vùng bot ĐANG NHÌN để bạn kiểm tra
    if debug_filename:
        cv2.imwrite(os.path.join(BASE_DIR, debug_filename), gray_screen)
        
    result = cv2.matchTemplate(gray_screen, template_img, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val >= confidence


class FishingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Fishing Pro")
        self.root.geometry("280x250")
        self.root.attributes('-topmost', True) 
        self.root.configure(bg="#2c3e50")

        self.btn_mau = tk.Button(root, text="1. Chọn Vùng Thanh Máu", command=lambda: self.start_selection('MAU'), bg="#8e44ad", fg="white", font=("Arial", 9, "bold"))
        self.btn_mau.pack(pady=(10, 5), fill="x", padx=20)

        self.btn_nhan_vat = tk.Button(root, text="2. Chọn Vùng Nhân Vật", command=lambda: self.start_selection('NHANVAT'), bg="#2980b9", fg="white", font=("Arial", 9, "bold"))
        self.btn_nhan_vat.pack(pady=5, fill="x", padx=20)

        self.lbl_status = tk.Label(root, text="Chưa thiết lập vùng quét...", bg="#2c3e50", fg="#bdc3c7", font=("Arial", 9, "italic"))
        self.lbl_status.pack(pady=5)

        self.btn_start = tk.Button(root, text="BẮT ĐẦU (F8)", command=self.start_bot, bg="#27ae60", fg="white", font=("Arial", 11, "bold"))
        self.btn_start.pack(pady=(10, 5), fill="x", padx=20)

        self.btn_stop = tk.Button(root, text="DỪNG LẠI (Q)", command=self.stop_bot, bg="#c0392b", fg="white", font=("Arial", 11, "bold"))
        self.btn_stop.pack(pady=5, fill="x", padx=20)

        self.current_selection_type = None
        threading.Thread(target=self.listen_hotkeys, daemon=True).start()

    def update_status(self, text, color="white"):
        self.lbl_status.config(text=text, fg=color)

    def listen_hotkeys(self):
        while True:
            if keyboard.is_pressed('f8') and not bot_is_running:
                self.start_bot()
                time.sleep(0.5)
            if keyboard.is_pressed('q') and bot_is_running:
                self.stop_bot()
                time.sleep(0.5)
            time.sleep(0.05)

    def start_selection(self, sel_type):
        self.current_selection_type = sel_type
        self.root.withdraw()
        
        self.top = tk.Toplevel(self.root)
        self.top.attributes('-alpha', 0.3)
        self.top.attributes('-fullscreen', True)
        self.top.attributes('-topmost', True)
        self.top.config(cursor="cross")

        self.canvas = tk.Canvas(self.top, cursor="cross", bg="black")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        color = "red" if self.current_selection_type == 'MAU' else "blue"
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline=color, width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        global REGION_MAU, REGION_NHAN_VAT
        end_x, end_y = event.x, event.y
        
        region_data = {
            "top": min(self.start_y, end_y), 
            "left": min(self.start_x, end_x), 
            "width": abs(self.start_x - end_x), 
            "height": abs(self.start_y - end_y)
        }
        
        if self.current_selection_type == 'MAU':
            REGION_MAU = region_data
            self.btn_mau.config(text="✓ Đã chọn vùng Máu", bg="#27ae60")
        elif self.current_selection_type == 'NHANVAT':
            REGION_NHAN_VAT = region_data
            self.btn_nhan_vat.config(text="✓ Đã chọn vùng Nhân Vật", bg="#27ae60")
            
        self.top.destroy()
        self.root.deiconify()
        
        if REGION_MAU and REGION_NHAN_VAT:
            self.update_status("Sẵn sàng cày cuốc!", "#f1c40f")

    def start_bot(self):
        global bot_is_running
        if not REGION_MAU or not REGION_NHAN_VAT:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng khoanh đủ 2 vùng quét trước khi Bắt Đầu!")
            return
            
        if not bot_is_running:
            bot_is_running = True
            self.btn_start.config(state="disabled")
            self.update_status("Khởi động...", "#2ecc71")
            threading.Thread(target=self.bot_logic, daemon=True).start()

    def stop_bot(self):
        global bot_is_running
        bot_is_running = False
        self.btn_start.config(state="normal")
        self.update_status("Đã dừng Bot.", "#e74c3c")

    def bot_logic(self):
        global bot_is_running
        
        while bot_is_running:
            self.update_status("Đang quăng cần...", "#3498db")
            pydirectinput.mouseDown()
            time.sleep(0.55) 
            pydirectinput.mouseUp()
            
            self.update_status("Đang chờ cá cắn...", "#f39c12")
            da_vao_chien_dau = False
            
            while bot_is_running:
                # TRUYỀN TÊN FILE DEBUG VÀO ĐÂY ĐỂ XEM BOT NHÌN GÌ
                if find_image(tpl_cham_than, REGION_NHAN_VAT, CONFIDENCE_QTE, "debug_nhan_vat.png"):
                    self.update_status("!! CÁ CẮN CÂU !!", "#e67e22")
                    pydirectinput.click() 
                    
                    thoi_gian_cho = 0
                    while bot_is_running and thoi_gian_cho < 3.0:
                        # Truyền file debug để xem vùng máu
                        if find_image(tpl_thanh_mau, REGION_MAU, CONFIDENCE_MAU, "debug_thanh_mau.png"):
                            da_vao_chien_dau = True
                            break
                        time.sleep(0.1)
                        thoi_gian_cho += 0.1
                    break
                    
                elif find_image(tpl_thanh_mau, REGION_MAU, CONFIDENCE_MAU):
                    da_vao_chien_dau = True
                    break
                    
                time.sleep(0.05)
                
            if not bot_is_running: break
            
            if da_vao_chien_dau:
                self.update_status("Đang chiến đấu!!", "#e74c3c")
                
                while bot_is_running and find_image(tpl_thanh_mau, REGION_MAU, CONFIDENCE_MAU):
                    if find_image(tpl_w, REGION_NHAN_VAT, CONFIDENCE_QTE): pydirectinput.press('w')
                    elif find_image(tpl_a, REGION_NHAN_VAT, CONFIDENCE_QTE): pydirectinput.press('a')
                    elif find_image(tpl_d, REGION_NHAN_VAT, CONFIDENCE_QTE): pydirectinput.press('d')
                    
                    pydirectinput.click()
                    pydirectinput.press('z')
                    pydirectinput.press('x')
                    pydirectinput.press('c')
                    pydirectinput.press('v')
            else:
                self.update_status("Lỗi: Mất dấu cá", "#c0392b")
                time.sleep(1)
                    
            self.update_status("Chờ reset...", "#95a5a6")
            time.sleep(3.5)

if __name__ == "__main__":
    root = tk.Tk()
    app = FishingApp(root)
    root.mainloop()