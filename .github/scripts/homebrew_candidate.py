#!/usr/bin/env python3
"""Point a copy of the real Homebrew formula at a locally built SDK archive.

The separate formula name and --skip-link installation let CI test the PR's
package using the tap's actual installation recipe, without replacing an
installed release or publishing anything to the tap.
"""
import argparse
import hashlib
from pathlib import Path
import re


def prepare(formula, archive):
    match = re.fullmatch(r'spectranext-sdk-(.+)-macos-arm64.tar.gz', archive.name)
    if not match:
        raise ValueError('Expected a macOS ARM64 SDK archive')
    source, count = re.subn(r'^class SpectranextSdk < Formula$',
                           'class SpectranextSdkCi < Formula', formula, flags=re.M)
    if count != 1:
        raise ValueError('Expected one SpectranextSdk formula class')
    fields = dict(version=match[1], url=archive.resolve().as_uri(),
                  sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    for field, value in fields.items():
        source, count = re.subn(rf'^  {field} "[^"]+"$',
                               lambda m: f'  {field} "{value}"', source, flags=re.M)
        if count != 1:
            raise ValueError(f'Expected one top-level {field}; found {count}')
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--formula', required=True, type=Path)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.name != 'spectranext-sdk-ci.rb':
        parser.error('--output must be named spectranext-sdk-ci.rb')
    if args.output.exists():
        parser.error(f'Refusing to overwrite {args.output}')
    args.output.write_text(prepare(args.formula.read_text(), args.archive))


if __name__ == '__main__':
    main()
