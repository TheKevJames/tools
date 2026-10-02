import contextlib
import os
import pathlib
import string
import tempfile
from collections.abc import Generator

import hypothesis
from hypothesis import strategies as st

from task import files
from task import schema

NAME = st.text(string.ascii_letters + string.digits, min_size=1, max_size=8)
# Summaries can't contain the characters the index line format reserves.
SUMMARY = (
    st.text(
        string.ascii_letters + string.digits + ' .,:;!?()-_/\'"',
        min_size=1,
        max_size=30,
    )
    .map(str.strip)
    .filter(bool)
)
DESCRIPTION = st.text(
    string.ascii_letters + string.digits + string.punctuation + ' \n',
    max_size=80,
).map(lambda x: x.strip() or None)
OWNER = st.none() | st.from_regex(schema.OWNER_RE, fullmatch=True)
LINK = st.none() | st.builds(
    lambda repo, path, line: (
        f'https://github.com/TheKevJames/{repo}/blob/HEAD/{path}#L{line}'
    ),
    NAME,
    NAME,
    st.integers(min_value=1),
)
INTERVAL = st.builds(
    lambda count, unit: f'{count}{unit}',
    st.integers(1, 99),
    st.sampled_from('dwm'),
)
DETAILS = st.none() | st.builds(
    lambda next_, interval, shift: schema.Details.model_validate(
        {
            'next': next_,
            'interval': interval and {'raw': interval},
            'shift': shift,
        }
    ),
    st.dates(),
    st.none() | INTERVAL,
    st.booleans(),
)
TASK = st.builds(
    schema.Task,
    summary=SUMMARY,
    details=DETAILS,
    tag=st.lists(NAME, min_size=1, max_size=3).map(
        lambda names: schema.parse_tag_path('/'.join(names))
    ),
    description=DESCRIPTION,
    owner=OWNER,
    link=LINK,
    priority=st.none() | st.sampled_from(schema.Priority),
    size=st.none() | st.sampled_from(schema.Size),
)


@contextlib.contextmanager
def task_folder() -> Generator[pathlib.Path]:
    with tempfile.TemporaryDirectory() as folder:
        os.environ['TASK_FOLDER'] = folder
        files.task_folder.cache_clear()
        files.index_file.cache_clear()
        yield pathlib.Path(folder)


@hypothesis.settings(max_examples=200, deadline=None)
@hypothesis.given(st.lists(TASK, max_size=12))
def test_save_load_roundtrip(tasks: list[schema.Task]) -> None:
    with task_folder():
        files.save(tasks)
        loaded = files.load()

    by_ident = sorted(tasks, key=lambda t: t.ident or 0)
    assert sorted(loaded, key=lambda t: t.ident or 0) == by_ident
