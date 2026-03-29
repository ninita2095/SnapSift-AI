import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext
import threading
import os
import zipfile
import shutil
import base64
from pathlib import Path
from datetime import datetime
import imagehash
from PIL import Image
import anthropic

API_KEY = "YOUR_API_KEY_HERE"
HASH_SENSITIVITY = 5
MIN_FILE_SIZE = 50000
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG'}
client = anthropic.Anthropic(api_key=API_KEY)
def extract_date(filename):
    name = Path(filename).stem
    for part in name.split('-'):
        if len(part) == 8 and part.isdigit():
            try:
                date = datetime.strptime(part, "%Y%m%d")
                return date.strftime("%Y"), date.strftime("%B")
            except:
                pass
    return "Unknown_Year", "Unknown_Month"

def classify_photo(img_path):
    try:
        with open(img_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        suffix = img_path.suffix.lower()
        media_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                     '.png': 'image/png', '.webp': 'image/webp'}
        media_type = media_map.get(suffix, 'image/jpeg')
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": media_type, "data": image_data}},
                {"type": "text", "text": (
                    "Classify this image into exactly one of these categories:\n"
                    "KEEP - real personal photo: people, events, food, pets, travel, places\n"
                    "DISCARD - not personal: memes, screenshots, documents, ads, flyers, QR codes\n"
                    "REVIEW - uncertain: doors, hallways, delivery photos, ambiguous locations\n"
                    "Reply with ONLY one word: KEEP, DISCARD, or REVIEW"
                )}
            ]}]
        )
        result = response.content[0].text.strip().upper()
        if result not in ["KEEP", "DISCARD", "REVIEW"]:
            result = "REVIEW"
        return result
    except Exception as e:
        if "credit" in str(e).lower() or "billing" in str(e).lower() or "400" in str(e):
            return "CREDIT_ERROR"
        return "REVIEW"

def organize_photo(img_path, classification, output_folder):
    year, month = extract_date(img_path.name)
    if classification == "KEEP":
        dest_dir = Path(output_folder) / "PHOTOS" / year / f"{month} {year}"
    elif classification == "DISCARD":
        dest_dir = Path(output_folder) / "DISCARDED"
    else:
        dest_dir = Path(output_folder) / "REVIEW"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / img_path.name
    if dest_file.exists():
        if img_path.stat().st_size > dest_file.stat().st_size:
            dest_file.unlink()
            shutil.copy2(img_path, dest_file)
        return
    shutil.copy2(img_path, dest_file)
def run_pipeline(zip_path, log, progress_var, progress_label, start_btn, open_btn, output_ref):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_folder = str(Path.home() / "Desktop" / f"SnapSift_Output_{timestamp}")
        output_ref.append(output_folder)

        def log_msg(msg):
            log.insert(tk.END, msg)
            log.see(tk.END)
            log.update()

        log_msg("\n📦 Extracting ZIP...\n")
        extract_dir = Path("temp_snapsift")
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_dir)

        log_msg("🔍 Filtering images...\n")
        images = [
            f for f in extract_dir.rglob("*")
            if f.is_file()
            and f.suffix in IMAGE_EXTENSIONS
            and f.stat().st_size >= MIN_FILE_SIZE
        ]
        log_msg(f"✅ Found {len(images)} images\n")

        log_msg("🔄 Detecting duplicates...\n")
        seen_hashes = {}
        unique = []
        dupes = 0
        for img_path in images:
            try:
                with Image.open(img_path) as img:
                    h = imagehash.phash(img)
                is_dup = any(abs(h - sh) <= HASH_SENSITIVITY for sh in seen_hashes)
                if not is_dup:
                    seen_hashes[h] = img_path
                    unique.append(img_path)
                else:
                    dupes += 1
            except:
                pass
        log_msg(f"✅ Unique: {len(unique)} | Duplicates removed: {dupes}\n\n")

        total = len(unique)
        stats = {"kept": 0, "discarded": 0, "review": 0}
        start_time = datetime.now()
        log_msg(f"🤖 Classifying {total} photos with Claude Vision...\n\n")

        for i, img_path in enumerate(unique, 1):
            classification = classify_photo(img_path)
            if classification == "CREDIT_ERROR":
                log_msg(f"\n⚠️  API credits exhausted after {i-1} photos\n")
                log_msg(f"✅ {stats['kept']} kept | ❌ {stats['discarded']} discarded\n")
                log_msg(f"📁 Remaining {total-i+1} photos moved to REVIEW\n")
                for remaining in unique[i-1:]:
                    organize_photo(remaining, "REVIEW", output_folder)
                break
            organize_photo(img_path, classification, output_folder)
            key = {"KEEP": "kept", "DISCARD": "discarded", "REVIEW": "review"}[classification]
            stats[key] += 1
            pct = int((i / total) * 100)
            progress_var.set(pct)
            progress_label.config(text=f"{i}/{total} — {img_path.name} → {classification}")
            log_msg(f"  {i}/{total} — {img_path.name} → {classification}\n")

        elapsed = str(datetime.now() - start_time).split('.')[0]
        log_msg("\n" + "=" * 45 + "\n")
        log_msg("  📊 RESULTS\n")
        log_msg("=" * 45 + "\n")
        log_msg(f"  ✅ Kept       : {stats['kept']}\n")
        log_msg(f"  ❌ Discarded  : {stats['discarded']}\n")
        log_msg(f"  ⚠️  Review     : {stats['review']}\n")
        log_msg(f"  🔄 Duplicates : {dupes}\n")
        log_msg(f"  ⏱️  Time       : {elapsed}\n")
        log_msg(f"\n✅ Done! Results saved to Desktop:\n{Path(output_folder).name}\n")
        shutil.rmtree(extract_dir, ignore_errors=True)
        start_btn.config(state=tk.NORMAL)
        open_btn.config(state=tk.NORMAL)

    except Exception as e:
        log.insert(tk.END, f"\n❌ Error: {e}\n")
        log.see(tk.END)
        start_btn.config(state=tk.NORMAL)
class SnapSiftApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SnapSift AI — Intelligent Photo Organizer")
        self.root.geometry("700x620")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")
        self.zip_path = None
        self.output_ref = []
        self.build_ui()

    def build_ui(self):
        tk.Label(self.root, text="📸 SnapSift AI",
                 font=("Arial", 22, "bold"),
                 bg="#1e1e2e", fg="#89b4fa").pack(pady=(20, 2))
        tk.Label(self.root, text="Intelligent Photo Organizer",
                 font=("Arial", 11),
                 bg="#1e1e2e", fg="#a6adc8").pack(pady=(0, 16))
        frame = tk.Frame(self.root, bg="#1e1e2e")
        frame.pack(padx=20, fill=tk.X)
        self.zip_label = tk.Label(frame, text="  No ZIP file selected",
                                   font=("Arial", 10),
                                   bg="#313244", fg="#cdd6f4",
                                   anchor="w", padx=10, pady=8)
        self.zip_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(frame, text="Browse ZIP",
                  command=self.browse_zip,
                  bg="#89b4fa", fg="#1e1e2e",
                  font=("Arial", 10, "bold"),
                  relief="flat", padx=12, pady=6,
                  cursor="hand2").pack(side=tk.RIGHT, padx=(8, 0))
        prog_frame = tk.Frame(self.root, bg="#1e1e2e")
        prog_frame.pack(padx=20, pady=(12, 0), fill=tk.X)
        self.progress_var = tk.IntVar()
        ttk.Progressbar(prog_frame, variable=self.progress_var,
                        maximum=100, length=660).pack(fill=tk.X)
        self.progress_label = tk.Label(prog_frame, text="Ready",
                                        font=("Arial", 9),
                                        bg="#1e1e2e", fg="#a6adc8")
        self.progress_label.pack(anchor="w", pady=(2, 0))
        self.log = scrolledtext.ScrolledText(
            self.root, height=18,
            font=("Courier", 9),
            bg="#181825", fg="#cdd6f4",
            relief="flat")
        self.log.pack(padx=20, pady=12, fill=tk.BOTH, expand=True)
        self.log.insert(tk.END, "Welcome to SnapSift AI!\n")
        self.log.insert(tk.END, "1. Click 'Browse ZIP' to select your photos ZIP file\n")
        self.log.insert(tk.END, "2. Click 'Start' to begin processing\n")
        self.log.insert(tk.END, "3. Results will be saved to your Desktop\n\n")
        btn_frame = tk.Frame(self.root, bg="#1e1e2e")
        btn_frame.pack(pady=(0, 16))
        self.start_btn = tk.Button(btn_frame, text="▶  Start Processing",
                                    command=self.start_processing,
                                    bg="#a6e3a1", fg="#1e1e2e",
                                    font=("Arial", 12, "bold"),
                                    relief="flat", padx=20, pady=8,
                                    cursor="hand2")
        self.start_btn.pack(side=tk.LEFT, padx=8)
        self.open_btn = tk.Button(btn_frame, text="📁 Open Results",
                                   command=self.open_results,
                                   bg="#313244", fg="#cdd6f4",
                                   font=("Arial", 12),
                                   relief="flat", padx=20, pady=8,
                                   cursor="hand2", state=tk.DISABLED)
        self.open_btn.pack(side=tk.LEFT, padx=8)

    def browse_zip(self):
        path = filedialog.askopenfilename(filetypes=[("ZIP files", "*.zip")])
        if path:
            self.zip_path = path
            self.zip_label.config(text=f"  {Path(path).name}")

    def start_processing(self):
        if not self.zip_path:
            self.log.insert(tk.END, "⚠️  Please select a ZIP file first!\n")
            return
        self.output_ref.clear()
        self.start_btn.config(state=tk.DISABLED)
        self.open_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        thread = threading.Thread(
            target=run_pipeline,
            args=(self.zip_path, self.log, self.progress_var,
                  self.progress_label, self.start_btn,
                  self.open_btn, self.output_ref))
        thread.daemon = True
        thread.start()

    def open_results(self):
        import subprocess
        if self.output_ref:
            output = Path(self.output_ref[0])
            if output.exists():
                subprocess.run(["open", str(output)])

if __name__ == "__main__":
    root = tk.Tk()
    app = SnapSiftApp(root)
    root.mainloop()
