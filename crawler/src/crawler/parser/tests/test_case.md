# Parser test cases

Offline tests for the HTML parser. No network, policy coordinator, PostgreSQL, or worker is required.

## test_html_parser.py

Uses a shared `HTML_FIXTURE` page (Open Graph title, description, author, published time, robots and keywords meta, a relative canonical link, a `<nav>`, a `<main>` with headings, a code block, three links, and a `<footer>`).

### TestParserIntegration (`parse`)

| Test | What it checks |
| --- | --- |
| `test_complete_html_pipeline` | Parsing the fixture returns one `ParsedDocument` with the Open Graph title, description, author, an absolute canonical hint without the fragment, a UTC `published_at`, headings, body text, an indented code block, language, robots directives, and keywords. Nav and footer text are excluded. Links are resolved, fragments stripped, duplicates collapsed (2 links), anchor text kept, and `nofollow` detected. |
| `test_xhtml_supported` | `application/xhtml+xml` is accepted and parsed. |
| `test_header_charset_decodes_text` | A `charset=iso-8859-1` in the Content-Type header is used to decode the body (`café`). |
| `test_title_falls_back_to_h1` | With no `<title>` or `og:title`, the first `<h1>` becomes the title. |
| `test_unsupported_or_missing_content_type` | `None`, empty, JSON, RSS, and PNG content types raise `UnsupportedContentTypeError`. |
| `test_invalid_charset` | An unknown charset raises `ContentDecodeError`. |
| `test_empty_html_body` | Empty or whitespace-only bodies raise `MalformedContentError`. |
| `test_body_requires_bytes` | Passing a `str` instead of `bytes` raises `TypeError`. |
| `test_invalid_page_urls` | Relative, `ftp:`, credentialed, bad-port, zero-port, and space-containing page URLs raise `ParserError`. |
| `test_empty_document_still_has_result` | An empty `<body>` still yields one document with an empty body and no links. |

### TestMainContentExtractor (`extract_main_content`)

| Test | What it checks |
| --- | --- |
| `test_main_content_over_navigation_and_footer` | `<main>` content is used, nav and footer are excluded, and the original soup is not mutated. |
| `test_preserves_code_indentation` | Indentation inside `<pre><code>` is preserved in `code_blocks` and the body. |
| `test_falls_back_to_article` | Without `<main>`, `<article>` is used and the nav is excluded. |
| `test_falls_back_to_body` | Without `<main>` or `<article>`, `<body>` text is used. |
| `test_excludes_hidden_and_noise` | Elements with `hidden`, `aria-hidden="true"`, a `cookie-banner` class, or `display:none` are dropped. |
| `test_invalid_input` | A non-BeautifulSoup argument raises `TypeError`. |

### TestMetadataExtraction (`extract_metadata`)

| Test | What it checks |
| --- | --- |
| `test_extracts_metadata_without_mutating_soup` | Title, description, author, UTC `published_at`, and robots directives are extracted, and the soup is unchanged. |
| `test_canonical_is_only_a_hint` | A cross-host canonical URL is kept (fragment removed) as a hint rather than rejected. |
| `test_invalid_canonical_falls_back_to_og_url` | A `javascript:` canonical is ignored and the relative `og:url` is resolved and used instead. |
| `test_missing_optional_metadata` | Missing title, description, canonical, and published date come back as `None`. |
| `test_invalid_page_url` | A relative page URL raises `ValueError`. |

### TestLinkExtraction (`extract_links`)

| Test | What it checks |
| --- | --- |
| `test_relative_links_fragments_and_duplicates` | Relative links are resolved against the page URL, fragments stripped, duplicates collapsed, and fragment-only links skipped. The first anchor text wins. |
| `test_base_href` | A `<base href>` is used to resolve relative links. |
| `test_rejects_non_http_and_malformed_destinations` | `mailto:`, `javascript:`, `data:`, credentialed, and bad-port links are dropped; only the valid link remains. |
| `test_cross_host_link_is_discovered_but_not_authorized` | External-host links are returned; authorizing them is left to the frontier/coordinator. |
| `test_nofollow_and_rel` | The `rel` tokens are exposed and `nofollow` is set. |
| `test_max_links` | `max_links=1` returns only the first link. |
| `test_invalid_inputs` | A non-soup argument raises `TypeError`; `max_links=0` and a relative page URL raise `ValueError`. |

## test_robots_metadata.py

| Test | What it checks |
| --- | --- |
| `test_all_applicable_meta_tags_are_respected` (parametrized) | Every applicable robots meta tag is combined: a `noindex` wins regardless of tag order, tags for `DevelopersEyeBot` (case-insensitive) apply, tags for `OtherBot` are ignored, and a `noindex` at the end of a very long content value is still found. It also checks that `process()` marks the document as skipped exactly when `noindex` applies. |
