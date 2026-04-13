# -*- coding: utf-8 -*-
"""
PDF parser for academic papers.

Excluded from audio (but noted in ParsedPaper.metadata):
  - Running page headers and footers (detected by position + cross-page repetition)
  - Publisher footnotes: copyright, DOI, received/accepted dates (pattern-matched)
  - Author affiliations and contact info (small font, first pages, pattern-matched)
  - Figure and table captions (pattern-matched)

Included in audio:
  - All body text, ordered correctly for single- and two-column layouts
  - Section announcements injected by processor.py
"""

import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------

@dataclass
class Section:
    title: str
    paragraphs: List[str] = field(default_factory=list)


@dataclass
class ParsedPaper:
    title: str
    sections: List[Section] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    # metadata keys (all excluded from audio):
    #   running_headers, running_footers, publisher_notes,
    #   affiliations, figure_captions, body_font_size


# ---------------------------------------------------------------------------
# Internal block representation
# ---------------------------------------------------------------------------

@dataclass
class _Block:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page_num: int
    page_height: float
    font_size: float
    label: str = "body"
    # label values:
    #   body | running_header | running_footer |
    #   publisher_note | affiliation | figure_caption


# ---------------------------------------------------------------------------
# Signal patterns
# ---------------------------------------------------------------------------

# Publisher notes, copyright, metadata lines
_PUBLISHER_PATTERNS = [
    re.compile(r'©|Copyright', re.I),
    re.compile(r'All rights reserved', re.I),
    re.compile(r'https?://doi\.org', re.I),
    re.compile(r'\bDOI\s*:\s*10\.\d{4}', re.I),
    re.compile(r'\bReceived\s*:', re.I),
    re.compile(r'\bAccepted\s*:', re.I),
    re.compile(r'\bPublished\s+(online|by)\b', re.I),
    re.compile(r'\bCorresponding author\b', re.I),
    re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[a-zA-Z]{2,}'),  # email
    re.compile(r'^\s*\d{1,4}\s*$'),          # bare page number
    re.compile(r'\bARXIV\s*:\s*\d', re.I),
    re.compile(r'\bPREPRINT\b', re.I),
    re.compile(r'\bunder review\b', re.I),
]

# Affiliation signals (only applied to small-font text on early pages)
_AFFILIATION_PATTERNS = [
    re.compile(r'\b(University|Institut[e]?|Department|Laboratory|'
               r'College|School of|Faculty of|Centre for)\b', re.I),
    re.compile(r'\bORCID\b', re.I),
    re.compile(r'^\s*[¹²³⁴⁵⁶⁷⁸⁹†‡∗\*]\s*[A-Z]'),   # superscript + institution
]

# Figure and table caption starts
_FIGURE_CAPTION_RE = re.compile(
    r'^(?:Fig(?:ure)?|Table|Appendix|Supplementary)\s*\.?\s*\d+', re.I
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_pdf(pdf_path: str) -> ParsedPaper:
    doc = fitz.open(pdf_path)
    n_pages = len(doc)

    # Pass 1 — extract all blocks with positional and font metadata
    all_blocks = _extract_blocks(doc)

    # Pass 2 — estimate the body font size (used for small-text detection)
    body_font_size = _estimate_body_font_size(all_blocks)

    # Pass 3 — rule-based labelling (position, patterns, font size)
    _classify_by_rules(all_blocks, body_font_size)

    # Pass 4 — cross-page repetition confirms running headers / footers
    _classify_by_repetition(all_blocks)

    # Pass 5 — order body blocks per page, respecting two-column layouts
    body_blocks = [b for b in all_blocks if b.label == "body"]
    ordered = _order_body_blocks(body_blocks, doc)

    # Build full text from body blocks only
    full_text = "\n\n".join(b.text for b in ordered)
    full_text = _dehyphenate(full_text)
    full_text = _strip_citations(full_text)
    full_text = _replace_figure_refs(full_text)

    title    = _extract_title(all_blocks)
    sections = _extract_sections(full_text)
    metadata = _build_metadata(all_blocks, body_font_size)

    doc.close()
    return ParsedPaper(title=title, sections=sections, metadata=metadata)


# ---------------------------------------------------------------------------
# Block extraction — uses get_text("dict") for font size access
# ---------------------------------------------------------------------------

def _extract_blocks(doc: fitz.Document) -> List[_Block]:
    blocks: List[_Block] = []
    for page_num, page in enumerate(doc):
        ph = page.rect.height
        for raw in page.get_text("dict").get("blocks", []):
            if raw.get("type") != 0:        # skip image blocks
                continue
            text = _reconstruct_text(raw).strip()
            if not text:
                continue
            bbox  = raw["bbox"]
            fsize = _dominant_font_size(raw)
            blocks.append(_Block(
                text=text,
                x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3],
                page_num=page_num,
                page_height=ph,
                font_size=fsize,
            ))
    return blocks


