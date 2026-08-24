from systematic_trader.tiingo_delisted import candidate_cache_key, issuer_name_match, issuer_name_score, name_tokens


def test_name_tokens_remove_legal_noise():
    assert name_tokens("Twitter, Inc. /DE/") == ["twitter"]


def test_issuer_name_match_accepts_legal_suffix_changes():
    assert issuer_name_match("TABLEAU SOFTWARE INC", "Tableau Software, LLC")
    assert issuer_name_score("MCAFEE CORP.", "McAfee Corporation") == 1.0


def test_issuer_name_match_rejects_recycled_ticker_company():
    assert not issuer_name_match("OLD DATA SYSTEMS INC", "New Mining Holdings Corporation")
    assert not issuer_name_match("GAN LTD", "GARAN INC")


def test_issuer_name_match_accepts_joined_tokens_and_punctuation_normalization():
    assert issuer_name_match("PC TEL INC", "PCTEL Inc")
    assert issuer_name_match("AARON'S COMPANY, INC.", "Aarons Company Inc (The)")


def test_issuer_name_match_still_rejects_highish_but_ambiguous_fuzzy_names():
    assert not issuer_name_match("PC TAL INC", "PCTEL Inc")


def test_candidate_cache_key_separates_shared_ticker_ciks():
    assert candidate_cache_key("AZPN", "0001897982") == "AZPN"
    assert candidate_cache_key("AZPN", "0000929940", "0001897982") == "AZPN__0000929940"
    assert candidate_cache_key("BRK/B", "0001067983") == "BRK_B"
