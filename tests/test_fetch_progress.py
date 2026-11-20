import threading

from blokjutsu import fetch as F


def test_folder_bytes_counts_partial_and_nested(tmp_path):
    (tmp_path / "a").write_bytes(b"x" * 10)
    (tmp_path / "b.incomplete").write_bytes(b"x" * 5)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c").write_bytes(b"x" * 3)
    assert F.folder_bytes(tmp_path) == 18
    assert F.finished_files(tmp_path) == 2           # a and sub, not the partial file
    assert F.folder_bytes(tmp_path / "missing") == 0


def test_watch_progress_survives_errors_and_never_goes_back(tmp_path, monkeypatch, capsys):
    values = iter([5, OSError("vanished"), 3, 9])
    stop = threading.Event()

    def measure():
        try:
            v = next(values)
        except StopIteration:
            stop.set()
            return 9
        if isinstance(v, Exception):
            raise v
        return v

    F.watch_progress(measure, 10, stop, every=0.001)
    reported = [int(line.split()[1]) for line in capsys.readouterr().out.splitlines() if line.startswith("PROGRESS")]
    assert reported and reported == sorted(reported) and reported[-1] == 9
