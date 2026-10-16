#!/usr/bin/env python3
"""Build every standalone example with the SDK sourced in the environment.

Keep each example in a separate build directory: the SDK's boot_file and upload
targets are intentionally local to one application. Build failures are collected
so the report still covers every example. No upload or emulator target is run.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--examples', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    examples = args.examples.resolve()
    output = args.output.resolve()
    for main in sorted(examples.glob('*/main.c')):
        if not (main.parent / 'CMakeLists.txt').is_file():
            parser.error(f'Missing CMakeLists.txt for {main.parent.name}')
    projects = sorted(examples.glob('*/CMakeLists.txt'))
    if not projects:
        parser.error(f'No standalone examples found under {examples}')
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for project in projects:
        name = project.parent.name
        build = output / name
        if build.exists():
            parser.error(f'Use a fresh output directory; {build} already exists')
        log = output / f'{name}.log'
        start = time.monotonic()
        print(f'::group::{name}', flush=True)
        commands = [
            ['cmake', '-S', str(project.parent), '-B', str(build)],
            ['cmake', '--build', str(build), '--parallel', '2'],
            ['cmake', '--build', str(build), '--target', 'boot_file'],
        ]
        code = 0
        with log.open('w') as stream:
            for command in commands:
                stream.write('$ ' + ' '.join(command) + '\n')
                stream.flush()
                code = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT).returncode
                if code:
                    break
        artifacts = sorted(p for p in build.glob('*.tap') if p.stat().st_size)
        boot = build / 'boot.zx'
        if not code and (not artifacts or not boot.is_file() or not boot.stat().st_size):
            code = 1
            with log.open('a') as stream:
                stream.write('ERROR: Build did not produce a nonempty TAP and boot.zx\n')
        result = dict(example=name, passed=code == 0, returncode=code,
                      seconds=round(time.monotonic() - start, 2),
                      artifacts=[str(p.relative_to(output)) for p in artifacts],
                      log=log.name)
        results.append(result)
        if code:
            print(log.read_text(), flush=True)
        print(f'{"PASS" if not code else "FAIL"}: {name} ({result["seconds"]}s)', flush=True)
        print('::endgroup::', flush=True)
        (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    passed = sum(row['passed'] for row in results)
    print(f'{passed}/{len(results)} examples passed. Logs: {output}', flush=True)
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
