# tests/test_project_graph.py
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import project_graph

LAYERS = "Utility; DB,FS,Connector; *; BusinessLogic; WebApi"


class TestProjectGraph(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="project_graph_test_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _project(self, name, *refs, folder=None):
        folder = folder or name
        os.makedirs(os.path.join(self.root, "src", folder), exist_ok=True)
        items = "\n".join(f'    <ProjectReference Include="..\\{r}\\{r}.csproj" />' for r in refs)
        with open(os.path.join(self.root, "src", folder, f"{name}.csproj"), "w", encoding="utf-8") as fh:
            fh.write(f'<Project Sdk="Microsoft.NET.Sdk">\n  <ItemGroup>\n{items}\n  </ItemGroup>\n</Project>\n')

    def test_no_projects(self):
        self.assertIn("no .csproj files", project_graph.digest(self.root))

    def test_builds_adjacency_from_project_references(self):
        self._project("App.Utility")
        self._project("App.DB", "App.Utility")
        graph, dangling = project_graph.build_graph(self.root)
        self.assertEqual(graph["App.DB"], ["App.Utility"])
        self.assertEqual(dangling, [])

    def test_bin_and_obj_are_skipped(self):
        self._project("App.Utility")
        self._project("Copy", folder=os.path.join("App.Utility", "obj"))
        graph, _ = project_graph.build_graph(self.root)
        self.assertEqual(list(graph), ["App.Utility"])

    def test_detects_cycle(self):
        self._project("A", "B")
        self._project("B", "C")
        self._project("C", "A")
        self._project("D", "A")
        result = project_graph.digest(self.root)
        self.assertIn("cycles (1):\n  A -> B -> C -> A", result)

    def test_no_cycle_reported_for_a_dag(self):
        self._project("A", "B", "C")
        self._project("B", "C")
        self._project("C")
        self.assertIn("cycles: none", project_graph.digest(self.root))

    def test_upward_reference_is_a_violation_same_layer_is_not(self):
        self._project("App.Utility", "App.BusinessLogic")
        self._project("App.Orders", "App.Invoices", "App.DB")
        self._project("App.Invoices")
        self._project("App.DB")
        self._project("App.BusinessLogic")
        result = project_graph.digest(self.root, LAYERS)
        self.assertIn("layer violations (1):\n  App.Utility (L0) -> App.BusinessLogic (L3)", result)

    def test_layer_tokens_match_name_segments_not_substrings(self):
        layers = project_graph.parse_layers(LAYERS)
        self.assertEqual(project_graph.layer_of("App.DB", layers), 1)
        self.assertEqual(project_graph.layer_of("App.Feedback", layers), 2)
        self.assertEqual(project_graph.layer_of("App.SapConnector", layers), 2)
        self.assertEqual(project_graph.layer_of("App.SapConnector", project_graph.parse_layers("*connector*")), 0)

    def test_unassigned_without_wildcard_layer(self):
        self._project("App.Utility")
        self._project("App.Orders")
        result = project_graph.digest(self.root, "Utility; WebApi")
        self.assertIn("unassigned (1): App.Orders", result)

    def test_dangling_reference_is_reported(self):
        self._project("App.Web", "App.Gone")
        result = project_graph.digest(self.root)
        self.assertIn("dangling references (1):\n  App.Web -> src/App.Gone/App.Gone.csproj", result)

    def test_duplicate_stems_fall_back_to_relative_path(self):
        self._project("Tools", folder="one")
        self._project("Tools", folder="two")
        graph, _ = project_graph.build_graph(self.root)
        self.assertEqual(sorted(graph), ["src/one/Tools.csproj", "src/two/Tools.csproj"])


if __name__ == "__main__":
    unittest.main()
