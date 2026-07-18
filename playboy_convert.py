# playboy_convert.py
# CBZ/PDF-output derivative of reconSuave/PlayboyPDF (EPL-2.0).
# https://github.com/reconSuave/PlayboyPDF
# CBZ conversion, resilient error handling, gatefold detection, and
# subprocess isolation developed with Claude (Anthropic), model Opus 4.8,
# and finalized in Claude Code (Fable 5).

import ctypes
import argparse
from ctypes import byref, c_int, c_char_p
import sys
import os
import gc
import zipfile
import traceback
import subprocess


def _fail_early(message):
    print(f"\n[ERROR] {message}")
    sys.exit(1)


# The Bondi DLL is 32-bit; a 64-bit Python cannot load it (WinError 193).
# Check up front so the user gets a clear message instead of a ctypes error.
if sys.maxsize > 2**32:
    _fail_early(
        "This script must run under 32-bit Python because BondiReader.DJVU.dll "
        "is a 32-bit DLL.\n"
        "Install 32-bit Python 3.10 and run:\n"
        "  py -3.10-32 playboy_convert.py <path>"
    )

try:
    from PIL import Image
except ImportError:
    _fail_early(
        "Pillow is not installed for this Python.\n"
        "Install it with:\n"
        "  py -3.10-32 -m pip install Pillow"
    )


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_int), ("cy", ctypes.c_int)]


# Dimension sanity bounds:
# - Single pages run ~2400x3300 (~8 megapixels)
# - Gatefold centerfolds run ~9100x4350 (~40 megapixels) - legitimate!
# - Check total pixels rather than per-side to allow wide centerfolds
#   while still catching corrupted dimensions that would exhaust memory.
MIN_PAGE_DIMENSION = 100             # pixels per side
MAX_PAGE_PIXELS = 100_000_000        # 100 MP (~400MB at 4 bytes/pixel, safe for 32-bit)
MAX_SINGLE_DIMENSION = 20000         # absolute ceiling on any single side

# Pages render at 300 DPI; used to size PDF pages in points (72 pt/inch).
ASSUMED_DPI = 300

# Resolve the DLLs relative to this script, not the caller's working
# directory, so the script can be invoked from anywhere.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# The reader needs three DLLs: BondiReader.DJVU.dll plus its two Visual C++
# 7.1 runtime dependencies (msvcr71.dll, msvcp71.dll). We look in a "dlls"
# subfolder first (the layout we ask users to set up), then fall back to the
# script folder itself for backward compatibility with the older flat layout.
DLL_DIR_CANDIDATES = [os.path.join(SCRIPT_DIR, "dlls"), SCRIPT_DIR]


def _find_dll_dir():
    for d in DLL_DIR_CANDIDATES:
        if os.path.exists(os.path.join(d, "BondiReader.DJVU.dll")):
            return d
    return None


DLL_DIR = _find_dll_dir()
# When missing, point at the preferred "dlls" location for a helpful error.
bondi_dll = os.path.join(
    DLL_DIR or os.path.join(SCRIPT_DIR, "dlls"), "BondiReader.DJVU.dll"
)

# Add the DLL folder to the Windows DLL search path so that BondiReader's
# dependencies (msvcr71/msvcp71) resolve even when they live in the "dlls"
# subfolder rather than next to the interpreter or on PATH.
if DLL_DIR and hasattr(os, "add_dll_directory") and os.path.isdir(DLL_DIR):
    os.add_dll_directory(DLL_DIR)

# These credentials are hard-coded into the Playboy DJVU files
default_username = "Playboy"
default_password = "XrvvFgTQcHrWtsF5JGQQkAJgJVS3EZ28fFOvgLFGG0J"


