"""Many small text files kept as one: the pack format, and reading a result that may live in one.

A results folder written one file per (point, job) holds hundreds of thousands of ~100-byte files
-- a 37 MB tree that occupies ~900 MB of 4 KB blocks and makes every ``git status`` crawl. A *pack*
holds them all in a single JSON file shaped like the folder tree they came from::

    {
     "pack_format": "tree/1",
     "entries": 5,
     "tree": {
      "kind=sgd/": {
       "rows=100/": {
        "result_repeat=*.json": [
         "result_repeat,accepted,fail",
         "0,12,1",
         "1,13,0"
        ],
        "elapsed.txt": "elapsed 1.0s\\n",
        "summary.json": {"accepted": [12, 13]},
        "notes.json": "{\\"a\\":1}"
       }
      }
     }
    }

Each directory is written once instead of once per file it holds, which is most of a result
file's path. Three kinds of key, told apart by their spelling:

- **directory** -- ends in ``/``; its value is the next level down.
- **table** -- holds a ``*``: every ``<prefix><N><suffix>`` file of the directory (``result_repeat=0
  .json``, ``result_repeat=1.json``, ...) as CSV rows, header first. The first column is ``N`` (named
  after the ``name=`` before it, else ``*``), the others are the keys of the flat JSON object each
  file holds, and a row's file is ``json.dumps({key: json.loads(cell), ...})``.
- **file** -- anything else. A JSON string is the file's raw text; any other JSON value is a ``.json``
  file's content, whose text is ``json.dumps(value)``.

The writer only uses the compact forms where they give back the file's text **byte for byte** -- a
table only for files that are canonical ``json.dumps`` output of a flat object of numbers, bools and
nulls sharing one key order, a parsed value only for a canonical ``json.dumps`` -- and otherwise
stores the raw string. So a pack is a lossless stand-in for its files whatever they hold.

Each entry still records its *relative path* (the keys along the way), which is what lets a pack
stand in for the files: discovery already parses parameters out of a result's relative path
(``ResultNamingConvention.parse``), so an entry parses exactly as the loose file it replaced.
``RESULTS_PACK`` is the name discovery looks for, beside the folder's manifest.

The format before 2026-11-13 -- every entry between ``BEGIN``/``END`` marker lines that each repeat
its whole path, five times the size -- is the *verbose* pack (``write_verbose_pack`` and friends).
It stays as ``distillation_simu/common/merge_text_files.py``'s format, and as what ``LEGACY_RESULTS_PACK`` names: a
folder still holding one is refused by discovery, with the command that converts it.
"""

from __future__ import annotations

import contextlib
import contextvars
import functools
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import (
    IO,
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Tuple,
)

RESULTS_PACK = "results.pack.json"
LEGACY_RESULTS_PACK = "results.pack.txt"
PACK_FORMAT = "tree/1"
CONVERT_HINT = "convert it with `python distillation_simu/simu_lab/pack_results.py pack <folder>`"


class PackEntry(NamedTuple):
    """Where a packed result's content is: the pack, and the entry's key in it."""

    path: Path
    key: str

    def read_text(self) -> str:
        return _reader_for(self.path)(self.path)[self.key]


def _reader_for(pack_path: Path):
    return read_verbose_pack if Path(pack_path).suffix == ".txt" else read_pack


@contextlib.contextmanager
def atomic_open(path: Path) -> Iterator[IO[str]]:
    """A text file to write, which replaces ``path`` only once the block completes.

    Written beside ``path`` and moved into place, so an interrupted write never leaves a truncated
    file where a whole one was, and a reader never sees a half-written one. The temporary file is
    created with mode 0666, so it ends up with the mode any other new file gets under the umask
    (``mkstemp``'s 0600 would hide it from everyone else on a shared filesystem).
    """
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            yield handle
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically -- see ``atomic_open``."""
    with atomic_open(path) as handle:
        handle.write(text)


# ============================================================================ the tree pack

_NUMBERED = re.compile(r"^(.*?)(0|[1-9]\d*)(\.json)$")
_CANONICAL_INT = re.compile(r"^(0|[1-9]\d*)$")
_PLACEHOLDER = re.compile(r"(\w+)=$")
_SCALAR = (int, float, bool, type(None))


def _natural(name: str) -> Tuple[List[object], str]:
    """``result_job=2`` before ``result_job=10``; the name itself breaks ties (``a1`` vs ``a01``)."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)], name


def _dumps(value: Any) -> str:
    """How a pack writes a value: readable, one line."""
    return json.dumps(value, ensure_ascii=False)


