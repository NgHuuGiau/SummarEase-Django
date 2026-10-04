"""Kiểm thử: nlp."""

from unittest.mock import patch

from django.test import TestCase

from .nlp import textrank_summarize
from .nlp_utils import (
    detect_language,
    extract_keywords,
    generate_title,
    highlight_keywords,
    normalize_text,
    split_sentences,
    split_words,
    truncate_text,
)


class NlpSplitTests(TestCase):
    def test_split_sentences_basic(self):
        result = split_sentences("Hello world. This is fun!")
        self.assertEqual(len(result), 2)

    def test_split_sentences_vietnamese_diacritic_start(self):
        text = "Em là học sinh. Ở trường tôi học giỏi. Đó là điều quan trọng."
        result = split_sentences(text)
        self.assertEqual(len(result), 3)

    def test_split_sentences_abbreviations(self):
        text = "Dr. Smith went to New York. He arrived at 5 p.m."
        result = split_sentences(text)
        self.assertEqual(len(result), 2)

    def test_split_sentences_vietnamese_abbrev(self):
        text = "Tp. Hồ Chí Minh là thành phố lớn nhất. Nó nằm ở phía Nam."
        result = split_sentences(text)
        self.assertEqual(len(result), 2)

    def test_split_words_basic(self):
        result = split_words("Hello World!")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_split_words_vietnamese(self):
        result = split_words("Xin chào thế giới!")
        self.assertIn("chào", result)
        self.assertIn("thế", result)


class NlpNormalizeTests(TestCase):
    def test_normalize_removes_extra_spaces(self):
        result = normalize_text("Hello    world\n\n  test")
        self.assertEqual(result, "Hello world test")

    def test_normalize_strips_whitespace(self):
        result = normalize_text("  hello  ")
        self.assertEqual(result, "hello")


class NlpDetectLanguageTests(TestCase):
    def test_detect_english_by_diacritics(self):
        result = detect_language("The quick brown fox jumps over the lazy dog.")
        self.assertEqual(result, "english")

    def test_detect_vietnamese_by_diacritics(self):
        result = detect_language("Xin chào thế giới! Hôm nay là một ngày đẹp trời.")
        self.assertEqual(result, "vietnamese")

    def test_detect_vietnamese_no_diacritics(self):
        result = detect_language("Xin chao the gioi! Hom nay la mot ngay dep troi.")
        self.assertEqual(result, "vietnamese")

    def test_detect_empty_falls_to_english(self):
        result = detect_language("")
        self.assertEqual(result, "english")


class NlpKeywordsTests(TestCase):
    def test_extract_keywords_returns_top_words(self):
        text = "python django python django django web framework python"
        result = extract_keywords(text, limit=3)
        self.assertIn("python", result)
        self.assertIn("django", result)
        self.assertGreaterEqual(len(result), 2)

    def test_highlight_keywords_adds_mark_tags(self):
        text = "python is great. django is better."
        result = highlight_keywords(text, ["python", "django"])
        self.assertIn("<mark>python</mark>", result)
        self.assertIn("<mark>django</mark>", result)

    def test_highlight_keywords_escapes_html(self):
        text = "test <script>alert('xss')</script>"
        result = highlight_keywords(text, ["test"])
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<script>", result)


class NlpTitleTests(TestCase):
    def test_generate_title_from_summary(self):
        result = generate_title("This is the first sentence of the summary.")
        self.assertEqual(result, "This is the first sentence of the summary.")

    def test_generate_title_with_source_name(self):
        result = generate_title("summary", "my-doc.pdf")
        self.assertIn("my-doc.pdf", result)

    def test_generate_title_empty_returns_default(self):
        result = generate_title("")
        self.assertEqual(result, "Tóm tắt tài liệu")


