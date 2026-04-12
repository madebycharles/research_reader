# -*- coding: utf-8 -*-
"""
Text processing pipeline that transforms parsed paper text into
audio-friendly speech, incorporating the key listening UX principles:
- Section announcements
- Acronym expansion on first use
- Symbol/special char normalisation
- XTTS-safe chunking (~200 chars)
"""

import re
from typing import List, Set

# ------------------------------------------------------------------
# Acronym table — expanded on first use per listening session
# ------------------------------------------------------------------

ACRONYMS = {
    'AI': 'Artificial Intelligence',
    'ML': 'Machine Learning',
    'NLP': 'Natural Language Processing',
    'LLM': 'Large Language Model',
    'LLMs': 'Large Language Models',
    'DL': 'Deep Learning',
    'RL': 'Reinforcement Learning',
    'RLHF': 'Reinforcement Learning from Human Feedback',
    'SFT': 'Supervised Fine-Tuning',
    'NN': 'Neural Network',
    'CNN': 'Convolutional Neural Network',
    'RNN': 'Recurrent Neural Network',
    'LSTM': 'Long Short-Term Memory',
    'GAN': 'Generative Adversarial Network',
    'VAE': 'Variational Auto-Encoder',
    'MLP': 'Multi-Layer Perceptron',
    'FFN': 'Feed-Forward Network',
    'MHA': 'Multi-Head Attention',
    'GPU': 'Graphics Processing Unit',
    'CPU': 'Central Processing Unit',
    'API': 'Application Programming Interface',
    'SOTA': 'State of the Art',
    'SoTA': 'State of the Art',
    'BERT': 'Bidirectional Encoder Representations from Transformers',
    'GPT': 'Generative Pre-trained Transformer',
    'CV': 'Computer Vision',
    'NLU': 'Natural Language Understanding',
    'NLG': 'Natural Language Generation',
    'RAG': 'Retrieval-Augmented Generation',
    'CLIP': 'Contrastive Language-Image Pre-training',
    'ViT': 'Vision Transformer',
    'ROI': 'Return on Investment',
    'KV': 'Key-Value',
    'FT': 'Fine-Tuning',
}

# Sections that are meaningless or distracting when read aloud
BOILERPLATE_TITLES = {
    'acknowledgments', 'acknowledgements', 'references',
    'bibliography', 'appendix', 'supplementary material',
    'supplementary', 'author contributions', 'competing interests',
    'conflict of interest', 'data availability', 'ethics statement',
    'funding', 'author information', 'code availability',
    'broader impact', 'societal impact',
}


# ------------------------------------------------------------------
# Public helpers
# ------------------------------------------------------------------

def is_boilerplate(section_title: str) -> bool:
    return section_title.lower().strip().rstrip('.') in BOILERPLATE_TITLES


def prepare_for_tts(
    section_title: str,
    paragraph: str,
    is_first_paragraph: bool,
    acronym_seen: Set[str],
) -> str:
    """
    Return TTS-ready text for one paragraph.
    - Injects section announcement on the first paragraph of each section.
    - Expands acronyms on first use (mutates acronym_seen).
    - Normalises symbols and cleans up the string.
    """
    parts: List[str] = []

    if is_first_paragraph:
        parts.append(f"Section: {_clean_header(section_title)}.")

    text = _expand_acronyms(paragraph, acronym_seen)
    text = _normalise_for_speech(text)

    if text.strip():
        parts.append(text)

    return ' '.join(parts)


def chunk_text(text: str, max_chars: int = 200) -> List[str]:
    """
    Split text into chunks that XTTS can handle well (~200 chars).
    Splits at sentence boundaries first, then clause boundaries.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks: List[str] = []
    current = ''

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + ' ' + sentence).strip()
        else:
            if current:
                chunks.append(current)

            if len(sentence) <= max_chars:
                current = sentence
            else:
                # Break long sentence at clause punctuation
                parts = re.split(r'(?<=[,;:])\s+', sentence)
                sub = ''
                for part in parts:
                    if len(sub) + len(part) + 2 <= max_chars:
                        sub = (sub + ' ' + part).strip()
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = part[:max_chars]  # hard cut last resort
                if sub:
                    chunks.append(sub)
                current = ''

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _clean_header(title: str) -> str:
    # Strip leading numbering: "2.1 Background" → "Background"
    title = re.sub(r'^[\dIVX]+[.\d]*\s+', '', title)
    return title.strip()


def _expand_acronyms(text: str, seen: Set[str]) -> str:
    for acronym, expansion in ACRONYMS.items():
        if acronym in seen:
            continue
        pattern = rf'\b{re.escape(acronym)}\b'
        if re.search(pattern, text):
            text = re.sub(pattern, f'{expansion} ({acronym})', text, count=1)
            seen.add(acronym)
    return text


_SYMBOL_MAP = [
    ('%',   ' percent'),
    ('&',   ' and '),
    ('+',   ' plus '),
    ('→',   ' leads to '),
    ('≈',   ' approximately '),
    ('±',   ' plus or minus '),
    ('≤',   ' less than or equal to '),
    ('≥',   ' greater than or equal to '),
    ('×',   ' times '),
    ('÷',   ' divided by '),
    ('∈',   ' in '),
    ('∑',   ' sum of '),
    ('∞',   'infinity'),
    ('α',   'alpha'),
    ('β',   'beta'),
    ('γ',   'gamma'),
    ('δ',   'delta'),
    ('ε',   'epsilon'),
    ('λ',   'lambda'),
    ('θ',   'theta'),
    ('σ',   'sigma'),
    ('μ',   'mu'),
    ('π',   'pi'),
    ('ρ',   'rho'),
    ('τ',   'tau'),
    ('φ',   'phi'),
]


def _normalise_for_speech(text: str) -> str:
    # Remove URLs and emails
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\S+@\S+\.\S+', '', text)

    # Number + % needs special handling before the generic % replacement
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 percent', text)

    for symbol, replacement in _SYMBOL_MAP:
        if symbol != '%':  # already handled above
            text = text.replace(symbol, replacement)

    # Strip remaining non-ASCII
    text = re.sub(r'[^\x00-\x7F]', ' ', text)

    # Strip characters TTS stumbles over
    text = re.sub(r'[#@^*~`|\\<>{}[\]_]', ' ', text)

    # Collapse repeated punctuation
    text = re.sub(r'[.]{2,}', '.', text)
    text = re.sub(r'\s{2,}', ' ', text)

    return text.strip()
