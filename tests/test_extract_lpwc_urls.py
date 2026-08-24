"""
Tests for src/semrepo/extraction/extract_lpwc_urls.py.

Uses a small synthetic N-Triples fixture rather than a real LPWC dump, same
independent-verification approach used for the WP3 SHACL shapes (synthetic
valid + intentionally-broken records, then check the output is exactly
right) -- see docs/wp3-* notes for that precedent.
"""

import json
from pathlib import Path

from semrepo.extraction.extract_lpwc_urls import extract_lpwc_repository_links, run

SAMPLE_NTRIPLES = """\
<http://example.org/paper/1> <https://linkedpaperswithcode.com/property/hasOfficialRepository> <http://example.org/repo/1> .
<http://example.org/repo/1> <http://purl.org/spar/fabio/hasURL> <https://github.com/foo/bar> .
<http://example.org/paper/2> <https://linkedpaperswithcode.com/property/hasOfficialRepository> <http://example.org/repo/2> .
<http://example.org/repo/2> <http://purl.org/spar/fabio/hasURL> <https://github.com/baz/qux> .
<http://example.org/paper/3> <https://linkedpaperswithcode.com/property/hasOfficialRepository> <http://example.org/repo/3> .
<http://example.org/paper/1> <http://purl.org/dc/terms/creator> <http://example.org/author/1> .
<http://example.org/author/1> <http://xmlns.com/foaf/0.1/name> "Jane Doe" .
"""
# Note: repo/3 is intentionally left WITHOUT a fabio:hasURL triple -- this
# is the "unresolved" case that must be skipped, not silently included with
# a missing URL.


def _write_fixture(tmp_path: Path) -> Path:
    fixture_path = tmp_path / "lpwc_sample.nt"
    fixture_path.write_text(SAMPLE_NTRIPLES, encoding="utf-8")
    return fixture_path


def test_extract_yields_only_resolvable_links(tmp_path):
    fixture_path = _write_fixture(tmp_path)

    links = list(extract_lpwc_repository_links(fixture_path, source_release="test-release-2026"))

    assert len(links) == 2, "repo/3 has no fabio:hasURL and must be excluded, not the other two"

    urls = {link.original_repository_url for link in links}
    assert urls == {"https://github.com/foo/bar", "https://github.com/baz/qux"}


def test_extract_preserves_paper_provenance(tmp_path):
    fixture_path = _write_fixture(tmp_path)

    links = {link.original_repository_url: link for link in extract_lpwc_repository_links(fixture_path, "test-release-2026")}

    bar_link = links["https://github.com/foo/bar"]
    assert bar_link.paper_entity == "http://example.org/paper/1"
    assert bar_link.lpwc_entity == "http://example.org/repo/1"
    assert bar_link.source_release == "test-release-2026"
    assert bar_link.extraction_timestamp  # non-empty ISO timestamp


def test_run_writes_valid_jsonl(tmp_path):
    fixture_path = _write_fixture(tmp_path)
    output_path = tmp_path / "out" / "lpwc_repository_links.jsonl"

    count = run(fixture_path, source_release="test-release-2026", output_path=output_path)

    assert count == 2
    assert output_path.exists()

    lines = output_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    for line in lines:
        record = json.loads(line)
        assert set(record.keys()) == {
            "lpwc_entity", "paper_entity", "original_repository_url",
            "source_release", "extraction_timestamp",
        }