class BondiDJVUActions:
    def __init__(self):
        self.lib = ctypes.CDLL(str(bondi_dll))
        self.open_file_name = None
        self.page_count = 0
        self.page_size_array = []

    def open_document(self, file_name: str, username: str, password: str) -> bool:
        if self.open_file_name is not None:
            self.close_document()
        self.open_file_name = file_name
        self.lib.OpenDocument(
            c_char_p(file_name.encode("utf-8")),
            c_char_p(username.encode("utf-8")),
            c_char_p(password.encode("utf-8")),
        )
        self.page_count = self.lib.GetPageCount()
        self.page_size_array = [(0, 0)] * self.page_count
        return True

    def close_document(self):
        if self.open_file_name is None:
            return
        try:
            self.lib.CloseDocument()
        except Exception:
            pass
        self.open_file_name = None
        self.page_count = 0
        self.page_size_array = []

    def get_page_size(self, page_index: int):
        if page_index < 0 or page_index >= self.page_count:
            return (0, 0)
        if self.page_size_array[page_index] != (0, 0):
            return self.page_size_array[page_index]
        size = SIZE()
        self.lib.GetPageSize(c_int(page_index), byref(size))
        self.page_size_array[page_index] = (size.cx, size.cy)
        return self.page_size_array[page_index]

    def save_page_bitmap(self, page_index: int, width: int, height: int):
        bitmap_data = (ctypes.c_byte * (4 * width * height))()
        success = self.lib.GetPageBitmapData(
            c_int(page_index),
            c_int(width),
            c_int(height),
            c_int(0),
            ctypes.byref(bitmap_data),
        )
        if success:
            img = Image.frombuffer(
                "RGBA", (width, height), bitmap_data, "raw", "BGRA", 0, 1
            )
            gc.collect()
            return img


def extract_page_safely(actions, page, page_count):
    """
    Attempts to extract a single page. Returns a PIL Image on success,
    or None if the page is corrupted/unreadable. Never raises.
    """
    try:
        size = actions.get_page_size(page)
    except Exception as e:
        print(f"  [SKIP] Page {page + 1}: could not read page size ({type(e).__name__})")
        return None

    width, height = size[0], size[1]

    # Sanity check on dimensions before attempting allocation
    if width <= 0 or height <= 0:
        print(f"  [SKIP] Page {page + 1}: invalid dimensions {width}x{height}")
        return None
    if width < MIN_PAGE_DIMENSION or height < MIN_PAGE_DIMENSION:
        print(f"  [SKIP] Page {page + 1}: dimensions too small {width}x{height}")
        return None
    if width > MAX_SINGLE_DIMENSION or height > MAX_SINGLE_DIMENSION:
        print(f"  [SKIP] Page {page + 1}: dimensions exceed single-side ceiling "
              f"{width}x{height} (likely corrupted)")
        return None

    total_pixels = width * height
    if total_pixels > MAX_PAGE_PIXELS:
        print(f"  [SKIP] Page {page + 1}: {width}x{height} = {total_pixels:,} pixels "
              f"exceeds {MAX_PAGE_PIXELS:,} (likely corrupted)")
        return None

    # Identify gatefold/centerfold pages for the log
    if width > height * 1.5:
        print(f"Processing page {page + 1} of {page_count} ({width}x{height}) "
              f"[gatefold]")
    else:
        print(f"Processing page {page + 1} of {page_count} ({width}x{height})")

    try:
        img = actions.save_page_bitmap(page, width, height)
        if img is None:
            print(f"  [SKIP] Page {page + 1}: DLL returned no bitmap data")
            return None
        return img
    except MemoryError:
        print(f"  [SKIP] Page {page + 1}: out of memory during bitmap allocation "
              f"({width}x{height})")
        gc.collect()
        return None
    except OSError as e:
        # The DLL throws C++ exceptions on corrupted pages (WinError 0xe06d7363)
        print(f"  [SKIP] Page {page + 1}: DLL error - {e}")
        return None
    except Exception as e:
        print(f"  [SKIP] Page {page + 1}: unexpected error - {type(e).__name__}: {e}")
        return None


def build_cbz(image_files, cbz_path):
    """Bundles PNG pages into a CBZ and deletes the source PNGs."""
    print(f"\nBundling {len(image_files)} pages into {cbz_path} ...")
    try:
        # ZIP_STORED: PNG is already compressed, don't double-compress
        with zipfile.ZipFile(cbz_path, 'w', zipfile.ZIP_STORED) as zf:
            for f in image_files:
                zf.write(f, os.path.basename(f))
                os.remove(f)
        print(f"Saved CBZ at {cbz_path}")
        return True
    except Exception as e:
        print(f"[FAIL] Could not write CBZ: {e}")
        return False


