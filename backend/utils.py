import io
import re
from typing import List
from fastapi import UploadFile
from docx import Document
from pptx import Presentation
import pdfplumber

# ReportLab
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter


async def read_file_to_text(file: UploadFile) -> str:
    """
    Read file bytes and return cleaned text. Handles txt/docx/pdf/pptx.
    For PDFs we use per-page extraction and then normalize.
    """
    contents = await file.read()
    name = file.filename.lower()

    if name.endswith(".txt"):
        raw = contents.decode("utf-8", errors="ignore")
        return normalize_whitespace(raw)

    if name.endswith(".docx"):
        doc = Document(io.BytesIO(contents))
        raw = "\n".join(p.text for p in doc.paragraphs)
        return normalize_whitespace(raw)

    if name.endswith(".pptx"):
        presentation = Presentation(io.BytesIO(contents))
        pieces = []
        for slide in presentation.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    pieces.append(shape.text)
        raw = "\n".join(pieces)
        return normalize_whitespace(raw)

    if name.endswith(".pdf"):
        pages_text = []
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                # split into lines to preserve page structure
                lines = [ln.rstrip() for ln in text.splitlines()]
                pages_text.append(lines)

        if not any(pages_text):
            return ""  # no selectable text

        # remove repeated headers/footers across pages
        pages_text = remove_repeated_header_footer(pages_text)

        # join lines inside pages with heuristics
        page_paragraphs = []
        for lines in pages_text:
            joined = join_broken_lines(lines)
            page_paragraphs.append(joined)

        # join pages with a page-break marker (double newline)
        raw = "\n\n".join(page_paragraphs)
        raw = normalize_whitespace(raw)
        return raw

    # default fallback
    return contents.decode("utf-8", errors="ignore")


# -------------------------
# Text cleaning helpers
# -------------------------
def normalize_whitespace(text: str) -> str:
    """Normalize whitespace, fix many spaces/newlines, convert weird non-breaking spaces."""
    if not text:
        return ""
    text = text.replace("\u00A0", " ")
    text = text.replace("\r", "")
    # collapse multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    # unify many newlines into max two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # trim spaces on each line
    text = "\n".join([ln.strip() for ln in text.splitlines()])
    # remove leading/trailing
    return text.strip()


def remove_repeated_header_footer(pages_lines: List[List[str]]) -> List[List[str]]:
    """
    Detect lines that repeat at top or bottom of many pages and remove them.
    Strategy:
      - Collect top N and bottom N lines for each page (non-empty).
      - Count occurrences across pages. If a line appears on >50% pages at same
        relative position, treat as header/footer and remove.
    """
    if not pages_lines:
        return pages_lines

    top_n = 3
    bottom_n = 3
    top_counts = {}
    bottom_counts = {}
    page_count = len(pages_lines)

    # collect candidates
    for lines in pages_lines:
        # normalized small-lines list
        nonempty = [ln.strip() for ln in lines if ln.strip()]
        # top candidates
        for i in range(min(top_n, len(nonempty))):
            key = normalize_short(nonempty[i])
            top_counts[key] = top_counts.get(key, 0) + 1
        # bottom candidates
        for i in range(min(bottom_n, len(nonempty))):
            key = normalize_short(nonempty[-1 - i])
            bottom_counts[key] = bottom_counts.get(key, 0) + 1

    # decide headers/footers present on >50% pages
    header_candidates = {k for k, v in top_counts.items() if v > page_count * 0.5}
    footer_candidates = {k for k, v in bottom_counts.items() if v > page_count * 0.5}

    cleaned_pages = []
    for lines in pages_lines:
        cleaned = []
        nonempty = [ln for ln in lines]  # preserve positions
        # remove top matches
        idx = 0
        # skip over header candidates at top
        while idx < len(nonempty):
            if nonempty[idx].strip() and normalize_short(nonempty[idx]) in header_candidates:
                idx += 1
                continue
            break
        # collect middle part
        middle = nonempty[idx:]
        # remove footer candidates from bottom
        while middle and middle[-1].strip() and normalize_short(middle[-1]) in footer_candidates:
            middle.pop()
        # final cleaned lines (strip)
        cleaned = [ln for ln in (l.strip() for l in middle) if ln != ""]
        cleaned_pages.append(cleaned)

    return cleaned_pages


def normalize_short(s: str) -> str:
    """Compact a short string for header/footer comparison."""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    # remove page number patterns like 'page 1 of 5'
    s = re.sub(r"page\s*\d+(\s*of\s*\d+)?", "", s)
    s = s.strip()
    return s


