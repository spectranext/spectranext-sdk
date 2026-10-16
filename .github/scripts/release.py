#!/usr/bin/env python3
"""Release metadata, archive checksums and an atomic Homebrew formula update."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

TAP = 'spectranext/homebrew-spectranext'
FORMULA = 'Formula/spectranext-sdk.rb'


def version_from_tag(tag):
    version = tag.removeprefix('v')
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?', version):
        raise ValueError('Use a release tag such as 0.1.5 or v0.1.5 (optional prerelease suffix).')
    return version


def github(path, payload=None):
    # The App token only accesses the tap. Use the built-in SDK token for
    # release metadata in the source repository, including manual reruns.
    token = os.environ['GH_TOKEN']
    if not path.startswith(f'repos/{TAP}/'):
        token = os.environ.get('SDK_GITHUB_TOKEN', token)
    request = urllib.request.Request('https://api.github.com/' + path,
        data=None if payload is None else json.dumps(payload).encode(),
        method='GET' if payload is None else 'PUT', headers={
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'X-GitHub-Api-Version': '2022-11-28',
        })
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def metadata(repo, tag, api=github):
    version = version_from_tag(tag)
    release = api(f'repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe="")}')
    if release['draft']:
        raise ValueError('Publish the release before running this workflow.')
    try:
        latest = api(f'repos/{repo}/releases/latest')
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        latest = {}
    asset = f'spectranext-sdk-{version}-macos-arm64.tar.gz'
    return dict(tag=tag, version=version, asset=asset,
        asset_exists=str(any(a['name'] == asset for a in release['assets'])).lower(),
        immutable=str(release.get('immutable', False)).lower(),
        promote=str(not release['prerelease'] and '-' not in version and latest.get('tag_name') == tag).lower())


def checksum(archive):
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    Path(str(archive) + '.sha256').write_text(f'{digest}  {Path(archive).name}\n')
    return digest


def update_formula(source, version, url, digest):
    current = re.search(r'^  version "([^"]+)"$', source, re.M)
    if not current:
        raise ValueError('Formula has no top-level version.')
    # Replaying an older release must not downgrade the tap.
    if tuple(map(int, current[1].split('.'))) > tuple(map(int, version.split('.'))):
        return source
    for field, value in [('version', version), ('url', url), ('sha256', digest)]:
        source, count = re.subn(rf'^  {field} "[^"]+"$', lambda m: f'  {field} "{value}"', source, flags=re.M)
        if count != 1:
            raise ValueError(f'Expected one top-level {field}; found {count}.')
    return source


def update_tap(repo, tag, archive, api=github):
    details = metadata(repo, tag, api)
    if details['promote'] != 'true':
        print('Not the latest stable release; leave Homebrew unchanged.')
        return
    if Path(archive).name != details['asset']:
        raise ValueError('Archive name does not match the release tag.')
    row = api(f'repos/{TAP}/contents/{FORMULA}')
    source = base64.b64decode(row['content']).decode()
    url = f'https://github.com/{repo}/releases/download/{tag}/{details["asset"]}'
    updated = update_formula(source, details['version'], url, checksum(archive))
    if updated == source:
        print('Homebrew formula already matches, or is newer; no commit needed.')
        return
    # Contents API checks the blob SHA: a concurrent edit fails instead of being overwritten.
    result = api(f'repos/{TAP}/contents/{FORMULA}', {
        'message': f'Update spectranext-sdk to {details["version"]}',
        'sha': row['sha'], 'content': base64.b64encode(updated.encode()).decode()})
    print('Updated Homebrew: ' + result['commit']['html_url'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['metadata', 'checksum', 'tap'])
    parser.add_argument('--tag')
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', 'spectranext/spectranext-sdk'))
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    if args.command in ('metadata', 'tap') and not args.tag:
        parser.error('--tag is required')
    if args.command in ('checksum', 'tap') and not args.archive:
        parser.error('--archive is required')
    if args.command == 'metadata':
        values = metadata(args.repo, args.tag)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.writelines(f'{key}={value}\n' for key, value in values.items())
        print(json.dumps(values, indent=2))
    elif args.command == 'checksum':
        print(checksum(args.archive))
    else:
        update_tap(args.repo, args.tag, args.archive)


if __name__ == '__main__':
    main()
