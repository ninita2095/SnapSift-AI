from dotenv import load_dotenv
load_dotenv()

#!/usr/bin/env python3
"""
SnapSift AI — Intelligent Photo Organizer
Filters, deduplicates, and organizes photos from any ZIP file
"""

import os
import sys
import zipfile
import shutil
import base64
import json
from pathlib import Path
from datetime import datetime
import imagehash
from PIL import Image
import anthropic
from config import ANTHROPIC_API_KEY, OUTPUT_FOLDER, HASH_SENSITIVITY, MIN_FILE_SIZE, IMAGE_EXTENSIONS, BATCH_SIZE

# Initialize Claude client
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─────────────────────────────────────────────
# CHECKPOINT — Save & Resume progress
# ─────────────────────────────────────────────
def load_checkpoint(zip_path):
    checkpoint_file = Path(f".checkpoint_{Path(zip_path).stem}.json")
    if checkpoint_file.exists():
        with open(checkpoint_file) as f:
            data = json.load(f)
        print(f"📌 Resuming from checkpoint — {len(data)} photos already processed")
        return data, checkpoint_file
    return {}, checkpoint_file

def save_checkpoint(checkpoint_file, data):
    with open(checkpoint_file, 'w') as f:
        json.dump(data, f)

# ─────────────────────────────────────────────
# STEP 1 — Extract ZIP
# ─────────────────────────────────────────────
def extract_zip(zip_path):
    print(f"\n📦 Extracting ZIP: {zip_path}")
    extract_dir = Path("temp_photos")
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    print(f"✅ Extracted to {extract_dir}")
    return extract_dir

# ─────────────────────────────────────────────
# STEP 2 — Filter images only + min size
# ─────────────────────────────────────────────
def filter_images(folder):
    print(f"\n🔍 Filtering image files...")
    all_files = list(folder.rglob("*"))
    images = []
    skipped = 0
    for f in all_files:
        if f.is_file() and f.suffix in IMAGE_EXTENSIONS:
            if f.stat().st_size >= MIN_FILE_SIZE:
                images.append(f)
            else:
                skipped += 1
    print(f"✅ Found {len(images)} images | Skipped {skipped} small files (stickers/icons)")
    return images

# ─────────────────────────────────────────────
# STEP 3 — Remove duplicates (perceptual hash)
# ─────────────────────────────────────────────
def remove_duplicates(images):
    print(f"\n🔄 Detecting duplicates...")
    seen_hashes = {}
    unique = []
    duplicates = 0
    for img_path in images:
        try:
            with Image.open(img_path) as img:
                h = imagehash.phash(img)
            is_duplicate = False
            for seen_hash in seen_hashes:
                if abs(h - seen_hash) <= HASH_SENSITIVITY:
                    is_duplicate = True
                    duplicates += 1
                    break
            if not is_duplicate:
                seen_hashes[h] = img_path
                unique.append(img_path)
        except Exception as e:
            print(f"  ⚠️ Could not process {img_path.name}: {e}")
    print(f"✅ Unique photos: {len(unique)} | Duplicates removed: {duplicates}")
    return unique

# ─────────────────────────────────────────────
# STEP 4 — Extract date from filename
# ─────────────────────────────────────────────
def extract_date(filename):
    name = Path(filename).stem
    parts = name.split('-')
    for i, part in enumerate(parts):
        if len(part) == 8 and part.isdigit():
            try:
                date = datetime.strptime(part, "%Y%m%d")
                return date.strftime("%Y"), date.strftime("%B")
            except:
                pass
    return "Unknown_Year", "Unknown_Month"

# ─────────────────────────────────────────────
# STEP 5 — Classify photos with Claude Vision
# ─────────────────────────────────────────────
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
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": """Classify this image into exactly one of these categories:
KEEP — real personal photo taken by a person, including:
- People, family, friends, selfies
- Events, celebrations, gatherings
- Food, pets, travel, nature
- Places, buildings, rooms
- Any photo that captures a real personal moment or location

DISCARD — not a personal photo, including:
- Memes, viral images, jokes
- Screenshots of conversations or apps
- Flyers, advertisements, banners
- Greeting cards (Happy Birthday, etc.)
- QR codes, barcodes
- Formal documents (receipts, invoices, forms)
- News articles, political content

REVIEW — uncertain cases, including:
- Doors, hallways, entrances (with or without packages)
- Any photo without people that could be a delivery confirmation
- Any ambiguous location photo
- Delivery photos (packages, doors, boxes)

Reply with ONLY one word: KEEP, DISCARD, or REVIEW"""
                    }
                ],
            }]
        )
        result = response.content[0].text.strip().upper()
        if result not in ["KEEP", "DISCARD", "REVIEW"]:
            result = "REVIEW"
        return result
    except Exception as e:
        print(f"  ⚠️ Classification error for {img_path.name}: {e}")
        return "REVIEW"

# ─────────────────────────────────────────────
# STEP 6 — Organize into output folders
# ─────────────────────────────────────────────
def organize_photo(img_path, classification):
    year, month = extract_date(img_path.name)
    if classification == "KEEP":
        dest_dir = Path(OUTPUT_FOLDER) / "PHOTOS" / year / f"{month} {year}"
    elif classification == "DISCARD":
        dest_dir = Path(OUTPUT_FOLDER) / "DISCARDED"
    else:
        dest_dir = Path(OUTPUT_FOLDER) / "REVIEW"    

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / img_path.name
    if dest_file.exists():
        # Keep the larger file (better quality)
        if img_path.stat().st_size > dest_file.stat().st_size:
            dest_file.unlink()
            shutil.copy2(img_path, dest_file)
        # Skip the smaller duplicate silently
        return dest_dir
    shutil.copy2(img_path, dest_file)
    return dest_dir

# ─────────────────────────────────────────────
# STEP 7 — Generate AI summary
# ─────────────────────────────────────────────
def generate_summary(stats):
    print(f"\n🤖 Generating intelligent summary...")
    prompt = f"""You are analyzing results from SnapSift AI, a photo organizer.
