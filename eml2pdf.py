import argparse
import email
from email import policy
from pathlib import Path
import multiprocessing
import traceback
from weasyprint import HTML

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
    with open(eml_path, 'rb') as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

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

    # Extract body content
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

    total = 0
    attachments = 0
    body_pdfs = 0
    failed = 0

    for eml_file in eml_files:
        total += 1
        print(f"Processing {eml_file.name}...")
        extracted, rendered, error = process_eml_file(eml_file, output_dir)

        attachments += extracted
        body_pdfs += int(rendered)
        failed += int(error)

    print("\n📊 Processing Complete:")
    print(f"   • Total .eml files processed: {total}")
    print(f"   • PDF attachments extracted: {attachments}")
    print(f"   • Email bodies converted to PDF: {body_pdfs}")
    print(f"   • Failures: {failed}")

if __name__ == "__main__":
    main()