def build_pdf(image_files, pdf_path):
    """Assembles JPEG pages into a PDF and deletes the source JPEGs.

    Each PDF page is sized to match its image's aspect ratio (at the
    assumed scan DPI), so gatefold centerfolds get a proper wide page
    instead of being squeezed onto A4.
    """
    from fpdf import FPDF  # imported lazily; only needed for PDF output

    print(f"\nAssembling {len(image_files)} pages into {pdf_path} ...")
    try:
        pdf = FPDF(unit="pt")
        for f in image_files:
            with Image.open(f) as im:
                width, height = im.size
            w_pt = width * 72.0 / ASSUMED_DPI
            h_pt = height * 72.0 / ASSUMED_DPI
            pdf.add_page(format=(w_pt, h_pt))
            pdf.image(f, 0, 0, w_pt, h_pt)
        pdf.output(pdf_path)
        for f in image_files:
            os.remove(f)
        print(f"Saved PDF at {pdf_path}")
        return True
    except Exception as e:
        print(f"[FAIL] Could not write PDF: {e}")
        return False


def process_file(
    file_path,
    actions,
    output_dir,
    formats,
    jpeg_quality=90,
    default_username=default_username,
    default_password=default_password,
):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    print(f"\n{'=' * 60}")
    print(f"Starting to process file: {file_path}")
    print(f"Output format(s): {', '.join(sorted(formats)).upper()}")
    print(f"{'=' * 60}")

    try:
        opened = actions.open_document(file_path, default_username, default_password)
    except Exception as e:
        print(f"[FAIL] Could not open document: {type(e).__name__}: {e}")
        return False

    if not opened:
        print("[FAIL] Failed to open document. Skipping.")
        return False

    print("Document opened successfully.")
    page_count = actions.page_count
    print(f"Page count: {page_count}")

    png_files = []   # lossless pages for CBZ
    jpg_files = []   # compressed pages for PDF
    skipped_pages = []

    for page in range(page_count):
        img = extract_page_safely(actions, page, page_count)
        if img is None:
            skipped_pages.append(page + 1)
            continue

        try:
            img = img.convert("RGB")
            # Zero-padded filenames keep CBZ readers in correct page order
            if "cbz" in formats:
                png_path = os.path.join(output_dir, f"{base_name}_{page:04d}.png")
                img.save(png_path, "PNG")
                png_files.append(png_path)
            if "pdf" in formats:
                jpg_path = os.path.join(output_dir, f"{base_name}_pdftmp_{page:04d}.jpg")
                img.save(jpg_path, "JPEG", quality=jpeg_quality)
                jpg_files.append(jpg_path)
        except Exception as e:
            print(f"  [SKIP] Page {page + 1}: failed to save image - {e}")
            skipped_pages.append(page + 1)
        finally:
            del img

    extracted_count = max(len(png_files), len(jpg_files))
    success = False
    if extracted_count:
        results = []
        if "cbz" in formats:
            cbz_path = os.path.join(output_dir, f"{base_name}.cbz")
            results.append(build_cbz(png_files, cbz_path))
        if "pdf" in formats:
            pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
            results.append(build_pdf(jpg_files, pdf_path))
        success = all(results)
    else:
        print("[FAIL] No pages were successfully extracted. Nothing created.")

    if skipped_pages:
        print(f"\n[!] Skipped {len(skipped_pages)} page(s): {skipped_pages}")
        log_path = os.path.join(output_dir, f"{base_name}_skipped.log")
        try:
            with open(log_path, 'w') as logf:
                logf.write(f"File: {file_path}\n")
                logf.write(f"Total pages: {page_count}\n")
                logf.write(f"Extracted: {extracted_count}\n")
                logf.write(f"Skipped: {len(skipped_pages)}\n")
                logf.write(f"Skipped page numbers: {skipped_pages}\n")
            print(f"    Skipped pages logged to {log_path}")
        except Exception:
            pass

    try:
        actions.close_document()
        print("Document closed.")
    except Exception:
        pass

    return success