class NlpTruncateTests(TestCase):
    def test_truncate_short_text(self):
        text = "short text"
        result = truncate_text(text, max_chars=100)
        self.assertEqual(result, text)

    def test_truncate_long_text(self):
        text = " ".join(["word"] * 100)
        result = truncate_text(text, max_chars=20)
        self.assertLessEqual(len(result), 20)

    def test_truncate_breaks_on_overflow(self):
        text = "This is one sentence. Another sentence that is really quite long."
        result = truncate_text(text, max_chars=20)
        self.assertLessEqual(len(result), 20)

    def test_load_stop_words_missing_file_returns_empty(self):
        import pathlib

        from .nlp_utils import load_stop_words

        load_stop_words.cache_clear()
        try:
            with patch(
                "summaries.nlp_utils.STOP_WORDS_PATH",
                pathlib.Path("no_such_dir/stopwords.txt"),
            ):
                self.assertEqual(load_stop_words(), frozenset())
        finally:
            load_stop_words.cache_clear()


class NlpEdgeCaseTests(TestCase):
    def test_split_sentences_single_sentence(self):
        result = split_sentences("Just one sentence here")
        self.assertEqual(len(result), 1)

    def test_split_sentences_empty(self):
        result = split_sentences("")
        self.assertEqual(result, [])

    def test_split_sentences_question_exclamation(self):
        result = split_sentences("What is this? Amazing! Yes.")
        self.assertEqual(len(result), 3)

    def test_split_words_empty(self):
        result = split_words("")
        self.assertEqual(result, [])

    def test_split_words_special_chars(self):
        result = split_words("hello... world!!! test's")
        self.assertIn("hello", result)
        self.assertIn("world", result)
        self.assertIn("test's", result)

    def test_normalize_empty(self):
        result = normalize_text("")
        self.assertEqual(result, "")

    def test_normalize_tabs(self):
        result = normalize_text("hello\t\tworld")
        self.assertEqual(result, "hello world")

    def test_detect_language_mixed(self):
        result = detect_language("Hello everyone! Hom nay troi dep qua.")
        self.assertEqual(result, "vietnamese")

    def test_detect_language_vietnamese_diacritics_only(self):
        result = detect_language("Xin chào, hôm nay là thứ năm.")
        self.assertEqual(result, "vietnamese")

    def test_detect_language_english_only(self):
        result = detect_language("Today is a great day to learn something new.")
        self.assertEqual(result, "english")

    def test_extract_keywords_empty(self):
        result = extract_keywords("")
        self.assertEqual(result, [])

    def test_extract_keywords_limit(self):
        text = "apple banana apple banana cherry apple date"
        result = extract_keywords(text, limit=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "apple")

    def test_highlight_keywords_no_match(self):
        result = highlight_keywords("hello world", ["python"])
        self.assertNotIn("<mark>", result)

    def test_highlight_keywords_mark_not_escaped(self):
        result = highlight_keywords("hello world", ["hello"])
        self.assertEqual(result, "<mark>hello</mark> world")

    def test_generate_title_adds_period(self):
        result = generate_title("Summary without period")
        self.assertTrue(result.endswith("."))

    def test_textrank_summarize_long_text(self):
        sentences = "This is the first sentence about Python. "
        sentences += "Django is a web framework written in Python. "
        sentences += "It is used by many developers worldwide. "
        sentences += "The framework follows the MVT architecture. "
        sentences += "Python is a versatile programming language. "
        result = textrank_summarize(sentences, ratio=0.5)
        self.assertIn("summary", result)
        self.assertIn("keywords", result)
        self.assertIn("title", result)

    def test_textrank_summarize_does_not_require_external_nlp_package(self):
        result = textrank_summarize("First sentence. Second sentence.", ratio=0.5)
        self.assertTrue(result["summary"])

    def test_textrank_summarize_empty_text(self):
        with self.assertRaises(ValueError) as ctx:
            textrank_summarize("   \n\t  ")
        self.assertIn("rỗng", str(ctx.exception))