def _reconstruct_text(raw: dict) -> str:
    """Rebuild plain text from a dict-mode block, preserving line structure."""
    lines = []
    for line in raw.get("lines", []):
        line_text = "".join(s.get("text", "") for s in line.get("spans", []))
        lines.append(line_text)
    return "\n".join(lines)


def _dominant_font_size(raw: dict) -> float:
    """Return the font size covering the most characters in this block."""
    tally: Dict[float, int] = defaultdict(int)
    for line in raw.get("lines", []):
        for span in line.get("spans", []):
            size = round(span.get("size", 0), 1)
            tally[size] += len(span.get("text", ""))
    return max(tally, key=tally.__getitem__) if tally else 0.0


# ---------------------------------------------------------------------------
# Body font size estimation
# ---------------------------------------------------------------------------

def _estimate_body_font_size(blocks: List[_Block]) -> float:
    """
    Mode font size among blocks with substantial text.
    Rounded to nearest 0.5 pt to cluster visually similar sizes.
    """
    sizes = [
        round(b.font_size * 2) / 2
        for b in blocks
        if len(b.text) > 80 and b.font_size > 0
    ]
    return statistics.mode(sizes) if sizes else 10.0


# ---------------------------------------------------------------------------
# Classification: rule-based
# ---------------------------------------------------------------------------

_TOP_MARGIN    = 0.07   # top 7% of page height
_BOTTOM_MARGIN = 0.93   # bottom 7% of page height
_SMALL_FONT    = 0.80   # < 80% of body size → candidate footnote / affiliation


def _classify_by_rules(blocks: List[_Block], body_font_size: float) -> None:
    """Label blocks in-place. Order of checks matters — first match wins."""
    for b in blocks:
        rel_y0 = b.y0 / b.page_height
        rel_y1 = b.y1 / b.page_height
        is_small = body_font_size > 0 and b.font_size < body_font_size * _SMALL_FONT

        # ── Strict margin zones → running header / footer candidate ──────────
        if rel_y1 < _TOP_MARGIN:
            b.label = "running_header"
            continue

        if rel_y0 > _BOTTOM_MARGIN:
            b.label = "running_footer"
            continue

        # ── Publisher / metadata patterns ─────────────────────────────────────
        if any(p.search(b.text) for p in _PUBLISHER_PATTERNS):
            b.label = "publisher_note"
            continue

        # ── Figure / table captions ───────────────────────────────────────────
        first_line = b.text.splitlines()[0].strip()
        if _FIGURE_CAPTION_RE.match(first_line):
            b.label = "figure_caption"
            continue

        # ── Author affiliations (small font, early pages only) ────────────────
        if b.page_num < 3 and is_small:
            if any(p.search(b.text) for p in _AFFILIATION_PATTERNS):
                b.label = "affiliation"
                continue

        # ── Small text in lower 20% of page → likely footnote ────────────────
        if rel_y0 > 0.80 and is_small and len(b.text) < 400:
            b.label = "publisher_note"
            continue


# ---------------------------------------------------------------------------
# Classification: cross-page repetition
# ---------------------------------------------------------------------------

def _classify_by_repetition(blocks: List[_Block]) -> None:
    """
    Text that appears (normalised) on 2+ pages in the header or footer zone
    is confirmed as a running header or footer — even if rule-based pass
    left it as "body" (some papers push headers slightly below the 7% line).
    """
    # Widen the zone a bit for this pass
    candidates = [
        b for b in blocks
        if b.y0 / b.page_height < 0.13 or b.y1 / b.page_height > 0.87
    ]

    def _norm(text: str) -> str:
        # Strip digits so "Page 1" and "Page 2" match; collapse whitespace
        return re.sub(r'\s+', ' ', re.sub(r'\d+', '#', text.strip().lower()))

    by_norm: Dict[str, List[_Block]] = defaultdict(list)
    for b in candidates:
        by_norm[_norm(b.text)].append(b)

    for key, group in by_norm.items():
        if len({b.page_num for b in group}) >= 2:
            for b in group:
                is_top = b.y0 / b.page_height < 0.5
                b.label = "running_header" if is_top else "running_footer"


# ---------------------------------------------------------------------------
# Body block ordering — two-column aware
# ---------------------------------------------------------------------------

def _order_body_blocks(blocks: List[_Block], doc: fitz.Document) -> List[_Block]:
    by_page: Dict[int, List[_Block]] = defaultdict(list)
    for b in blocks:
        by_page[b.page_num].append(b)

    ordered: List[_Block] = []
    for page_num in sorted(by_page):
        page_blocks = by_page[page_num]
        page_width  = doc[page_num].rect.width

        # Convert to tuple format expected by _is_two_column
        raw = [(b.x0, b.y0, b.x1, b.y1, b.text, 0, 0) for b in page_blocks]

        if _is_two_column(raw, page_width):
            mid   = page_width * 0.5
            left  = sorted([b for b in page_blocks if b.x0 < mid],  key=lambda b: b.y0)
            right = sorted([b for b in page_blocks if b.x0 >= mid], key=lambda b: b.y0)
            ordered.extend(left + right)
        else:
            ordered.extend(sorted(page_blocks, key=lambda b: b.y0))

    return ordered


