# NWT Flashcards

A simple, responsive flashcard app to help memorise scriptures from the New World Translation. The verse list is drawn from the full Bible course [**Enjoy Life Forever**](https://www.jw.org/finder?srcid=jwlshare&wtlocale=E&lank=pub-lffv) on jw.org.

**Live site:** [nwt.qbitservices.com](https://nwt.qbitservices.com)

**Repository:** [github.com/JakeLHX/nwtFlashcards](https://github.com/JakeLHX/nwtFlashcards)

---

## Features

- **336 unique verses** from the Enjoy Life Forever course, each with full NWT text
- **Two study modes**
  - **Verse → Text** — see the reference, recall the scripture
  - **Text → Verse** — see the scripture, recall the reference
- **Tap-to-flip** flashcards with previous/next navigation
- **Shuffle** the deck at any time
- **Open in Bible** link on each card (jw.org)
- Mobile-first, responsive layout

---

## Tech stack

- [Vite](https://vitejs.dev/) + [React](https://react.dev/)
- Python 3 scripts for data extraction and processing
- Hosted on [Cloudflare Pages](https://pages.cloudflare.com/)

---

## Project structure

```
nwtFlashcards/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── App.jsx              # Main app, controls, navigation
│   ├── App.css
│   ├── components/
│   │   └── FlashCard.jsx    # Flip card component
│   └── data/
│       └── scriptures.json  # Generated flashcard data (do not edit by hand)
└── scripts/
    ├── lff_E.rtf/           # Enjoy Life Forever lesson RTF files
    ├── nwt_E.rtf/             # NWT RTF files (verse text source)
    ├── scripture_extractor.py # Extract links from LFF RTF
    ├── build_scriptures.py    # Build cleaned flashcard JSON
    └── extracted_scriptures.json  # Raw extraction output
```

---

## Getting started

### Prerequisites

- Node.js 18+ (20+ recommended)
- Python 3.10+
- npm

### Install and run

```bash
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

### Build for production

```bash
npm run build
npm run preview   # optional — preview the production build locally
```

Output is written to `dist/`.

---

## Data pipeline

Flashcard data is generated from two RTF sources:

1. **Enjoy Life Forever** (`scripts/lff_E.rtf/`) — identifies which scriptures appear in the course and their jw.org links
2. **NWT** (`scripts/nwt_E.rtf/`) — supplies the actual verse text

### Step 1 — Extract scriptures from LFF

```bash
python scripts/scripture_extractor.py \
  --rtf-dir scripts/lff_E.rtf \
  --scriptures-only \
  -o scripts/extracted_scriptures.json
```

### Step 2 — Build flashcard JSON

```bash
npm run build:data
# or directly:
python scripts/build_scriptures.py
```

This writes `src/data/scriptures.json`. The build script:

- Keeps only scripture links (`bible=` URLs)
- Trims multi-verse ranges and full chapters down to a single verse
- Normalises references (e.g. `"verses 4"` → `"1 Timothy 3:4"`)
- Deduplicates by bible code
- Pulls NWT verse text from the RTF files

Each entry in `scriptures.json` looks like:

```json
{
  "text": "1 Timothy 3:4",
  "scripture": "a man presiding over his own household in a fine manner...",
  "url": "https://www.jw.org/finder?pub=nwtsty&bible=54003004&wtlocale=E&srcid=share",
  "bible_code": "54003004",
  "lessons": [63]
}
```

After updating the source RTF files, re-run both steps before building the app.

---

## Deployment (Cloudflare Pages)

| Setting | Value |
|---------|-------|
| Build command | `npm run build` |
| Build output directory | `dist` |
| Node.js version | 20 (or latest LTS) |

Connect the GitHub repository and point your custom domain (`nwt.qbitservices.com`) to the Cloudflare Pages project.

If you update scripture data in CI, run `npm run build:data` before `npm run build`, or add a combined build script.

---

## Scripts reference

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server |
| `npm run build` | Production build → `dist/` |
| `npm run preview` | Serve production build locally |
| `npm run build:data` | Regenerate `src/data/scriptures.json` |

---

## Copyright

Scripture text is from the **New World Translation of the Holy Scriptures**.  
© Watch Tower Bible and Tract Society of Pennsylvania.

Enjoy Life Forever course material © Watch Tower Bible and Tract Society of Pennsylvania.

This project is a personal study aid and is not affiliated with or endorsed by jw.org.
