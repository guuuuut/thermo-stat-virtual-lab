"""Exercise the actual deployment transaction in an isolated local directory."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache'
SHELL = Path('E:/Git/usr/bin/bash.exe') if os.name == 'nt' else Path('/bin/sh')


def shell_path(path: Path) -> str:
    if os.name == 'nt':
        return '/' + path.drive[0].lower() + path.as_posix()[2:]
    return str(path)


@unittest.skipUnless(SHELL.is_file(), 'A POSIX shell is required for the transaction test')
class DeploymentTransactionTest(unittest.TestCase):
    def setUp(self) -> None:
        CACHE.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='deploy-transaction-', dir=CACHE)
        self.root = Path(self.temp.name).resolve()
        self.assertTrue(self.root.is_relative_to(CACHE.resolve()))
        self.site = self.root / 'site'
        self.backups = self.root / 'backups'
        self.fakebin = self.root / 'fakebin'
        self.fakebin.mkdir()
        commands = {
            'systemctl': '#!/bin/sh\nexit 0\n',
            'curl': '#!/bin/sh\nif [ "${FAIL_HEALTH:-0}" = 1 ]; then exit 9; fi\nexit 0\n',
        }
        if os.name == 'nt':
            # NTFS cannot apply the Linux mode bits; test content operations only.
            commands['install'] = '#!/bin/sh\nif [ "$1" = -d ]; then shift; [ "$1" = -m ] && shift 2; mkdir -p "$@"; else [ "$1" = -m ] && shift 2; cp "$1" "$2"; fi\n'
        for name, text in commands.items():
            path = self.fakebin / name
            path.write_text(text, encoding='ascii')
            path.chmod(0o755)
        source = (ROOT / 'scripts/deploy_site.ps1').read_text(encoding='utf-8-sig')
        match = re.search(r"\$remoteDeployContent = @'\r?\n(.*?)\r?\n'@", source, re.S)
        self.assertIsNotNone(match)
        script = match[1].replace('site=/var/www/visual-lab', f'site="{shell_path(self.site)}"')
        script = script.replace('backup="/root/visual-lab-backups/deploy-$stamp"', f'backup="{shell_path(self.backups)}/deploy-$stamp"')
        self.script = self.root / 'deploy.sh'
        self.script.write_text(script + '\n', encoding='utf-8', newline='\n')
        self.assets = ['index.html', 'learning.html', 'downloads/pressure_diffusion_trajectories.zip', 'homework.html', 'downloads/homework_20261027.zip']
        self.retired = ['pressure_analysis.html', 'results/diffusion_pressure/diffusion_vs_pressure.csv']
        self.incoming = []
        for i, name in enumerate(self.assets):
            path = self.root / f'incoming-{i}'
            path.write_bytes(('new:' + name).encode())
            self.incoming.append(path)

    def tearDown(self) -> None:
        self.assertTrue(self.root.resolve().is_relative_to(CACHE.resolve()))
        self.temp.cleanup()

    def existing(self, include_homework: bool) -> dict[str, bytes]:
        old = {}
        for name in self.assets[:3] + (self.assets[3:] if include_homework else []) + self.retired:
            path = self.site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            old[name] = ('old:' + name).encode()
            path.write_bytes(old[name])
        return old

    def execute(self, fail: bool) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env['PATH'] = str(self.fakebin) + os.pathsep + str(SHELL.parent) + os.pathsep + env.get('PATH', '')
        env['FAIL_HEALTH'] = '1' if fail else '0'
        args = [str(SHELL), shell_path(self.script), 'test', shell_path(self.incoming[0]), shell_path(self.incoming[1]), shell_path(self.incoming[2]), 'example.test', shell_path(self.incoming[3]), shell_path(self.incoming[4])]
        return subprocess.run(args, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)

    def test_success_installs_all_assets_and_retires_answers(self) -> None:
        self.existing(include_homework=False)
        result = self.execute(fail=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in self.assets:
            self.assertEqual((self.site / name).read_bytes(), ('new:' + name).encode())
        for name in self.retired:
            self.assertFalse((self.site / name).exists())
        self.assertFalse(list(self.site.rglob('*.next')))

    def test_failure_restores_existing_homework_and_retired_files(self) -> None:
        old = self.existing(include_homework=True)
        result = self.execute(fail=True)
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertTrue((self.backups / 'deploy-test/index.html').exists())
        for name, content in old.items():
            self.assertEqual((self.site / name).read_bytes(), content)
        self.assertFalse(list(self.site.rglob('*.next')))

    def test_failure_removes_new_homework_files(self) -> None:
        old = self.existing(include_homework=False)
        result = self.execute(fail=True)
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertTrue((self.backups / 'deploy-test/index.html').exists())
        for name, content in old.items():
            self.assertEqual((self.site / name).read_bytes(), content)
        for name in self.assets[3:]:
            self.assertFalse((self.site / name).exists())


if __name__ == '__main__':
    unittest.main()
