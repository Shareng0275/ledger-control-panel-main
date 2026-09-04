#!/usr/bin/env python3
"""
=============================================================================
Document Generation and HTTP File Server Automation
=============================================================================

This module automates the generation of synthetic financial documents (PDF
and DOCX formats) organized into a categorized directory hierarchy, and
launches an asynchronous or threaded local HTTP server with correct MIME
type resolution.

Architecture:
1. Document Generation Engine:
   - Minimal binary valid PDF generation using standard PostScript object models.
   - OpenXML standard DOCX archive creation using Python's built-in zipfile module.
2. File System Organization:
   - Structured multi-tier folder layout with deterministic naming conventions.
3. HTTP Server Handler:
   - Extended http.server with explicit MIME type resolution and directory browsing.
=============================================================================
"""

import http.server
import mimetypes
import os
import socketserver
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# -----------------------------------------------------------------------------
# Configuration Constants
# -----------------------------------------------------------------------------
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080
BASE_OUTPUT_DIR = Path("sample_documents")
TOTAL_PDF_COUNT = 50
TOTAL_DOCX_COUNT = 50

# Subdirectory Organization Taxonomy
CATEGORIES = [
    "settlement_statements",
    "vendor_invoices",
    "treasury_reports",
    "audit_certificates",
    "tax_withholding_summaries",
]


# =============================================================================
# 1. Document Generation Utilities (Pure Standard Library)
# =============================================================================

def generate_minimal_pdf(file_path: Path, title: str, document_id: str) -> None:
    """
    Generates a syntactically valid PDF document without external dependencies.
    
    The PDF structure complies with the Adobe PDF 1.4 specification:
    - Object 1: Catalog Dictionary
    - Object 2: Outlines Dictionary
    - Object 3: Pages Collection
    - Object 4: Page Object (Letter dimension 612x792 pt)
    - Object 5: Text Content Stream
    - Object 6: Standard Type 1 Font (Helvetica)
    """
    creation_date = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
    
    # Text content stream with financial header positioning
    stream_content = (
        "BT\n"
        "/F1 16 Tf\n"
        "50 720 Td\n"
        f"({title}) Tj\n"
        "/F1 10 Tf\n"
        "0 -30 Td\n"
        f"(Document ID: {document_id}) Tj\n"
        "0 -18 Td\n"
        f"(Generated Timestamp: {datetime.now(timezone.utc).isoformat()}) Tj\n"
        "0 -18 Td\n"
        "(Classification: CONFIDENTIAL FINANCIAL RECORD) Tj\n"
        "0 -35 Td\n"
        "(Summary: This document contains formal accounting and reconciliation entries.) Tj\n"
        "0 -18 Td\n"
        "(Reconciliation Status: VERIFIED AND ARCHIVED) Tj\n"
        "ET\n"
    )
    stream_bytes = stream_content.encode("latin-1")
    stream_len = len(stream_bytes)

    # Assemble PostScript objects
    objects: List[bytes] = [
        b"%PDF-1.4\n",
        b"1 0 obj\n<< /Type /Catalog /Pages 3 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Outlines /Count 0 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Pages /Kids [4 0 R] /Count 1 >>\nendobj\n",
        b"4 0 obj\n<< /Type /Page /Parent 3 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 6 0 R >> >> >>\nendobj\n",
        f"5 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin-1") + stream_bytes + b"\nendstream\nendobj\n",
        b"6 0 obj\n<< /Type /Font /Subtype /Type1 /Name /F1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    # Calculate xref byte offsets
    body = b""
    xref_offsets = [0]
    for obj in objects:
        if obj.startswith(b"%PDF"):
            body += obj
            continue
        xref_offsets.append(len(body))
        body += obj

    xref_pos = len(body)
    xref = f"xref\n0 {len(xref_offsets)}\n0000000000 65535 f \n".encode("latin-1")
    for offset in xref_offsets[1:]:
        xref += f"{offset:010d} 00000 n \n".encode("latin-1")

    trailer = (
        f"trailer\n<< /Size {len(xref_offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("latin-1")

    # Write complete binary payload
    file_path.write_bytes(body + xref + trailer)


def generate_minimal_docx(file_path: Path, title: str, document_id: str) -> None:
    """
    Generates a valid Microsoft Word OpenXML (.docx) archive.
    
    Constructs the necessary OpenXML package components:
    - [Content_Types].xml: MIME type bindings
    - _rels/.rels: Package-level relationship mapping
    - word/document.xml: Core document body and paragraph XML
    - word/_rels/document.xml.rels: Document relationship specifications
    """
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
        '</Types>'
    )

    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
        '</Relationships>'
    )

    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
        '  <w:body>\n'
        '    <w:p>\n'
        '      <w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t>' + title + '</w:t></w:r>\n'
        '    </w:p>\n'
        '    <w:p>\n'
        '      <w:r><w:rPr><w:color w:val="555555"/><w:sz w:val="20"/></w:rPr><w:t>Document Reference: ' + document_id + '</w:t></w:r>\n'
        '    </w:p>\n'
        '    <w:p>\n'
        '      <w:r><w:t>Timestamp: ' + datetime.now(timezone.utc).isoformat() + '</w:t></w:r>\n'
        '    </w:p>\n'
        '    <w:p>\n'
        '      <w:r><w:t>Status: Approved and synchronized with general ledger.</w:t></w:r>\n'
        '    </w:p>\n'
        '  </w:body>\n'
        '</w:document>'
    )

    doc_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )

    # Write compressed OpenXML zip archive
    with zipfile.ZipFile(file_path, mode="w", compression=zipfile.ZIP_DEFLATED) as docx_zip:
        docx_zip.writestr("[Content_Types].xml", content_types_xml)
        docx_zip.writestr("_rels/.rels", root_rels_xml)
        docx_zip.writestr("word/document.xml", doc_xml)
        docx_zip.writestr("word/_rels/document.xml.rels", doc_rels_xml)


