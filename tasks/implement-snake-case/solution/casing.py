import re


def to_snake_case(name):
    """Convert a camelCase/PascalCase identifier to snake_case.

    Splits an acronym from a following capitalized word (HTTPServer ->
    HTTP_Server) and a lowercase/digit from a following capital (camelCase ->
    camel_Case), then lowercases the whole thing.
    """
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()
