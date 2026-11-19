from app.service.evaluation import evaluate, normalize, phrase_coverage, word_error_rate


def test_normalize_strips_case_and_punctuation():
    assert normalize("Hello, World!  It's--fine.") == "hello world it's fine"


def test_wer_identical_is_zero():
    assert word_error_rate("the order has shipped", "The order has shipped.") == 0.0


def test_wer_counts_substitution_deletion_insertion():
    # ref 4 words; 1 substitution + 1 deletion + 1 insertion = 3 edits
    assert word_error_rate("a b c d", "a x c e f") == 0.75
    assert word_error_rate("a b c d", "a b c") == 0.25


def test_phrase_coverage_matches_whole_words():
    found, missing = phrase_coverage("your tracking number is ready", ["tracking number", "track"])
    assert found == ["tracking number"]
    assert missing == ["track"]


def test_evaluate_pass_requires_wer_and_phrases():
    ok = evaluate("hello support line", "hello support line", ["support line"], 0.5)
    assert ok["passed"] is True
    missing = evaluate("hello support line", "hello support", ["support line"], 0.5)
    assert missing["passed"] is False
