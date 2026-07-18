# Playboy: Cover to Cover — DJVU Converter

Convert the encrypted `.djvu` files from the **"Playboy: Cover to Cover — The
Complete Hugh Hefner Reader"** hard drive / DVD set into open formats you can
read on any device:

- **CBZ** — lossless 24-bit PNG pages in a standard comic-book archive
  (recommended; opens in any comic/e-book reader)
- **PDF** — pages assembled into a PDF, with gatefold centerfolds placed on
  properly proportioned wide pages

There is a **point-and-click app** (no typing required) and a command-line
tool for advanced/batch use.

> **You must own the "Playboy: Cover to Cover" set.** This tool does **not**
> include the reader files needed to open the DJVUs — you copy those from your
> own installation (see [Step 3](#step-3--add-your-reader-files-the-dlls)).
> Nothing here lets you obtain the magazines you don't already own.

---

## Contents

- [What you need](#what-you-need)
- [Setup (do this once)](#setup-do-this-once)
  - [Step 1 — Install Python](#step-1--install-python)
  - [Step 2 — Download this tool](#step-2--download-this-tool)
  - [Step 3 — Add your reader files (the DLLs)](#step-3--add-your-reader-files-the-dlls)
  - [Step 4 — Install the add-ons](#step-4--install-the-add-ons)
- [Using the app](#using-the-app)
- [Folder layout](#folder-layout)
- [Troubleshooting](#troubleshooting)
- [Advanced: command line](#advanced-command-line)
- [How it works / design notes](#how-it-works--design-notes)
- [Credit / provenance](#credit--provenance)
- [License](#license)

---

## What you need

1. A **Windows** PC (the reader is a Windows program).
2. Your own **"Playboy: Cover to Cover"** hard drive or DVDs (for the reader
   files — see Step 3).
3. About 15 minutes for one-time setup. After that, converting is just a few
   clicks.

Each converted issue is large (a CBZ can be ~700 MB, a PDF ~300 MB), so make
sure you have free disk space where you save them.

---

## Setup (do this once)

### Step 1 — Install Python

Python is a free program this tool runs on. You need the **32-bit** version —
this is important, because the Playboy reader is 32-bit and won't work with the
64-bit Python.

1. Go to the official download page:
   **https://www.python.org/downloads/release/python-31011/**
2. Scroll down to the **"Files"** table.
3. Click **"Windows installer (32-bit)"** to download it.
   - ⚠️ Make sure it says **(32-bit)**. Do **not** pick the "64-bit" or
     "ARM64" one.
4. Open the downloaded file to start the installer.
5. On the first screen, **check the box that says "Add python.exe to PATH"**
   at the bottom, then click **"Install Now"**.
6. When it finishes, click **Close**.

That's it — you don't need to open Python yourself. The buttons in this tool
use it for you.

### Step 2 — Download this tool

1. On this project's GitHub page, click the green **"Code"** button, then
   **"Download ZIP"**.
2. Find the downloaded ZIP (usually in your **Downloads** folder), right-click
   it, and choose **"Extract All…"**.
3. Pick a location that's easy to find — for example your **Documents**
   folder — and extract. You'll get a folder like `Playboy-DeBondi`.

### Step 3 — Add your reader files (the DLLs)

The converter needs three small files from your **own** Playboy set. They are
**not** included here and are not shared publicly. You copy them from your own
installation into the **`dlls`** folder inside the tool.

The three files are:

- `BondiReader.DJVU.dll`
- `msvcr71.dll`
- `msvcp71.dll`

**How to find them on your Playboy set:**

1. Open your "Playboy: Cover to Cover" hard drive or DVD in **File Explorer**.
2. In the search box at the top-right of the File Explorer window, type:
   `BondiReader.DJVU.dll` and press Enter.
3. When it shows up, right-click it and choose **"Open file location"**.
4. `msvcr71.dll` and `msvcp71.dll` are usually in that same folder. If you
   don't see them, search the drive for each of them by name too.
5. Copy all three files into the **`dlls`** folder inside your extracted
   `Playboy-DeBondi` folder.

There's a reminder file, `dlls\PUT_YOUR_DLLS_HERE.txt`, in that folder if you
need it later.

### Step 4 — Install the add-ons

Double-click **`Install Requirements.bat`**. A black window opens, installs two
small Python add-ons (for images and PDFs), and tells you when it's done. You
only do this once.

---

## Using the app

Double-click **`Playboy Converter.bat`**. The converter window opens.

1. **What do you want to convert?**
   - *A whole folder of issues* — convert every `.djvu` in a folder in one go.
   - *A single .djvu issue* — convert just one.
2. **Source** — click **Browse…** and pick the folder (or the single `.djvu`
   file).
3. **Save to** — click **Browse…** and pick where the finished files should
   go. (Defaults to an `output` folder inside the tool.)
4. **Format** — **CBZ** (best for comic readers), **PDF**, or **Both**.
5. Click **Convert**.

Progress shows in the window as each page is processed. A large issue can take
a few minutes; a whole folder can take a while — that's normal. When it says
**"Done"**, your files are in the *Save to* folder.

You can click **Cancel** at any time to stop.

---

## Folder layout

After setup, your tool folder looks like this:

```
Playboy-DeBondi\
├─ Playboy Converter.bat      ← double-click this to open the app
├─ Install Requirements.bat   ← double-click once during setup
├─ playboy_convert_gui.py     ← the app
├─ playboy_convert.py         ← the converter engine (also usable from the command line)
├─ requirements.txt
├─ README.md
├─ dlls\                      ← YOU put your three reader files here
│   ├─ BondiReader.DJVU.dll        (you provide)
│   ├─ msvcr71.dll                 (you provide)
│   ├─ msvcp71.dll                 (you provide)
│   └─ PUT_YOUR_DLLS_HERE.txt
└─ output\                    ← converted files appear here by default (created automatically)
```

---

## Troubleshooting

**Double-clicking "Playboy Converter.bat" flashes a window and closes / says
Python isn't installed.**
Python isn't installed, or the 64-bit version was installed by mistake. Redo
[Step 1](#step-1--install-python) and be sure to pick **Windows installer
(32-bit)** and to check **"Add python.exe to PATH"**.

**The app opens but says "The reader DLLs were not found."**
The three files aren't in the `dlls` folder, or one is missing. Redo
[Step 3](#step-3--add-your-reader-files-the-dlls). All three
(`BondiReader.DJVU.dll`, `msvcr71.dll`, `msvcp71.dll`) must be in `dlls`.

**The app opens but converting fails right away mentioning "Pillow".**
The add-ons weren't installed. Double-click **`Install Requirements.bat`**
(Step 4) and wait for it to say "Done."

**A few pages get skipped in a converted issue.**
Some source pages in the set are corrupted. The converter skips those and keeps
going, and lists them in a `<issue>_skipped.log` file next to your output. The
rest of the issue converts fine.

**A batch converts only some issues.**
After a batch, open `_batch_summary.log` in your *Save to* folder — it lists
which issues succeeded and which failed, and why.

---

## Advanced: command line

The engine, `playboy_convert.py`, runs on its own for scripting or batch runs.
It requires **32-bit Python 3.10**, invoked as `py -3.10-32`.

One-time package install:

```
py -3.10-32 -m pip install -r requirements.txt
```

(`Pillow` is always required; `fpdf2` is only needed for PDF output.)

Interactive prompts:

```
py -3.10-32 playboy_convert.py
```

Convert a whole folder to CBZ:

```
py -3.10-32 playboy_convert.py "C:\path\to\Issues" --output_dir "C:\path\to\converted"
```

Choose the format:

```
py -3.10-32 playboy_convert.py "C:\path\to\Issues" --format pdf
py -3.10-32 playboy_convert.py "C:\path\to\Issues" --format both
```

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--format {cbz,pdf,both}` | `cbz` | Output format |
| `--output_dir DIR` | `./output` | Where converted files are written |
| `--jpeg-quality N` | `90` | JPEG quality for PDF pages (CBZ is always lossless PNG) |

The engine looks for the reader DLLs in the `dlls` folder first, then in the
same folder as the script (so an older flat layout still works).

---

## How it works / design notes

- **Subprocess isolation:** in batch (folder) mode, each DJVU file is converted
  in a fresh Python process. The 32-bit reader fragments memory over long runs;
  a clean process per file prevents one bad file from degrading the rest of the
  batch.
- **Per-page resilience:** corrupted pages (the reader throws `0xe06d7363`) are
  skipped and logged to `<issue>_skipped.log` instead of aborting the file.
- **Gatefolds:** centerfold pages (~9100×4350) are detected by total pixel
  count rather than per-side limits, so they convert intact. In PDF output they
  get a correctly proportioned wide page.
- **CBZ packing:** PNGs are stored uncompressed in the zip (`ZIP_STORED`) — PNG
  is already compressed, so re-compressing would only waste time.
- A `_batch_summary.log` is written after each batch run.

---

## Credit / provenance

This tool is a derivative of
[reconSuave/PlayboyPDF](https://github.com/reconSuave/PlayboyPDF) (EPL-2.0),
which figured out the interface to the Bondi reader DLL and the DJVU
credentials. See also the companion tool
[reconSuave/RollingStoner](https://github.com/reconSuave/RollingStoner).

This version adds the graphical app, CBZ output, resilient per-page error
handling, gatefold/centerfold detection, per-file subprocess isolation for long
batch runs, and a unified CBZ/PDF format selector. Those additions were
developed with Claude (Anthropic).

## License

[Eclipse Public License 2.0](LICENSE), matching the upstream PlayboyPDF project.
