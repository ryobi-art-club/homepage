"""コミット予定の検査を、架空の内容だけを置いた一時リポジトリで確かめる。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_repository_contents as scan


# 実際の宛先は使わず、検査で禁止される形だけを作る
PRIVATE_ADDRESS = 'member' + '@' + 'private.local'
PUBLIC_ADDRESS = 'contact' + '@' + 'club.local'
OTHER_ADDRESS = 'other' + '@' + 'club.local'
SOURCE = Path(__file__).resolve().parent.parent


class RepositoryIndexTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        env = os.environ.copy()
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR',
                    'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'):
            env.pop(key, None)
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        self.enterContext(mock.patch.dict(os.environ, env, clear=True))
        self.enterContext(mock.patch.object(scan, 'ROOT', self.root))
        self.git('init', '--quiet')
        self.write_static(PUBLIC_ADDRESS)
        self.write('.gitignore', 'ignored.txt\n')
        self.git('add', '--', 'src/site_static.json', '.gitignore')

    def git(self, *args, input=None):
        return subprocess.run(['git', *args], cwd=self.root, input=input,
                              capture_output=True, check=True).stdout

    def write(self, name, text, encoding='utf-8'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding=encoding)

    def write_static(self, address):
        self.write('src/site_static.json', json.dumps({
            'requests_static': {'contact_email': address}, 'social_links': {'email': ''}
        }))

    def test_staged_private_text_is_detected_after_working_file_is_cleaned_or_deleted(self):
        self.write('note.txt', PRIVATE_ADDRESS)
        self.git('add', '--', 'note.txt')
        self.write('note.txt', '修正済み')
        self.assertTrue(any('note.txt' in problem for problem in scan.check_contents(staged=True)))
        self.assertEqual(scan.check_contents(), [])
        (self.root / 'note.txt').unlink()
        self.assertTrue(any('note.txt' in problem for problem in scan.check_contents(staged=True)))

    def test_unstaged_and_untracked_text_is_checked_only_in_normal_mode(self):
        self.write('note.txt', '公開する文章')
        self.git('add', '--', 'note.txt')
        self.write('note.txt', PRIVATE_ADDRESS)
        self.write('untracked.txt', PRIVATE_ADDRESS)
        self.write('ignored.txt', PRIVATE_ADDRESS)
        self.assertEqual(scan.check_contents(staged=True), [])
        problems = scan.check_contents()
        self.assertEqual({problem.split('：')[0] for problem in problems}, {'note.txt', 'untracked.txt'})

    def test_staged_deletion_and_rename_use_the_paths_left_in_the_index(self):
        self.write('note.txt', PRIVATE_ADDRESS)
        self.git('add', '--', 'note.txt')
        self.git('rm', '--cached', '--', 'note.txt')
        self.assertEqual(scan.check_contents(staged=True), [])
        self.write('note.txt', '公開する文章')
        self.git('add', '--', 'note.txt')
        self.git('mv', '--', 'note.txt', 'renamed.xlsx')
        self.assertEqual(scan.check_contents(staged=True), ['renamed.xlsx：公開してはいけない種類のファイル'])

    def test_public_contact_is_read_from_the_same_index_as_the_checked_text(self):
        self.write('contact.txt', PUBLIC_ADDRESS)
        self.git('add', '--', 'contact.txt')
        self.write_static(OTHER_ADDRESS)
        self.assertEqual(scan.check_contents(staged=True), [])
        self.assertTrue(any('contact.txt' in problem for problem in scan.check_contents()))
        self.write('contact.txt', OTHER_ADDRESS)
        self.git('add', '--', 'contact.txt')
        self.assertTrue(any('contact.txt' in problem for problem in scan.check_contents(staged=True)))
        self.assertEqual(scan.check_contents(), [])

    def test_japanese_paths_spaces_and_windows_encodings_are_checked(self):
        for name, encoding in [('資料/確認 メモ.txt', 'utf-8'), ('wide.txt', 'utf-16'), ('sjis.txt', 'cp932')]:
            self.write(name, '連絡先 ' + PRIVATE_ADDRESS, encoding)
            self.git('add', '--', name)
            self.write(name, '修正済み')
        expected = {'資料/確認 メモ.txt', 'wide.txt', 'sjis.txt'}
        self.assertEqual({problem.split('：')[0] for problem in scan.check_contents(staged=True)}, expected)

    def test_binary_files_are_not_decoded(self):
        self.write('image.png', PRIVATE_ADDRESS)
        self.git('add', '--', 'image.png')
        self.assertEqual(scan.check_contents(staged=True), [])

    def test_git_selected_index_is_used_for_partial_commits(self):
        alternate = self.root / '.git' / 'selected-index'
        shutil.copyfile(self.root / '.git' / 'index', alternate)
        self.write('note.txt', PRIVATE_ADDRESS)
        with mock.patch.dict(os.environ, {'GIT_INDEX_FILE': str(alternate)}):
            self.git('add', '--', 'note.txt')
            self.assertTrue(any('note.txt' in problem for problem in scan.check_contents(staged=True)))
        self.assertEqual(scan.check_contents(staged=True), [])

    def test_missing_index_settings_do_not_fall_back_to_the_working_file(self):
        self.git('rm', '--cached', '--', 'src/site_static.json')
        with self.assertRaisesRegex(ValueError, 'src/site_static.json'):
            scan.check_contents(staged=True)

    def test_conflicted_index_is_rejected(self):
        object_id = self.git('rev-parse', ':src/site_static.json').strip()
        self.git('update-index', '--index-info', input=b'100644 ' + object_id + b' 1\tconflict.txt\n')
        with self.assertRaisesRegex(ValueError, '競合'):
            scan.check_contents(staged=True)

    def test_git_failure_stops_staged_check_but_normal_check_can_run_without_git(self):
        self.write('untracked.txt', PRIVATE_ADDRESS)
        with mock.patch.object(scan.subprocess, 'run', side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                scan.check_contents(staged=True)
            self.assertTrue(any('untracked.txt' in problem for problem in scan.check_contents()))

    def test_blob_read_failure_is_not_treated_as_a_successful_scan(self):
        run = subprocess.run

        def fail_cat_file(command, **kwargs):
            if command[1] == 'cat-file':
                raise subprocess.CalledProcessError(1, command)
            return run(command, **kwargs)

        with mock.patch.object(scan.subprocess, 'run', side_effect=fail_cat_file):
            with self.assertRaises(subprocess.CalledProcessError):
                scan.check_contents(staged=True)

    def test_hook_uses_staged_mode_without_running_the_fixture_tests(self):
        shell = shutil.which('sh')
        if not shell:
            self.skipTest('フックを動かす sh がありません')
        for name in ('tests/test_repository_contents.py', '.githooks/pre-commit'):
            self.write(name, (SOURCE / name).read_text(encoding='utf-8'))
        env = os.environ.copy()
        env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')

        def run_hook():
            return subprocess.run([shell, '.githooks/pre-commit'], cwd=self.root, env=env, capture_output=True)

        self.write('note.txt', PRIVATE_ADDRESS)
        self.git('add', '--', 'note.txt')
        self.write('note.txt', '修正済み')
        self.assertNotEqual(run_hook().returncode, 0)
        self.git('add', '--', 'note.txt')
        self.write('note.txt', PRIVATE_ADDRESS)
        self.assertEqual(run_hook().returncode, 0)
        self.git('rm', '--cached', '--', 'src/site_static.json')
        failed = run_hook()
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('公開前の検査に通らなかったため'.encode('utf-8'), failed.stderr)


if __name__ == '__main__':
    unittest.main()
