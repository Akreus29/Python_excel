import re

def hex_to_32bit_bin(hex_val) -> str:
    """Convert hex value to 32-bit binary string."""
    try:
        hex_str = str(hex_val).strip().lower()
        if hex_str.startswith("0x"):
            hex_str = hex_str[2:]
        hex_str = hex_str.zfill(8)
        return bin(int(hex_str, 16))[2:].zfill(32)
    except Exception:
        return "0" * 32

def is_likely_binary(value: str) -> bool:
    """
    Determine if a string is likely a binary string vs hex.
    
    Rules:
    - If it contains any non-hex characters (not 0-9, a-f, A-F), it's not valid
    - If it contains hex digits (2-9, a-f, A-F), it's definitely hex
    - If it only contains 0s and 1s:
        - Length <= 8: assume it's hex (like '11111111' = 0x11111111)
        - Length > 8: assume it's binary
    """
    val_str = str(value).strip().lower()
    
    # Remove 0x prefix if present
    if val_str.startswith('0x'):
        val_str = val_str[2:]
    
    # Check if all characters are valid hex
    if not all(c in '0123456789abcdef' for c in val_str):
        return False  # Not valid hex or binary
    
    # If it contains any hex digits (2-9, a-f), it's definitely hex
    if any(c in '23456789abcdef' for c in val_str):
        return False
    
    # At this point, it only contains 0s and 1s
    # If length <= 8, it's likely a hex value (e.g., '11111111' = 0x11111111)
    # If length > 8, it's likely a binary string
    return len(val_str) > 8

def detect_bit_length(value) -> int:
    """Detect the bit length of a value (binary string or hex)."""
    val_str = str(value).strip()

    if is_likely_binary(val_str):
        return len(val_str)
    else:
        return 32  # Hex values are always 32-bit

def slice_bits_custom(bin_str: str, bit_assignments: list[int]) -> list[str]:
    """Slice binary string according to custom bit assignments."""
    slices = []
    start = 0

    for bits in bit_assignments:
        if start >= len(bin_str):
            slices.append('0' * bits)
        elif start + bits > len(bin_str):
            remaining = len(bin_str) - start
            slice_val = bin_str[start:] + '0' * (bits - remaining)
            slices.append(slice_val)
        else:
            slice_val = bin_str[start:start + bits].zfill(bits)  # Force pad to required bit length
            slices.append(slice_val)
        start += bits

    return slices

def parse_bit_assignments(assignment_str: str) -> list[int]:
    """Parse comma-separated bit assignments string."""
    try:
        parts = assignment_str.strip().split(',')
        return [int(p.strip()) for p in parts if p.strip()]
    except ValueError:
        raise ValueError("Invalid bit assignments. Please use comma-separated integers.")

def generate_column_names(base_name: str, bit_assignments: list[int]) -> list[str]:
    """Generate default column names based on bit assignments."""
    names = []
    for i, bits in enumerate(bit_assignments):
        names.append(f"{base_name}_b{i}_{bits}bit")
    return names

def slice_bits(bin_str: str, slice_size: int) -> list[str]:
    """Original uniform slicing function - works with any bit length."""
    slices = []
    bit_length = len(bin_str)

    for i in range(0, bit_length, slice_size):
        end_pos = min(i + slice_size, bit_length)
        slices.append(bin_str[i:end_pos])

    return slices