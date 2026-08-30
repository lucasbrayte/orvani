from automation.categorizer import CategoryDecision, categorize


def test_known_source_category_wins():
    # Dropping exact source mappings would incorrectly let the clothing keyword win.
    value = categorize("Eletrônicos > Áudio", "Camisa com fone", "Moda")

    assert value == CategoryDecision("Eletrônicos", "Áudio", True)


def test_known_first_source_segment_is_confident_when_full_mapping_is_unknown():
    # Checking only full paths would turn a valid official category into Outros.
    assert categorize("Casa > Organização incomum", "Produto", None) == CategoryDecision(
        "Casa", None, True
    )


def test_keyword_is_used_after_source_category_rules():
    # Removing keyword rules would leave recognizable products queued for manual review.
    assert categorize(None, "Fone bluetooth compacto", "Som para viagem") == CategoryDecision(
        "Eletrônicos", "Áudio", True
    )


def test_keyword_matches_complete_unicode_tokens_and_explicit_plural_forms():
    # Substring matching would classify "fonemas", while the configured plural must still match.
    assert categorize(None, "FONES bluetooth", None) == CategoryDecision(
        "Eletrônicos", "Áudio", True
    )
    assert categorize(None, "fonemas para estudar", None) == CategoryDecision(
        "Outros", None, False
    )
    assert categorize(None, "LUMINA\u0301RIA portátil", None) == CategoryDecision(
        "Casa", "Iluminação", True
    )


def test_unknown_category_requires_review():
    # Treating arbitrary text as a known category would silently misclassify a product.
    assert categorize(None, "Objeto singular", "Sem classificação") == CategoryDecision(
        "Outros", None, False
    )


def test_category_matching_uses_deterministic_unicode_normalization():
    # Without Unicode normalization, equivalent decomposed accents lose a source mapping.
    assert categorize("  Eletr\u00f4nicos\u00a0>\u00a0A\u0301udio ", "Produto", None) == CategoryDecision(
        "Eletrônicos", "Áudio", True
    )
