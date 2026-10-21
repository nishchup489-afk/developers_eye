# Adding RSS and Atom ingestion

**Files involved:** feed parser/package, structured record helpers, source discovery, worker dispatch, parser/worker documentation and feed/ingestion tests.

## The problem

RSS sources were skipped at seed discovery and non-page/non-sitemap worker targets were disabled. Feed entries could not become stored documents.

## What changed

Parse RSS 2.0 and Atom 1.0 with bounded, DTD-free XML; resolve entry identities, content, authors, UTC dates and pagination. Seed rss targets, filter imported documents by source host/path scope, process entries through the shared pipeline and preserve HTTP robots directives. Article HTML fetches are optional through follow_entry_links. Add a full explanatory document outside the update log.

## Verification

All 60 targeted parser, discovery, ingestion, scope and worker-monitoring tests pass without live HTTP or PostgreSQL. New cases cover RSS extensions, Atom XML bases and XHTML/text content, pagination, invalid identities/dates, XML limits and scoped worker output.
