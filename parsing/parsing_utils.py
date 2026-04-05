
def truncate_with_elipses(your_string, length, padding=0):
    truncated = your_string
    if length > 0 and len(your_string) > length:
        truncated = your_string[:length-3]
        truncated = truncated + "..."

    if length > 0 and truncated == your_string:
        truncated = truncated.ljust(length)

    if padding > 0:
        truncated = truncated + " " * padding

    return truncated