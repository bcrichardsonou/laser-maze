import fcntl
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('service_deploy', Path(__file__).parents[1] / 'deploy.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def test_stop_precedes_upload_and_restart_follows_success(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if 'start' in args:
                with (self.state / 'deploy.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return subprocess.CompletedProcess(args, 0, 'loaded\n')
        with patch.object(deploy.subprocess,'run',side_effect=run), patch.object(deploy.subprocess,'check_output',return_value='active\n'):
            with deploy.managed_game(self.state):
                self.assertIn('stop', calls[-1])
                with (self.state/'deploy.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertIn('start', calls[-1])

    def test_failed_upload_stays_stopped(self):
        with patch.object(deploy.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'loaded\n')) as run, patch.object(deploy.subprocess,'check_output',return_value='active\n'):
            with self.assertRaises(RuntimeError):
                with deploy.managed_game(self.state): raise RuntimeError('upload failed')
        self.assertFalse(any('start' in c.args[0] for c in run.call_args_list))

    def test_manually_stopped_service_is_not_started(self):
        with patch.object(deploy.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'loaded\n')) as run, patch.object(deploy.subprocess,'check_output',return_value='inactive\n'):
            with deploy.managed_game(self.state): pass
        self.assertFalse(any('start' in c.args[0] for c in run.call_args_list))

    def test_first_install_without_service_needs_no_sudo(self):
        with patch.object(deploy.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'not-found\n')) as run:
            with deploy.managed_game(self.state): pass
        self.assertEqual(run.call_count,1)

    def test_parallel_upload_cannot_stop_service(self):
        with (self.state/'upload.lock').open('a') as lock, patch.object(deploy.subprocess,'run') as run:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(RuntimeError):
                with deploy.managed_game(self.state): pass
            run.assert_not_called()

    def test_sync_continues_while_game_owns_controller_lock(self):
        argv=['deploy.py','--state',str(self.state),'sync']
        with (self.state/'deploy.lock').open('a') as lock, patch.object(deploy.sys,'argv',argv), patch.object(deploy,'Portal'), patch.object(deploy,'sync_reports') as sync, patch.object(deploy,'managed_game') as lifecycle:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            deploy.main()
            sync.assert_called_once();lifecycle.assert_not_called()

if __name__=='__main__': unittest.main()
