import importlib.resources


def loads(filename: str) -> str:
    return importlib.resources.read_text(__package__, filename)