def process_single_file_inprocess(file_path, output_dir, formats, jpeg_quality):
    """Runs one file in the current process. Returns True on success."""
    actions = BondiDJVUActions()
    return process_file(file_path, actions, output_dir, formats,
                        jpeg_quality=jpeg_quality)


def process_directory_with_isolation(directory, output_dir, format_arg, jpeg_quality):
    """
    Processes a directory of DJVU files by spawning a fresh subprocess
    for each file. This prevents memory fragmentation in the 32-bit
    DLL from cascading across the batch - each file gets a clean
    process and Windows reclaims all memory when it exits.

    NOTE: Batch isolation assumes running from source (sys.executable is a
    Python interpreter). If ever frozen with Nuitka/PyInstaller, this
    re-invoke strategy needs rework - sys.executable would point at the
    bundled binary. When frozen, we fall back to in-process looping.
    """
    djvu_files = sorted([f for f in os.listdir(directory) if f.endswith(".djvu")])
    print(f"Found {len(djvu_files)} DJVU file(s) to process.")

    frozen = getattr(sys, "frozen", False)
    if frozen:
        print("[!] Running as a frozen binary - subprocess isolation unavailable, "
              "processing in-process. Long batches may degrade from memory "
              "fragmentation; consider running from source.\n")
    else:
        print("Running with subprocess isolation - each file gets a fresh process.\n")

    formats = _formats_from_arg(format_arg)
    succeeded = []
    failed = []

    for idx, file in enumerate(djvu_files, 1):
        file_path = os.path.join(directory, file)
        print(f"\n{'#' * 60}")
        print(f"# [{idx}/{len(djvu_files)}] {file}")
        print(f"{'#' * 60}")

        if frozen:
            try:
                ok = process_single_file_inprocess(
                    file_path, output_dir, formats, jpeg_quality)
                (succeeded if ok else failed).append(
                    file if ok else (file, "processing failed"))
            except Exception as e:
                failed.append((file, f"{type(e).__name__}: {e}"))
            continue

        # Spawn a fresh Python subprocess for this single file.
        # sys.executable points to the same 32-bit Python we're running on.
        # No capture_output: the child writes directly to this console so
        # the user sees live per-page progress (intentional - do not buffer).
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    os.path.abspath(__file__),
                    file_path,
                    "--output_dir", output_dir,
                    "--format", format_arg,
                    "--jpeg-quality", str(jpeg_quality),
                    "--single-file-mode",  # Internal flag to prevent recursion
                ],
                cwd=SCRIPT_DIR,
            )
            if result.returncode == 0:
                succeeded.append(file)
            else:
                failed.append((file, f"exit code {result.returncode}"))
        except Exception as e:
            failed.append((file, f"{type(e).__name__}: {e}"))
            print(f"[FAIL] Subprocess error on {file}: {e}")

    # Final summary
    print(f"\n{'=' * 60}")
    print(f"BATCH COMPLETE")
    print(f"{'=' * 60}")
    print(f"Succeeded: {len(succeeded)} / {len(djvu_files)}")
    if failed:
        print(f"Failed:    {len(failed)}")
        for fname, reason in failed:
            print(f"  - {fname}: {reason}")

    # Write a batch summary log
    summary_path = os.path.join(output_dir, "_batch_summary.log")
    try:
        with open(summary_path, 'w') as f:
            f.write(f"Batch run summary\n")
            f.write(f"Total files: {len(djvu_files)}\n")
            f.write(f"Succeeded: {len(succeeded)}\n")
            f.write(f"Failed: {len(failed)}\n\n")
            if succeeded:
                f.write("Successful files:\n")
                for fname in succeeded:
                    f.write(f"  {fname}\n")
            if failed:
                f.write("\nFailed files:\n")
                for fname, reason in failed:
                    f.write(f"  {fname}: {reason}\n")
        print(f"\nBatch summary written to {summary_path}")
    except Exception:
        pass