Here are the processing statistics:
- Total photos processed: {stats['total']}
- Personal photos kept: {stats['kept']}
- Photos discarded (memes/docs/ads): {stats['discarded']}
- Photos sent to review: {stats['review']}
- Duplicates removed: {stats['duplicates']}
- Date range: {stats['date_range']}

Write a brief 3-sentence professional summary of these results for a portfolio.
Mention the ML concepts used: computer vision classification, perceptual hashing for deduplication, and LLM summarization."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  SnapSift AI — Intelligent Photo Organizer")
    print("=" * 50)
    start_time = datetime.now()
    # Get ZIP path
    if len(sys.argv) < 2:
        zip_path = input("\n📁 Enter the path to your ZIP file: ").strip()
    else:
        zip_path = sys.argv[1]

    if not Path(zip_path).exists():
        print(f"❌ File not found: {zip_path}")
        sys.exit(1)

    # Run pipeline
    extract_dir = extract_zip(zip_path)
    images = filter_images(extract_dir)
    total_original = len(images)

    unique_images = remove_duplicates(images)
    duplicates_removed = total_original - len(unique_images)

    # Classify each photo
    print(f"\n🤖 Classifying {len(unique_images)} photos with Claude Vision...")
    print("   (This may take a few minutes...)\n")

    stats = {"kept": 0, "discarded": 0, "review": 0,
             "total": len(unique_images), "duplicates": duplicates_removed,
             "date_range": ""}

    # Load checkpoint
    checkpoint_data, checkpoint_file = load_checkpoint(zip_path)

    dates = []
    for i, img_path in enumerate(unique_images, 1):
        # Skip already classified photos
        if img_path.name in checkpoint_data:
            classification = checkpoint_data[img_path.name]
            stats[{"keep":"kept","discard":"discarded","review":"review"}[classification.lower()]] += 1
            year, month = extract_date(img_path.name)
            if year != "Unknown_Year":
                dates.append(year)
            bar = "█" * int((i / len(unique_images)) * 20)
            print(f"  [{bar:<20}] {i}/{len(unique_images)} — {img_path.name} → {classification} ⏭️ (cached)")
            continue
        try:
            classification = classify_photo(img_path)
        except Exception as e:
            if "credit" in str(e).lower() or "billing" in str(e).lower() or "400" in str(e):
                print(f"\n⚠️  API credits exhausted after {i-1} photos")
                print(f"   ✅ {stats['kept']} photos classified and saved to PHOTOS/")
                print(f"   ❌ {stats['discarded']} discarded")
                print(f"   📁 Remaining {len(unique_images)-i+1} photos moved to REVIEW/")
                for remaining in unique_images[i-1:]:
                    organize_photo(remaining, "REVIEW")
                break
            else:
                classification = "REVIEW"
        organize_photo(img_path, classification)
        stats[{"keep":"kept","discard":"discarded","review":"review"}[classification.lower()]] += 1
        year, month = extract_date(img_path.name)
        if year != "Unknown_Year":
            dates.append(year)
        bar = "█" * int((i / len(unique_images)) * 20)
        print(f"  [{bar:<20}] {i}/{len(unique_images)} — {img_path.name} → {classification}")
        # Save to checkpoint
        checkpoint_data[img_path.name] = classification
        save_checkpoint(checkpoint_file, checkpoint_data)

    # Date range
    if dates:
        stats["date_range"] = f"{min(dates)} to {max(dates)}"

    # Summary
    print("\n" + "=" * 50)
    print("  📊 RESULTS")
    print("=" * 50)
    print(f"  Total processed : {stats['total']}")
    print(f"  ✅ Kept         : {stats['kept']}")
    print(f"  ❌ Discarded    : {stats['discarded']}")
    print(f"  ⚠️  Review       : {stats['review']}")
    print(f"  🔄 Duplicates   : {stats['duplicates']}")
    print(f"  📅 Date range   : {stats['date_range']}")

    summary = generate_summary(stats)
    print(f"\n🤖 AI Summary:\n{summary}")

    # Save summary to file
    summary_path = Path(OUTPUT_FOLDER) / "summary.txt"
    with open(summary_path, "w") as f:
        f.write(f"SnapSift AI — Processing Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Total: {stats['total']} | Kept: {stats['kept']} | ")
        f.write(f"Discarded: {stats['discarded']} | Review: {stats['review']}\n\n")
        f.write(summary)

    # Cleanup temp folder
    shutil.rmtree(extract_dir)
    print(f"\n✅ Done! Results saved to: {OUTPUT_FOLDER}/")
    elapsed = datetime.now() - start_time
    print(f"  ⏱️  Time elapsed : {str(elapsed).split('.')[0]}")
    print("=" * 50)

if __name__ == "__main__":
    main()