def _no_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"{key!r} appears twice in one object")
        result[key] = value
    return result


class _Dir:
    __slots__ = ("dirs", "files")

    def __init__(self) -> None:
        self.dirs: Dict[str, _Dir] = {}
        self.files: Dict[str, str] = {}


def _check_path(rel_path: str) -> List[str]:
    if "\n" in rel_path or "\r" in rel_path:
        raise ValueError(f"a pack entry's path cannot hold a line break: {rel_path!r}")
    segments = rel_path.split("/")
    for segment in segments:
        if segment in ("", ".", ".."):
            raise ValueError(f"a pack entry's path cannot hold an empty, '.' or '..' part: {rel_path!r}")
        if "*" in segment:
            raise ValueError(f"a pack entry's path cannot hold a '*', which marks a table: {rel_path!r}")
    return segments


def _build(items: List[Tuple[str, str]]) -> _Dir:
    root = _Dir()
    for rel_path, content in items:
        *dirs, name = _check_path(rel_path)
        node = root
        for depth, segment in enumerate(dirs):
            if segment in node.files:
                raise ValueError(f"{'/'.join(dirs[: depth + 1])!r} is both a file and a directory")
            node = node.dirs.setdefault(segment, _Dir())
        if name in node.files:
            raise ValueError(f"{rel_path!r} appears twice; a pack holds one entry per path")
        if name in node.dirs:
            raise ValueError(f"{rel_path!r} is both a file and a directory")
        node.files[name] = content
    return root


def _row_text(header: List[str], row: str) -> Tuple[str, str]:
    """``(N, the file's text)`` for one table row -- the only way a table is ever read back."""
    number, _, rest = row.partition(",")
    if not _CANONICAL_INT.match(number):
        raise ValueError(f"a table row's first cell is not a file number: {row!r}")
    # One parse per row, not per cell: a 75k-row pack reads 3x faster.
    try:
        values = json.loads(f"[{rest}]")
    except ValueError as error:
        raise ValueError(f"a table row does not parse: {row!r}") from error
    if len(values) != len(header) - 1 or not all(isinstance(v, _SCALAR) for v in values):
        raise ValueError(f"a table row is not {len(header) - 1} plain values: {row!r}")
    return number, json.dumps(dict(zip(header[1:], values)))


def _tables(files: Dict[str, str]) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """``(tables, what is left)``: every numbered family of the directory's files that a table
    reproduces byte for byte, as rows; everything else as it was."""
    families: Dict[Tuple[str, str], List[Tuple[int, str]]] = {}
    for name in files:
        match = _NUMBERED.match(name)
        if match:
            families.setdefault((match.group(1), match.group(3)), []).append(
                (int(match.group(2)), name))
    tables: Dict[str, List[str]] = {}
    taken = set()
    for (prefix, suffix), members in families.items():
        if len(members) < 2:
            continue
        members.sort()
        rows = _table_rows(prefix, [(number, files[name]) for number, name in members])
        if rows is not None:
            tables[prefix + "*" + suffix] = rows
            taken.update(name for _, name in members)
    return tables, {name: text for name, text in files.items() if name not in taken}


def _table_rows(prefix: str, members: List[Tuple[int, str]]) -> Optional[List[str]]:
    keys: Optional[List[str]] = None
    rows = []
    for number, text in members:
        try:
            value = json.loads(text)
        except ValueError:
            return None
        if not isinstance(value, dict):
            return None
        if keys is None:
            keys = list(value)
            if not keys or any("," in key for key in keys):
                return None
        if list(value) != keys or not all(isinstance(v, _SCALAR) for v in value.values()):
            return None
        rows.append(",".join([str(number), *(json.dumps(value[key]) for key in keys)]))
    placeholder = _PLACEHOLDER.search(prefix)
    header = [placeholder.group(1) if placeholder else "*", *keys]
    # The guarantee, checked rather than argued: every row gives its file back exactly.
    for (number, text), row in zip(members, rows):
        if _row_text(header, row) != (str(number), text):
            return None
    return [",".join(header), *rows]


def _file_value(name: str, text: str) -> Any:
    """A ``.json`` file's content parsed, where re-serialising gives the text back; else the text."""
    if name.endswith(".json"):
        try:
            value = json.loads(text)
        except ValueError:
            return text
        if not isinstance(value, str) and json.dumps(value) == text:
            return value
    return text


