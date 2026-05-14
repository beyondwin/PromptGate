import unittest


class PromptGatePackageTest(unittest.TestCase):
    def test_package_exports_version(self):
        import promptgate

        self.assertEqual(promptgate.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
