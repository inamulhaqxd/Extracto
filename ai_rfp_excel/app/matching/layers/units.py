import re

# Storage units normalized to Bytes
STORAGE_UNITS: dict[str, float] = {
    "b": 1.0,
    "byte": 1.0,
    "bytes": 1.0,
    "kb": 1024.0,
    "kilobyte": 1024.0,
    "kilobytes": 1024.0,
    "mb": 1024.0**2,
    "megabyte": 1024.0**2,
    "megabytes": 1024.0**2,
    "mbytes": 1024.0**2,
    "gb": 1024.0**3,
    "gigabyte": 1024.0**3,
    "gigabytes": 1024.0**3,
    "gbytes": 1024.0**3,
    "tb": 1024.0**4,
    "terabyte": 1024.0**4,
    "terabytes": 1024.0**4,
    "tbytes": 1024.0**4,
    "pb": 1024.0**5,
    "petabyte": 1024.0**5,
    "petabytes": 1024.0**5,
}

# Network bandwidth normalized to bps
NETWORK_UNITS: dict[str, float] = {
    "bps": 1.0,
    "kbps": 1e3,
    "mbps": 1e6,
    "gbps": 1e9,
    "gbe": 1e9,
    "tbps": 1e12,
}

# Frequency normalized to Hz
FREQUENCY_UNITS: dict[str, float] = {
    "hz": 1.0,
    "khz": 1e3,
    "mhz": 1e6,
    "ghz": 1e9,
}

# Power normalized to Watts
POWER_UNITS: dict[str, float] = {
    "w": 1.0,
    "watt": 1.0,
    "watts": 1.0,
    "kw": 1e3,
    "kilowatt": 1e3,
    "kilowatts": 1e3,
}


def parse_numeric_with_unit(text: str) -> tuple[float, str, float] | None:
    """Extract numeric value, unit string, and normalized base unit value from text."""
    pattern = r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)"
    match = re.search(pattern, text)
    if not match:
        return None

    num_val = float(match.group(1))
    raw_unit = match.group(2).lower()

    if raw_unit in STORAGE_UNITS:
        return num_val, raw_unit, num_val * STORAGE_UNITS[raw_unit]
    if raw_unit in NETWORK_UNITS:
        return num_val, raw_unit, num_val * NETWORK_UNITS[raw_unit]
    if raw_unit in FREQUENCY_UNITS:
        return num_val, raw_unit, num_val * FREQUENCY_UNITS[raw_unit]
    if raw_unit in POWER_UNITS:
        return num_val, raw_unit, num_val * POWER_UNITS[raw_unit]

    return None


def normalize_unit_string(text: str) -> str:
    """Normalize text representations like '64 gigabytes', '64 GB', '64GB' to canonical tokens."""
    res = text
    # Normalize gigabytes -> GB, terabytes -> TB, etc.
    replacements = [
        (r"(?i)\b(\d+(?:\.\d+)?)\s*(?:gigabytes?|gbytes?|gb)\b", r"\1GB"),
        (r"(?i)\b(\d+(?:\.\d+)?)\s*(?:terabytes?|tbytes?|tb)\b", r"\1TB"),
        (r"(?i)\b(\d+(?:\.\d+)?)\s*(?:megabytes?|mbytes?|mb)\b", r"\1MB"),
        (r"(?i)\b(\d+(?:\.\d+)?)\s*(?:gigahertz|ghz)\b", r"\1GHz"),
        (r"(?i)\b(\d+(?:\.\d+)?)\s*(?:megahertz|mhz)\b", r"\1MHz"),
        (r"(?i)\b(\d+(?:\.\d+)?)\s*(?:gbps|gbe)\b", r"\1Gbps"),
        (r"(?i)\b(\d+(?:\.\d+)?)\s*(?:mbps)\b", r"\1Mbps"),
        (r"(?i)\b(\d+(?:\.\d+)?)\s*(?:watts?|w)\b", r"\1W"),
        (r"(?i)\b(\d+(?:\.\d+)?)\s*(?:kilowatts?|kw)\b", r"\1kW"),
    ]
    for pat, rep in replacements:
        res = re.sub(pat, rep, res)
    return res.strip()


def compare_quantities(
    val1_str: str,
    val2_str: str,
    operator: str = ">=",
) -> bool | None:
    """Compare two quantity strings with unit conversion.

    Returns True if comparison holds, False if not, None if units incompatible.
    """
    p1 = parse_numeric_with_unit(val1_str)
    p2 = parse_numeric_with_unit(val2_str)

    if not p1 or not p2:
        return None

    _, u1, base1 = p1
    _, u2, base2 = p2

    # Check if both are same category
    same_cat = (
        (u1 in STORAGE_UNITS and u2 in STORAGE_UNITS)
        or (u1 in NETWORK_UNITS and u2 in NETWORK_UNITS)
        or (u1 in FREQUENCY_UNITS and u2 in FREQUENCY_UNITS)
        or (u1 in POWER_UNITS and u2 in POWER_UNITS)
    )

    if not same_cat:
        return None

    if operator in (">=", "at least", "minimum", "min"):
        return base1 >= base2
    if operator in ("<=", "up to", "maximum", "max"):
        return base1 <= base2
    if operator in (">", "greater than"):
        return base1 > base2
    if operator in ("<", "less than"):
        return base1 < base2
    if operator in ("=", "==", "exact"):
        return abs(base1 - base2) < 1e-6

    return None
