from backend.AI.RAG.semantic_search import _search_plans, _significant_words


def _flatten(plans: list[tuple[list[str], int]]) -> set[str]:
    return {word for words, _required in plans for word in words}


def test_location_question_expands_to_address_terms():
    words = _significant_words("Ou se trouve l'ASIN ?")

    expanded = _flatten(_search_plans("Ou se trouve l'ASIN ?", words))

    assert {"asin", "adresse", "localisation", "siege", "immeuble", "cotonou"}.issubset(expanded)


def test_acronym_question_expands_to_official_name_terms():
    words = _significant_words("Quel est le role de l'ASIN ?")

    expanded = _flatten(_search_plans("Quel est le role de l'ASIN ?", words))

    assert {"asin", "agence", "systemes", "numerique"}.issubset(expanded)


def test_role_question_expands_to_mission_terms():
    words = _significant_words("Que fait la SBIN ?")

    expanded = _flatten(_search_plans("Que fait la SBIN ?", words))

    assert {"sbin", "role", "mission", "attributions", "operateur"}.issubset(expanded)


def test_overview_question_expands_to_presentation_terms():
    words = _significant_words("Parle-moi de l'ASIN")

    expanded = _flatten(_search_plans("Parle-moi de l'ASIN", words))

    assert {"asin", "role", "mission", "attributions", "definition"}.issubset(expanded)


def test_unknown_question_keeps_original_terms_only():
    words = _significant_words("Quelle est la couleur du portail ?")

    expanded = _flatten(_search_plans("Quelle est la couleur du portail ?", words))

    assert expanded == set(words)
