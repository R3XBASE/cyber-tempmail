#!/usr/bin/env python3

import requests
import json
import random
import string
import os
import time
import threading
import re
import sys
from datetime import datetime, timedelta
import hashlib

# Warna untuk output terminal (Cyberpunk Neon Palette)
R = '\033[31m'  # Neon Red
G = '\033[32m'  # Neon Green
C = '\033[36m'  # Neon Cyan
W = '\033[0m'   # Reset
Y = '\033[33m'  # Neon Yellow
B = '\033[34m'  # Neon Blue
P = '\033[35m'  # Neon Purple
N = '\033[90m'  # Dark Gray (untuk efek shadow)

# File penyimpanan email
EMAIL_STORAGE = "temp_emails.json"

# API Endpoints dan konfigurasi
SERVICES = {
    "mail.tm": {
        "base_url": "https://api.mail.tm",
        "headers": {"Content-Type": "application/json"},
        "timeout": None  # Tidak ada batas waktu spesifik
    },
    "guerrillamail": {
        "base_url": "https://api.guerrillamail.com",
        "headers": {},
        "timeout": 3600  # 60 menit dalam detik
    },
    "tempmailo": {
        "base_url": "https://api.tempmailo.com",
        "headers": {},
        "timeout": 172800  # 2 hari dalam detik
    }
    # Temp-Mail.org dihapus karena tidak stabil
}

class TempMail:
    def __init__(self):
        self.email_data = {}
        self.load_emails()

    def generate_random_string(self, length=10):
        """Menghasilkan string acak untuk bagian lokal email."""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def create_account(self):
        """Membuat akun email sementara dari layanan acak."""
        service = random.choice(list(SERVICES.keys()))
        email = None
        created_at = int(time.time())

        try:
            if service == "mail.tm":
                local_part = self.generate_random_string()
                domain = self.get_random_domain(service)
                email = f"{local_part}@{domain}"
                password = self.generate_random_string(12)
                payload = {"address": email, "password": password}
                response = requests.post(f"{SERVICES[service]['base_url']}/accounts", json=payload, headers=SERVICES[service]["headers"], timeout=10)
                if response.status_code == 201:
                    self.email_data[email] = {"service": service, "password": password, "id": response.json()["id"], "created_at": created_at}
            
            elif service == "guerrillamail":
                response = requests.get(f"{SERVICES[service]['base_url']}/ajax.php?f=get_email_address", headers=SERVICES[service]["headers"], timeout=10)
                if response.status_code == 200:
                    email = response.json()["email_addr"]
                    self.email_data[email] = {"service": service, "sid_token": response.json()["sid_token"], "created_at": created_at}
            
            elif service == "tempmailo":
                local_part = self.generate_random_string()
                domain = "tempmailo.com"
                email = f"{local_part}@{domain}"
                self.email_data[email] = {"service": service, "created_at": created_at}

            if email:
                self.save_emails()
                return email, service
            raise Exception(f"Failed to create email with {service}")
        except (requests.exceptions.RequestException, Exception) as e:
            print(f"{R}[-] Error creating email with {service}: {str(e)}{W}")
            return None, None

    def get_random_domain(self, service):
        """Mengambil domain acak dari layanan tertentu."""
        response = requests.get(f"{SERVICES[service]['base_url']}/domains", headers=SERVICES[service]["headers"], timeout=10)
        if response.status_code == 200:
            domains = response.json()["hydra:member"]
            return random.choice(domains)["domain"]
        raise Exception(f"Failed to fetch domains for {service}")

    def authenticate(self, email):
        """Login ke akun email (hanya untuk mail.tm)."""
        if email not in self.email_data or self.email_data[email].get("service", "mail.tm") != "mail.tm":
            return False
        try:
            payload = {"address": email, "password": self.email_data[email]["password"]}
            response = requests.post(f"{SERVICES['mail.tm']['base_url']}/token", json=payload, headers=SERVICES["mail.tm"]["headers"], timeout=10)
            if response.status_code == 200:
                SERVICES["mail.tm"]["headers"]["Authorization"] = f"Bearer {response.json()['token']}"
                return True
        except requests.exceptions.RequestException:
            return False
        return False

    def check_inbox(self, email):
        """Memeriksa inbox berdasarkan layanan."""
        service = self.email_data[email].get("service", "mail.tm")
        try:
            if service == "mail.tm":
                if not self.authenticate(email):
                    return None
                response = requests.get(f"{SERVICES[service]['base_url']}/messages", headers=SERVICES[service]["headers"], timeout=10)
                return response.json()["hydra:member"] if response.status_code == 200 else []
            
            elif service == "guerrillamail":
                sid_token = self.email_data[email]["sid_token"]
                response = requests.get(f"{SERVICES[service]['base_url']}/ajax.php?f=check_email&seq=0&sid_token={sid_token}", headers=SERVICES[service]["headers"], timeout=10)
                return response.json()["list"] if response.status_code == 200 else []
            
            elif service == "tempmailo":
                return []  # Placeholder, bisa diganti dengan scraping jika diperlukan
            
            return []
        except requests.exceptions.RequestException as e:
            print(f"{R}[-] Error checking inbox with {service}: {str(e)}{W}")
            return []

    def get_message_content(self, email, message_id):
        """Mengambil isi pesan berdasarkan layanan."""
        service = self.email_data[email].get("service", "mail.tm")
        try:
            if service == "mail.tm":
                response = requests.get(f"{SERVICES[service]['base_url']}/messages/{message_id}", headers=SERVICES[service]["headers"], timeout=10)
                return response.json() if response.status_code == 200 else None
            elif service in ["guerrillamail", "tempmailo"]:
                return message_id  # Langsung kembalikan pesan dari check_inbox
            return None
        except requests.exceptions.RequestException:
            return None

    def delete_email(self, email):
        """Menghapus email dari penyimpanan."""
        if email in self.email_data:
            del self.email_data[email]
            self.save_emails()
            return True
        return False

    def save_emails(self):
        """Menyimpan email ke file JSON."""
        with open(EMAIL_STORAGE, 'w') as f:
            json.dump(self.email_data, f, indent=4)

    def load_emails(self):
        """Memuat daftar email dari file JSON."""
        if os.path.exists(EMAIL_STORAGE):
            with open(EMAIL_STORAGE, 'r') as f:
                try:
                    self.email_data = json.load(f)
                    for email in self.email_data:
                        if "service" not in self.email_data[email]:
                            self.email_data[email]["service"] = "mail.tm"
                    self.save_emails()
                except json.JSONDecodeError:
                    self.email_data = {}
        else:
            self.email_data = {}

