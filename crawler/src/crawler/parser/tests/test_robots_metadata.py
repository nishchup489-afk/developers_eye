import pytest

from crawler.parser.parser import parse
from crawler.processing.processing import process


@pytest.mark.parametrize('tags,noindex,nofollow', [
    ('<meta name="robots" content="index"><meta name="robots" content="noindex">', True, False),
    ('<meta name="robots" content="noindex"><meta name="robots" content="index">', True, False),
    ('<meta name="DevelopersEyeBot" content="noindex, nofollow">', True, True),
    ('<meta name="OtherBot" content="noindex, nofollow">', False, False),
    ('<meta name="robots" content="index"><meta name="DEVELOPERSEYEBOT" content="nofollow">', False, True),
    ('<meta name="robots" content="' + 'index, ' * 400 + 'noindex">', True, False),
])
def test_all_applicable_meta_tags_are_respected(tags, noindex, nofollow):
    html = f'<html><head><title>Python</title>{tags}</head><body><main>A useful Python documentation page with sample code.</main></body></html>'
    parsed = parse(url='https://example.com/docs', content=html.encode(), content_type='text/html')
    directives = parsed.documents[0].metadata.get('robots_directives', ())
    assert ('noindex' in directives) is noindex
    assert ('nofollow' in directives) is nofollow
    result = process(parsed)
    assert bool(result.skipped) is noindex
