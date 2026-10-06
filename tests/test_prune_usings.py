# tests/test_prune_usings.py
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import prune_usings

BOM = b"\xef\xbb\xbf"
PROGRAM = (
    BOM + b"// Demo/Program.cs\r\n"
    b"using System;\r\n"
    b"using System.Linq;\r\n"
    b"using System.Collections.Generic;\r\n"
    b"using System.Text;\r\n"
    b"\r\n"
    b"using System.IO;\r\n"
    b"namespace Demo;\r\n"
    b"// caf\xe9 mojibake \xc3\xa8\r\n"
)


def _sarif(path, spans, suppressed=False):
    results = []
    for start, end in spans:
        result = {
            "ruleId": "IDE0005",
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": pathlib.Path(path).as_uri()},
                        "region": {"startLine": start, "startColumn": 1, "endLine": end, "endColumn": 5},
                    }
                }
            ],
        }
        if suppressed:
            result["suppressions"] = [{"kind": "inSource"}]
        results.append(result)
    return {"version": "2.1.0", "runs": [{"results": results}]}


class PruneUsingsTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prune_usings_test_")
        self.sarif_dir = os.path.join(self.root, "sarif")
        os.makedirs(self.sarif_dir)
        self.program = self._write_bytes(os.path.join("Demo", "Program.cs"), PROGRAM)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write_bytes(self, relative, data):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def _read_bytes(self, relative):
        with open(os.path.join(self.root, relative), "rb") as fh:
            return fh.read()

    def _write_sarif(self, directory, filename, payload):
        with open(os.path.join(directory, filename), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)


class TestSarifParsing(PruneUsingsTestCase):
    def test_span_expands_to_every_line(self):
        self._write_sarif(self.sarif_dir, "Demo_net10.0_111.sarif", _sarif(self.program, [(3, 3), (5, 7)]))
        found, compiled = prune_usings.parse_sarif_dir(self.sarif_dir)
        self.assertEqual(sorted(line for _, line in found), [3, 5, 6, 7])
        self.assertEqual(compiled, {"Demo_111": {"net10.0"}})

    def test_empty_sarif_still_counts_as_a_compiled_tfm(self):
        self._write_sarif(self.sarif_dir, "Demo_net9.0_111.sarif", {"version": "2.1.0", "runs": [{"results": []}]})
        _, compiled = prune_usings.parse_sarif_dir(self.sarif_dir)
        self.assertEqual(compiled, {"Demo_111": {"net9.0"}})

    def test_suppressed_and_generated_results_are_ignored(self):
        generated = self._write_bytes(os.path.join("Demo", "obj", "Debug", "GlobalUsings.g.cs"), b"global using System;\n")
        self._write_sarif(self.sarif_dir, "Demo_net10.0_111.sarif", _sarif(self.program, [(3, 3)], suppressed=True))
        self._write_sarif(self.sarif_dir, "Other_net10.0_222.sarif", _sarif(generated, [(1, 1)]))
        found, _ = prune_usings.parse_sarif_dir(self.sarif_dir)
        self.assertEqual(found, {})

    def test_underscores_in_project_name(self):
        self.assertEqual(prune_usings._sarif_context("My_Cool_Proj_net8.0_42.sarif"), ("My_Cool_Proj_42", "net8.0"))


class TestSelectRemovable(PruneUsingsTestCase):
    def test_line_flagged_in_only_one_tfm_is_kept(self):
        self._write_sarif(self.sarif_dir, "Demo_net10.0_111.sarif", _sarif(self.program, [(3, 3), (5, 5)]))
        self._write_sarif(self.sarif_dir, "Demo_net9.0_111.sarif", _sarif(self.program, [(3, 3)]))
        found, compiled = prune_usings.parse_sarif_dir(self.sarif_dir)
        removable, partial = prune_usings.select_removable(found, compiled)
        self.assertEqual(list(removable.values()), [[3]])
        self.assertEqual(list(partial.values()), [[5]])

    def test_blank_lines_inside_a_span_are_dropped(self):
        self.assertEqual(prune_usings.keep_using_lines(self.program, [5, 6, 7]), [5, 7])


class TestRemoveUsingLines(PruneUsingsTestCase):
    def test_removes_lines_byte_exact(self):
        removed, skipped = prune_usings.remove_using_lines(self.program, [3, 5, 7])
        self.assertEqual((removed, skipped), ([3, 5, 7], []))
        expected = PROGRAM.replace(b"using System.Linq;\r\n", b"").replace(b"using System.Text;\r\n", b"")
        expected = expected.replace(b"using System.IO;\r\n", b"")
        self.assertEqual(self._read_bytes(os.path.join("Demo", "Program.cs")), expected)

    def test_line_that_is_no_longer_a_using_is_skipped(self):
        removed, skipped = prune_usings.remove_using_lines(self.program, [1, 8, 99])
        self.assertEqual((removed, skipped), ([], [1, 8, 99]))
        self.assertEqual(self._read_bytes(os.path.join("Demo", "Program.cs")), PROGRAM)

    def test_first_line_keeps_the_bom(self):
        path = self._write_bytes("First.cs", BOM + b"using System.Linq;\nnamespace A;\n")
        prune_usings.remove_using_lines(path, [1])
        self.assertEqual(self._read_bytes("First.cs"), BOM + b"namespace A;\n")

    def test_using_statement_is_not_a_directive(self):
        path = self._write_bytes("Stmt.cs", b"using (var x = Open()) { }\nusing static System.Math;\nusing L = System.Collections.Generic.List<int>;\n")
        removed, skipped = prune_usings.remove_using_lines(path, [1, 2, 3])
        self.assertEqual((removed, skipped), ([2, 3], [1]))


