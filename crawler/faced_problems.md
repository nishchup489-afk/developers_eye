.order_by(
    CrawlTarget.priority.desc(),
    CrawlTarget.next_fetch_at.asc(),
    CrawlTarget.id.asc(),
)
.limit(limit)
.with_for_update(skip_locked=True)