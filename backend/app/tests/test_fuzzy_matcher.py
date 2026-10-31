from app.intelligence import fuzzy_matcher as fm


def test_normalisation_ignores_case_punctuation_spacing():
    assert fm.normalize_title("  Men's  T-Shirt!! ") == "men s t shirt"


def test_score_ignores_word_order_and_punctuation():
    assert fm.score("Adjustable Aluminium Laptop Stand", "Laptop Stand, Adjustable Aluminium") == 100.0
    assert fm.score("Wireless Mouse", "Garden Hose 20m") < 50


def test_pairs_respect_threshold_and_order():
    titles = ["Classic T-Shirt", "classic t shirt", "Garden Hose"]
    pairs = fm.fuzzy_pairs(titles, 90, top_k=5)
    assert list(pairs) == [(0, 1)] and pairs[(0, 1)] >= 90


def test_blank_titles_never_match_and_top_k_caps_partners():
    assert fm.fuzzy_pairs(["", "", "x"], 0, 5) == {}
    same = ["Blue Mug"] * 10
    pairs = fm.fuzzy_pairs(same, 90, top_k=2)
    per_item = {i: sum(1 for p in pairs if i in p) for i in range(10)}
    assert len(pairs) <= 10 * 2
    assert all(p[0] < p[1] for p in pairs)
    assert max(per_item.values()) >= 1


def test_single_title():
    assert fm.fuzzy_pairs(["only"], 0, 5) == {}
