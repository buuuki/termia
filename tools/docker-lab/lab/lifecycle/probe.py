import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path.cwd()))
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import GLib

from termia.app import TermiaApp, TermiaWindow
from termia.file_transfer import FileTransferController, build_scp_commands
from termia.models import Server
from termia.session_commands import build_ssh_command
from termia.stores import ConnectionStore
from termia.terminal_processes import process_session_members, process_start_time

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get('TERMIA_LAB_PORT', '32768'))
HOST = os.environ.get('TERMIA_LAB_HOST', '127.0.0.1')
def synthetic_password():
    return Path('/opt/lab-password').read_text().strip()


def drain():
    context = GLib.MainContext.default()
    for _ in range(100):
        if not context.pending():
            break
        context.iteration(False)


def status():
    result = json.loads(Path(os.environ.get('TERMIA_LAB_STATUS', str(ROOT/'observations/status.json'))).read_text())
    assert time.time() - result['time'] < 4, 'Container monitor is stale'
    return result


def isolated_command(server, ssh_path, **kwargs):
    command = build_ssh_command(server, ssh_path, **kwargs)
    index = command.index(ssh_path) + 1
    command[index:index] = ['-F', '/dev/null', '-o', 'UserKnownHostsFile='+str(Path.home()/'.ssh/known_hosts'), '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes', '-o', 'ConnectTimeout=5']
    return command


class DockerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        trust = Path.home()/'.ssh/known_hosts'
        trust.parent.mkdir(mode=0o700, exist_ok=True)
        scan = subprocess.run(['ssh-keyscan', '-T', '5', '-p', str(PORT), HOST], capture_output=True, text=True, check=True)
        assert scan.stdout.strip()
        trust.write_text(scan.stdout)
        cls.app = TermiaApp()
        cls.app.register(None)

    def wait(self, predicate, description, timeout=12):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            drain()
            if predicate():
                return
            time.sleep(.02)
        self.fail(description+'; container='+json.dumps(status()))

    def server(self, auth, token):
        return Server(token, token, HOST, 'lab', PORT,
                      password=synthetic_password() if auth == 'password' else '',
                      public_key=os.environ.get('TERMIA_LAB_KEY', str(ROOT/'synthetic')) if auth == 'key' else '',
                      command_on_start='exec python3 /opt/remote_job.py '+token)

    def window(self, root, enabled):
        store = ConnectionStore(root/'connections.json', root/'settings.json', root/'statistics.json', root/'lock', root/'history')
        store.data.app.open_local_terminal_on_startup = False
        store.data.app.confirm_disconnect = False
        store.data.app.confirm_close_app = False
        store.data.app.sftp_enabled = enabled
        store.data.app.statistics_enabled = enabled
        with patch('termia.app.ConnectionStore', return_value=store):
            window = TermiaWindow(self.app)
        window.present()
        return window, store

    def cleanup(self, window, store):
        window.shutdown_in_progress = True
        window.cancel_file_transfers(close_dialog=True)
        window.prepare_terminal_sessions_for_shutdown()
        window.terminate_open_terminal_processes(force=True)
        window.snippet_dialogs.shutdown()
        window.notes_dialogs.shutdown()
        for session in window.session_registry.sessions():
            if session.detached_window:
                session.detached_window.destroy()
        window.destroy()
        store.close()
        drain()

    def test_authentication_smoke(self):
        def exercise_case(auth):
            with self.subTest(auth=auth), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                window, store = self.window(root, True)
                try:
                    server = self.server(auth, uuid.uuid4().hex)
                    store.data.servers.append(server)
                    with patch('termia.terminal_sessions.build_ssh_command', side_effect=isolated_command):
                        session = window.open_terminal_tab(server)
                        self.wait(lambda: server.id in status()['jobs'], 'SSH authentication failed')
                    window.sftp_tool.browse(Mock(), session, server)
                    self.wait(lambda: bool(window.file_transfer_controllers), 'SFTP not registered')
                    sftp = next(iter(window.file_transfer_controllers))
                    self.wait(lambda: sftp.connection_ready and not sftp.service.busy, 'SFTP authentication failed')
                    source, target = root / 'source', root / 'download'
                    source.write_bytes(b'Synthetic laboratory transfer\n')
                    done = []
                    remote = '/home/lab/smoke-' + server.id
                    sftp.run(lambda backend, report: backend.upload(source, remote, report),
                             lambda value: done.append(value), transfer=True)
                    self.wait(lambda: bool(done), 'SFTP upload failed')
                    done.clear()
                    sftp.run(lambda backend, report: backend.download(remote, target, report),
                             lambda value: done.append(value), transfer=True)
                    self.wait(lambda: bool(done), 'SFTP download failed')
                    self.assertEqual(target.read_bytes(), source.read_bytes())
                    window.close_tab(session.id, session.page, disconnect=True)
                    self.wait(lambda: sftp.service.stopped, 'SFTP workers did not stop')
                    self.wait(lambda: status()['established'] == 0 and not status()['processes'],
                              'Smoke test left remote resources')
                finally:
                    self.cleanup(window, store)

        for auth in ('password', 'key'):
            exercise_case(auth)

    def test_ssh_lifecycle(self):
        with patch('termia.terminal_sessions.build_ssh_command', side_effect=isolated_command):
            def exercise_case(auth, enabled, action):
                with self.subTest(auth=auth, optional=enabled, action=action), tempfile.TemporaryDirectory(prefix='termia-docker-lifecycle-') as temporary:
                    window, store = self.window(Path(temporary), enabled)
                    owned = {}
                    try:
                        self.wait(lambda: status()['established'] == 0 and not status()['processes'], 'Previous case left remote resources')
                        tokens = [uuid.uuid4().hex for _ in range(3)]
                        servers = [self.server(auth, token) for token in tokens]
                        store.data.servers.extend(servers)
                        first = window.open_terminal_tab(servers[0])
                        second = window.open_terminal_tab(servers[1])
                        self.wait(lambda: all(t in status()['jobs'] for t in tokens[:2]), 'SSH sessions did not execute the synthetic command')
                        terminal = window.split_terminal_pane(first, first.terminal, 'horizontal')
                        window.start_ssh_split_terminal(first, terminal, servers[2], announce=False)
                        self.wait(lambda: tokens[2] in status()['jobs'], 'SSH split did not connect')
                        processes = [first.child_process, second.child_process, window.pane_state(first, terminal).child_process]
                        for process in processes:
                            self.assertIsNotNone(process)
                            for member in process_session_members(process.session_id):
                                owned[member.pid] = member.start_time
                        sftp = None
                        if enabled:
                            window.sftp_tool.browse(Mock(), first, servers[0])
                            self.wait(lambda: bool(window.file_transfer_controllers), 'SFTP window was not registered')
                            sftp = next(iter(window.file_transfer_controllers))
                            self.wait(lambda: sftp.connection_ready and not sftp.service.busy, 'SFTP did not connect')
                        self.wait(lambda: status()['established'] == (4 if enabled else 3), 'Unexpected SSH/SFTP connection count')
                        remote_pids = {token: status()['jobs'][token] for token in tokens}
                        def remote_gone(token):
                            return not any(p['pid'] in remote_pids[token] for p in status()['processes'])
                        if action == 'disconnect-pane':
                            window.disconnect_pane(first, first.terminal)
                            self.wait(lambda: remote_gone(tokens[0]), 'Disconnected pane retained remote processes')
                            self.assertFalse(remote_gone(tokens[1]))
                            self.assertFalse(remote_gone(tokens[2]))
                            window.close_tab(first.id, first.page, disconnect=True)
                        elif action == 'disconnect-session':
                            window.disconnect_session(first)
                        elif action == 'close-tab':
                            window.close_tab(first.id, first.page, disconnect=True)
                        elif action == 'close-detached':
                            window.detach_tab(Mock(), first)
                            first.detached_window.close()
                        else:
                            with patch('termia.app.log_event') as events:
                                window.close()
                                self.wait(lambda: any(c.args == ('application.shutdown_finished',) for c in events.call_args_list), 'Application shutdown did not finish')
                                events.assert_any_call('application.shutdown_finished', cleanup='stopped')
                                self.assertFalse(any(c.args == ('application.shutdown_cleanup_unverified',) for c in events.call_args_list))
                        self.wait(lambda: remote_gone(tokens[0]) and remote_gone(tokens[2]), 'Closed session retained remote processes')
                        if action != 'close-app':
                            self.assertFalse(remote_gone(tokens[1]), 'Unrelated SSH tab was terminated')
                            window.close_tab(second.id, second.page, disconnect=True)
                            if window.session_registry.contains(first.id):
                                window.close_tab(first.id, first.page, disconnect=True)
                        if sftp:
                            self.wait(lambda: sftp.service.stopped, 'SFTP service did not stop')
                        self.wait(lambda: all(process_start_time(pid) != birth for pid,birth in owned.items()), 'Local VTE/SSH process still exists, possibly zombie')
                        self.wait(lambda: status()['established'] == 0 and not status()['processes'], 'Remote user processes, zombies or established sockets remain')
                        print(f'PASS SSH auth={auth} optional={enabled} action={action}: local identities gone, remote jobs gone, 0 connections/zombies', flush=True)
                    finally:
                        self.cleanup(window, store)

            for auth in ('password', 'key'):
                for enabled in (False, True):
                    for action in ('disconnect-pane', 'disconnect-session', 'close-tab', 'close-detached', 'close-app'):
                        exercise_case(auth, enabled, action)

    def test_scp_active_transfer_cleanup(self):
        def exercise_case(auth, action):
            with self.subTest(auth=auth, action=action), tempfile.TemporaryDirectory(prefix='termia-docker-scp-') as temporary:
                root = Path(temporary)
                window, store = self.window(root, True)
                controller = None
                try:
                    self.wait(lambda: status()['established'] == 0 and not status()['processes'], 'Previous case left remote resources')
                    server = self.server(auth, uuid.uuid4().hex)
                    source = root/('synthetic-'+server.id)
                    with source.open('wb') as stream:
                        stream.truncate(32*1024*1024)
                    controller = FileTransferController(window, window.t, window.toast_label, window.add_dialog_action_button, Mock(), window.unregister_file_transfer)
                    window.register_file_transfer(controller)
                    state = controller.show_transfer_dialog(server, '/home/lab', source.name)
                    controller.active_state = state
                    state['phase'] = 'copy'
                    _, command = build_scp_commands(server, [source], '/usr/bin/ssh', '/usr/bin/scp', sshpass_path='/usr/bin/sshpass' if auth == 'password' else None, destination='/home/lab')
                    index = command.index('/usr/bin/scp')+1
                    command[index:index] = ['-l', '512', '-F', '/dev/null', '-o', 'UserKnownHostsFile='+str(Path.home()/'.ssh/known_hosts'), '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes', '-o', 'ConnectTimeout=5']
                    success = Mock()
                    controller.run_command(command, synthetic_password() if auth == 'password' else '', state, success)
                    self.wait(lambda: status()['established'] == 1 and any('sftp-server' in p['args'] for p in status()['processes']), 'SCP did not begin its real transfer')
                    self.assertFalse(state.get('completed'))
                    identity = controller.refresh_process_identity(state['process_identity'])
                    owned = {p.pid:p.start_time for p in process_session_members(identity.session_id)}
                    self.assertTrue(owned)
                    if action == 'cancel':
                        controller.cancel_active_transfer(close_dialog=True)
                    else:
                        with patch('termia.app.log_event') as events:
                            window.close()
                            self.wait(lambda: any(c.args == ('application.shutdown_finished',) for c in events.call_args_list), 'Application did not finish SCP cleanup')
                            events.assert_any_call('application.shutdown_finished', cleanup='stopped')
                    self.wait(lambda: controller.shutdown_cleanup_state() == 'stopped', 'SCP cleanup did not finish')
                    self.wait(lambda: all(process_start_time(pid) != birth for pid,birth in owned.items()), 'SCP local process or zombie remains')
                    self.wait(lambda: status()['established'] == 0 and not status()['processes'], 'SCP remote process/socket/zombie remains')
                    success.assert_not_called()
                    print(f'PASS SCP auth={auth} action={action}: active transfer cancelled, local identities gone, 0 remote connections/zombies', flush=True)
                finally:
                    if controller:
                        controller.cancel_active_transfer(close_dialog=True)
                    self.cleanup(window, store)

        for auth in ('password', 'key'):
            for action in ('cancel', 'close-app'):
                exercise_case(auth, action)

    def test_sftp_active_transfer_cleanup(self):
        def exercise_case(auth, action):
            with self.subTest(auth=auth, action=action), tempfile.TemporaryDirectory(prefix='termia-docker-sftp-') as temporary:
                root = Path(temporary)
                window, store = self.window(root, True)
                try:
                    self.wait(lambda: status()['established'] == 0 and not status()['processes'], 'Previous case left remote resources')
                    server = self.server(auth, uuid.uuid4().hex)
                    window.sftp_tool.browse(Mock(), None, server)
                    self.wait(lambda: bool(window.file_transfer_controllers), 'SFTP not registered')
                    sftp = next(iter(window.file_transfer_controllers))
                    self.wait(lambda: sftp.connection_ready and not sftp.service.busy, 'SFTP not ready')
                    old_service = sftp.service
                    transport = old_service.backend.client.get_transport()
                    source = root/'synthetic.bin'
                    with source.open('wb') as stream:
                        stream.truncate(32*1024*1024)
                    started = Event()
                    def upload(backend, report):
                        def progress(*args, **kwargs):
                            started.set()
                            time.sleep(.02)
                            report(*args, **kwargs)
                        return backend.upload(source, '/home/lab/'+server.id, progress)
                    sftp.run(upload, transfer=True)
                    self.wait(started.is_set, 'Real SFTP upload did not start')
                    self.assertTrue(old_service.busy)
                    if action == 'cancel-reconnect':
                        sftp.cancel()
                        self.wait(lambda: old_service.stopped, 'Cancelled transfer workers remain')
                        self.wait(lambda: status()['established'] == 0 and not status()['processes'], 'Cancelled transport remains')
                        sftp.connect_backend()
                        self.wait(lambda: sftp.service is not old_service and sftp.connection_ready and not sftp.service.busy, 'Reconnect did not create a working new service')
                        sftp.close()
                    elif action == 'disconnect':
                        sftp.disconnect()
                    elif action == 'close-window':
                        sftp.close()
                    else:
                        with patch('termia.app.log_event') as events:
                            window.close()
                            self.wait(lambda: any(c.args == ('application.shutdown_finished',) for c in events.call_args_list), 'Application did not finish active-transfer cleanup')
                            events.assert_any_call('application.shutdown_finished', cleanup='stopped')
                    self.wait(lambda: sftp.service.stopped and old_service.stopped, 'SFTP workers remain')
                    self.wait(lambda: not transport.is_alive() and not transport.is_active(), 'Paramiko transport thread remains')
                    self.wait(lambda: status()['established'] == 0 and not status()['processes'], 'Remote SFTP process/socket/zombie remains')
                    self.assertEqual(sftp.shutdown_cleanup_state(), 'stopped')
                    print(f'PASS SFTP auth={auth} action={action}: real active upload stopped, transport/worker gone, 0 remote connections/zombies', flush=True)
                finally:
                    self.cleanup(window, store)

        for auth in ('password', 'key'):
            for action in ('cancel-reconnect', 'disconnect', 'close-window', 'close-app'):
                exercise_case(auth, action)


if __name__ == '__main__':
    unittest.main(failfast=True)
