import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import pandas as pd
import time
import urllib.parse
import threading

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import sqlite3
import datetime


# ===== Glass Theme Colors =====
GLASS_BG = "#96608c"
GLASS_CARD = "#a690b4"
GLASS_BORDER = "#4b3d57"

PRIMARY = "#4C5E74"          # WhatsApp green
PRIMARY_HOVER = "#519be1"

TEXT_MAIN = "#1e1e1e"
TEXT_MUTED = "#6b7280"

SUCCESS = "#4CAF50"
ERROR = "#E53935"



# ---------------- Driver ----------------
def init_driver(headless=False):
    options = webdriver.ChromeOptions()
    options.add_argument(r"--user-data-dir=C:\chrome-whatsapp-profile")
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get("https://web.whatsapp.com")
        return driver
    except Exception as e:
        print("[ERROR] Failed to start Chrome:", e)
        return None

def wait_for_login(driver, timeout=60):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true']"))
        )
        return True
    except:
        return False

# ---------------- Database ----------------
DB_FILE = "whatsapp_contacts.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            name TEXT,
            status TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_contact(phone, name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO contacts (phone, name, status) VALUES (?, ?, ?)",
                  (phone, name, "Pending"))
        conn.commit()
    except Exception as e:
        print("DB insert error:", e)
    conn.close()

def update_status(phone, status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE contacts SET status=?, timestamp=? WHERE phone=?", (status, timestamp, phone))
    conn.commit()
    conn.close()

# ---------------- Phone cleaning ----------------
def clean_phone(number_str):
    if pd.isna(number_str):
        return ""
    s = str(number_str)
    return "".join(ch for ch in s if ch.isdigit())

def normalize_number(number: str) -> str:
    number = number.strip().replace(" ", "").replace("-", "")
    if number.startswith("92") and len(number) == 12:
        return number
    if number.startswith("03") and len(number) == 11:
        return "92" + number[1:]
    if number.startswith("0") and len(number) >= 10:
        return "92" + number[1:]
    if number.startswith("3") and len(number) == 10:
        return "92" + number
    return number

# ---------------- WhatsApp ----------------
def send_message_to_number(driver, phone, encoded_message, log_callback):
    url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}"
    try:
        driver.get(url)
        chat_box = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true' and @data-tab='10']"))
        )
        time.sleep(0.5)
        chat_box.click()
        chat_box.send_keys(Keys.ENTER)
        time.sleep(0.5)
        # fallback send button
        try:
            send_btn = driver.find_element(By.XPATH, "//span[@data-icon='send']")
            send_btn.click()
        except:
            pass
        log_callback(f"✔ Sent to {phone}")
        return True
    except:
        log_callback(f"❌ Skipped invalid/failed number: {phone}")
        return False