def _dump(node: _Dir, depth: int, out: List[str]) -> None:
    """Write ``node``'s members, one per line (and one table row per line), comma-separated."""
    pad = " " * depth
    tables, files = _tables(node.files)
    members: List[Tuple[str, str, Any]] = (
        [("table", key, rows) for key, rows in sorted(tables.items(), key=lambda kv: _natural(kv[0]))]
        + [("file", name, files[name]) for name in sorted(files, key=_natural)]
        + [("dir", name, node.dirs[name]) for name in sorted(node.dirs, key=_natural)]
    )
    for index, (kind, key, value) in enumerate(members):
        comma = "," if index < len(members) - 1 else ""
        if kind == "dir":
            out.append(f"{pad}{_dumps(key + '/')}: {{")
            _dump(value, depth + 1, out)
            out.append(f"{pad}}}{comma}")
        elif kind == "table":
            out.append(f"{pad}{_dumps(key)}: [")
            out.extend(f"{pad} {_dumps(row)}{',' if i < len(value) - 1 else ''}"
                       for i, row in enumerate(value))
            out.append(f"{pad}]{comma}")
        else:
            out.append(f"{pad}{_dumps(key)}: {_dumps(_file_value(key, value))}{comma}")


def write_pack(pack_path: Path, entries: Mapping[str, str] | Iterable[Tuple[str, str]]) -> int:
    """Write ``entries`` (``relative path -> content``) as one tree pack; returns how many.

    The order entries are given in does not matter: directories and files come out sorted (numbers
    naturally), so a pack is a function of its entries and re-packing an unchanged folder gives no
    diff. Refuses a path given twice, a path that is also another's directory, a line break, ``*``
    or an empty/``.``/``..`` part in a path. Written to a temporary file and moved into place, so an
    interrupted write never leaves a truncated pack where a whole one was.
    """
    items = list(entries.items() if isinstance(entries, Mapping) else entries)
    root = _build(items)
    lines = ["{", f' "pack_format": {_dumps(PACK_FORMAT)},', f' "entries": {len(items)},']
    if root.dirs or root.files:
        lines.append(' "tree": {')
        _dump(root, 2, lines)
        lines.append(" }")
    else:
        lines.append(' "tree": {}')
    lines.append("}")
    with atomic_open(pack_path) as out:
        out.write("\n".join(lines) + "\n")
    return len(items)


def _walk(node: Any, prefix: str, out: Dict[str, str], where: Path) -> None:
    if not isinstance(node, dict):
        raise ValueError(f"{where}: {prefix or 'the tree'} is not a directory object")
    for key, value in node.items():
        if key.endswith("/"):
            _walk(value, prefix + key, out, where)
            continue
        if "*" in key:
            if (key.count("*") != 1 or not isinstance(value, list) or len(value) < 2
                    or not all(isinstance(row, str) for row in value)):
                raise ValueError(f"{where}: {prefix + key!r} is not a table (a header and its rows)")
            header = value[0].split(",")
            if len(set(header)) != len(header):
                raise ValueError(f"{where}: {prefix + key!r} has a repeated column")
            found = [(prefix + key.replace("*", number), text)
                     for number, text in (_row_text(header, row) for row in value[1:])]
        else:
            found = [(prefix + key, value if isinstance(value, str) else json.dumps(value))]
        for rel_path, text in found:
            if rel_path in out:
                raise ValueError(f"{where}: {rel_path!r} appears twice")
            out[rel_path] = text


def read_pack(pack_path: Path) -> Mapping[str, str]:
    """Every entry of a pack, ``relative path -> content``, in file order, as a read-only mapping.

    Raises ``ValueError`` on anything that is not a well-formed pack -- not JSON (truncated, say),
    another format, an object key repeated, a malformed table, a path held twice, or a count other
    than the header's -- rather than returning partial data from a file that was edited.

    Parsed once per version of the file: the cache is keyed on the pack's size and mtime, so a
    rewritten pack is re-read and an unchanged one is not -- discovery calls this once per experiment
    type and a reader once per result. The cache names a pack by its absolute path, not its resolved
    one: ``resolve()`` walks every component through the filesystem, and at one call per result that
    was a visible share of reading a folder.
    """
    stat = os.stat(pack_path)
    return _read_pack(os.path.abspath(pack_path), stat.st_size, stat.st_mtime_ns)


