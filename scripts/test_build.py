import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('rules_build', Path(__file__).with_name('build.py'))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class MrsDomainSemanticsTest(unittest.TestCase):
    def test_domain_remains_exact_match(self):
        with tempfile.TemporaryDirectory() as directory:
            captured = []

            def capture_converter(command, check):
                captured.extend(Path(command[-2]).read_text(encoding='utf-8').splitlines())

            rules = {'domain': ['example.com'], 'domain_suffix': [],
                     'domain_keyword': [], 'ip_cidr': []}
            with patch.object(build, 'MRS_DIR', Path(directory)), \
                 patch.object(build.subprocess, 'run', side_effect=capture_converter), \
                 contextlib.redirect_stdout(io.StringIO()):
                build.build_mrs('exact', rules)
            self.assertEqual(captured, ['example.com'])


    def test_suffix_keeps_subdomain_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            captured = []

            def capture_converter(command, check):
                captured.extend(Path(command[-2]).read_text(encoding='utf-8').splitlines())

            rules = {'domain': [], 'domain_suffix': ['example.com'],
                     'domain_keyword': [], 'ip_cidr': []}
            with patch.object(build, 'MRS_DIR', Path(directory)), \
                 patch.object(build.subprocess, 'run', side_effect=capture_converter), \
                 contextlib.redirect_stdout(io.StringIO()):
                build.build_mrs('suffix', rules)
            self.assertEqual(captured, ['+.example.com'])

    def test_mixed_list_preserves_both_rule_types(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'mixed.list'
            source.write_text('# comment\nDOMAIN,exact.example\nDOMAIN-SUFFIX,suffix.example\nDOMAIN,exact.example\n', encoding='utf-8')
            rules = build.parse_rules(source)
            captured = []

            def capture_converter(command, check):
                captured.extend(Path(command[-2]).read_text(encoding='utf-8').splitlines())

            with patch.object(build, 'MRS_DIR', Path(directory)), \
                 patch.object(build.subprocess, 'run', side_effect=capture_converter), \
                 contextlib.redirect_stdout(io.StringIO()):
                build.build_mrs('mixed', rules)
            self.assertEqual(captured, ['exact.example', '+.suffix.example'])


if __name__ == '__main__':
    unittest.main()