def clear_screen():
    """Membersihkan layar terminal."""
    os.system('clear')

def loading_animation(text, duration=2):
    """Animasi loading cyberpunk."""
    animation = ['[■□□□□]', '[■■□□□]', '[■■■□□]', '[■■■■□]', '[■■■■■]']
    end_time = time.time() + duration
    while time.time() < end_time:
        for char in animation:
            sys.stdout.write(f'\r{P}[CYBERLINK] {text} {C}{char}{W}')
            sys.stdout.flush()
            time.sleep(0.1)
    sys.stdout.write(f'\r{P}[CYBERLINK] {text} {G}ONLINE{W}\n')
    sys.stdout.flush()

def glitch_effect(text):
    """Efek glitch sederhana untuk teks."""
    return f"{R}{text[:3]}{G}{text[3:]}{W}"

def get_remaining_time(email_data, email):
    """Menghitung waktu tersisa berdasarkan layanan."""
    service = email_data[email].get("service", "mail.tm")
    created_at = email_data[email].get("created_at", int(time.time()))
    timeout = SERVICES[service]["timeout"]
    if timeout:
        expires_at = created_at + timeout
        remaining = max(0, expires_at - int(time.time()))
        hours, remainder = divmod(remaining, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    return "Unknown"

def display_header():
    """Menampilkan header cyberpunk dengan waktu real-time."""
    clear_screen()
    current_time = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
    header = f"""
{B}┌──[ {P}TEMPMAIL BY R3XBASE {B}]──────────────────┐{W}
{N}│ {C}Neon Grid Online | Cybernode Active       {N}│{W}
{B}│ {Y}System Time: {W}{current_time} {N}          │{W}
{B}└──────────────────────────────────────────┘{W}
    """
    print(header)

def display_menu():
    """Menampilkan menu dengan gaya cyberpunk."""
    display_header()
    print(f"{C}┌──[ {Y}NEON CORE OPTIONS {C}]─────────────┐{W}")
    print(f"{G}│ [1] {W}Spawn New Datastream (Email)    {G}│{W}")
    print(f"{G}│ [2] {W}Access Stored Nodes (List)      {G}│{W}")
    print(f"{G}│ [3] {W}Scan Inbox (Manual Hack)        {G}│{W}")
    print(f"{G}│ [4] {W}Real-Time Grid Scan (Live)      {G}│{W}")
    print(f"{G}│ [5] {W}Purge Node (Delete Email)       {G}│{W}")
    print(f"{G}│ [6] {W}Disconnect from Matrix (Exit)   {G}│{W}")
    print(f"{C}└──────────────────────────────────┘{W}")

def main():
    tempmail = TempMail()
    running = False

    def check_inbox_real_time(email):
        """Fungsi untuk memeriksa inbox secara real-time."""
        while running:
            messages = tempmail.check_inbox(email)
            clear_screen()
            display_header()
            remaining_time = get_remaining_time(tempmail.email_data, email)
            print(f"{Y}[!] Accessing grid for: {W}{glitch_effect(email)} {Y}[Time Left: {remaining_time}]{W}")
            if messages:
                print(f"{G}[+] Decrypted signals: {len(messages)}{W}")
                for msg in messages:
                    content = tempmail.get_message_content(email, msg if tempmail.email_data[email]["service"] != "mail.tm" else msg["id"])
                    if content:
                        from_addr = content["from"]["address"] if tempmail.email_data[email]["service"] == "mail.tm" else content.get("mail_from", "Unknown")
                        subject = content["subject"] if tempmail.email_data[email]["service"] == "mail.tm" else content.get("mail_subject", "No Subject")
                        body = content.get("text", "No text content") if tempmail.email_data[email]["service"] == "mail.tm" else content.get("mail_text", "No content")
                        otp = re.search(r'\b\d{6}\b', body)
                        otp_text = f"{P}DECRYPTED KEY: {otp.group()}{W}" if otp else f"{Y}No key detected{W}"
                        print(f"\n{C}┌──[ {G}DATASTREAM {C}]──────┐{W}")
                        print(f"{C}│ {G}Origin: {W}{from_addr}")
                        print(f"{C}│ {G}Header: {W}{subject}")
                        print(f"{C}│ {otp_text}")
                        print(f"{C}│ {G}Payload: {W}{body[:200]}...")
                        print(f"{C}└────────────────────┘{W}")
            else:
                print(f"{Y}[!] Grid silent - no signals detected.{W}")
            print(f"\n{Y}[Disconnect with Ctrl+C]{W}")
            time.sleep(5)

    while True:
        display_menu()
        choice = input(f"{G}[//] {W}Input command: ")

        if choice == "1":
            display_header()
            print(f"{P}[*] Spawning new datastream...{W}")
            loading_animation("Initializing Node")
            email, service = tempmail.create_account()
            if email:
                remaining_time = get_remaining_time(tempmail.email_data, email)
                print(f"{G}[+] Datastream live: {W}{glitch_effect(email)} {Y}[Service: {service} | Time Left: {remaining_time}]{W}")
            else:
                print(f"{R}[-] Failed to spawn datastream.{W}")
            time.sleep(2)

        elif choice == "2":
            display_header()
            emails = list(tempmail.email_data.keys())
            if not emails:
                print(f"{Y}[!] No nodes in memory.{W}")
            else:
                print(f"{C}┌──[ {Y}STORED NODES {C}]──────────┐{W}")
                for i, email in enumerate(emails, 1):
                    remaining_time = get_remaining_time(tempmail.email_data, email)
                    print(f"{G}│ [{i}] {W}{email} {Y}[Time Left: {remaining_time}]{G}│{W}")
                print(f"{C}└──────────────────────────┘{W}")
            input(f"{G}[//] Press Enter to return...{W}")

        elif choice == "3":
            display_header()
            emails = list(tempmail.email_data.keys())
            if not emails:
                print(f"{Y}[!] No nodes in memory.{W}")
            else:
                print(f"{C}┌──[ {Y}STORED NODES {C}]──────────┐{W}")
                for i, email in enumerate(emails, 1):
                    remaining_time = get_remaining_time(tempmail.email_data, email)
                    print(f"{G}│ [{i}] {W}{email} {Y}[Time Left: {remaining_time}]{G}│{W}")
                print(f"{C}└──────────────────────────┘{W}")
                try:
                    selection = int(input(f"{G}[//] {W}Select node: ")) - 1
                    selected_email = emails[selection]
                    loading_animation(f"Scanning {selected_email}")
                    messages = tempmail.check_inbox(selected_email)
                    if messages:
                        print(f"{G}[+] Decrypted signals: {len(messages)}{W}")
                        for msg in messages:
                            content = tempmail.get_message_content(selected_email, msg if tempmail.email_data[selected_email]["service"] != "mail.tm" else msg["id"])
                            if content:
                                from_addr = content["from"]["address"] if tempmail.email_data[selected_email]["service"] == "mail.tm" else content.get("mail_from", "Unknown")
                                subject = content["subject"] if tempmail.email_data[selected_email]["service"] == "mail.tm" else content.get("mail_subject", "No Subject")
                                body = content.get("text", "No text content") if tempmail.email_data[selected_email]["service"] == "mail.tm" else content.get("mail_text", "No content")
                                otp = re.search(r'\b\d{6}\b', body)
                                otp_text = f"{P}DECRYPTED KEY: {otp.group()}{W}" if otp else f"{Y}No key detected{W}"
                                print(f"\n{C}┌──[ {G}DATASTREAM {C}]──────┐{W}")
                                print(f"{C}│ {G}Origin: {W}{from_addr}")
                                print(f"{C}│ {G}Header: {W}{subject}")
                                print(f"{C}│ {otp_text}")
                                print(f"{C}│ {G}Payload: {W}{body[:200]}...")
                                print(f"{C}└────────────────────┘{W}")
                    else:
                        print(f"{Y}[!] Grid silent - no signals detected.{W}")
                except (ValueError, IndexError):
                    print(f"{R}[-] Invalid node selection.{W}")
            input(f"{G}[//] Press Enter to return...{W}")

        elif choice == "4":
            display_header()
            emails = list(tempmail.email_data.keys())
            if not emails:
                print(f"{Y}[!] No nodes in memory.{W}")
            else:
                print(f"{C}┌──[ {Y}STORED NODES {C}]──────────┐{W}")
                for i, email in enumerate(emails, 1):
                    remaining_time = get_remaining_time(tempmail.email_data, email)
                    print(f"{G}│ [{i}] {W}{email} {Y}[Time Left: {remaining_time}]{G}│{W}")
                print(f"{C}└──────────────────────────┘{W}")
                try:
                    selection = int(input(f"{G}[//] {W}Select node: ")) - 1
                    selected_email = emails[selection]
                    loading_animation(f"Connecting to {selected_email}")
                    running = True
                    thread = threading.Thread(target=check_inbox_real_time, args=(selected_email,))
                    thread.start()
                    thread.join()
                except (ValueError, IndexError):
                    print(f"{R}[-] Invalid node selection.{W}")
                except KeyboardInterrupt:
                    running = False
                    print(f"{G}[+] Disconnected from grid.{W}")
                    time.sleep(1)

        elif choice == "5":
            display_header()
            emails = list(tempmail.email_data.keys())
            if not emails:
                print(f"{Y}[!] No nodes in memory.{W}")
            else:
                print(f"{C}┌──[ {Y}STORED NODES {C}]──────────┐{W}")
                for i, email in enumerate(emails, 1):
                    remaining_time = get_remaining_time(tempmail.email_data, email)
                    print(f"{G}│ [{i}] {W}{email} {Y}[Time Left: {remaining_time}]{G}│{W}")
                print(f"{C}└──────────────────────────┘{W}")
                try:
                    selection = int(input(f"{G}[//] {W}Select node to purge: ")) - 1
                    selected_email = emails[selection]
                    loading_animation(f"Purging {selected_email}")
                    if tempmail.delete_email(selected_email):
                        print(f"{G}[+] Node purged: {W}{glitch_effect(selected_email)}")
                    else:
                        print(f"{R}[-] Failed to purge node.{W}")
                except (ValueError, IndexError):
                    print(f"{R}[-] Invalid node selection.{W}")
            time.sleep(2)

        elif choice == "6":
            display_header()
            print(f"{G}[+] Shutting down Neon Grid...{W}")
            loading_animation("Disconnecting")
            print(f"{P}[CYBERLINK] {G}R3XBASE SYSTEM OFFLINE{W}")
            break

        else:
            display_header()
            print(f"{R}[-] Command rejected - invalid input.{W}")
            time.sleep(1)

if __name__ == "__main__":
    main()
