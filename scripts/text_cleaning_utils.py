"""Text cleaning utilities for Project Gutenberg books.

Provides functions to strip Gutenberg headers/footers, remove escape sequences,
normalize Unicode tokens, and collapse whitespace. Used by the downloader and
sample-generation scripts.
"""

# Markers that delimit the actual book text inside a Gutenberg file
TEXT_START_MARKERS = [
    "*** START OF",
    "***START OF",
    "*** START PROJECT",
]

TEXT_END_MARKERS = [
    "*** END OF",
    "***END OF",
    "*** END PROJECT",
    "End of the Project",
    "End of Project",
]


def strip_gutenberg_headers(text: str) -> str:
    """Remove Gutenberg preamble/postamble surrounding the book text.

    Scans first 600 lines for a start marker and lines 100+ for an end marker.
    Returns the text between those markers, or the original text if none found.
    """
    lines = text.splitlines()
    start_idx = 0
    end_idx = len(lines)

    # Find start marker in the first 600 lines
    for i, line in enumerate(lines[:600]):
        upper = line.strip().upper()
        if any(upper.startswith(m.upper()) for m in TEXT_START_MARKERS):
            start_idx = i + 1  # skip the marker line itself
            break

    # Find end marker after line 100
    for i in range(max(100, start_idx), len(lines)):
        upper = lines[i].strip().upper()
        if any(upper.startswith(m.upper()) for m in TEXT_END_MARKERS):
            end_idx = i
            break

    return "\n".join(lines[start_idx:end_idx])


def remove_escape_sequences(text: str) -> str:
    """Replace literal newlines, carriage returns, and tabs with spaces."""
    return text.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def remove_funny_tokens(text: str) -> str:
    """Replace common Unicode punctuation with ASCII equivalents.

    Handles curly quotes (\u201c \u201d \u2018 \u2019) and em-dash (\u2014).
    """
    replacements = {
        "\u201c": " ",   # left double curly quote
        "\u201d": " ",   # right double curly quote
        "\u2018": "'",   # left single curly quote
        "\u2019": "'",   # right single curly quote
        "\u2014": " ",   # em-dash
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into single spaces and strip edges."""
    return " ".join(text.split())


def clean_gutenberg_text(text: str) -> str:
    """Full cleaning pipeline for a raw Gutenberg book text.

    1. Strip Gutenberg headers/footers
    2. Remove escape sequences
    3. Replace Unicode funny tokens
    4. Normalize whitespace
    """
    text = strip_gutenberg_headers(text)
    text = remove_escape_sequences(text)
    text = remove_funny_tokens(text)
    text = normalize_whitespace(text)
    return text


if __name__ == "__main__":
    import sys

    raw = sys.stdin.read()
    print(clean_gutenberg_text(raw))
