# Processing test cases

Offline tests for content processing: `ParsedDocument -> normalize -> classify -> fingerprint -> ProcessingResult`. No HTTP, DNS, PostgreSQL, or worker is needed.

## test_processing.py

A unittest suite with a Colorama runner when run directly (`python crawler/src/crawler/processing/tests/test_processing.py`). Fixtures `parsed_doc()`, `normalized_doc()`, and `parse_result()` build documents with only the fields under test overridden.

### Test01Normalization (`normalize_document`)

| Test | What it checks |
| --- | --- |
| `test_cleans_short_fields` | Extra spaces and tabs are collapsed in title, description, and author. |
| `test_cleans_body_and_blank_lines` | Body whitespace is collapsed, `\r\n` becomes `\n`, and runs of blank lines shrink to one. |
| `test_preserves_code_indentation` | Code blocks keep their indentation in both the body and `code_blocks`. |
| `test_cleans_headings_and_code_blocks` | Headings are whitespace-collapsed, empty headings and empty code blocks are dropped, and code is trimmed of surrounding blank lines but keeps leading indentation. |
| `test_normalizes_unicode_nfc` | Decomposed Unicode (`e` + combining accent) is normalized to NFC (`é`). |
| `test_removes_fragment_from_url` | The `#fragment` is removed from the document URL. |
| `test_accepts_same_host_canonical_hint` | A relative same-host canonical hint is resolved and used (fragment removed). |
| `test_rejects_external_canonical_hint` | A canonical hint on another host is ignored; the page URL is kept. |
| `test_rejects_https_downgrade_hint` | An `http://` canonical hint for an `https://` page is ignored. |
| `test_rejects_bad_canonical_hint_without_failing` | A `javascript:` canonical hint is ignored without raising. |
| `test_does_not_mutate_source_metadata` | Changing the normalized metadata (including nested dicts) does not affect the source document. |
| `test_rejects_invalid_source_urls` | `ftp:`, credentialed, space-containing, and relative URLs raise `ValueError`. |
| `test_rejects_wrong_input_type` | A non-`ParsedDocument` input raises `TypeError`. |
| `test_rejects_bad_code_block_types` | A non-string code block raises `TypeError`. |

### Test02Classification (`classify_document`)

Each URL check also asserts the method starts with `rules:` and confidence is between 0 and 1.

| Test | What it checks |
| --- | --- |
| `test_github_issue` | GitHub `/issues/N` is `ISSUE` with method `rules:github_issue`. |
| `test_github_repository` | A GitHub `owner/repo` URL is `REPOSITORY`. |
| `test_github_discussion` | GitHub `/discussions/N` is `DISCUSSION`. |
| `test_gitlab_issue` | GitLab `/-/issues/N` is `ISSUE`. |
| `test_stackoverflow_question_not_help_page` | Stack Overflow `/questions/...` is `QUESTION`, but `/help` is `OTHER`. |
| `test_reddit_discussion` | A Reddit `/comments/` URL is `DISCUSSION`. |
| `test_docs_host` | A `docs.` host is `DOCUMENTATION`. |
| `test_tutorial_path_overrides_documentation_host` | A `/tutorial/` path on a docs host is `TUTORIAL`. |
| `test_blog_platform` | A dev.to URL is `BLOG`. |
| `test_event_platform` | A Meetup `/events/` URL is `EVENT`. |
| `test_title_fallback` | With no URL rule, a "Getting Started with Docker" title gives `TUTORIAL` and a `docker` tag. |
| `test_article_metadata_fallback` | `og:type: article` metadata gives `BLOG`. |
| `test_unknown_page_falls_back_to_other` | An unmatched page is `OTHER` with confidence `0.0`. |
| `test_does_not_match_fake_github_domain` | `notgithub.com` is not treated as GitHub. |
| `test_tags_from_short_fields_not_body` | Tags come from title and description in order (`python`, `fastapi`, `postgresql`, `docker`), not from body text. |
| `test_rejects_bad_document_type` | A non-document input raises `TypeError`. |
| `test_rejects_non_http_canonical_url` | An `ftp:` canonical URL raises `ValueError`. |

### Test03Fingerprint (`fingerprint_document`)

| Test | What it checks |
| --- | --- |
| `test_sha256_is_lowercase_hex` | The hash is 64 lowercase hex characters. |
| `test_same_document_same_hash` | Hashing is deterministic. |
| `test_url_author_and_metadata_do_not_change_hash` | URL, canonical URL, author, metadata, and published date are not part of the hash. |
| `test_body_change_changes_hash` | Changing the body changes the hash. |
| `test_title_and_description_change_hash` | Changing title or description changes the hash. |
| `test_headings_and_code_blocks_change_hash` | Changing headings or code blocks changes the hash. |
| `test_different_field_boundaries_do_not_collide` | `title="ab", description="c"` and `title="a", description="bc"` hash differently. |
| `test_rejects_wrong_input` | A non-document input raises `TypeError`. |
| `test_rejects_invalid_code_blocks` | A non-string code block raises `TypeError`. |

### Test04Processor (`process` and `process_document`)

| Test | What it checks |
| --- | --- |
| `test_one_document_end_to_end` | One document is normalized, classified as `TUTORIAL`, tagged `python`, and given a SHA-256 content hash, with nothing skipped. |
| `test_missing_title_uses_heading` | With no title, the first heading becomes the title and `generated_title` is set. |
| `test_missing_title_uses_url` | With no title or headings, the last URL path segment (`tutorial`) becomes the title and `generated_title` is set. |
| `test_noindex_string_skips_document` | A string `"NOINDEX, FOLLOW"` directive skips the document with reason `NOINDEX`. |
| `test_none_directive_skips_document` | A `none` directive (case and whitespace insensitive) skips with `NOINDEX`. |
| `test_nofollow_alone_does_not_prevent_indexing` | `nofollow` alone still produces a processed document. |
| `test_empty_body_is_skipped` | An empty body with no code skips with `EMPTY_CONTENT`. |
| `test_whitespace_only_body_is_skipped` | A whitespace-only body skips with `EMPTY_CONTENT`. |
| `test_code_only_page_is_accepted` | An empty body with code blocks is processed. |
| `test_invalid_url_becomes_skipped_document` | A `file://` URL skips with `INVALID_URL` instead of raising. |
| `test_malformed_body_becomes_processing_error` | A non-string body skips with `PROCESSING_ERROR`. |
| `test_processes_multiple_documents_independently` | In a batch of four, a noindex and an empty document are skipped while two are processed, and the GitHub issue is classified as `ISSUE`. |
| `test_empty_parse_result_is_valid` | An empty parse result gives empty documents and skipped tuples. |
| `test_source_url_is_preserved` | The result keeps the parse result's `source_url`. |
| `test_classification_metadata_is_preserved` | Original metadata is kept, classification `method` and `confidence` are added, and the source metadata is not mutated. |
| `test_noindex_short_circuits_classification` | A noindex document is skipped before `classify_document` is called (patched to fail if called). |
| `test_different_urls_same_content_not_deduped_here` | Two URLs with identical content are both processed and share the same content hash; dedup happens later. |
| `test_wrong_processor_inputs_raise_type_error` | Wrong input types to `process_document` and `process` raise `TypeError`. |

## test_fingerprint.py

A script-style check with no `test_` functions or asserts; it prints results at import time. It builds three `NormalizedDocument`s and prints whether the hash is the same for the same content on a different URL (expected `True`), different for changed body content on the same URL (expected `False`), and 64 characters long.
