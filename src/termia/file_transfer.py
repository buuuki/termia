# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .models import Server

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
        has_known_host_key: Callable[[str, int], bool],
    ) -> None:
        self.parent = parent
        self.t = translate
        self.toast_label = toast_label
        self.add_dialog_action_button = add_dialog_action_button
        self.has_known_host_key = has_known_host_key

    def open_file_selection(self, server: Server) -> None:
        dialog = Gtk.FileDialog(title=self.t("send_files_to_server"))
        dialog.open_multiple(
            self.parent,
            None,
            lambda current_dialog, result: self._on_files_selected(current_dialog, result, server),
        )

    def _on_files_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, server: Server) -> None:
        try:
            model = dialog.open_multiple_finish(result)
        except GLib.Error:
            return
        if model is None:
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

    def start_upload(self, server: Server, local_paths: list[Path]) -> None:
        ssh_path = GLib.find_program_in_path("ssh")
        scp_path = GLib.find_program_in_path("scp")
        if ssh_path is None or scp_path is None:
            self.toast_label.set_label(self.t("send_files_to_server_missing"))
            return
        if not self.has_known_host_key(server.host, server.port):
            self.toast_label.set_label(self.t("send_files_to_server_fingerprint"))
            return

        sshpass_path = None
        if server.password:
            sshpass_path = GLib.find_program_in_path("sshpass")
            if sshpass_path is None:
                self.toast_label.set_label(self.t("sshpass_missing"))
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
        dialog_state["status"].set_label(self.t("send_files_to_server_prepare_remote"))
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
            "pulse_id": None,
            "completed": False,
        }
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
            dialog.destroy()
            return
        if response == Gtk.ResponseType.CANCEL:
            cancellable = state.get("cancellable")
            if isinstance(cancellable, Gio.Cancellable):
                cancellable.cancel()
            process = state.get("process")
            if isinstance(process, Gio.Subprocess):
                process.force_exit()
            self.finish_dialog(state, self.t("send_files_to_server_cancelled"), failed=True)
            return
        self.cleanup_dialog(state)
        dialog.destroy()

    def _start_copy_step(
        self,
        server: Server,
        scp_command: list[str],
        state: dict[str, Any],
        use_sshpass: bool,
    ) -> None:
        state["status"].set_label(self.t("send_files_to_server_copying"))
        self.run_command(
            scp_command,
            server.password if use_sshpass else "",
            state,
            lambda: self.finish_dialog(
                state,
                self.t("send_files_to_server_finished").format(name=server.name),
            ),
        )

    def run_command(self, command: list[str], password: str, state: dict[str, Any], on_success: Callable[[], None]) -> None:
        try:
            launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
            if password:
                launcher.setenv("SSHPASS", password, True)
            process = launcher.spawnv(command)
        except GLib.Error as exc:
            self.finish_dialog(
                state,
                self.t("send_files_to_server_start_failed").format(error=exc.message),
                failed=True,
            )
            return
        state["process"] = process
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
            if state["cancellable"].is_cancelled():
                return
            self.finish_dialog(state, self.t("send_files_to_server_failed_generic"), failed=True)
            return
        if not process.get_successful():
            detail = self.last_output_line(stdout, stderr)
            self.finish_dialog(
                state,
                self.t("send_files_to_server_failed_detail").format(error=detail),
                failed=True,
            )
            return
        state["process"] = None
        on_success()

    def last_output_line(self, stdout: str | None, stderr: str | None) -> str:
        lines = [line.strip() for line in f"{stdout or ''}\n{stderr or ''}".splitlines() if line.strip()]
        return lines[-1] if lines else self.t("send_files_to_server_failed_generic")

    def finish_dialog(self, state: dict[str, Any], message: str, failed: bool = False) -> None:
        self.cleanup_dialog(state)
        state["completed"] = True
        state["status"].set_label(message)
        state["progress"].set_fraction(0.0 if failed else 1.0)
        state["cancel"].set_label(self.t("close"))
        self.toast_label.set_label(message)

    def cleanup_dialog(self, state: dict[str, Any]) -> None:
        pulse_id = state.get("pulse_id")
        if pulse_id is not None:
            GLib.source_remove(pulse_id)
            state["pulse_id"] = None
        state["process"] = None
