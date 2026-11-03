import pytest

from crawler.policy_and_politeness.robots_policy import is_crawl_allowed, parse_robots


@pytest.mark.parametrize('rules,path,allowed', [
    ('Disallow: /private/*', '/private/file', False),
    ('Disallow: /*.pdf$', '/file.pdf', False),
    ('Disallow: /*.pdf$', '/file.pdf?download=1', True),
    ('Disallow: /\nAllow: /public/', '/public/page', True),
    ('Allow: /public/\nDisallow: /', '/public/page', True),
    ('Disallow: /same\nAllow: /same', '/same', True),
    ('Allow: /same\nDisallow: /same', '/same', True),
    ('Disallow:', '/anything', True),
    ('Disallow: /Case', '/case', True),
    ('Disallow: /foo%62ar', '/foobar', False),
    ('Disallow: /foobar', '/foo%62ar', False),
    ('Disallow: /caf\u00e9', '/caf%C3%A9', False),
    ('Disallow: /foo%2Fbar', '/foo/bar', True),
    ('Disallow: /foo%2fbar', '/foo%2Fbar', False),
    ('Disallow: /literal%2A', '/literal*', False),
    ('Disallow: /literal%24', '/literal$', False),
    ('Disallow: /*?secret=*', '/docs?secret=1', False),
    ('Disallow: /a*b*c$', '/a123b456c', False),
    ('Disallow: /a*b*c$', '/a123b456c/trailing', True),
    ('Disallow: /*', '/robots.txt', True),
    ('Disallow: /private/ # comment', '/private/file', False),
])
def test_path_matching(rules, path, allowed):
    assert is_crawl_allowed('User-agent: *\n' + rules, 'https://example.com' + path) is allowed


def test_merge_repeated_matching_groups():
    rules = 'User-agent: DevelopersEyeBot\nDisallow: /a\nUser-agent: DevelopersEyeBot\nDisallow: /b'
    assert not is_crawl_allowed(rules, 'https://example.com/a')
    assert not is_crawl_allowed(rules, 'https://example.com/b')


def test_specific_group_replaces_wildcard_case_insensitively():
    rules = 'User-agent: *\nDisallow: /\nUser-agent: developerseyebot\nAllow: /'
    assert is_crawl_allowed(rules, 'https://example.com/docs', 'DevelopersEyeBot/1.0')


def test_multiple_agents_and_other_records_do_not_end_group():
    rules = '\ufeffUser-agent: OtherBot\nUser-agent: DevelopersEyeBot\nSitemap: https://example.com/map.xml\nDisallow: /private'
    assert not is_crawl_allowed(rules, 'https://example.com/private')


def test_empty_specific_group_allows_without_wildcard_fallback():
    assert is_crawl_allowed('User-agent: *\nDisallow: /\nUser-agent: DevelopersEyeBot', 'https://example.com/docs')


def test_nontext_rejected():
    with pytest.raises(TypeError):
        parse_robots(None)
