"""Allow exactly the reviewed parser selection; keep every source gate pinned."""
REVIEWED_SELECTION = '''parsed = urllib.parse.urlparse(final_url)
        reviewed_rthk = (
            parsed.scheme == "https" and parsed.hostname == "news.rthk.hk"
            and parsed.port in {None, 443} and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment
            and re.fullmatch(r"/rthk/ch/component/k2/[0-9]+-[0-9]{8}\\.htm", parsed.path)
        )
        reviewed_cna = bool(re.fullmatch(r"https://www\\.cna\\.com\\.tw/news/aopl/[0-9]{12}\\.aspx", final_url))
        reviewed_jiji = bool(re.fullmatch(r"https://www\\.jiji\\.com/jc/article\\?k=[0-9]{13}&g=(?:pol|soc)(?:&m=rss)?", final_url))
        parser = RthkArticleBodyParser() if reviewed_rthk else CnaArticleBodyParser() if reviewed_cna else JijiArticleBodyParser() if reviewed_jiji else ArticleTextParser()'''


def original_extraction_except_reviewed_parser(segment):
    assert segment.count(REVIEWED_SELECTION) == 1, "unreviewed source extraction change"
    return segment.replace(REVIEWED_SELECTION, "parser = ArticleTextParser()", 1)


def original_trust_except_user_approved_cna(segment):
    reviewed = '''approved_cna = (
        source == "中央通訊社" and candidate.get("provider") in {"CNA Official RSS", "CNA Official Japan Topic"}
        and candidate.get("desk") in {"asia", "japan"}
        and (candidate.get("provider") != "CNA Official Japan Topic" or candidate.get("desk") == "japan")
        and re.fullmatch(r"https://www\\.cna\\.com\\.tw/news/aopl/[0-9]{12}\\.aspx", url)
    )
    if not producer.TRUSTED_SOURCE.search(source) and not approved_cna:'''
    assert segment.count(reviewed) == 1, "unreviewed source trust expansion"
    return segment.replace(reviewed, "if not producer.TRUSTED_SOURCE.search(source):", 1)
