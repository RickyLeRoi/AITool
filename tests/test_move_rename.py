# tests/test_move_rename.py
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import move_rename

BOM = b"\xef\xbb\xbf"
NAMESPACES = {"Company.Old": "Company.New"}
FOO = (
    BOM + b"// src/Old/Foo.cs\r\n"
    b"using Company.Old.Data;\r\n"
    b"using Company.OldStuff;\r\n"
    b"\r\n"
    b"namespace Company.Old.Services;\r\n"
    b"// caf\xe9 mojibake \xc3\xa8\r\n"
    b"public class Foo { Other.Company.Old.X x; global::Company.Old.Y y; }\r\n"
)


class MoveRenameTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="move_rename_test_")
        self.foo = self._write("src/Old/Foo.cs", FOO)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _path(self, relative):
        return os.path.join(self.root, *relative.split("/"))

    def _write(self, relative, data):
        path = self._path(relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def _read(self, relative):
        with open(self._path(relative), "rb") as fh:
            return fh.read()

    def _map(self, moves=(), namespaces=None, name="map.json"):
        payload = {"moves": [{"from": s, "to": d} for s, d in moves], "namespaces": namespaces or {}}
        return self._write(name, json.dumps(payload).encode("utf-8"))


class TestNamespaceRename(MoveRenameTestCase):
    def rename(self, data):
        return move_rename.rename_namespaces(data, move_rename.namespace_pattern(NAMESPACES), NAMESPACES)

    def test_prefix_and_boundaries(self):
        data, count = self.rename(FOO)
        self.assertEqual(count, 3)
        self.assertIn(b"using Company.New.Data;\r\n", data)
        self.assertIn(b"using Company.OldStuff;\r\n", data)
        self.assertIn(b"namespace Company.New.Services;\r\n", data)
        self.assertIn(b"Other.Company.Old.X", data)
        self.assertIn(b"global::Company.New.Y", data)

    def test_bytes_outside_matches_are_untouched(self):
        data, _ = self.rename(FOO)
        self.assertTrue(data.startswith(BOM))
        self.assertIn(b"caf\xe9 mojibake \xc3\xa8\r\n", data)
        self.assertEqual(data.count(b"\r\n"), FOO.count(b"\r\n"))

    def test_paths_file_names_and_assembly_name_are_left_alone(self):
        csproj = (
            b'<ProjectReference Include="..\\Company.Old\\Company.Old.csproj" />\n'
            b"<RootNamespace>Company.Old</RootNamespace>\n"
            b"<AssemblyName>Company.Old</AssemblyName>\n"
        )
        data, count = self.rename(csproj)
        self.assertEqual(count, 1)
        self.assertIn(b"<RootNamespace>Company.New</RootNamespace>", data)
        self.assertIn(b"<AssemblyName>Company.Old</AssemblyName>", data)
        self.assertIn(b"..\\Company.Old\\Company.Old.csproj", data)

    def test_razor_xaml_and_json_type_names(self):
        data, count = self.rename(
            b"@using Company.Old.Pages\n"
            b'xmlns:local="clr-namespace:Company.Old.Views"\n'
            b'"Type": "Company.Old.Sink, Company.Old"\n'
        )
        self.assertEqual(count, 4)
        self.assertNotIn(b"Company.Old", data)

    def test_longest_key_wins_no_chained_replacement(self):
        namespaces = {"A.B": "X", "A.B.C": "Y", "X": "Z"}
        pattern = move_rename.namespace_pattern(namespaces)
        data, _ = move_rename.rename_namespaces(b"using A.B.C.D; using A.B; using X;", pattern, namespaces)
        self.assertEqual(data, b"using Y.D; using X; using Z;")


class TestHeader(MoveRenameTestCase):
    def test_header_path_updated_keeping_crlf_and_bom(self):
        data, changed = move_rename.update_header(FOO, self.foo, self._path("src/New/Sub/Foo.cs"), self.root)
        self.assertTrue(changed)
        self.assertTrue(data.startswith(BOM + b"// src/New/Sub/Foo.cs\r\nusing"))

    def test_project_relative_header_keeps_its_base(self):
        data = b"// Old/Foo.cs\n"
        new, changed = move_rename.update_header(data, self.foo, self._path("src/New/Foo.cs"), self.root)
        self.assertTrue(changed)
        self.assertEqual(new, b"// New/Foo.cs\n")

    def test_backslash_style_is_preserved(self):
        new, _ = move_rename.update_header(b"// src\\Old\\Foo.cs\r\n", self.foo, self._path("src/New/Foo.cs"), self.root)
        self.assertEqual(new, b"// src\\New\\Foo.cs\r\n")

    def test_non_path_comment_is_left_alone(self):
        data = b"// Copyright 2020 Someone\r\n"
        self.assertEqual(move_rename.update_header(data, self.foo, self._path("src/New/Foo.cs"), self.root), (data, False))


class TestDigest(MoveRenameTestCase):
    def setUp(self):
        super().setUp()
        self.bar = self._write("src/Other/Bar.cs", b"using Company.Old.Services;\r\nclass Bar {}\r\n")
        self.csproj = self._write("src/Other/Other.csproj", b"<RootNamespace>Company.Old</RootNamespace>\r\n")

    def test_dry_run_changes_nothing(self):
        map_path = self._map([("src/Old/Foo.cs", "src/New/Foo.cs")], NAMESPACES)
        result = move_rename.digest(map_path, self.root)
        self.assertIn("src/Old/Foo.cs -> src/New/Foo.cs (planned, header updated)", result)
        self.assertIn("namespace replacements: 5 in 3 files", result)
        self.assertIn("dry run", result)
        self.assertEqual(self._read("src/Old/Foo.cs"), FOO)

    def test_apply_moves_and_rewrites(self):
        map_path = self._map([("src/Old/Foo.cs", "src/New/Foo.cs")], NAMESPACES)
        result = move_rename.digest(map_path, self.root, apply=True)
        self.assertIn("(moved, header updated)", result)
        self.assertFalse(os.path.exists(self.foo))
        moved = self._read("src/New/Foo.cs")
        self.assertTrue(moved.startswith(BOM + b"// src/New/Foo.cs\r\n"))
        self.assertIn(b"namespace Company.New.Services;\r\n", moved)
        self.assertEqual(self._read("src/Other/Bar.cs"), b"using Company.New.Services;\r\nclass Bar {}\r\n")
        self.assertEqual(self._read("src/Other/Other.csproj"), b"<RootNamespace>Company.New</RootNamespace>\r\n")

    def test_map_file_itself_is_never_rewritten(self):
        map_path = self._map(namespaces=NAMESPACES)
        before = self._read("map.json")
        move_rename.digest(map_path, self.root, apply=True)
        self.assertEqual(self._read("map.json"), before)

    def test_existing_target_refuses_everything(self):
        self._write("src/New/Foo.cs", b"already here")
        map_path = self._map([("src/Old/Foo.cs", "src/New/Foo.cs")], NAMESPACES)
        result = move_rename.digest(map_path, self.root, apply=True)
        self.assertIn("target already exists", result)
        self.assertEqual(self._read("src/Old/Foo.cs"), FOO)
        self.assertEqual(self._read("src/Other/Bar.cs"), b"using Company.Old.Services;\r\nclass Bar {}\r\n")

    def test_invalid_namespace_key_is_rejected(self):
        map_path = self._map(namespaces={"Società.Old": "Company.New"})
        self.assertIn("not an ASCII dotted identifier", move_rename.digest(map_path, self.root))

    def test_utf16_file_is_reported_not_corrupted(self):
        utf16 = "namespace Company.Old;".encode("utf-16")
        self._write("src/Other/Wide.cs", utf16)
        result = move_rename.digest(self._map(namespaces=NAMESPACES), self.root, apply=True)
        self.assertIn("skipped (binary or UTF-16, check by hand):\n  src/Other/Wide.cs", result)
        self.assertEqual(self._read("src/Other/Wide.cs"), utf16)

    def test_git_mv_used_for_tracked_files(self):
        git = lambda *args: subprocess.run(["git", *args], cwd=self.root, capture_output=True, stdin=subprocess.DEVNULL)
        if git("init", "-q").returncode != 0:
            self.skipTest("git not available")
        git("-c", "core.autocrlf=false", "add", "src")
        map_path = self._map([("src/Old/Foo.cs", "src/New/Foo.cs")])
        result = move_rename.digest(map_path, self.root, apply=True)
        self.assertIn("(git mv, header updated)", result)
        staged = git("diff", "--cached", "--name-status").stdout.decode()
        self.assertIn("src/New/Foo.cs", staged)


if __name__ == "__main__":
    unittest.main()
