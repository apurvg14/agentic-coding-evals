import math


def page_offset(page, per_page):
    """Zero-based index of the first item on a (1-indexed) page."""
    return (page - 1) * per_page


def total_pages(total_items, per_page):
    """Number of pages needed to show all items."""
    if total_items <= 0:
        return 0
    return math.ceil(total_items / per_page)
