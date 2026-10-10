File	Functions	Responsibility
seed.py	load_source(), seed_sources()	Load JSON definitions, validate with Pydantic, insert into source
registry.py	get_enabled_sources(), register_source(), update_source()	Manage registered sources in PostgreSQL
discovery.py	discover_initial_targets()	Read enabled sources and determine which URLs or endpoints to queue
sitemap.py	discover_sitemaps(), parse_sitemap()	Discover and parse XML sitemaps, including sitemap indexes
feeds.py	parse_feed(), extract_feed_urls()	Extract article URLs from RSS/Atom feeds
api_discovery.py	discover_api_resources(), get_next_cursor()	Discover API resources through pagination
sources/*.json	Data, no functions	Curated source configurations