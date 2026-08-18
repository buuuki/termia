# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import signal
from collections.abc import Callable
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .debug import log_event
from .models import Server
from .terminal_processes import (
    TerminalProcess,
    capture_terminal_process,
    signal_terminal_process,
    terminal_process_is_active,
)

DESTINATION = "/tmp/.termia"


def build_scp_commands(
    server: Server,
    local_paths: list[Path],
    ssh_path: str,
    scp_path: str,
    *,
    sshpass_path: str | None = None,
    destination: str = DESTINATION,
) -> tuple[list[str], list[str]]:
    ssh_target = f"{server.user}@{server.host}"
    ssh_command = [ssh_path, "-p", str(server.port)]
    scp_command = [scp_path, "-P", str(server.port)]
    if server.public_key:
        identity_file = str(Path(server.public_key).expanduser())
        ssh_command.extend(["-i", identity_file])
        scp_command.extend(["-i", identity_file])
    if any(path.is_dir() for path in local_paths):
        scp_command.append("-r")
    ssh_command.extend([ssh_target, "mkdir", "-p", destination])
    scp_command.extend(str(path) for path in local_paths)
    scp_command.append(f"{ssh_target}:{destination}/")
    if sshpass_path is not None:
        ssh_command = [sshpass_path, "-e", *ssh_command]
        scp_command = [sshpass_path, "-e", *scp_command]
    return ssh_command, scp_command


