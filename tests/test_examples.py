import py_compile
import runpy
from pathlib import Path

import pytest

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.py"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_compiles(path):
    py_compile.compile(str(path), doraise=True)


def test_custom_source_example_runs_offline(capsys):
    runpy.run_path(str(Path(__file__).parent.parent / "examples" / "custom_source.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert "מכרז לדוגמה" in out
