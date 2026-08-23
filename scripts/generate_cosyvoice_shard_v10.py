#!/usr/bin/env python3
"""Run the current F01 anchor generator with cache-isolated policy identity."""
import cosyvoice_cache_identity as cache_identity
import generate_cosyvoice_shard_anchor as anchor

cache_identity.install(anchor.legacy.gen)

if __name__ == "__main__":
    raise SystemExit(anchor.legacy.main())
