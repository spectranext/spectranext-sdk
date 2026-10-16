"""Check that CI cannot silently accept missing or failed example builds."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('homebrew_candidate', SCRIPTS / 'homebrew_candidate.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class ExampleChecks(unittest.TestCase):
    def test_missing_build_recipe_cannot_silently_skip_an_example(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'p2p-chat').mkdir()
            (root / 'p2p-chat/main.c').touch()
            (root / 'other').mkdir()
            (root / 'other/CMakeLists.txt').touch()
            result = subprocess.run([sys.executable, str(SCRIPTS / 'build_examples.py'),
                                     '--examples', str(root), '--output', str(root / 'out')],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Missing CMakeLists.txt for p2p-chat', result.stderr)

    def test_failed_and_missing_builds_do_not_hide_other_examples(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            examples = root / 'examples'
            for name in ['a-failed', 'b-missing', 'c-good']:
                (examples / name).mkdir(parents=True)
                (examples / name / 'CMakeLists.txt').touch()
            # A dependency's demonstration project is not a standalone example.
            vendor = examples / 'c-good/vendor/example'
            vendor.mkdir(parents=True)
            (vendor / 'CMakeLists.txt').touch()
            tools = root / 'tools'
            tools.mkdir()
            cmake = tools / 'cmake'
            cmake.write_text(f'#!{sys.executable}\n' + '''
from pathlib import Path
import sys
if sys.argv[1] == '-S':
    Path(sys.argv[4]).mkdir(parents=True)
    sys.exit(0)
build = Path(sys.argv[2])
if build.name == 'a-failed':
    print('deliberate compiler failure')
    sys.exit(1)
if build.name == 'c-good':
    (build / 'application.tap').write_bytes(b'TAP')
    (build / 'boot.zx').write_bytes(b'BASIC')
''')
            cmake.chmod(0o755)
            env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'])
            result = subprocess.run([sys.executable, str(SCRIPTS / 'build_examples.py'),
                                     '--examples', str(examples), '--output', str(root / 'out')],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            rows = json.loads((root / 'out/results.json').read_text())
            self.assertEqual([(r['example'], r['passed']) for r in rows],
                             [('a-failed', False), ('b-missing', False), ('c-good', True)])
            self.assertIn('deliberate compiler failure', (root / 'out/a-failed.log').read_text())
            self.assertIn('nonempty TAP', (root / 'out/b-missing.log').read_text())

    def test_homebrew_candidate_preserves_install_recipe_and_toolchain(self):
        formula = '''class SpectranextSdk < Formula
  version "0.1.4"
  url "https://example.test/release.tar.gz"
  sha256 "old"
  resource "z88dk" do
    version "pinned"
    url "https://example.test/toolchain.zip"
    sha256 "pinned"
  end
  def install
    libexec.install Dir["*"]
  end
end
'''
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'spectranext-sdk-0.0.0-macos-arm64.tar.gz'
            archive.write_bytes(b'candidate archive')
            output = candidate.prepare(formula, archive)
            self.assertIn('class SpectranextSdkCi < Formula', output)
            self.assertIn('  version "0.0.0"', output)
            self.assertIn(archive.resolve().as_uri(), output)
            self.assertEqual(output.split('  resource')[1], formula.split('  resource')[1])
            with self.assertRaises(ValueError):
                candidate.prepare(formula.replace('  sha256 "old"\n', ''), archive)


if __name__ == '__main__':
    unittest.main()
