def parse_line(line):
    """Split one CSV line into fields.

    A field may be wrapped in double quotes, in which case any commas inside
    the quotes are part of the field, not separators. The surrounding quotes
    are not part of the returned value.
    """
    fields = []
    cur = []
    in_quotes = False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == "," and not in_quotes:
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields
