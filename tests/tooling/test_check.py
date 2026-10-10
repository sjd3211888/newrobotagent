"""Behavioral regression checks for repository tooling, using isolated fixtures."""

import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check.py"
SPEC = importlib.util.spec_from_file_location("repo_check", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


class RepositoryFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def write(self, name, source=""):
        file = self.root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(source, encoding="utf-8")
        return file


class MarkdownChecks(RepositoryFixture):
    def test_reports_missing_local_file_with_line_number(self):
        file = self.write("docs/README.md", "# Intro\n\n[broken](missing.md)\n")
        errors = checker.link_issues(self.root, file)
        self.assertEqual(len(errors), 1)
        self.assertIn("docs/README.md:3", errors[0])

    def test_ignores_fences_inline_code_external_urls_and_anchors(self):
        file = self.write("README.md", """```md
[example](missing.md)
```
~~~
[example](also-missing.md)
~~~
`[inline](missing.md)`
[website](https://example.com/doc)
[mail](mailto:help@example.com)
[heading](#intro)
""")
        self.assertEqual(checker.link_issues(self.root, file), [])

    def test_handles_long_fence_and_double_backtick_inline_code(self):
        file = self.write("README.md", "````md\n```\n[x](bad.md)\n````\n"
                          "``example ` [x](missing.md)``\n")
        self.assertEqual(checker.link_issues(self.root, file), [])

    def test_reference_image_collapsed_shortcut_and_space_destinations(self):
        self.write("docs/a (copy).md")
        self.write("docs/picture.png")
        file = self.write("docs/README.md", "[Full][ref]\n[ref][]\n[ref]\n"
                          "![picture](picture.png)\n[space](<a (copy).md> \"title\")\n"
                          "[ref]: <a (copy).md>\n")
        self.assertEqual(len(checker.markdown_links(file.read_text())), 5)
        self.assertEqual(checker.link_issues(self.root, file), [])

    def test_missing_explicit_reference_is_failure(self):
        file = self.write("README.md", "[Title][missing]\n")
        self.assertIn("undefined link reference", checker.link_issues(self.root, file)[0])

    def test_relative_utf8_encoded_and_nested_parentheses_targets(self):
        self.write("docs/说明.md")
        self.write("docs/a(b(c)).md")
        file = self.write("README.md", "[utf8](docs/%E8%AF%B4%E6%98%8E.md)\n"
                          "[nested](docs/a(b(c)).md#heading)\n")
        self.assertEqual(checker.link_issues(self.root, file), [])

    def test_rejects_repository_escape_and_absolute_paths(self):
        file = self.write("README.md", "[escape](../outside.md)\n"
                          "[windows](D:/voiceagent/README.md)\n[unix](/tmp/file.md)\n")
        errors = checker.link_issues(self.root, file)
        self.assertEqual(len(errors), 3)
        self.assertTrue(any("escapes repository" in error for error in errors))

    def test_rejects_non_utf8_markdown(self):
        file = self.write("README.md")
        file.write_bytes(b"\xff\xfe")
        self.assertIn("cannot read UTF-8", checker.link_issues(self.root, file)[0])

    def test_existing_local_state_and_file_uris_are_not_portable_links(self):
        self.write(".local/evidence.md")
        file = self.write("README.md", "[state](.local/evidence.md)\n"
                          "[absolute](file:///D:/voiceagent/README.md)\n")
        errors = checker.link_issues(self.root, file)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("local-only/generated" in error for error in errors))
        self.assertTrue(any("file URI" in error for error in errors))

    def test_escaped_brackets_are_examples_not_links(self):
        file = self.write("README.md", r"\[not a link](missing.md)" + "\n")
        self.assertEqual(checker.link_issues(self.root, file), [])


class LayoutChecks(RepositoryFixture):
    def test_rejects_unknown_roots_local_state_and_artifacts(self):
        files = [self.write(name) for name in (
            "scratch/script.py", "notes.md", ".local/session.json", "dist/package.zip")]
        errors = checker.layout_issues(self.root, files)
        self.assertTrue(any("unexpected root file" in error for error in errors))
        self.assertTrue(any("unexpected root directory" in error for error in errors))
        self.assertTrue(any("local-only" in error for error in errors))
        self.assertTrue(any("artifact" in error for error in errors))

    def test_config_examples_allowed_runtime_env_rejected(self):
        allowed = [self.write("configs/app.example.yaml"), self.write("configs/prompts/system.md")]
        self.assertEqual(checker.layout_issues(self.root, allowed), [])
        files = [self.write("configs/robot.json"), self.write("configs/.env")]
        self.assertEqual(len(checker.layout_issues(self.root, files)), 3)

    def test_required_documents_are_enforced(self):
        file = self.write("README.md")
        with contextlib.redirect_stdout(io.StringIO()):
            errors = checker.check_docs(self.root, [file])
        self.assertTrue(any("AGENTS.md: required file" in error for error in errors))

    def test_git_inventory_includes_tracked_ignored_but_excludes_local_experiments(self):
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self.write(".gitignore", ".local/\n")
        self.write(".local/tracked.json")
        subprocess.run(["git", "add", "-f", "--", ".local/tracked.json"],
                       cwd=self.root, check=True)
        self.write(".local/untracked.json")
        self.write("docs/新文档.md")
        self.write("docs/deleted.md")
        subprocess.run(["git", "add", "--", "docs/deleted.md"], cwd=self.root, check=True)
        (self.root / "docs/deleted.md").unlink()
        files = checker.discover_files(self.root)
        names = {file.relative_to(self.root).as_posix() for file in files}
        self.assertIn(".local/tracked.json", names)
        self.assertIn("docs/新文档.md", names)
        self.assertNotIn(".local/untracked.json", names)
        self.assertNotIn("docs/deleted.md", names)
        self.assertTrue(any("local-only" in issue for issue in checker.layout_issues(self.root, files)))


