import re


def is_bin_pattern(text):
    cleaned = text.strip()
    if re.match(r"^\d{6,16}[xX]*$", cleaned):
        return True
    if re.match(r"^[\dxX]{6,19}$", cleaned):
        digits_only = re.sub(r"[^0-9]", "", cleaned)
        if len(digits_only) >= 6:
            return True
    return False


def extract_bin_prefix(text):
    cleaned = re.sub(r"[^0-9]", "", text.lower().split("x")[0] if "x" in text.lower() else text)
    return cleaned if len(cleaned) >= 6 else None


def validate_bin_input(text):
    if not text or len(text) < 6:
        return False, "BIN must be at least 6 digits."
    prefix = extract_bin_prefix(text)
    if not prefix:
        return False, "Invalid BIN format."
    return True, prefix
