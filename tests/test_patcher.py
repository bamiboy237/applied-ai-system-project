"""tests for patcher - inject, clean, parse_reviews, unified_diff."""

from codereview.patcher import clean, inject, parse_reviews, unified_diff

SAMPLE = """\
def process(items=[]):
    for item in items:
        try:
            print(item)
        except:
            pass


def greet(name):
    return "Hello, " + name
"""


class TestParseReviews:
    def test_parses_single_review(self):
        assert parse_reviews("REVIEW:1: avoid mutable default") == {
            1: ["avoid mutable default"]
        }

    def test_parses_multiple_reviews(self):
        text = "REVIEW:1: bad\nREVIEW:5: also bad"
        assert parse_reviews(text) == {1: ["bad"], 5: ["also bad"]}

    def test_ignores_prose_lines(self):
        text = "Here are some issues:\nREVIEW:3: fix this\nThanks."
        assert parse_reviews(text) == {3: ["fix this"]}

    def test_empty_input(self):
        assert parse_reviews("") == {}

    def test_strips_leading_whitespace_on_review_lines(self):
        assert parse_reviews("  REVIEW:2: indented") == {2: ["indented"]}


class TestInject:
    def test_injects_comment_above_correct_line(self):
        result = inject(SAMPLE, {1: "avoid mutable default"})
        lines = result.splitlines()
        assert lines[0] == "# REVIEW: avoid mutable default"
        assert lines[1] == "def process(items=[]):"

    def test_preserves_indentation(self):
        result = inject(SAMPLE, {5: "bare except swallows everything"})
        lines = result.splitlines()
        comment = next(line for line in lines if "# REVIEW:" in line)
        assert comment.startswith("        ")  # 8 spaces — matches the except line

    def test_multiple_reviews_land_in_right_order(self):
        result = inject(SAMPLE, {1: "bad default", 9: "use f-string"})
        lines = result.splitlines()
        assert "# REVIEW: bad default" in lines[0]
        assert any("# REVIEW: use f-string" in line for line in lines)

    def test_out_of_range_line_is_skipped(self):
        result = inject(SAMPLE, {999: "does not exist"})
        assert "# REVIEW:" not in result

    def test_inject_is_reversible_by_clean(self):
        cleaned, count = clean(inject(SAMPLE, {1: "test"}))
        assert cleaned == SAMPLE
        assert count == 1


class TestClean:
    def test_removes_review_comments(self):
        source = inject(SAMPLE, {1: "avoid mutable default"})
        cleaned, count = clean(source)
        assert "# REVIEW:" not in cleaned
        assert count == 1

    def test_removes_indented_review_comments(self):
        source = inject(SAMPLE, {5: "bare except"})
        cleaned, count = clean(source)
        assert "# REVIEW:" not in cleaned
        assert count == 1

    def test_clean_on_clean_file_removes_nothing(self):
        cleaned, count = clean(SAMPLE)
        assert cleaned == SAMPLE
        assert count == 0

    def test_clean_is_idempotent(self):
        source = inject(SAMPLE, {1: "test"})
        once, _ = clean(source)
        twice, count = clean(once)
        assert once == twice
        assert count == 0


class TestUnifiedDiff:
    def test_diff_is_non_empty_when_reviews_added(self):
        after = inject(SAMPLE, {1: "avoid mutable default"})
        diff = unified_diff("sample.py", SAMPLE, after)
        assert diff != ""

    def test_diff_contains_added_comment(self):
        after = inject(SAMPLE, {1: "avoid mutable default"})
        diff = unified_diff("sample.py", SAMPLE, after)
        assert "+# REVIEW: avoid mutable default" in diff

    def test_diff_is_empty_when_source_unchanged(self):
        diff = unified_diff("sample.py", SAMPLE, SAMPLE)
        assert diff == ""