# ---------------- GUI ----------------
class WhatsAppModernApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WhatsApp Bulk Messenger — Modern Edition")
        self.geometry("780x730")
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")  # base only (required)

        self.configure(fg_color=GLASS_BORDER)
        self.excel_path = ""

        # Header

        header = ctk.CTkLabel(
        self,
        text="WhatsApp Bulk Messaging App",
        font=("Poppins", 28, "bold"),
        text_color=TEXT_MAIN
    )
        header.pack(pady=12)
        # header = ctk.CTkLabel(self, text="WhatsApp Bulk Messaging App", font=("Poppins", 28, "bold"))
        # header.pack(pady=10)

        # File select
        file_frame = ctk.CTkFrame(
        self,
        fg_color=GLASS_CARD,
        border_color=GLASS_BORDER,
        border_width=1,
        corner_radius=18
    )
        file_frame.pack(pady=10, padx=20, fill="x")
        # file_frame = ctk.CTkFrame(self, corner_radius=15)
        # file_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(file_frame, text="Choose Excel File:", font=("Poppins", 14)).pack(pady=5)
        choose_button = ctk.CTkButton(
            file_frame,
            text="Browse File",
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color="white",
            corner_radius=16,
            width=200,
            command=self.choose_file
        )
        choose_button.pack(pady=5)
        # choose_button = ctk.CTkButton(file_frame, text="Browse File", command=self.choose_file, width=200)
        # choose_button.pack(pady=5)
        self.file_label = ctk.CTkLabel(file_frame, text="No file selected", text_color="black", font=("Poppins", 12))
        self.file_label.pack(pady=5)

        # Message box
        msg_frame = ctk.CTkFrame(
        self,
        fg_color=GLASS_CARD,
        border_color=GLASS_BORDER,
        border_width=1,
        corner_radius=18
    )
        msg_frame.pack(pady=10, padx=20, fill="both")
        # msg_frame = ctk.CTkFrame(self, corner_radius=15)
        # msg_frame.pack(pady=8, padx=20, fill="both")
        ctk.CTkLabel(msg_frame, text="Message Template:", font=("Poppins", 14)).pack(pady=5)
        self.message_box = ctk.CTkTextbox(
            msg_frame,
            height=80,
            width=300,
            corner_radius=16,
            fg_color="#f9fafb",
            text_color=TEXT_MAIN,
            border_color=GLASS_BORDER,
            border_width=1
        )
        self.message_box = ctk.CTkTextbox(msg_frame, height=80, width=300, corner_radius=12)
        self.message_box.insert("1.0", "Assalamualaikum {name},\nThis is an automated message.")
        self.message_box.pack(pady=10)

        # -------- Status Filter --------
        filter_frame = ctk.CTkFrame(
        self,
        fg_color=GLASS_CARD,
        border_color=GLASS_BORDER,
        border_width=1,
        corner_radius=18
    )
        filter_frame.pack(pady=10, padx=20, fill="x")
        # filter_frame = ctk.CTkFrame(self, corner_radius=15)
        # filter_frame.pack(pady=5, padx=20, fill="x")

        self.only_applied_var = ctk.BooleanVar(value=True)

        self.only_applied_checkbox = ctk.CTkCheckBox(
            filter_frame,
            text="Send messages only to contacts with status = 'Applied'",
            variable=self.only_applied_var,
            text_color=TEXT_MAIN,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER
        )

        # self.only_applied_checkbox = ctk.CTkCheckBox(
        #     filter_frame,
        #     text="Send messages only to contacts with status = 'Applied'",
        #     variable=self.only_applied_var
        # )
        self.only_applied_checkbox.pack(pady=10, padx=10, anchor="w")

        # Buttons
        send_button = ctk.CTkButton(
            self,
            text="Start Sending",
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color="white",
            font=("Poppins", 16, "bold"),
            height=42,
            corner_radius=18,
            command=self.start_sending_thread
        )
        send_button.pack(pady=10)
        # send_button = ctk.CTkButton(self, text="Start Sending", font=("Poppins", 16, "bold"),
        #                             command=self.start_sending_thread, height=35, corner_radius=10)
        # send_button.pack(pady=8)
        view_button = ctk.CTkButton(
            self,
            text="View Contacts & Status",
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color="white",
            font=("Poppins", 16, "bold"),
            height=42,
            corner_radius=18,
            command=self.show_contacts
        )
        view_button.pack(pady=10)
        # view_button = ctk.CTkButton(self, text="View Contacts & Status", font=("Poppins", 14, "bold"),
        #                              command=self.show_contacts, height=30, corner_radius=10)
        # view_button.pack(pady=3)

        # Log area
        log_frame = ctk.CTkFrame(
        self,
        fg_color=GLASS_CARD,
        border_color=GLASS_BORDER,
        border_width=1,
        corner_radius=18
    )
        log_frame.pack(pady=10, padx=20, fill="x")
        # log_frame = ctk.CTkFrame(self, corner_radius=15)
        # log_frame.pack(pady=10, padx=20, fill="both", expand=True)
        ctk.CTkLabel(log_frame, text="Log Output:", font=("Poppins", 14)).pack(pady=5)
        self.log_window = ctk.CTkTextbox(
        log_frame,
        height=400,
        width=700,
        corner_radius=16,
        fg_color="#f9fafb",
        text_color=TEXT_MAIN,
        border_color=GLASS_BORDER,
        border_width=1
    )
        self.log_window = ctk.CTkTextbox(log_frame, height=400, width=700)
        self.log_window.pack(padx=10, pady=3)

    # ---------------- GUI Methods ----------------
    def choose_file(self):
        self.excel_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if self.excel_path:
            self.file_label.configure(text=self.excel_path, text_color="white")

    def log(self, text):
        self.log_window.insert("end", text + "\n")
        self.log_window.see("end")
        self.update()

    def show_contacts(self):
        contacts_window = ctk.CTkToplevel(self)
        contacts_window.title("Contacts & Status")
        contacts_window.geometry("600x400")
        frame = ctk.CTkFrame(contacts_window, corner_radius=15)
        frame.pack(padx=10, pady=10, fill="both", expand=True)
        textbox = ctk.CTkTextbox(frame, width=580, height=350)
        textbox.pack(padx=10, pady=10, fill="both", expand=True)
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT phone, name, status, timestamp FROM contacts")
        rows = c.fetchall()
        conn.close()
        textbox.insert("0.0", f"{'Phone':<15}{'Name':<20}{'Status':<10}{'Timestamp':<20}\n")
        textbox.insert("0.0", "-"*70 + "\n")
        for row in rows:
            phone, name, status, timestamp = row
            timestamp = timestamp if timestamp else "-"
            textbox.insert("end", f"{phone:<15}{name:<20}{status:<10}{timestamp:<20}\n")
        textbox.configure(state="disabled")

    # ---------------- Thread ----------------
    def start_sending_thread(self):
        threading.Thread(target=self.start_sending, daemon=True).start()

    # ---------------- Sending ----------------
    def start_sending(self):
        if not self.excel_path:
            self.log("❌ Please select an Excel file first.")
            return

        message_template = self.message_box.get("1.0", "end").strip()

        try:
            df = pd.read_excel(self.excel_path)
        except:
            self.log("❌ Could not read Excel file.")
            return
        
        # Ensure number column exists
        if "number" not in df.columns:
            self.log("❌ Excel must have a 'number' column.")
            return

        # -------- STATUS FILTER LOGIC --------
        if self.only_applied_var.get():  # checkbox ON
            if "status" in df.columns:
                self.log("🔍 Filtering contacts with status = 'Applied'")
                df = df[df["status"].astype(str).str.strip().str.lower() == "applied"]
            else:
                self.log("⚠ No 'status' column found — sending to ALL numbers.")
        else:
            self.log("ℹ Status filter disabled — sending to ALL numbers.")

        df = df.reset_index(drop=True)

        if df.empty:
            self.log("❌ No contacts found after filtering.")
            return
        
        # Ensure 'number' and 'status' columns exist
        # if "number" not in df.columns or "status" not in df.columns:
        #     self.log("❌ Excel must have 'number' and 'status' columns.")
        #     return

        # # Filter only rows where status is 'Applied'
        # df = df[df["status"].str.strip().str.lower() == "applied"].reset_index(drop=True)

        # if df.empty:
        #     self.log("❌ No contacts with status 'Applied' found.")
        #     return

        # Clean and normalize numbers
        df["number"] = df["number"].apply(clean_phone).apply(normalize_number)
        df = df[df["number"] != ""].reset_index(drop=True)
        if df.empty:
            self.log("❌ No valid phone numbers after cleaning.")
            return
        
        if "WhatsApp Status" not in df.columns:
            df["WhatsApp Status"] = ""

        # Add contacts to DB
        for _, row in df.iterrows():
            phone = row["number"]
            name = row.get("name", "")
            add_contact(phone, name)

        # if "number" not in df.columns:
        #     self.log("❌ Excel missing 'number' column.")
        #     return

        # df["number"] = df["number"].apply(clean_phone).apply(normalize_number)
        # df = df[df["number"] != ""].reset_index(drop=True)
        # if df.empty:
        #     self.log("❌ No valid phone numbers.")
        #     return

        # # Add contacts to DB
        # for _, row in df.iterrows():
        #     phone = row["number"]
        #     name = row.get("name", "")
        #     add_contact(phone, name)

        # ---------------- Chrome Login ----------------
        self.log("🚀 Launching Chrome for login…")
        driver = init_driver(headless=False)
        if not driver:
            self.log("❌ Could not start Chrome.")
            return

        self.log("📱 Please scan QR if needed…")
        if not wait_for_login(driver, timeout=120):
            self.log("❌ Login failed or timeout.")
            driver.quit()
            return
        self.log("✅ Login successful!")
        driver.quit()

        # ---------------- Chrome Headless ----------------
        self.log("🚀 Relaunching Chrome in background (headless)…")
        driver = init_driver(headless=True)
        if not driver:
            self.log("❌ Could not start Chrome headless.")
            return
        self.log("✅ Chrome ready for sending…")

        # ---------------- Sending Loop ----------------
        for i, row in df.iterrows():
            phone = row["number"]
            name = row.get("name", "")

            # Skip already sent
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT status FROM contacts WHERE phone=?", (phone,))
            result = c.fetchone()
            conn.close()
            if result and result[0] == "Sent":
                self.log(f"⚠ Skipping {phone} — already sent.")
                continue

            try:
                msg = message_template.format(name=name)
            except:
                msg = message_template

            encoded = urllib.parse.quote(msg)
            self.log(f"➡ Sending to {phone} ({i+1}/{len(df)})…")
            success = send_message_to_number(driver, phone, encoded, self.log)

            if success:
                update_status(phone, "Sent")
                df.loc[i, "WhatsApp Status"] = ""  # leave blank for valid
            else:
                update_status(phone, "Failed")
                df.loc[i, "WhatsApp Status"] = "Invalid"  # mark invalid

            # Save Excel after each row (optional, safe)
            df.to_excel(self.excel_path, index=False)

            # encoded = urllib.parse.quote(msg)
            # self.log(f"➡ Sending to {phone} ({i+1}/{len(df)})…")
            # success = send_message_to_number(driver, phone, encoded, self.log)
            # if success:
            #     update_status(phone, "Sent")
            # else:
            #     update_status(phone, "Failed")
            time.sleep(4)

        self.log("🎉 All messages sent!")
        driver.quit()


# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    app = WhatsAppModernApp()
    app.mainloop()