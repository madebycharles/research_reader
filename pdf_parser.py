"""
PDF parser with intelligent handling of:
- Two-column academic paper layouts
- Hyphenated line breaks
- Section header detection
- Inline citation stripping
- Figure/table placeholder insertion
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional
import fitz  # PyMuPDF


@dataclass
class Section:
    title: str
    paragraphs: List[str] = field(default_factory=list)


@dataclass
class ParsedPaper:
    title: str
    sections: List[Section] = field(default_factory=list)


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def parse_pdf(pdf_path: str) -> ParsedPaper:
    doc = fitz.open(pdf_path)

    raw_blocks: List[str] = []

    for page in doc:
        page_width = page.rect.width
        # type=0 → text blocks; returns (x0, y0, x1, y1, text, block_no, block_type)
        blocks = [b for b in page.get_text("blocks") if b[6] == 0]

        if _is_two_column(blocks, page_width):
            mid = page_width * 0.5
            left  = sorted([b for b in blocks if b[0] < mid], key=lambda b: b[1])
            right = sorted([b for b in blocks if b[0] >= mid], key=lambda b: b[1])
            ordered = left + right
        else:
            ordered = sorted(blocks, key=lambda b: b[1])

        for block in ordered:
            text = block[4].strip()
            if text:
                raw_blocks.append(text)

    doc.close()

    full_text = "\n\n".join(raw_blocks)
    full_text = _dehyphenate(full_text)
    full_text = _strip_citations(full_text)
    full_text = _replace_figure_refs(full_text)

    title = _extract_title(raw_blocks)
    sections = _extract_sections(full_text)

    return ParsedPaper(title=title, sections=sections)


# ------------------------------------------------------------------
# Column detection
# ------------------------------------------------------------------

def _is_two_column(blocks: list, page_width: float) -> bool:
    """Return True if blocks suggest a two-column layout."""
    texts = [b for b in blocks if len(b[4].strip()) > 30]
    if len(texts) < 4:
        return False

    x0_vals = [b[0] for b in texts]
    mid = page_width * 0.45

    left_count  = sum(1 for x in x0_vals if x < mid)
    right_count = sum(1 for x in x0_vals if x >= mid)

    # Both halves must have meaningful content
    return right_count >= 2 and (right_count / len(x0_vals)) >= 0.20


# ------------------------------------------------------------------
# Text cleaning
# ------------------------------------------------------------------

def _dehyphenate(text: str) -> str:
    """Fix words split with a hyphen across a line break."""
    # "investiga-\ntion" → "investigation"
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    # Single newlines within a block → space (preserve paragraph breaks = double newlines)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    text = re.sub(r' {2,}', ' ', text)
    return text


def _strip_citations(text: str) -> str:
    """Remove inline citations that are meaningless when read aloud."""
    # Numeric: [1], [1,2], [1-4], [1, 2, 3]
    text = re.sub(r'\[\d+(?:[,\s\-]\d+)*\]', '', text)
    # Author-year: (Smith, 2023) (Smith et al., 2023) (Smith & Jones, 2022)
    text = re.sub(r'\([A-Z][a-zé]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][a-z]+))?,\s*\d{4}[a-z]?\)', '', text)
    # Multiple author-year separated by semicolons: (A, 2020; B, 2021)
    text = re.sub(r'\([^)]{0,80}\d{4}[^)]{0,20}\)', '', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r' ([.,;:])', r'\1', text)
    return text


def _replace_figure_refs(text: str) -> str:
    """Replace figure/table references with verbal equivalents."""
    text = re.sub(r'(?i)\bfig(?:ure)?\.?\s*(\d+[a-z]?)\b', r'Figure \1', text)
    text = re.sub(r'(?i)\btab(?:le)?\.?\s*(\d+[a-z]?)\b', r'Table \1', text)
    # Remove raw figure/table blocks (lines that are only a caption label)
    text = re.sub(r'(?m)^(Figure|Table)\s+\d+[.:]\s*$', '', text)
    return text


# ------------------------------------------------------------------
# Structure extraction
# ------------------------------------------------------------------

# Patterns that strongly suggest a section header
_HEADER_PATTERNS = [
    re.compile(r'^\d+\.?\d*\.?\s+[A-Z]'),           # "1. Introduction" / "2.1 Method"
    re.compile(r'^[IVX]+\.\s+[A-Z]'),                # "I. Introduction" (Roman)
    re.compile(r'^(Abstract|Introduction|Background|Related Work|'
               r'Methodology|Methods|Experiments?|Results?|'
               r'Discussion|Conclusion|References|Acknowledgm)', re.I),
    re.compile(r'^[A-Z][A-Z\s]{4,}$'),               # "INTRODUCTION" all-caps
]


def _looks_like_header(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 80:
        return False
    for pat in _HEADER_PATTERNS:
        if pat.match(line):
            return True
    # Short title-cased line with no trailing sentence punctuation
    if len(line) < 60 and not line.endswith(('.', ',', ';', '?', '!')):
        words = line.split()
        if len(words) >= 2:
            cap_ratio = sum(1 for w in words if w and w[0].isupper()) / len(words)
            if cap_ratio >= 0.7:
                return True
    return False


def _extract_sections(text: str) -> List[Section]:
    sections: List[Section] = []
    current = Section(title="Preamble")
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

        if _looks_like_header(line):
            flush_section()
            current = Section(title=line)
        else:
            current_para.append(line)

    flush_section()

    if not sections:
        return [Section(title="Content", paragraphs=[text])]

    return sections


# ------------------------------------------------------------------
# Title extraction
# ------------------------------------------------------------------

def _extract_title(blocks: List[str]) -> str:
    for block in blocks[:8]:
        line = block.strip().splitlines()[0].strip()
        if 15 < len(line) < 200 and not line.lower().startswith('http'):
            return line
    return "Untitled Paper"