class TestEditorconfigPatch(PruneUsingsTestCase):
    def test_patch_and_restore_are_byte_exact(self):
        original = b"root = true\r\n\r\n[*.cs]\r\ndotnet_diagnostic.IDE0005.severity = none # quiet\r\nother = 1\r\n"
        path = self._write_bytes(".editorconfig", original)
        backups = tempfile.mkdtemp(dir=self.root)
        patched = []
        prune_usings.patch_editorconfigs(self.root, backups, patched)
        self.assertIn(b"dotnet_diagnostic.IDE0005.severity = warning # quiet\r\n", self._read_bytes(".editorconfig"))
        self.assertEqual(len(os.listdir(backups)), 1)
        self.assertEqual(prune_usings.restore_files(patched), [])
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), original)

    def test_already_warning_is_left_alone(self):
        self._write_bytes(".editorconfig", b"root = true\n[*.cs]\ndotnet_diagnostic.IDE0005.severity = warning\n")
        patched = []
        prune_usings.patch_editorconfigs(self.root, tempfile.mkdtemp(dir=self.root), patched)
        self.assertEqual(patched, [])


class TestResolveTarget(PruneUsingsTestCase):
    def test_prefers_solution_over_projects(self):
        self._write_bytes("App.sln", b"")
        self._write_bytes("App.csproj", b"")
        self.assertTrue(prune_usings.resolve_target(self.root).endswith("App.sln"))

    def test_ambiguous_solutions_raise(self):
        self._write_bytes("A.sln", b"")
        self._write_bytes("B.slnx", b"")
        with self.assertRaises(ValueError):
            prune_usings.resolve_target(self.root)


class TestDigest(PruneUsingsTestCase):
    def setUp(self):
        super().setUp()
        self._write_bytes("Demo.csproj", b"<Project />")
        self.editorconfig = b"root = true\n[*.cs]\ndotnet_diagnostic.IDE0005.severity = silent\n"
        self._write_bytes(".editorconfig", self.editorconfig)

    def _fake_build(self, spans, exit_code=0, output="", seen=None):
        def run(cmd, cwd, timeout, env):
            targets = re.search(r"CustomBeforeMicrosoftCommonTargets=([^\"]+)", cmd).group(1)
            sarif_dir = os.path.join(os.path.dirname(targets), "sarif")
            self._write_sarif(sarif_dir, "Demo_net10.0_111.sarif", _sarif(self.program, spans))
            if seen is not None:
                seen.append(self._read_bytes(".editorconfig"))
            return exit_code, output

        return mock.patch.object(prune_usings, "run_command", side_effect=run)

    def test_dry_run_lists_lines_and_changes_nothing(self):
        seen = []
        with self._fake_build([(3, 3), (5, 7)], seen=seen):
            result = prune_usings.digest(self.root)
        self.assertIn("removable (3 lines, 1 files)", result)
        self.assertIn("3 using System.Linq; | 5 using System.Text; | 7 using System.IO;", result)
        self.assertIn("dry run", result)
        self.assertIn(b"severity = warning", seen[0])
        self.assertEqual(self._read_bytes(".editorconfig"), self.editorconfig)
        self.assertEqual(self._read_bytes(os.path.join("Demo", "Program.cs")), PROGRAM)

    def test_apply_removes_lines(self):
        with self._fake_build([(3, 3)]):
            result = prune_usings.digest(self.root, apply=True)
        self.assertIn("removed 1 lines in 1 files", result)
        self.assertNotIn(b"System.Linq", self._read_bytes(os.path.join("Demo", "Program.cs")))

    def test_build_failure_removes_nothing(self):
        output = "Foo.cs(3,1): error CS0246: The type or namespace name 'X' could not be found [Demo.csproj]\n"
        with self._fake_build([(3, 3)], exit_code=1, output=output):
            result = prune_usings.digest(self.root, apply=True)
        self.assertIn("build failed", result)
        self.assertEqual(self._read_bytes(os.path.join("Demo", "Program.cs")), PROGRAM)
        self.assertEqual(self._read_bytes(".editorconfig"), self.editorconfig)

    def test_codeless_nuget_error_counts_as_build_failure(self):
        output = "C:\\dotnet\\sdk\\NuGet.targets(782,5): error : Value cannot be null. (Parameter 'path1') [Demo.csproj]\n"
        with self._fake_build([(3, 3)], exit_code=1, output=output):
            result = prune_usings.digest(self.root, apply=True)
        self.assertIn("build failed", result)
        self.assertIn("Value cannot be null", result)

    def test_ide0005_promoted_to_error_is_not_a_build_failure(self):
        output = "Program.cs(3,1): error IDE0005: Using directive is unnecessary. [Demo.csproj]\n"
        with self._fake_build([(3, 3)], exit_code=1, output=output):
            result = prune_usings.digest(self.root)
        self.assertIn("removable (1 lines, 1 files)", result)

    def test_editorconfig_restored_even_if_build_raises(self):
        with mock.patch.object(prune_usings, "run_command", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                prune_usings.digest(self.root)
        self.assertEqual(self._read_bytes(".editorconfig"), self.editorconfig)


if __name__ == "__main__":
    unittest.main()
