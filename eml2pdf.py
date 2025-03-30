import argparse
import email
from email import policy
from pathlib import Path
import multiprocessing
import traceback
import os
from weasyprint import HTML
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def render_pdf_safe(body_html, pdf_path, log_path):
    try:
        HTML(string=body_html).write_pdf(str(pdf_path))
        print(f"[+] Saved email body as PDF: {pdf_path.name}")
    except Exception as e:
        with open(log_path, "w") as f:
            f.write("PDF rendering failed:\n")
            traceback.print_exc(file=f)
        print(f"[!] Failed to render PDF: {pdf_path.name} (logged to {log_path.name})")

def process_eml_file(eml_path: Path, output_dir: Path):
    try:
        with open(eml_path, 'rb') as f:
            msg = email.message_from_binary_file(f, policy=policy.default)
    except Exception as e:
        print(f"[!] Failed to open {eml_path.name}: {e}")
        return 0, False, True  # attachments, rendered, crashed

    eml_name = eml_path.stem
    extracted = 0
    rendered = False
    crashed = False

    # Extract PDF attachments
    for part in msg.iter_attachments():
        filename = part.get_filename()
        content_type = part.get_content_type()
        if filename and content_type == 'application/pdf':
            attachment_path = output_dir / f"{eml_name}__{filename}"
            with open(attachment_path, 'wb') as f:
                f.write(part.get_payload(decode=True))
            print(f"[+] Extracted attachment: {attachment_path.name}")
            extracted += 1

    # Extract email body
    body = None
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                body = part.get_content()
                break
            elif part.get_content_type() == "text/plain":
                body = "<pre>" + part.get_content() + "</pre>"
    else:
        ct = msg.get_content_type()
        if ct == "text/html":
            body = msg.get_content()
        elif ct == "text/plain":
            body = "<pre>" + msg.get_content() + "</pre>"

    if body:
        pdf_path = output_dir / f"{eml_name}.pdf"
        log_path = LOG_DIR / f"render_fail_{eml_name}.log"

        proc = multiprocessing.Process(target=render_pdf_safe, args=(body, pdf_path, log_path))
        proc.start()
        proc.join(timeout=30)

        if proc.exitcode == 0:
            rendered = True
        else:
            crashed = True
            print(f"[!] PDF rendering crashed for {eml_name} — see log: {log_path.name}")
    else:
        print(f"[!] No body content in {eml_name}")

    return extracted, rendered, crashed

def main():
    parser = argparse.ArgumentParser(description="Extract PDF attachments and convert EML bodies to PDF.")
    parser.add_argument("folder", type=str, help="Folder containing .eml files")
    args = parser.parse_args()

    input_dir = Path(args.folder)
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"❌ Invalid folder path: {input_dir}")
        return

    output_dir = input_dir / "output"
    output_dir.mkdir(exist_ok=True)

    eml_files = list(input_dir.glob("*.eml"))
    if not eml_files:
        print("No .eml files found.")
        return

    total = len(eml_files)
    attachments = 0
    body_pdfs = 0
    failed = 0
    num_workers = os.cpu_count() or 4

    print(f"⚙️ Processing {total} files with {num_workers} workers...\n")

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(process_eml_file, eml_path, output_dir): eml_path
            for eml_path in eml_files
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
            eml_path = futures[future]
            try:
                extracted, rendered, error = future.result()
                attachments += extracted
                body_pdfs += int(rendered)
                failed += int(error)
            except Exception as e:
                print(f"[!] Exception while processing {eml_path.name}: {e}")
                failed += 1

    print("\n📊 Processing Complete:")
    print(f"   • Total .eml files processed: {total}")
    print(f"   • PDF attachments extracted: {attachments}")
    print(f"   • Email bodies converted to PDF: {body_pdfs}")
    print(f"   • Failures: {failed}")

if __name__ == "__main__":
    main()