import os
import unittest
from types import SimpleNamespace
from unittest import mock

from journey_helper import winapi


def processes(*items):
    return [SimpleNamespace(info={'pid': pid, 'name': name}) for pid, name in items]


class FindGamePidsTests(unittest.TestCase):
    def find(self, *items):
        with mock.patch('psutil.process_iter', return_value=processes(*items)):
            return winapi.find_game_pids(['StarSavior.exe'], 'starsavior')

    def test_finds_game(self):
        self.assertEqual(self.find((10, 'StarSavior.exe'), (11, 'explorer.exe')), [10])

    def test_excludes_the_helper_itself(self):
        # 助手的名稱也含 starsavior：先開助手時曾把自己的小窗當成遊戲視窗
        pids = self.find((10, 'StarSavior.exe'), (20, 'StarSaviorJourneyHelper.exe'),
                         (21, 'StarSaviorJourneyHelper (1).exe'))
        self.assertEqual(pids, [10])

    def test_excludes_own_process_whatever_its_name(self):
        pids = self.find((os.getpid(), 'StarSavior.exe'), (10, 'StarSavior.exe'))
        self.assertEqual(pids, [10])

    def test_keyword_still_matches_other_names(self):
        self.assertEqual(self.find((10, 'Star_Savior-Launcher.exe')), [10])


if __name__ == '__main__':
    unittest.main()
