"""Allow exactly the reviewed parser selection; keep every source gate pinned."""
REVIEWED_SELECTION = '''parsed = urllib.parse.urlparse(final_url)
        reviewed_rthk = (
            parsed.scheme == "https" and parsed.hostname == "news.rthk.hk"
            and parsed.port in {None, 443} and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment
            and re.fullmatch(r"/rthk/ch/component/k2/[0-9]+-[0-9]{8}\\.htm", parsed.path)
        )
        parser = RthkArticleBodyParser() if reviewed_rthk else ArticleTextParser()'''


def original_extraction_except_reviewed_parser(segment):
    assert segment.count(REVIEWED_SELECTION) == 1, "unreviewed source extraction change"
    return segment.replace(REVIEWED_SELECTION, "parser = ArticleTextParser()", 1)
