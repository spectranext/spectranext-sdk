import base64
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('release', Path(__file__).parents[1] / 'release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

FORMULA = '''class SpectranextSdk < Formula
  version "0.1.3"
  url "https://example.test/old.tar.gz"
  sha256 "old"

  resource "z88dk" do
    version "20260530-a996c99f3d-24825"
    url "http://nightly.z88dk.org/z88dk-osx.zip"
    sha256 "toolchain-checksum"
  end
end
'''


class ReleaseTests(unittest.TestCase):
    def api(self, path, payload=None):
        if path.endswith('/releases/tags/v0.1.4'):
            return dict(draft=False, prerelease=False, tag_name='v0.1.4', assets=[])
        if path.endswith('/releases/latest'):
            return dict(tag_name='v0.1.4')
        if path.endswith(release.FORMULA):
            if payload is None:
                return dict(sha='expected-blob', content=base64.b64encode(FORMULA.encode()).decode())
            self.updates.append(payload)
            return {'commit': {'html_url': 'https://example.test/commit'}}
        self.fail(path)

    def setUp(self):
        self.updates = []

    def test_tags_and_shell_metacharacters(self):
        self.assertEqual(release.version_from_tag('v0.1.4'), '0.1.4')
        self.assertEqual(release.version_from_tag('0.1.5-rc.1'), '0.1.5-rc.1')
        for tag in ['../main', '0.1.4;whoami', '0.1.4\nfoo=x', 'latest', '01.2.3', '1.2.3+build']:
            with self.assertRaises(ValueError):
                release.version_from_tag(tag)

    def test_metadata_promotes_only_latest_stable(self):
        result = release.metadata('spectranext/spectranext-sdk', 'v0.1.4', self.api)
        self.assertEqual(result['version'], '0.1.4')
        self.assertEqual(result['asset'], 'spectranext-sdk-0.1.4-macos-arm64.tar.gz')
        self.assertEqual(result['promote'], 'true')
        def older(path):
            row = self.api(path)
            if path.endswith('/latest'): row['tag_name'] = '0.1.5'
            return row
        self.assertEqual(release.metadata('r/r', 'v0.1.4', older)['promote'], 'false')
        def prerelease(path):
            row = self.api(path)
            if '/tags/' in path: row['prerelease'] = True
            return row
        self.assertEqual(release.metadata('r/r', 'v0.1.4', prerelease)['promote'], 'false')

    def test_existing_asset_is_reused_and_draft_rejected(self):
        def existing(path):
            row = self.api(path)
            row['assets'] = [{'name': 'spectranext-sdk-0.1.4-macos-arm64.tar.gz'}]
            return row
        self.assertEqual(release.metadata('r/r', 'v0.1.4', existing)['asset_exists'], 'true')
        def draft(path):
            row = self.api(path); row['draft'] = True; return row
        with self.assertRaises(ValueError): release.metadata('r/r', 'v0.1.4', draft)

    def test_formula_preserves_toolchain_and_is_idempotent(self):
        updated = release.update_formula(FORMULA, '0.1.4', 'https://example.test/new.tar.gz', 'abc')
        self.assertIn('  version "0.1.4"', updated)
        self.assertEqual(updated.split('  resource')[1], FORMULA.split('  resource')[1])
        self.assertEqual(release.update_formula(updated, '0.1.4', 'https://example.test/new.tar.gz', 'abc'), updated)
        self.assertEqual(release.update_formula(updated, '0.1.2', 'old', 'old'), updated)
        with self.assertRaises(ValueError):
            release.update_formula(FORMULA.replace('  sha256 "old"\n', ''), '0.1.4', 'url', 'abc')

    def test_tap_commit_uses_archive_checksum_and_blob_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'spectranext-sdk-0.1.4-macos-arm64.tar.gz'
            archive.write_bytes(b'archive contents')
            release.update_tap('spectranext/spectranext-sdk', 'v0.1.4', archive, self.api)
            self.assertEqual(len(self.updates), 1)
            payload = self.updates[0]
            self.assertEqual(payload['sha'], 'expected-blob')
            text = base64.b64decode(payload['content']).decode()
            self.assertIn(hashlib.sha256(archive.read_bytes()).hexdigest(), text)
            self.assertIn('/releases/download/v0.1.4/spectranext-sdk-0.1.4-macos-arm64.tar.gz', text)
            self.assertEqual(Path(str(archive)+'.sha256').read_text().split()[1], archive.name)


if __name__ == '__main__':
    unittest.main()