# =============================================================================
# 2. Directory Creation & Population Logic
# =============================================================================

def populate_sample_documents(base_dir: Path) -> Dict[str, int]:
    """
    Creates the directory hierarchy and populates exactly 50 PDF and 50 DOCX files.
    
    Naming Convention:
    - PDF:  {category}/DOC_PDF_{index:03d}_{category_slug}.pdf
    - DOCX: {category}/DOC_DOCX_{index:03d}_{category_slug}.docx
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    created_counts = {"pdf": 0, "docx": 0}

    print(f"[*] Initializing sample document repository in: {base_dir.resolve()}")

    # 1. Populate 50 PDF files evenly across categories
    for i in range(1, TOTAL_PDF_COUNT + 1):
        category = CATEGORIES[(i - 1) % len(CATEGORIES)]
        target_dir = base_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"DOC_PDF_{i:03d}_{category.upper()}.pdf"
        file_path = target_dir / filename
        doc_id = f"REF-PDF-2026-{i:04d}"
        title = f"Financial Record {i:03d} - {category.replace('_', ' ').title()}"

        generate_minimal_pdf(file_path, title, doc_id)
        created_counts["pdf"] += 1

    # 2. Populate 50 DOCX files evenly across categories
    for i in range(1, TOTAL_DOCX_COUNT + 1):
        category = CATEGORIES[(i - 1) % len(CATEGORIES)]
        target_dir = base_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"DOC_DOCX_{i:03d}_{category.upper()}.docx"
        file_path = target_dir / filename
        doc_id = f"REF-DOCX-2026-{i:04d}"
        title = f"Operational Report {i:03d} - {category.replace('_', ' ').title()}"

        generate_minimal_docx(file_path, title, doc_id)
        created_counts["docx"] += 1

    print(f"[+] Successfully generated {created_counts['pdf']} PDF files.")
    print(f"[+] Successfully generated {created_counts['docx']} DOCX files.")
    print(f"[+] Total files created: {created_counts['pdf'] + created_counts['docx']}")
    return created_counts


# =============================================================================
# 3. HTTP Server Handler with Custom MIME Types
# =============================================================================

class DocumentHttpHandler(http.server.SimpleHTTPRequestHandler):
    """
    Custom HTTP request handler ensuring proper MIME type mapping and logging.
    """

    def __init__(self, *args, directory=None, **kwargs):
        # Explicitly register standard OpenXML and PDF MIME types
        mimetypes.init()
        mimetypes.add_type("application/pdf", ".pdf", strict=True)
        mimetypes.add_type(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
            strict=True,
        )
        super().__init__(*args, directory=str(directory), **kwargs)

    def log_message(self, format, *args):
        """Format request logs with ISO UTC timestamps."""
        sys.stderr.write(
            f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] "
            f"{self.address_string()} - {format % args}\n"
        )


# =============================================================================
# 4. Main Server Execution Routine
# =============================================================================

def start_document_server(directory: Path, host: str = SERVER_HOST, port: int = SERVER_PORT) -> None:
    """
    Binds and runs the HTTP server serving the sample_documents directory.
    """
    handler = lambda *args, **kwargs: DocumentHttpHandler(*args, directory=directory, **kwargs)

    # Enable socket reuse to avoid 'Address already in use' during restarts
    socketserver.TCPServer.allow_reuse_address = True

    try:
        with socketserver.TCPServer((host, port), handler) as httpd:
            server_url = f"http://{host}:{port}/"
            print("==================================================================")
            print("  LEDGER CONTROL — DOCUMENT HTTP REPOSITORY SERVER ACTIVE")
            print("==================================================================")
            print(f"  Root Directory : {directory.resolve()}")
            print(f"  Localhost Link : {server_url}")
            print(f"  Status         : Serving files with application/pdf & .docx MIME types")
            print("  Press Ctrl+C to terminate the server.")
            print("==================================================================")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server shutdown initiated by user. Terminating process.")
    except Exception as exc:
        print(f"[!] Server runtime error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # 1. Populate the documents directory
    populate_sample_documents(BASE_OUTPUT_DIR)

    # 2. Start the HTTP server
    start_document_server(BASE_OUTPUT_DIR, host=SERVER_HOST, port=SERVER_PORT)
