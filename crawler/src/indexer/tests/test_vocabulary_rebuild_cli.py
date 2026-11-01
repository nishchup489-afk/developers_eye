"""CLI contract tests for the one-shot vocabulary rebuild (no database)."""

from __future__ import annotations

import argparse

import pytest

from indexer import vocabulary_rebuild


def test_default_options_are_one_shot() -> None:
    args = vocabulary_rebuild.parse_args([])
    assert args.once is False
    assert args.progress_every == 1000
    assert args.write_batch_size == 500
    assert args.log_level == "INFO"


def test_explicit_options() -> None:
    args = vocabulary_rebuild.parse_args([
        "--once", "--progress-every", "250",
        "--write-batch-size", "100", "--log-level", "DEBUG",
    ])
    assert args.once is True
    assert args.progress_every == 250
    assert args.write_batch_size == 100
    assert args.log_level == "DEBUG"


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--progress-every", "0"),
        ("--progress-every", "-1"),
        ("--progress-every", "abc"),
        ("--write-batch-size", "0"),
        ("--write-batch-size", "nan"),
    ],
)
def test_reject_invalid_positive_options(option: str, value: str) -> None:
    with pytest.raises(SystemExit) as exc:
        vocabulary_rebuild.parse_args([option, value])
    assert exc.value.code == 2


def test_cli_runs_and_logs_success(monkeypatch, caplog) -> None:
    opts = argparse.Namespace(
        once=True, progress_every=250, write_batch_size=100, log_level="INFO"
    )
    monkeypatch.setattr(vocabulary_rebuild, "parse_args", lambda: opts)
    monkeypatch.setattr(vocabulary_rebuild, "setup_logging", lambda _: None)
    seen = {}

    async def fake_run(*, progress_every: int, write_batch_size: int):
        seen.update(
            progress_every=progress_every, write_batch_size=write_batch_size
        )
        return 12, 34

    monkeypatch.setattr(vocabulary_rebuild, "_run", fake_run)

    with caplog.at_level("INFO", logger="indexer.vocabulary_rebuild"):
        vocabulary_rebuild.main()

    assert seen == {"progress_every": 250, "write_batch_size": 100}
    assert "VOCABULARY REBUILD START" in caplog.text
    assert "VOCABULARY REBUILD COMPLETE" in caplog.text
    assert "documents=12 unique_terms=34" in caplog.text


def test_cli_returns_nonzero_when_rebuild_fails(monkeypatch, caplog) -> None:
    opts = vocabulary_rebuild.parse_args([])
    monkeypatch.setattr(vocabulary_rebuild, "parse_args", lambda: opts)
    monkeypatch.setattr(vocabulary_rebuild, "setup_logging", lambda _: None)

    async def fake_run(*, progress_every: int, write_batch_size: int):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(vocabulary_rebuild, "_run", fake_run)

    with caplog.at_level("ERROR", logger="indexer.vocabulary_rebuild"):
        with pytest.raises(SystemExit) as exc:
            vocabulary_rebuild.main()

    assert exc.value.code == 1
    assert "VOCABULARY REBUILD FAILED" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("progress_every", "write_batch_size"),
    [(0, 100), (1, 0), (-1, 10), (True, 10)],
)
async def test_rebuild_validates_limits_before_connecting(
    progress_every: int, write_batch_size: int
) -> None:
    with pytest.raises(ValueError):
        await vocabulary_rebuild.rebuild_vocabulary(
            None, progress_every=progress_every, write_batch_size=write_batch_size
        )