# ---------------------------------------------------------------------------
# Metadata assembly
# ---------------------------------------------------------------------------

def _build_metadata(blocks: List[_Block], body_font_size: float) -> Dict:
    def collect(label: str) -> List[str]:
        seen: set = set()
        result = []
        for b in blocks:
            if b.label == label and b.text not in seen:
                seen.add(b.text)
                result.append(b.text)
        return result

    return {
        "running_headers":  collect("running_header"),
        "running_footers":  collect("running_footer"),
        "publisher_notes":  collect("publisher_note"),
        "affiliations":     collect("affiliation"),
        "figure_captions":  collect("figure_caption"),
        "body_font_size":   body_font_size,
    }


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

def _extract_title(blocks: List[_Block]) -> str:
    """
    Title is typically the largest-font body block on page 0.
    Falls back to the first substantive line across all body blocks.
    """
    page0_body = [b for b in blocks if b.page_num == 0 and b.label == "body"]
    if page0_body:
        largest = max(page0_body, key=lambda b: b.font_size)
        line = largest.text.splitlines()[0].strip()
        if 10 < len(line) < 300:
            return line

    for b in blocks:
        if b.label == "body":
            line = b.text.splitlines()[0].strip()
            if 10 < len(line) < 300 and not line.lower().startswith("http"):
                return line

    return "Untitled Paper"


# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------

def _is_two_column(blocks: list, page_width: float) -> bool:
    texts = [b for b in blocks if len(b[4].strip()) > 30]
    if len(texts) < 4:
        return False
    x0_vals    = [b[0] for b in texts]
    mid        = page_width * 0.45
    left_count = sum(1 for x in x0_vals if x < mid)
    right_count = sum(1 for x in x0_vals if x >= mid)
    return right_count >= 2 and (right_count / len(x0_vals)) >= 0.20


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def _dehyphenate(text: str) -> str:
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    text = re.sub(r' {2,}', ' ', text)
    return text


def _strip_citations(text: str) -> str:
    text = re.sub(r'\[\d+(?:[,\s\-]\d+)*\]', '', text)
    text = re.sub(r'\([A-Z][a-zé]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][a-z]+))?,\s*\d{4}[a-z]?\)', '', text)
    text = re.sub(r'\([^)]{0,80}\d{4}[^)]{0,20}\)', '', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r' ([.,;:])', r'\1', text)
    return text


def _replace_figure_refs(text: str) -> str:
    text = re.sub(r'(?i)\bfig(?:ure)?\.?\s*(\d+[a-z]?)\b', r'Figure \1', text)
    text = re.sub(r'(?i)\btab(?:le)?\.?\s*(\d+[a-z]?)\b', r'Table \1', text)
    text = re.sub(r'(?m)^(Figure|Table)\s+\d+[.:]\s*$', '', text)
    return text


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

_SECTION_HEADER_PATTERNS = [
    re.compile(r'^\d+\.?\d*\.?\s+[A-Z]'),
    re.compile(r'^[IVX]+\.\s+[A-Z]'),
    re.compile(r'^(Abstract|Introduction|Background|Related Work|'
               r'Methodology|Methods|Experiments?|Results?|'
               r'Discussion|Conclusion|References|Acknowledgm)', re.I),
    re.compile(r'^[A-Z][A-Z\s]{4,}$'),
]


def _looks_like_section_header(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 80:
        return False
    for pat in _SECTION_HEADER_PATTERNS:
        if pat.match(line):
            return True
    if len(line) < 60 and not line.endswith(('.', ',', ';', '?', '!')):
        words = line.split()
        if len(words) >= 2:
            cap_ratio = sum(1 for w in words if w and w[0].isupper()) / len(words)
            if cap_ratio >= 0.7:
                return True
    return False


def _extract_sections(text: str) -> List[Section]:
    sections: List[Section] = []
    current      = Section(title="Preamble")
    current_para: List[str] = []

    def flush_paragraph():
        para = ' '.join(current_para).strip()
        if para:
            current.paragraphs.append(para)
        current_para.clear()

    def flush_section():
        flush_paragraph()
        if current.paragraphs:
            sections.append(current)

    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            continue
        if _looks_like_section_header(line):
            flush_section()
            current = Section(title=line)
        else:
            current_para.append(line)

    flush_section()

    if not sections:
        return [Section(title="Content", paragraphs=[text])]
    return sections
