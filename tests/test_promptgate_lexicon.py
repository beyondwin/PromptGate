import tempfile
import unittest
from pathlib import Path

from promptgate.config import load_config
from promptgate.lexicon import load_configured_lexicon, load_lexicon, match_lexicon


class PromptGateLexiconTest(unittest.TestCase):
    def test_load_lexicon_reads_entries(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "lexicon.yaml"
            path.write_text(
                """
lexicon:
  - phrase: "코드말고"
    interpretation: "Exclude code."
    exclusion: "code"
""".strip(),
                encoding="utf-8",
            )

            entries = load_lexicon(path)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].phrase, "코드말고")
        self.assertEqual(entries[0].exclusion, "code")

    def test_match_lexicon_returns_prompt_payloads(self):
        entries = load_lexicon(Path("core/lexicon/default-user-lexicon.yaml"))

        matches = match_lexicon("코드말고 방향만 잡아줘", entries)
        payloads = [match.as_prompt_payload() for match in matches]

        self.assertIn("코드말고", [payload["phrase"] for payload in payloads])
        self.assertIn("방향만", [payload["phrase"] for payload in payloads])

    def test_load_configured_lexicon_uses_existing_config(self):
        config = load_config(Path.cwd())

        entries = load_configured_lexicon(config)

        self.assertGreaterEqual(len(entries), 1)
        self.assertIn("정리좀", [entry.phrase for entry in entries])

    def test_invalid_lexicon_shape_raises_value_error(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "bad.yaml"
            path.write_text("lexicon: wrong", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_lexicon(path)


if __name__ == "__main__":
    unittest.main()
