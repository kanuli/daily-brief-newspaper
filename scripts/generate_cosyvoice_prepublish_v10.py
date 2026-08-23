#!/usr/bin/env python3
"""Run verified-draft F01 generation with cache-isolated policy identity."""
import cosyvoice_cache_identity as cache_identity
import generate_cosyvoice_prepublish_shard as pre

cache_identity.install(pre.gen)

if __name__ == "__main__":
    raise SystemExit(pre.main())