@functools.lru_cache(maxsize=16)
def _read_pack(absolute: str, size: int, mtime_ns: int) -> Mapping[str, str]:
    where = Path(absolute)
    try:
        with open(where, "r", encoding="utf-8") as handle:
            data = json.load(handle, object_pairs_hook=_no_duplicate_keys)
    except ValueError as error:
        raise ValueError(f"{where} is not a readable pack: {error}") from error
    if not isinstance(data, dict) or set(data) != {"pack_format", "entries", "tree"}:
        raise ValueError(f"{where} is not a pack: expected pack_format, entries and tree")
    if data["pack_format"] != PACK_FORMAT:
        raise ValueError(f"{where}: unknown pack format {data['pack_format']!r}")
    entries: Dict[str, str] = {}
    _walk(data["tree"], "", entries, where)
    if data["entries"] != len(entries):
        raise ValueError(f"{where}: the header announces {data['entries']} entries, found {len(entries)}")
    return MappingProxyType(entries)


# ============================================================================ the verbose pack

_COUNT_LINE = re.compile(r"^Number of files merged: (\d+)$")
_BEGIN = re.compile(r"^----- BEGIN FILE (\d+)/(\d+): (.*) -----$")
_END = re.compile(r"^----- END FILE (\d+)/(\d+): (.*) -----$")
_RULE = "=" * 80


def write_verbose_pack(
    pack_path: Path,
    entries: Mapping[str, str] | Iterable[Tuple[str, str]],
    *,
    source: Optional[Path] = None,
    stamp: bool = False,
) -> int:
    """Write ``entries`` (``relative path -> content``, in the order given) as one verbose pack::

        Number of files merged: 2
        ================================================================================

        ----- BEGIN FILE 1/2: kind=sgd/rows=100/result_repeat=0.json -----
        {"accepted": 12}
        ----- END FILE 1/2: kind=sgd/rows=100/result_repeat=0.json -----

        ----- BEGIN FILE 2/2: ...

    The writer *always* appends a newline after an entry's content and the reader strips exactly
    one, so a file that ended in a newline round-trips with it. ``stamp`` adds a generation
    timestamp and ``source``'s absolute path to the header; leave it off for anything under version
    control. Returns the number of entries written.
    """
    items = list(entries.items() if isinstance(entries, Mapping) else entries)
    total = len(items)
    seen = set()
    for rel_path, _ in items:
        if "\n" in rel_path or "\r" in rel_path:
            raise ValueError(f"a pack entry's path cannot hold a line break: {rel_path!r}")
        if rel_path in seen:
            raise ValueError(f"{rel_path!r} appears twice; a pack holds one entry per path")
        seen.add(rel_path)
    with atomic_open(pack_path) as out:
        if stamp:
            out.write(f"Merged text file generated on {datetime.now(timezone.utc).isoformat()}\n")
            if source is not None:
                out.write(f"Source folder: {Path(source).resolve()}\n")
        out.write(f"Number of files merged: {total}\n")
        out.write(_RULE + "\n\n")
        for index, (rel_path, content) in enumerate(items, start=1):
            out.write(f"----- BEGIN FILE {index}/{total}: {rel_path} -----\n")
            out.write(content)
            out.write("\n")
            out.write(f"----- END FILE {index}/{total}: {rel_path} -----\n\n")
    return total


def iter_verbose_pack(pack_path: Path) -> Iterator[Tuple[str, str]]:
    """Yield ``(relative path, content)`` for every entry of a verbose pack, in file order, one entry
    in memory at a time.

    Raises ``ValueError`` on anything that is not a well-formed pack -- an END outside any entry, an
    entry never closed, or fewer/more entries than the header announces. Inside an entry, only the
    END marker naming that entry's own index and path closes it; any other marker-shaped line is
    content. Reading is in universal-newline mode, so a CRLF checkout reads the same.
    """
    announced: Optional[int] = None
    seen = 0
    current: Optional[Tuple[int, str]] = None
    buffer: list[str] = []

    with open(pack_path, "r", encoding="utf-8") as f:
        for line in f:
            bare = line[:-1] if line.endswith("\n") else line
            if current is None:
                begin = _BEGIN.match(bare)
                if begin:
                    current = (int(begin.group(1)), begin.group(3))
                    buffer = []
                    continue
                if _END.match(bare):
                    raise ValueError(f"{pack_path}: an END marker with no matching BEGIN")
                count = _COUNT_LINE.match(bare)
                if count and announced is None and seen == 0:
                    announced = int(count.group(1))
                continue

            end = _END.match(bare)
            if end and (int(end.group(1)), end.group(3)) == current:
                rel_path = current[1]
                content = "".join(buffer)
                if content.endswith("\n"):
                    content = content[:-1]
                seen += 1
                current = None
                yield rel_path, content
                continue
            buffer.append(line)

    if current is not None:
        raise ValueError(f"{pack_path}: {current[1]!r} was never closed with an END marker")
    if announced is not None and announced != seen:
        raise ValueError(f"{pack_path}: the header announces {announced} entries, found {seen}")