class CodeChecks(RepositoryFixture):
    def setUp(self):
        super().setUp()
        self.write("tests/tooling/test_fixture.py", "# isolated fixture\n")
        self.commands = []

    def run_fake(self, root, command, capture=False):
        self.commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def check(self, files, runner=None):
        with patch.object(checker, "run_command", runner or self.run_fake), \
                patch.object(checker.shutil, "which", return_value="available"), \
                contextlib.redirect_stdout(io.StringIO()):
            return checker.check_code(self.root, files)

    def test_absent_go_is_explicitly_not_applicable(self):
        self.assertEqual(self.check([]), [])
        self.assertFalse(any(command[0] in {"go", "gofmt"} for command in self.commands))

    def test_go_source_without_module_fails(self):
        errors = self.check([self.write("internal/app/app.go", "package app\n")])
        self.assertIn("Go source exists but root go.mod is missing", errors)

    def test_nested_module_and_new_language_cannot_be_silently_skipped(self):
        errors = self.check([self.write("sdk/go/go.mod"), self.write("web/src/app.ts")])
        self.assertTrue(any("Nested Go modules" in error for error in errors))
        self.assertTrue(any("web/src/app.ts" in error for error in errors))

    def test_python_syntax_errors_are_reported(self):
        errors = self.check([self.write("scripts/bad.py", "def invalid(:\n")])
        self.assertTrue(any("Python syntax/encoding" in error for error in errors))

    def test_go_tests_and_format_failures_propagate_without_rewriting(self):
        self.write("go.mod", "module example.test/robot\n")
        file = self.write("internal/app/app.go", "package app\n")
        original = file.read_bytes()

        def failed(root, command, capture=False):
            self.commands.append(command)
            result = 1 if command[:2] == ["go", "test"] else 0
            output = "internal/app/app.go\n" if command[0] == "gofmt" else ""
            return subprocess.CompletedProcess(command, result, stdout=output, stderr="")

        errors = self.check([file], failed)
        self.assertTrue(any("format check failed" in error for error in errors))
        self.assertIn("Command failed: go test -count=1 ./...", errors)
        self.assertEqual(file.read_bytes(), original)
        self.assertIn(["go", "vet", "./..."], self.commands)
        self.assertFalse(any("-w" in command for command in self.commands))

    def test_tooling_failure_propagates(self):
        def failed(root, command, capture=False):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

        self.assertIn("Python tooling tests failed", self.check([], failed))

    def test_missing_go_toolchain_is_a_failure_for_an_existing_module(self):
        self.write("go.mod", "module example.test/robot\n")
        with patch.object(checker, "run_command", self.run_fake), \
                patch.object(checker.shutil, "which", return_value=None), \
                contextlib.redirect_stdout(io.StringIO()):
            errors = checker.check_code(self.root, [])
        self.assertIn("Go module exists but go/gofmt is unavailable", errors)

    def test_generated_go_formatting_is_skipped_but_module_checks_run(self):
        self.write("go.mod", "module example.test/robot\n")
        file = self.write("internal/proto/generated.go",
                          "// Code generated by protoc. DO NOT EDIT.\npackage proto\n")
        self.assertEqual(self.check([file]), [])
        self.assertFalse(any(command[0] == "gofmt" for command in self.commands))
        self.assertIn(["go", "vet", "./..."], self.commands)
        self.assertIn(["go", "test", "-count=1", "./..."], self.commands)


class CommandLineChecks(unittest.TestCase):
    def test_failures_return_nonzero(self):
        with patch.object(checker, "discover_files", return_value=[]), \
                patch.object(checker, "check_docs", return_value=["broken link"]), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(checker.main(["--scope", "docs"]), 1)

    def test_docs_scope_does_not_run_code(self):
        with patch.object(checker, "discover_files", return_value=[]), \
                patch.object(checker, "check_docs", return_value=[]), \
                patch.object(checker, "check_code") as code, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main(["--scope", "docs"]), 0)
            code.assert_not_called()

    def test_all_is_the_default(self):
        with patch.object(checker, "discover_files", return_value=[]), \
                patch.object(checker, "check_docs", return_value=[]) as docs, \
                patch.object(checker, "check_code", return_value=[]) as code, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main([]), 0)
            docs.assert_called_once()
            code.assert_called_once()

    def test_code_scope_does_not_run_document_checks(self):
        with patch.object(checker, "discover_files", return_value=[]), \
                patch.object(checker, "check_docs") as docs, \
                patch.object(checker, "check_code", return_value=[]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(checker.main(["--scope", "code"]), 0)
            docs.assert_not_called()

    def test_inventory_failure_returns_controlled_error(self):
        with patch.object(checker, "discover_files", side_effect=RuntimeError("inventory failed")), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(checker.main(["--scope", "docs"]), 1)
            self.assertIn("inventory failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
