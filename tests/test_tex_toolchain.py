from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tex_toolchain  # noqa: E402


class TinyTeXPathTests(unittest.TestCase):
    def test_tinytex_bin_prepends_path_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory).resolve()
            with (
                patch("tex_toolchain.configure_pytinytex"),
                patch(
                    "tex_toolchain.pytinytex.get_tinytex_path",
                    return_value=str(bin_dir),
                ),
                patch.dict(os.environ, {"PATH": "existing"}),
            ):
                self.assertEqual(tex_toolchain.tinytex_bin(), bin_dir)
                self.assertEqual(os.environ["PATH"].split(os.pathsep)[0], str(bin_dir))
                tex_toolchain.tinytex_bin()
                self.assertEqual(
                    sum(
                        os.path.normcase(entry) == os.path.normcase(str(bin_dir))
                        for entry in os.environ["PATH"].split(os.pathsep)
                    ),
                    1,
                )


if __name__ == "__main__":
    unittest.main()