def read_verbose_pack(pack_path: Path) -> Mapping[str, str]:
    """Every entry of a verbose pack as a read-only mapping, cached like ``read_pack``."""
    stat = os.stat(pack_path)
    return _read_verbose_pack(os.path.abspath(pack_path), stat.st_size, stat.st_mtime_ns)


@functools.lru_cache(maxsize=4)
def _read_verbose_pack(absolute: str, size: int, mtime_ns: int) -> Mapping[str, str]:
    entries: Dict[str, str] = {}
    for rel_path, content in iter_verbose_pack(Path(absolute)):
        if rel_path in entries:
            raise ValueError(f"{absolute}: {rel_path!r} appears twice")
        entries[rel_path] = content
    return MappingProxyType(entries)


# ============================================================================ reading a folder

_PACK_NAMES = frozenset({RESULTS_PACK, LEGACY_RESULTS_PACK})
_legacy_readable: contextvars.ContextVar[bool] = contextvars.ContextVar("legacy_readable", default=False)


@contextlib.contextmanager
def legacy_packs_readable() -> Iterator[None]:
    """Within the block, a folder's ``LEGACY_RESULTS_PACK`` is read like a pack instead of refused.

    For the conversion only (``pack_results.pack``), which must count a folder's results as they
    stand before it rewrites them.
    """
    token = _legacy_readable.set(True)
    try:
        yield
    finally:
        _legacy_readable.reset(token)


def _refuse_legacy(folder: Path) -> None:
    raise ValueError(
        f"{folder} holds a {LEGACY_RESULTS_PACK}, the verbose pack format this code no longer reads "
        f"as results; {CONVERT_HINT}"
    )


def iter_result_paths(
    root: Path, pattern: str = "**/*"
) -> List[Tuple[str, Optional[PackEntry]]]:
    """Every result a folder holds, as ``(path relative to root, pack entry or None)``.

    The loose files matching the glob ``pattern``, then every entry of ``root/RESULTS_PACK``: an
    entry records its path relative to ``root``, so it stands for the file it replaced. A path both
    loose and packed raises ``ValueError`` rather than being counted twice, and so does a folder
    still holding a ``LEGACY_RESULTS_PACK`` (outside ``legacy_packs_readable``).
    """
    root = Path(root)
    loose = [path.relative_to(root).as_posix() for path in root.glob(pattern)
             if path.is_file() and path.relative_to(root).as_posix() not in _PACK_NAMES]
    found: List[Tuple[str, Optional[PackEntry]]] = [(rel_path, None) for rel_path in loose]
    taken = set(loose)
    packs = [root / RESULTS_PACK]
    if (root / LEGACY_RESULTS_PACK).is_file():
        if not _legacy_readable.get():
            _refuse_legacy(root)
        packs.append(root / LEGACY_RESULTS_PACK)
    for pack in packs:
        if not pack.is_file():
            continue
        for rel_path in _reader_for(pack)(pack):
            if rel_path in taken:
                raise ValueError(
                    f"{rel_path} is both a loose file and an entry of {pack}, or in two packs; "
                    f"delete one (or re-pack the folder) before reading it"
                )
            taken.add(rel_path)
            found.append((rel_path, PackEntry(pack, rel_path)))
    return found


def read_result_text(path: Path, pack: Optional[Path] = None) -> str:
    """The content of a result file, whether it sits on disk or inside a pack.

    A loose file wins. Otherwise ``pack`` if given -- what discovery records for a packed result --
    else the nearest folder among ``path``'s ancestors holding a ``RESULTS_PACK``, looked up under
    ``path``'s position relative to that folder. Only the nearest: a pack further up belongs to
    another folder. A nearest folder holding only a ``LEGACY_RESULTS_PACK`` is refused, with the
    command that converts it. Raises ``FileNotFoundError`` if nothing holds it.
    """
    path = Path(path)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    if pack is None:
        for ancestor in path.parents:
            if (ancestor / RESULTS_PACK).is_file():
                pack = ancestor / RESULTS_PACK
                break
            if (ancestor / LEGACY_RESULTS_PACK).is_file():
                if not _legacy_readable.get():
                    _refuse_legacy(ancestor)
                pack = ancestor / LEGACY_RESULTS_PACK
                break
    if pack is not None and Path(pack).is_file():
        entries = _reader_for(pack)(pack)
        rel_path = path.relative_to(Path(pack).parent).as_posix()
        if rel_path in entries:
            return entries[rel_path]
    raise FileNotFoundError(f"{path} is neither on disk nor in a {RESULTS_PACK} above it")