def join_broken_lines(lines: List[str]) -> str:
    """
    Heuristic reflow for lines:
      - If a line ends with '-' then it's hyphenation: remove '-' and join.
      - If a line doesn't end with sentence end (.!?;:) and next line starts with lowercase/continuation,
        join with space.
      - If current line is very short and next line starts with lowercase, join.
      - Otherwise keep newline (paragraph boundary).
    """
    out_lines = []
    i = 0
    while i < len(lines):
        cur = lines[i].rstrip()
        if cur == "":
            # preserve paragraph break
            out_lines.append("")
            i += 1
            continue

        # accumulate run
        run = cur
        j = i + 1
        while j < len(lines):
            nxt = lines[j].lstrip()
            if nxt == "":
                break  # paragraph break
            # hyphenation case
            if run.endswith("-"):
                run = run[:-1] + nxt  # remove hyphen and join immediately
                j += 1
                continue
            # if current ends with punctuation, keep as new line
            if re.search(r"[\.!\?:]" + r"\s*$", run):
                break
            # if next starts with lowercase or digit, probably a continuation
            if re.match(r"^[a-z0-9]", nxt):
                run = run + " " + nxt
                j += 1
                continue
            # if current is short (<=40 chars) and next starts lowercase, join
            if len(run) < 40 and re.match(r"^[a-z]", nxt):
                run = run + " " + nxt
                j += 1
                continue
            # otherwise do not join
            break

        out_lines.append(run.strip())
        i = j
    # join runs with single newline; treat empty strings as paragraph separators
    paragraphs = []
    cur_para = []
    for ln in out_lines:
        if ln == "":
            if cur_para:
                paragraphs.append(" ".join(cur_para).strip())
                cur_para = []
        else:
            cur_para.append(ln)
    if cur_para:
        paragraphs.append(" ".join(cur_para).strip())

    # return page text with paragraphs separated by blank line
    return "\n\n".join(paragraphs)


# -------------------------
# PDF builder (robust multi-page)
# -------------------------
def build_pdf_from_text(text: str) -> bytes:
    """
    Create a multi-page PDF from cleaned text. We chunk into sensible sizes
    (prefer breaking at sentence boundaries) to ensure ReportLab flows pages.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=36,
        bottomMargin=36,
        leftMargin=40,
        rightMargin=40
    )
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]

    story = []
    # split into paragraphs (double-newline)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    # If very few paragraphs or very long paragraphs, further chunk them
    def chunk_paragraph(paragraph: str, max_chars: int = 900) -> List[str]:
        if len(paragraph) <= max_chars:
            return [paragraph]
        # attempt to split on sentence boundaries:
        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        chunks = []
        cur = ""
        for s in sentences:
            if len(cur) + len(s) + 1 <= max_chars:
                cur = (cur + " " + s).strip()
            else:
                if cur:
                    chunks.append(cur.strip())
                cur = s
        if cur:
            chunks.append(cur.strip())
        # fallback: if any chunk longer than max_chars, do hard split
        final = []
        for c in chunks:
            if len(c) <= max_chars:
                final.append(c)
            else:
                for i in range(0, len(c), max_chars):
                    final.append(c[i:i+max_chars])
        return final

    for para in paragraphs:
        chunks = chunk_paragraph(para)
        for ch in chunks:
            # preserve line breaks within chunk by replacing single newlines with <br/>
            ch = ch.replace("\n", "<br/>")
            story.append(Paragraph(ch, normal_style))
            story.append(Spacer(1, 8))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
def build_docx_from_text(text: str) -> bytes:
    """
    Create a DOCX file from cleaned text with basic formatting.
    """
    buffer = io.BytesIO()
    doc = Document()
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    for para in paragraphs:
        doc.add_paragraph(para)
        doc.add_paragraph("")  # add a blank line between paragraphs

    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()

async def extract_images_from_pdf(file: UploadFile) -> list[io.BytesIO]:
    """
    Extract all images (diagrams) from the uploaded PDF and return as list of BytesIO.
    """
    images = []
    contents = await file.read()
    doc = fitz.open(stream=contents, filetype="pdf")
    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = io.BytesIO(base_image["image"])
            images.append(image_bytes)
    return images

def generate_food_app_pdf() -> bytes:
    architecture_text = """
Food Delivery Application - System Design & Architecture

1. Overview
This application allows users to browse restaurants, explore menus, place orders, track delivery status, and make online payments. Restaurants manage their menus and orders, while delivery partners receive delivery assignments.

2. Core Features
- User Authentication & Profile Management
- Restaurant Listing & Menu Display
- Real-Time Order Placement
- Payment Gateway Integration
- Live Order Status Tracking
- Delivery Partner Tracking
- Ratings & Feedback System

3. Technology Stack
Frontend:
- ReactJS / Next.js
- Redux Toolkit / Context for State Management
- TailwindCSS / Material UI

Backend:
- Node.js with Express OR Java Spring Boot
- RESTful APIs with JWT Authentication

Database:
- PostgreSQL / MySQL
- Redis for Caching

Cloud & DevOps:
- AWS EC2, S3, API Gateway, Lambda
- Docker + Kubernetes
- CI/CD using GitHub Actions or Jenkins

4. High-Level Flow
User → Frontend → Backend Services → DB & Payment → Notification Service → Delivery Tracking

5. Order Workflow
- User selects items and places order
- Payment is processed
- Backend assigns delivery partner
- Delivery tracking enabled via WebSocket / Kafka
- User receives real-time updates

6. Deployment Architecture
- Load Balancer → Auto Scaling EC2 / Kubernetes Pods
- Centralized Logging & Monitoring (CloudWatch / Grafana)
"""

    # ✅ Make sure build_pdf_from_text is imported above
    return build_pdf_from_text(architecture_text)
