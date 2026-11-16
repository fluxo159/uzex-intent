#!/usr/bin/env python3
"""Run pinned Gitleaks against all Git history, checking its binary checksum."""
import hashlib
import io
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import urllib.request

VERSION = '8.30.1'
BUILDS = {
    ('Darwin', 'arm64'): ('darwin_arm64', 'b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5'),
    ('Darwin', 'x86_64'): ('darwin_x64', 'dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709'),
    ('Linux', 'aarch64'): ('linux_arm64', 'e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080'),
    ('Linux', 'x86_64'): ('linux_x64', '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'),
}


def main():
    build = BUILDS.get((platform.system(), platform.machine()))
    if not build:
        raise SystemExit('Unsupported platform for this pinned scanner.')
    name, expected = build
    url = f'https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/gitleaks_{VERSION}_{name}.tar.gz'
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit('Scanner download failed its SHA-256 check.')
    with tempfile.TemporaryDirectory(prefix='lecture-secret-scan-') as directory:
        scanner = Path(directory) / 'gitleaks'
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            member = archive.getmember('gitleaks')
            if not member.isfile() or member.size > 64 * 1024 * 1024:
                raise SystemExit('Unexpected scanner archive.')
            scanner.write_bytes(archive.extractfile(member).read())
        scanner.chmod(0o700)
        root = Path(__file__).resolve().parents[1]
        return subprocess.run([str(scanner), 'git', '--redact=100', '--no-banner', '--log-opts=--all', str(root)], cwd=root).returncode


if __name__ == '__main__':
    raise SystemExit(main())
