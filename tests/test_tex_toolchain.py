from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, call, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tex_toolchain  # noqa: E402


class TinyTeXPathTests(unittest.TestCase):
    def test_windows_c_utf8_locale_is_normalized_for_tex_live(self) -> None:
        locale = {"LC_ALL": "C.UTF-8", "LC_CTYPE": "C.UTF-8", "LANG": "C.UTF-8"}
        with (
            patch("tex_toolchain.os.name", "nt"),
            patch.dict(os.environ, locale),
            patch("tex_toolchain.pytinytex.clear_path_cache") as clear_path_cache,
        ):
            tex_toolchain.configure_pytinytex()

            for variable in locale:
                self.assertEqual(os.environ[variable], "C")
            clear_path_cache.assert_called_once_with()

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

    def test_build_checks_line_spacing_before_latexmk(self) -> None:
        with (
            patch("tex_toolchain.verify_toolchain"),
            patch("tex_toolchain.subprocess.run") as run,
        ):
            tex_toolchain.build()

        spacing_check = call(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_line_spacing.py"),
                "--check",
            ],
            check=True,
            cwd=ROOT,
            env=ANY,
        )
        self.assertEqual(run.call_args_list[0], spacing_check)
        self.assertEqual(run.call_args_list[1].args[0][0], "latexmk")

    def test_build_stops_when_line_spacing_check_fails(self) -> None:
        failure = subprocess.CalledProcessError(1, "line-spacing-check")
        with (
            patch("tex_toolchain.verify_toolchain"),
            patch("tex_toolchain.subprocess.run", side_effect=failure) as run,
            self.assertRaises(subprocess.CalledProcessError),
        ):
            tex_toolchain.build()
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
