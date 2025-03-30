# 📧 eml2pdf

A fast and clean command-line tool to extract PDF attachments and convert email body content from `.eml` files to clean, searchable PDFs — plus CSV metadata for receipts.

---

## ✨ Features

- ✅ Extracts **PDF attachments**
- 📝 Converts **email body (HTML/text)** to `.pdf`
- 💰 Extracts structured data:
  - **Amount Paid** (e.g. $12.99, USD 10.00)
  - **Invoice Date**
  - **Vendor Name**
- 📋 Outputs `receipt_report.csv` with metadata
- 📊 **Progress bar** with `tqdm`
- ⚡ Full parallelism using `ProcessPoolExecutor`
- 🧼 Clean, readable logging with `--verbose` flag
- 🛡️ Crash-safe PDF rendering

---

## 💻 Requirements

- Python 3.8+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- macOS users: install system dependencies for `WeasyPrint`:

follow https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#macos

```bash
brew install weasyprint
```

Setup as instruct in https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#missing-library

```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
```

# Clone the project
git clone https://github.com/your-username/eml2pdf.git
cd eml2pdf

# Set up environment
uv venv
source .venv/bin/activate

# Install the tool in editable mode
uv pip install -e .

# 🚀 Usage

```bash
eml2pdf /path/to/folder-with-eml-files
```

	•	Processes all .eml files in the folder
	•	Creates output/ folder with:
	•	Extracted PDF attachments (named like: originalname__filename.pdf)
	•	Email body PDF: originalname.pdf
	•	Creates logs/ folder for any crash logs (render_fail_*.log)

## 📂 Example Output

```bash
$ eml2pdf ~/Downloads/invoices2024
Processing Your receipt from FlutterFlow.eml...
[+] Extracted attachment: Receipt-2376-9625.pdf
[+] Saved email body as PDF: Your receipt from FlutterFlow.pdf

📊 Processing Complete:
   • Total .eml files processed: 48
   • PDF attachments extracted: 71
   • Email bodies converted to PDF: 46
   • Failures: 2
```