def _formats_from_arg(format_arg):
    return {"cbz", "pdf"} if format_arg == "both" else {format_arg}


def _check_requirements(formats):
    """Friendly up-front checks so failures don't happen mid-batch."""
    if not os.path.exists(bondi_dll):
        _fail_early(
            f"BondiReader.DJVU.dll not found.\n"
            f"Expected it in: {os.path.join(SCRIPT_DIR, 'dlls')}\n"
            "Copy these three files from your own 'Playboy: Cover to Cover' "
            "installation into that 'dlls' folder:\n"
            "  BondiReader.DJVU.dll\n"
            "  msvcr71.dll\n"
            "  msvcp71.dll"
        )
    if "pdf" in formats:
        try:
            import fpdf  # noqa: F401
        except ImportError:
            _fail_early(
                "PDF output requires the fpdf2 package.\n"
                "Install it with:\n"
                "  py -3.10-32 -m pip install fpdf2"
            )


def _prompt_interactive():
    """Friendly prompts for users who run the script with no arguments
    (e.g. double-clicking a launcher)."""
    print("=" * 60)
    print("Playboy: Cover to Cover - DJVU converter")
    print("=" * 60)
    path = input("\nDJVU file or folder to convert: ").strip().strip('"')
    if not path:
        _fail_early("No path given.")

    print("\nOutput format:")
    print("  1. CBZ (lossless PNG pages, best for comic readers) [default]")
    print("  2. PDF")
    print("  3. Both")
    choice = input("Choose 1, 2 or 3: ").strip()
    format_arg = {"1": "cbz", "2": "pdf", "3": "both"}.get(choice, "cbz")

    default_out = os.path.join(os.getcwd(), "output")
    out = input(f"\nOutput folder [{default_out}]: ").strip().strip('"')
    output_dir = out or default_out

    return path, format_arg, output_dir


def main():
    parser = argparse.ArgumentParser(
        description="Convert 'Playboy: Cover to Cover' (Bondi) DJVU files to CBZ "
                    "archives (lossless 24-bit PNG pages) and/or PDF. Uses "
                    "subprocess isolation for batch runs to prevent memory "
                    "fragmentation. Run with no arguments for interactive mode."
    )
    parser.add_argument("path", nargs="?",
                        help="The DJVU file or directory to process.")
    parser.add_argument(
        "--format",
        choices=["cbz", "pdf", "both"],
        default="cbz",
        help="Output format: cbz (default), pdf, or both.",
    )
    parser.add_argument(
        "--output_dir",
        default=os.path.join(os.getcwd(), "output"),
        help="Directory to save the converted files (default: ./output).",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=90,
        dest="jpeg_quality",
        help="JPEG quality for PDF pages, 1-95 (default: 90). CBZ is always "
             "lossless PNG.",
    )
    # Internal flag used when this script invokes itself for a single file.
    # Prevents directory mode from recursing.
    parser.add_argument(
        "--single-file-mode",
        dest="single_file_mode",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.path is None:
        args.path, args.format, args.output_dir = _prompt_interactive()

    formats = _formats_from_arg(args.format)
    _check_requirements(formats)

    output_dir = args.output_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if os.path.isdir(args.path) and not args.single_file_mode:
        # Batch mode: spawn a subprocess per file for memory isolation
        process_directory_with_isolation(
            args.path, output_dir, args.format, args.jpeg_quality)
    elif os.path.isfile(args.path) and args.path.endswith(".djvu"):
        # Single file mode: actually do the work
        try:
            ok = process_single_file_inprocess(
                args.path, output_dir, formats, args.jpeg_quality)
            sys.exit(0 if ok else 1)
        except Exception as e:
            print(f"\n[FAIL] Unhandled error: {type(e).__name__}: {e}")
            traceback.print_exc()
            sys.exit(2)
    else:
        print("The specified path is not a .djvu file or a directory.")
        sys.exit(1)

    print("\nAll done.")


if __name__ == "__main__":
    main()
