"""検査の失敗ログに、見つかった値そのものを再掲しないことを確かめる。"""
import io
import os
import shutil
import subprocess
import sys
import unittest

import test_repository_contents as scan
import test_repository_index as index_tests


# 判定対象の形だけを作る。実際のアドレス、公開先、鍵は使わない
WEB_APP = 'https:' + '//' + 'script.google.com' + '/macros/s/' + 'EXAMPLE-ONLY/exec'
KEY_MARKER = '-----BEGIN ' + 'FAKE PRIVATE KEY-----'
KEY_BODY = 'EXAMPLE-ONLY-KEY-CONTENT'


class RepositoryOutputTest(unittest.TestCase):
    def setUp(self):
        self.repo = index_tests.RepositoryIndexTest()
        self.addCleanup(self.repo.doCleanups)
        self.repo.setUp()
        content = '\n'.join([index_tests.PRIVATE_ADDRESS, index_tests.PRIVATE_ADDRESS,
                             index_tests.OTHER_ADDRESS, WEB_APP, KEY_MARKER, KEY_BODY])
        self.repo.write('note.txt', content)
        self.repo.git('add', '--', 'note.txt')

    def assert_hidden(self, output):
        for value in [index_tests.PRIVATE_ADDRESS, index_tests.OTHER_ADDRESS, WEB_APP, KEY_MARKER, KEY_BODY]:
            self.assertNotIn(value.encode('ascii'), output)
        self.assertIn(b'note.txt', output)
        for label in ['メールアドレス', '管理画面の URL', '秘密鍵']:
            self.assertTrue(any(label.encode(encoding) in output for encoding in ['utf-8', 'cp932']), label)

    def test_findings_contain_only_the_file_and_each_information_type_once(self):
        expected = ['note.txt：メールアドレス', 'note.txt：管理画面の URL', 'note.txt：秘密鍵']
        for staged in [False, True]:
            self.assertEqual(scan.check_contents(staged=staged), expected)

    def test_unittest_failure_and_its_list_diff_do_not_repeat_values(self):
        stream = io.StringIO()
        case = scan.RepositoryContentsTest('test_no_private_information_is_committed')
        result = unittest.TextTestRunner(stream=stream).run(unittest.TestSuite([case]))
        self.assertFalse(result.wasSuccessful())
        self.assert_hidden(stream.getvalue().encode('utf-8'))

    def test_staged_command_and_real_hook_reject_without_repeating_values(self):
        for name in ['tests/test_repository_contents.py', '.githooks/pre-commit']:
            self.repo.write(name, (index_tests.SOURCE / name).read_text(encoding='utf-8'))
        commands = [[sys.executable, 'tests/test_repository_contents.py', '--staged']]
        shell = shutil.which('sh')
        if shell:
            commands.append([shell, '.githooks/pre-commit'])
        env = os.environ.copy()
        env['PATH'] = os.path.dirname(sys.executable) + os.pathsep + env.get('PATH', '')
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run(command, cwd=self.repo.root, env=env, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assert_hidden(result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
