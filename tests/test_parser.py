import pytest
from pathlib import Path
from bugbee.parser.error_parser import extract_location, sanitize_error, error_hash

def test_extract_location_python():
    stderr = 'Traceback (most recent call last):\n  File "example.py", line 3, in <module>\n    raise ValueError("boom")\nValueError: boom\n'
    path, line = extract_location(stderr, ["python", "example.py"])
    assert path == Path('example.py')
    assert line == 3

def test_sanitize_error():
    raw = "/usr/home/project/example.py:12:23 error at 12:34:56"
    sanitized = sanitize_error(raw)
    assert "<PATH>" in sanitized
    assert "<TIME>" in sanitized or "<NUM>" in sanitized

def test_error_hash_is_stable():
    s = "some deterministic error text"
    h1 = error_hash(s)
    h2 = error_hash(s)
    assert h1 == h2
