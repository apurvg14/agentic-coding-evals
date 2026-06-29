def is_valid(number):
    """Return True if the digit string passes the Luhn checksum.

    Walking right to left, every second digit is doubled (subtract 9 if the
    result exceeds 9); the card is valid if the total is a multiple of 10.
    """
    digits = [int(c) for c in number]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0
