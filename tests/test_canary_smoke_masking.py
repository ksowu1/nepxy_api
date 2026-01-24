from __future__ import annotations

import canary_smoke


def test_mask_secret_handles_empty():
    assert canary_smoke._mask_secret(None) == "<empty>"
    assert canary_smoke._mask_secret("") == "<empty>"


def test_mask_secret_masks_all_but_last_four():
    assert canary_smoke._mask_secret("abcd") == "****"
    assert canary_smoke._mask_secret("abcdef") == "**cdef"
