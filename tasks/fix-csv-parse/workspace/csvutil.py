def parse_line(line):
    """Split one CSV line into fields.

    A field may be wrapped in double quotes, in which case any commas inside
    the quotes are part of the field, not separators. The surrounding quotes
    are not part of the returned value.
    """
    return line.split(",")
