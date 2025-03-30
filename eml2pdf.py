import argparse
import email
from email import policy
from pathlib import Path
import traceback
import os
import csv
import multiprocessing
from weasyprint import HTML
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from bs4 import BeautifulSoup
from price_parser import Price
import dateparser

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def extract_invoice_data(text):
    amount = ""
    invoice_date = ""

    for line in text.splitlines():
        if not amount:
            price = Price.fromstring(line)
            if price.amount is not None:
                amount = str(price.amount)

        if not invoice_date:
            dt = dateparser.parse(line, settings={"STRICT_PARSING": True})
            if dt:
                invoice_date = dt.strftime("%Y-%m-%d")

        if amount and invoice_date:
            break

    return amount, invoice_date

def render_pdf_safe(body_html, pdf_path, log_path):
    try:
        HTML(string=body_html).write_pdf(str(pdf_path))
    except Exception as e:
        with open(log_path, "w") as f:
            f.write("PDF rendering failed:\n")
            traceback.print_exc(file=f)

def process_eml_file(eml_path: Path, output_dir: Path, verbose: bool = False):
    try:
        with open(eml_path, 'rb') as f:
            msg = email.message_from_binary_file(f, policy=policy.default)
    except Exception as e:
        tqdm.write(f"[!] Failed to open {eml_path.name}: {e}")
        return basic_result(eml_path.name, crashed=True)

    eml_name = eml_path.stem
    extracted = 0
    rendered = False
    crashed = False
    amount_paid = ""
    invoice_date = ""

    from_header = msg.get("From", "")
    if "<" in from_header and ">" in from_header:
        email_part = from_header.split("<")[1].split(">")[0]
    else:
        email_part = from_header
    domain = email_part.split("@")[-1]
    vendor = domain.split(".")[0].capitalize() if domain else ""

    for part in msg.iter_attachments():
        filename = part.get_filename()
        content_type = part.get_content_type()
        if filename and content_type == 'application/pdf':
            attachment_path = output_dir / f"{eml_name}__{filename}"
            with open(attachment_path, 'wb') as f:
                f.write(part.get_payload(decode=True))
            extracted += 1
            if verbose:
                tqdm.write(f"[📎] {attachment_path.name}")

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

        try:
            plain_text = BeautifulSoup(body, "html.parser").get_text() if "html" in msg.get_content_type() else body
            amount_paid, invoice_date = extract_invoice_data(plain_text)

            proc = multiprocessing.Process(target=render_pdf_safe, args=(body, pdf_path, log_path))
            proc.start()
            proc.join(timeout=30)

            if proc.exitcode == 0:
                rendered = True
                if verbose:
                    tqdm.write(f"[📝] {pdf_path.name}")
            else:
                crashed = True
                tqdm.write(f"[!] PDF render crash for {pdf_path.name} — see {log_path.name}")
        except Exception as e:
            crashed = True
            tqdm.write(f"[!] Exception during rendering: {e}")
    else:
        if verbose:
            tqdm.write(f"[!] No body content in {eml_name}")

    return {
        "file": eml_path.name,
        "from": from_header,
        "subject": msg.get("Subject", ""),
        "date": msg.get("Date", ""),
        "attachments": extracted,
        "body_rendered": rendered,
        "crashed": crashed,
        "amount_paid": amount_paid,
        "invoice_date": invoice_date,
        "vendor": vendor
    }

def basic_result(filename, crashed=False):
    return {
        "file": filename,
        "from": "",
        "subject": "",
        "date": "",
        "attachments": 0,
        "body_rendered": False,
        "crashed": crashed,
        "amount_paid": "",
        "invoice_date": "",
        "vendor": ""
    }

def main():
    parser = argparse.ArgumentParser(description="Extract PDF attachments and convert EML bodies to PDF.")
    parser.add_argument("folder", type=str, help="Folder containing .eml files")
    parser.add_argument("--verbose", action="store_true", help="Show detailed processing logs")
    args = parser.parse_args()

    input_dir = Path(args.folder)
    if not input_dir.exists() or not input_dir.is_dir():
        tqdm.write(f"❌ Invalid folder path: {input_dir}")
        return

    output_dir = input_dir / "output"
    output_dir.mkdir(exist_ok=True)

    eml_files = list(input_dir.glob("*.eml"))
    if not eml_files:
        tqdm.write("No .eml files found.")
        return

    total = len(eml_files)
    attachments = 0
    body_pdfs = 0
    failed = 0
    report_rows = []
    num_workers = os.cpu_count() or 4

    tqdm.write(f"⚙️ Processing {total} files with {num_workers} workers...\n")

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(process_eml_file, eml_path, output_dir, args.verbose): eml_path
            for eml_path in eml_files
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing", ncols=80):
            eml_path = futures[future]
            try:
                result = future.result()
                attachments += result["attachments"]
                body_pdfs += int(result["body_rendered"])
                failed += int(result["crashed"])

                report_rows.append([
                    result["file"],
                    result["vendor"],
                    result["from"],
                    result["subject"],
                    result["date"],
                    result["invoice_date"],
                    "yes" if result["body_rendered"] else "no",
                    result["attachments"],
                    "yes" if result["crashed"] else "no",
                    result["amount_paid"]
                ])
            except Exception as e:
                failed += 1
                tqdm.write(f"[!] Error in worker: {e}")
                report_rows.append([
                    eml_path.name, "", "", "", "", "", "no", 0, "yes", ""
                ])

    report_path = output_dir / "receipt_report.csv"
    try:
        with open(report_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "File", "Vendor", "From", "Subject", "Email Date",
                "Invoice Date", "Body PDF", "Attachments", "Crashed", "Amount Paid"
            ])
            writer.writerows(report_rows)
        tqdm.write(f"\n📁 CSV report saved to: {report_path}")
    except Exception as e:
        tqdm.write(f"[!] Failed to write CSV: {e}")

    print(f"\n📊 Processing Complete:")
    print(f"   • Total .eml files processed: {total}")
    print(f"   • PDF attachments extracted: {attachments}")
    print(f"   • Email bodies converted to PDF: {body_pdfs}")
    print(f"   • Failures: {failed}")

if __name__ == "__main__":
    main()