# SPDX-License-Identifier: GPL-3.0-or-later
"""Host-owned connection state for one SFTP explorer."""
from collections.abc import Callable
from dataclasses import dataclass, replace

from .known_hosts import ScannedHostKey, append_scanned_host_key
from .sftp_service import Endpoint, SFTPService, UnknownHost


@dataclass(frozen=True)
class ExplorerConnection:
    address: str
    create_service: Callable
    accept_host: Callable
    use_password: Callable[[str], None]
    clear_password: Callable[[], None]
    failure_details: Callable


class SFTPConnection:
    def __init__(self, endpoint: Endpoint, backend_factory=None):
        self._endpoint = endpoint
        self.backend_factory = backend_factory

    @property
    def address(self) -> str:
        return f"{self._endpoint.host}:{self._endpoint.port}"

    def failure_details(self, error):
        from .sftp_backend import failure_details

        return failure_details(error)

    def create_service(self, dispatch):
        from .sftp_backend import ParamikoBackend

        factory = self.backend_factory or ParamikoBackend
        return SFTPService(factory(self._endpoint), dispatch)

    def explorer(self) -> ExplorerConnection:
        return ExplorerConnection(
            self.address, self.create_operations, self.accept_host, self.use_password,
            self.clear_password, self.failure_details,
        )

    def create_operations(self, dispatch):
        return ExplorerOperations(self.create_service(dispatch))

    def accept_host(self, error: UnknownHost) -> bool:
        key = ScannedHostKey(error.hostname, error.key_type, error.key_data, error.fingerprint)
        return append_scanned_host_key(key)

    def use_password(self, password: str) -> None:
        self._endpoint = replace(self._endpoint, password=password)

    def clear_password(self) -> None:
        self.use_password("")


class ExplorerOperations:
    """View-facing operations and status for a host-owned worker service."""

    def __init__(self, service: SFTPService):
        self._service = service
        self.connect = service.connect
        self.list_directory = service.list_directory
        self.mkdir = service.mkdir
        self.rename = service.rename
        self.delete = service.delete
        self.upload = service.upload
        self.download = service.download
        self.cancel = service.cancel
        self.close = service.close
        self.shutdown_cleanup_state = service.shutdown_cleanup_state

    @property
    def busy(self):
        return self._service.busy

    @property
    def stopped(self):
        return self._service.stopped

    @property
    def cleanup_failed(self):
        return self._service.cleanup_failed

    @property
    def is_cancelled(self):
        return self._service.cancelled.is_set()
