import subprocess
import unittest
from subprocess import Popen

from mock import Mock, patch

import om_manager
from settings import Settings


class TestOmManager(unittest.TestCase):
    def setUp(self):
        self.settings = Mock(Settings)
        self.settings.opsman_url = 'https://cf.example.com'
        self.settings.opsman_user = 'admin'
        self.settings.opsman_password = 'monkey-123'

    def to_bytes(self, str: str):
        return bytearray(str, "utf-8")

    @patch('subprocess.Popen')
    def test_calls_auth(self, mock_popen):
        p = Mock(Popen)
        mock_popen.return_value = p
        p.returncode = 0
        p.communicate.return_value = self.to_bytes("out: foo"), self.to_bytes("error: bar")
        om_manager.config_opsman_auth(self.settings)
        mock_popen.assert_called_with(
            "om -k --target https://cf.example.com configure-authentication --username admin --password monkey-123 --decryption-passphrase monkey-123",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )

    @patch('subprocess.Popen')
    @patch('builtins.print')
    def test_prints_error(self, mock_print, mock_popen):
        p = Mock(Popen)
        mock_popen.return_value = p
        p.returncode = 1
        p.communicate.return_value = self.to_bytes("out: foo"), self.to_bytes("error: bar")

        om_manager.config_opsman_auth(self.settings)

        self.assertEqual(mock_print.call_count, 2)
        mock_print.assert_called_with("error: bar")

    @patch('subprocess.Popen')
    @patch('time.sleep')
    @patch('builtins.print')
    def test_retries_recoverable(self, mock_print, mock_sleep, mock_popen):
        recoverable_errors = ["out: i/o timeout", "connection refused"]
        p = Mock(Popen)
        mock_popen.return_value = p
        p.returncode = 1
        for recoverable_error in recoverable_errors:
            mock_popen.reset_mock()
            p.communicate.return_value = self.to_bytes(recoverable_error), self.to_bytes("error: bar")
            om_manager.config_opsman_auth(self.settings)

            self.assertEqual(mock_popen.call_count, 6)

    @patch('subprocess.Popen')
    @patch('time.sleep')
    @patch('builtins.print')
    def test_progressive_backoff(self, mock_print, mock_sleep, mock_popen):
        p = Mock(Popen)
        mock_popen.return_value = p
        p.returncode = 1
        mock_popen.reset_mock()
        p.communicate.return_value = self.to_bytes("out: i/o timeout"), self.to_bytes("error: bar")
        om_manager.config_opsman_auth(self.settings)

        self.assertEqual(mock_sleep.call_count, 5)
        self.assertEqual(mock_sleep.call_args_list[0][0][0], 0)
        self.assertEqual(mock_sleep.call_args_list[1][0][0], 1)
        self.assertEqual(mock_sleep.call_args_list[2][0][0], 8)
        self.assertEqual(mock_sleep.call_args_list[3][0][0], 27)
        self.assertEqual(mock_sleep.call_args_list[4][0][0], 64)

    @patch('subprocess.Popen')
    @patch('time.sleep')
    @patch('builtins.print')
    def test_fails_non_recoverable(self, mock_print, mock_sleep, mock_popen):
        p = Mock(Popen)
        mock_popen.return_value = p
        p.returncode = 1
        mock_popen.reset_mock()
        p.communicate.return_value = self.to_bytes("out: no such host"), self.to_bytes("error: bar")
        returncode = om_manager.config_opsman_auth(self.settings)

        self.assertEqual(mock_popen.call_count, 1)
        self.assertEqual(returncode, 1)