class FileTransferController:
    def __init__(
        self,
        parent: Gtk.Window,
        translate: Callable[[str], str],
        toast_label: Gtk.Label,
        add_dialog_action_button: Callable[..., Gtk.Button],
        inspect_known_host: Callable[[str, int, Callable[[bool], None]], None],
        on_inactive: Callable[[FileTransferController], None] | None = None,
        owner_session_id: str | None = None,
    ) -> None:
        self.parent = parent
        self.t = translate
        self.toast_label = toast_label
        self.add_dialog_action_button = add_dialog_action_button
        self.inspect_known_host = inspect_known_host
        self.on_inactive = on_inactive
        self.owner_session_id = owner_session_id
        self.selection_cancellable: Gio.Cancellable | None = None
        self.active_state: dict[str, Any] | None = None
        self.inactive_notified = False
        self.cancelled = False

    def open_file_selection(self, server: Server) -> None:
        dialog = Gtk.FileDialog(title=self.t("send_files_to_server"))
        self.selection_cancellable = Gio.Cancellable()
        dialog.open_multiple(
            self.parent,
            self.selection_cancellable,
            lambda current_dialog, result: self._on_files_selected(current_dialog, result, server),
        )

    def _on_files_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, server: Server) -> None:
        try:
            model = dialog.open_multiple_finish(result)
        except GLib.Error:
            self.mark_inactive()
            return
        self.selection_cancellable = None
        if self.cancelled:
            self.mark_inactive()
            return
        if model is None:
            self.mark_inactive()
            return

        local_paths: list[Path] = []
        for index in range(model.get_n_items()):
            item = model.get_item(index)
            if item is None:
                continue
            path = item.get_path()
            if path:
                local_paths.append(Path(path).expanduser())
        if local_paths:
            self.start_upload(server, local_paths)
            return
        self.mark_inactive()

    def start_upload(self, server: Server, local_paths: list[Path]) -> None:
        ssh_path = GLib.find_program_in_path("ssh")
        scp_path = GLib.find_program_in_path("scp")
        if ssh_path is None or scp_path is None:
            self.toast_label.set_error(self.t("send_files_to_server_missing"))
            self.mark_inactive()
            return
        self.inspect_known_host(
            server.host,
            server.port,
            lambda known: self._start_upload_after_known_host_check(server, local_paths, ssh_path, scp_path, known),
        )

    def _start_upload_after_known_host_check(
        self,
        server: Server,
        local_paths: list[Path],
        ssh_path: str,
        scp_path: str,
        known_host: bool,
    ) -> None:
        if self.cancelled:
            self.mark_inactive()
            return
        if not known_host:
            self.toast_label.set_label(self.t("send_files_to_server_fingerprint"))
            self.mark_inactive()
            return

        sshpass_path = None
        if server.password:
            sshpass_path = GLib.find_program_in_path("sshpass")
            if sshpass_path is None:
                self.toast_label.set_error(self.t("sshpass_missing"))
                self.mark_inactive()
                return
        ssh_command, scp_command = build_scp_commands(
            server,
            local_paths,
            ssh_path,
            scp_path,
            sshpass_path=sshpass_path,
        )
        file_list = ", ".join(path.name for path in local_paths)
        dialog_state = self.show_transfer_dialog(server, DESTINATION, file_list)
        dialog_state["phase"] = "prepare"
        log_event(
            "scp.transfer_started",
            authentication="password" if sshpass_path else "key_or_agent",
            item_count=len(local_paths),
        )
        dialog_state["status"].set_label(self.t("send_files_to_server_prepare_remote"))
        log_event("scp.transfer_phase", phase="prepare")
        self.run_command(
            ssh_command,
            server.password if sshpass_path else "",
            dialog_state,
            lambda: self._start_copy_step(server, scp_command, dialog_state, bool(sshpass_path)),
        )
        self.toast_label.set_label(self.t("send_files_to_server_started").format(name=server.name))

    def show_transfer_dialog(self, server: Server, destination: str, file_list: str) -> dict[str, Any]:
        dialog = Gtk.Dialog(
            title=self.t("send_files_to_server_title").format(name=server.name),
            transient_for=self.parent,
            modal=False,
        )
        dialog.set_resizable(False)
        dialog.set_default_size(460, -1)
        cancel = self.add_dialog_action_button(dialog, self.t("cancel"), Gtk.ResponseType.CANCEL, last=True)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(12)
        target = Gtk.Label(label=self.t("send_files_to_server_running").format(name=server.name, destination=destination))
        target.set_xalign(0)
        target.set_wrap(True)
        files = Gtk.Label(label=file_list)
        files.set_xalign(0)
        files.set_wrap(True)
        files.add_css_class("dim-label")
        progress = Gtk.ProgressBar()
        progress.pulse()
        status = Gtk.Label(label="")
        status.set_xalign(0)
        status.set_wrap(True)
        status.add_css_class("dim-label")
        content.append(target)
        content.append(files)
        content.append(progress)
        content.append(status)

        state: dict[str, Any] = {
            "dialog": dialog,
            "cancel": cancel,
            "progress": progress,
            "status": status,
            "cancellable": Gio.Cancellable(),
            "process": None,
            "process_identity": None,
            "force_termination_id": None,
            "pulse_id": None,
            "completed": False,
            "cancelled": False,
            "dialog_destroyed": False,
            "phase": "select",
        }
        self.active_state = state
        state["pulse_id"] = GLib.timeout_add(120, self.pulse_progress, state)
        dialog.connect("response", self.on_dialog_response, state)
        dialog.present()
        return state

    def pulse_progress(self, state: dict[str, Any]) -> bool:
        progress = state.get("progress")
        if isinstance(progress, Gtk.ProgressBar):
            progress.pulse()
        return GLib.SOURCE_CONTINUE

    def on_dialog_response(self, dialog: Gtk.Dialog, response: Gtk.ResponseType, state: dict[str, Any]) -> None:
        if state.get("completed"):
            self.cleanup_dialog(state)
            self.destroy_transfer_dialog(state)
            return
        self.cancel_transfer(state)
        if response != Gtk.ResponseType.CANCEL:
            self.destroy_transfer_dialog(state)

    def cancel_transfer(self, state: dict[str, Any]) -> None:
        if state.get("completed"):
            return
        state["cancelled"] = True
        self.cancelled = True
        cancellable = state.get("cancellable")
        if isinstance(cancellable, Gio.Cancellable):
            cancellable.cancel()
        self.request_process_termination(state)
        self.finish_dialog(
            state,
            self.t("send_files_to_server_cancelled"),
            outcome="cancelled",
        )

    def cancel_active_transfer(self, *, close_dialog: bool = False) -> None:
        self.cancelled = True
        if self.selection_cancellable is not None:
            self.selection_cancellable.cancel()
            self.selection_cancellable = None
        state = self.active_state
        if state is not None:
            self.cancel_transfer(state)
            if close_dialog:
                self.destroy_transfer_dialog(state)
            return
        self.mark_inactive()

    @staticmethod
    def destroy_transfer_dialog(state: dict[str, Any]) -> None:
        if state.get("dialog_destroyed"):
            return
        state["dialog_destroyed"] = True
        dialog = state.get("dialog")
        destroy = getattr(dialog, "destroy", None)
        if callable(destroy):
            destroy()

    def mark_inactive(self) -> None:
        if self.inactive_notified:
            return
        self.inactive_notified = True
        if self.on_inactive is not None:
            self.on_inactive(self)

    def _start_copy_step(
        self,
        server: Server,
        scp_command: list[str],
        state: dict[str, Any],
        use_sshpass: bool,
    ) -> None:
        if state.get("completed"):
            return
        state["phase"] = "copy"
        state["status"].set_label(self.t("send_files_to_server_copying"))
        log_event("scp.transfer_phase", phase="copy")
        self.run_command(
            scp_command,
            server.password if use_sshpass else "",
            state,
            lambda: self.finish_dialog(
                state,
                self.t("send_files_to_server_finished").format(name=server.name),
                outcome="success",
            ),
        )

    def run_command(self, command: list[str], password: str, state: dict[str, Any], on_success: Callable[[], None]) -> None:
        if state.get("completed"):
            return
        setsid_path = GLib.find_program_in_path("setsid")
        if setsid_path is None:
            self.finish_dialog(
                state,
                self.t("send_files_to_server_missing"),
                outcome="failed",
            )
            return
        try:
            launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
            if password:
                launcher.setenv("SSHPASS", password, True)
            process = launcher.spawnv([setsid_path, "--wait", *command])
        except GLib.Error as exc:
            self.finish_dialog(
                state,
                self.t("send_files_to_server_start_failed").format(error=exc.message),
                outcome="failed",
            )
            return
        state["process"] = process
        state["process_identity"] = self.capture_subprocess_identity(process)
        log_event("scp.process_started", phase=state.get("phase"))
        process.communicate_utf8_async(
            None,
            state["cancellable"],
            lambda current_process, result: self.on_command_finished(current_process, result, state, on_success),
        )

    def on_command_finished(
        self,
        process: Gio.Subprocess,
        result: Gio.AsyncResult,
        state: dict[str, Any],
        on_success: Callable[[], None],
    ) -> None:
        try:
            _ok, stdout, stderr = process.communicate_utf8_finish(result)
        except GLib.Error:
            if state.get("completed") or state["cancellable"].is_cancelled():
                return
            self.clear_process_state(state, process)
            self.finish_dialog(
                state,
                self.t("send_files_to_server_failed_generic"),
                outcome="failed",
            )
            return
        self.clear_process_state(state, process)
        if state.get("completed"):
            return
        if not process.get_successful():
            detail = self.last_output_line(stdout, stderr)
            self.finish_dialog(
                state,
                self.t("send_files_to_server_failed_detail").format(error=detail),
                outcome="failed",
            )
            return
        on_success()

    @staticmethod
    def capture_subprocess_identity(process: Gio.Subprocess) -> TerminalProcess | None:
        identifier = process.get_identifier()
        if identifier is None:
            return None
        try:
            return capture_terminal_process(int(identifier))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def refresh_process_identity(process: TerminalProcess) -> TerminalProcess:
        current = capture_terminal_process(process.pid)
        if process.start_time is not None and current.start_time != process.start_time:
            return process
        return current

    def request_process_termination(self, state: dict[str, Any]) -> None:
        process = state.get("process")
        identity = state.get("process_identity")
        accepted = False
        termination_signal = "SIGTERM"
        if isinstance(identity, TerminalProcess):
            identity = self.refresh_process_identity(identity)
            state["process_identity"] = identity
            accepted = signal_terminal_process(identity, signal.SIGTERM)
        if not accepted and isinstance(process, Gio.Subprocess):
            process.force_exit()
            accepted = True
            termination_signal = "force_exit"
        log_event(
            "scp.process_termination_requested",
            accepted=accepted,
            phase=state.get("phase"),
            signal=termination_signal,
        )
        if isinstance(identity, TerminalProcess) and accepted:
            state["force_termination_id"] = GLib.timeout_add(
                500,
                self.force_process_termination,
                state,
                identity,
            )

    def force_process_termination(
        self,
        state: dict[str, Any],
        identity: TerminalProcess,
    ) -> bool:
        if state.get("force_termination_id") is not None:
            state["force_termination_id"] = None
        identity = self.refresh_process_identity(identity)
        if not terminal_process_is_active(identity):
            log_event("scp.process_force_termination_skipped", reason="already_exited")
            return GLib.SOURCE_REMOVE
        accepted = signal_terminal_process(identity, signal.SIGKILL)
        log_event(
            "scp.process_termination_requested",
            accepted=accepted,
            phase=state.get("phase"),
            signal="SIGKILL",
        )
        return GLib.SOURCE_REMOVE

    @staticmethod
    def clear_process_state(state: dict[str, Any], process: Gio.Subprocess) -> None:
        if state.get("process") is process:
            state["process"] = None
            state["process_identity"] = None

    def last_output_line(self, stdout: str | None, stderr: str | None) -> str:
        lines = [line.strip() for line in f"{stdout or ''}\n{stderr or ''}".splitlines() if line.strip()]
        return lines[-1] if lines else self.t("send_files_to_server_failed_generic")

    def finish_dialog(self, state: dict[str, Any], message: str, *, outcome: str) -> None:
        if state.get("completed"):
            return
        self.cleanup_dialog(state)
        state["completed"] = True
        state["status"].set_label(message)
        state["progress"].set_fraction(1.0 if outcome == "success" else 0.0)
        state["cancel"].set_label(self.t("close"))
        if outcome == "failed":
            self.toast_label.set_error(message)
        elif outcome == "cancelled":
            self.toast_label.set_label(message)
        else:
            self.toast_label.set_success(message)
        log_event("scp.transfer_finished", outcome=outcome, phase=state.get("phase"))
        self.active_state = None
        self.mark_inactive()

    def cleanup_dialog(self, state: dict[str, Any]) -> None:
        pulse_id = state.get("pulse_id")
        if pulse_id is not None:
            GLib.source_remove(pulse_id)
            state["pulse_id"] = None
