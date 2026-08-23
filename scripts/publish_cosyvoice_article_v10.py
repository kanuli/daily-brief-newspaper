#!/usr/bin/env python3
"""Run the current F01 publisher with cache-isolated policy identity."""
import cosyvoice_cache_identity as cache_identity
import publish_cosyvoice_article_anchor as anchor

cache_identity.install(anchor.legacy.gen)

if __name__ == "__main__":
    code = anchor.legacy.main()
    anchor._stamp_manifest()
    raise SystemExit(code)
