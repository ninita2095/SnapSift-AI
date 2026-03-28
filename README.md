# SnapSift AI 📸

> AI-powered photo organizer — automatically filters, deduplicates, and organizes photos from any ZIP file.

## What it does

SnapSift AI takes a ZIP file of photos and:
- ✅ **Keeps** personal photos (people, events, travel, food, pets)
- ❌ **Discards** non-personal content (memes, screenshots, documents, ads)
- ⚠️ **Flags** ambiguous photos for manual review
- 🔄 **Removes** duplicate images using perceptual hashing
- 📁 **Organizes** kept photos by Year → Month
- 🤖 **Generates** an intelligent summary of results

## ML Concepts Demonstrated

| Concept | Implementation |
|---|---|
| Computer Vision | Claude Vision classifies each image |
| Supervised Learning | Pre-defined categories with prompt engineering |
| Similarity Detection | Perceptual hashing for deduplication |
| NLP / LLM | Claude generates processing summary |
| Data Pipeline | End-to-end: input → filter → classify → organize → report |

## Privacy First 🔒

All processing runs **locally on your machine**. Photos never leave your device — only the image data is sent to Claude API for classification, which Anthropic does not retain.

## How to Run

**1. Clone the repository**
```bash
git clone https://github.com/ninita2095/SnapSift-AI.git
cd SnapSift-AI
```

**2. Install dependencies**
```bash
pip3 install anthropic Pillow imagehash requests python-dotenv
```

**3. Add your API key**
```bash
echo "ANTHROPIC_API_KEY=your-key-here" > .env
```

**4. Run**
```bash
python3 snapsift.py /path/to/your/photos.zip
```

## Output Structure
```
SnapSift_Output_YYYYMMDD_HHMM/
  ├── PHOTOS/
  │   └── 2024/
  │       └── September 2024/
  ├── DISCARDED/
  ├── REVIEW/
  └── summary.txt
```

## Results (Validation — 49 photos)

| Metric | Result |
|---|---|
| ✅ Personal photos kept | 21 (43%) |
| ❌ Non-personal discarded | 27 (55%) |
| ⚠️ Flagged for review | 1 (2%) |
| ⏱️ Processing time | 46 seconds |

## Built With

- Python 3.9+
- Claude API (claude-haiku-4-5) — Anthropic
- Pillow — Image processing
- ImageHash — Perceptual hashing

## Course Context

Developed as Artifact 4 for AIML-500: Machine Learning Fundamentals
Indiana Wesleyan University | Master's in AI
