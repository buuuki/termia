#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: MIT
import json
import locale
import os
import signal
import subprocess
import time

import yaml
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango, Vte


APP_ID = "local.termia"
APP_DIR = Path(__file__).resolve().parent
DATA_FILE = Path(GLib.get_user_config_dir()) / "termia" / "connections.json"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
STATISTICS_FILE = STATE_DIR / "termia" / "statistics.json"
ABOUT_IMAGE = APP_DIR / "assets" / "termia-about-256.png"

DEFAULT_LS_COLORS = 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=00:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.avif=01;35:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.webp=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:*~=00;90:*#=00;90:*.bak=00;90:*.crdownload=00;90:*.dpkg-dist=00;90:*.dpkg-new=00;90:*.dpkg-old=00;90:*.dpkg-tmp=00;90:*.old=00;90:*.orig=00;90:*.part=00;90:*.rej=00;90:*.rpmnew=00;90:*.rpmorig=00;90:*.rpmsave=00;90:*.swp=00;90:*.tmp=00;90:*.ucf-dist=00;90:*.ucf-new=00;90:*.ucf-old=00;90:'
DEFAULT_ANSI_PALETTE = ['#2e3436', '#cc0000', '#4e9a06', '#c4a000', '#3465a4', '#75507b', '#06989a', '#d3d7cf', '#555753', '#ef2929', '#8ae234', '#fce94f', '#729fcf', '#ad7fa8', '#34e2e2', '#eeeeec']
TERMINAL_PALETTES = {
    "Ubuntu": ("#eeeeec", "#300a24"),
    "Polaris": ("#d8dee9", "#1f2430"),
    "Solarized": ("#839496", "#002b36"),
    "Tango": ("#eeeeec", "#2e3436"),
    "Claro": ("#2e3436", "#f6f5f4"),
}
APP_THEMES = {"system": "Sistema", "light": "Claro", "dark": "Oscuro"}
LANGUAGES = {"es": "Castellano", "ca": "Català", "en": "English"}


def detect_system_language() -> str:
    language = (locale.getlocale()[0] or os.environ.get("LANG") or "").lower()
    if language.startswith("ca"):
        return "ca"
    if language.startswith("es"):
        return "es"
    return "en"


TRANSLATIONS = {
    "es": {
        "servers": "Servidores", "new_group": "Nuevo grupo", "new_server": "Nuevo servidor",
        "terminal": "Terminal", "preferences": "Preferencias", "filter_servers": "Filtrar servidores",
        "connect": "Conectar", "edit_server": "Editar servidor", "delete_server": "Eliminar servidor", "clone_connection": "Clonar conexión",
        "edit_group": "Editar grupo", "delete_group": "Eliminar grupo", "no_group": "Sin grupo",
        "parent_group": "Grupo padre", "no_parent_group": "Sin grupo padre",
        "cancel": "Cancelar", "close": "Cerrar", "save": "Guardar", "name": "Nombre", "host": "IP o host",
        "ssh_user": "Usuario SSH", "ssh_port": "Puerto SSH", "group": "Grupo",
        "password": "Contraseña", "public_key": "Clave SSH privada",
        "ssh_fingerprint_manual": "Host nuevo: responde al fingerprint en esta terminal. Después introduce la contraseña manualmente o con Super+Shift+P.",
        "password_warning": "Aviso: la contraseña se guardará en texto plano en connections.json.",
        "theme": "Tema", "language": "Idioma", "restart_language": "El idioma se aplicará al reiniciar la aplicación.",
        "close_tab": "Cerrar pestaña", "disconnect": "Desconectar", "connecting": "Conectando",
        "close_tab_on_disconnect": "Cerrar la pestaña al desconectar una sesión",
        "confirm_disconnect": "Confirmar para desconectar", "confirm_close_app": "Confirmar para cerrar Termia",
        "sudo_password_shortcut": "Enviar contraseña con Super+Shift+P",
        "sudo_password_enter": "Enviar contraseña y pulsar Enter",
        "sudo_password_sent": "Contraseña guardada enviada a la terminal",
        "sudo_password_unavailable": "Esta terminal no tiene una contraseña guardada",
        "close_app": "Cerrar Termia", "close_app_confirm": "¿Quieres cerrar Termia?",
        "font_size": "Fuente y tamaño", "terminal_font_size_changed": "Tamaño de fuente del terminal: {size}", "foreground": "Foreground", "background": "Background", "palettes": "Paletas",
        "configuration": "Configuración", "connections_file": "Fichero de conexiones", "export_config": "Exportar configuración", "import_config": "Importar configuración",
        "summary": "{groups} grupos · {subgroups} subgrupos · {servers} servidores",
        "import_asbru": "Importar configuración de Ásbrú", "clear_config": "Eliminar toda la configuración", "configure_terminal": "Configurar terminal", "local_terminal": "Terminal local",
        "statistics": "Estadísticas", "connections": "Conexiones", "commands": "Comandos", "keystrokes": "Pulsaciones",
        "global": "Global", "current_run": "Ejecución actual", "shortest_duration": "Duración más corta", "longest_duration": "Duración más larga", "average_duration": "Duración media",
        "copy": "Copiar", "paste": "Pegar", "session_statistics": "Estadísticas de la sesión", "server_connections": "Conexiones globales a este servidor",
        "clear_confirm": "¿Quieres eliminar todos los grupos y servidores? Esta acción no se puede deshacer.", "rename_tab": "Renombrar pestaña", "duplicate_tab": "Duplicar pestaña", "detach_tab": "Mover a nueva ventana",
        "expand_all": "Expandir todos los grupos", "collapse_all": "Contraer todos los grupos",
        "help": "Ayuda", "about": "Acerca de",
        "help_title": "Ayuda de Termia",
        "help_content": (
            "Termia es un gestor de conexiones SSH con terminales embebidas.\n\n"
            "Características principales:\n"
            "- Organiza servidores en grupos y subgrupos.\n"
            "- Crea, edita, elimina y filtra conexiones SSH.\n"
            "- Abre varias conexiones al mismo servidor en pestañas independientes.\n"
            "- Abre terminales locales y permite renombrar las pestañas.\n"
            "- Muestra el estado, el PID y el tiempo de conexión de cada sesión.\n"
            "- Guarda estadísticas locales agregadas y muestra estadísticas por terminal.\n"
            "- Permite enviar opcionalmente la contraseña guardada con Super+Shift+P.\n"
            "- Configura la fuente, el tamaño y los colores del terminal.\n"
            "- Importa y exporta configuraciones, incluida la importación básica desde Ásbrú.\n\n"
            "Uso rápido:\n"
            "Utiliza los iconos del panel lateral para crear grupos o servidores. Haz doble clic "
            "sobre un servidor para conectar y utiliza el botón derecho para ver las acciones disponibles."
        ),
        "about_content": "Gestor de conexiones SSH con terminales embebidas",
    },
    "ca": {
        "servers": "Servidors", "new_group": "Nou grup", "new_server": "Nou servidor",
        "terminal": "Terminal", "preferences": "Preferències", "filter_servers": "Filtrar servidors",
        "connect": "Connectar", "edit_server": "Editar servidor", "delete_server": "Eliminar servidor", "clone_connection": "Clonar connexió",
        "edit_group": "Editar grup", "delete_group": "Eliminar grup", "no_group": "Sense grup",
        "parent_group": "Grup pare", "no_parent_group": "Sense grup pare",
        "cancel": "Cancel·lar", "close": "Tancar", "save": "Desar", "name": "Nom", "host": "IP o host",
        "ssh_user": "Usuari SSH", "ssh_port": "Port SSH", "group": "Grup",
        "password": "Contrasenya", "public_key": "Clau SSH privada",
        "ssh_fingerprint_manual": "Host nou: respon al fingerprint en aquest terminal. Després introdueix la contrasenya manualment o amb Super+Shift+P.",
        "password_warning": "Avís: la contrasenya es desarà en text pla a connections.json.",
        "theme": "Tema", "language": "Idioma", "restart_language": "L'idioma s'aplicarà en reiniciar l'aplicació.",
        "close_tab": "Tancar pestanya", "disconnect": "Desconnectar", "connecting": "Connectant",
        "close_tab_on_disconnect": "Tancar la pestanya en desconnectar una sessió",
        "confirm_disconnect": "Confirmar per desconnectar", "confirm_close_app": "Confirmar per tancar Termia",
        "sudo_password_shortcut": "Enviar contrasenya amb Super+Shift+P",
        "sudo_password_enter": "Enviar contrasenya i prémer Enter",
        "sudo_password_sent": "Contrasenya desada enviada al terminal",
        "sudo_password_unavailable": "Aquest terminal no té cap contrasenya desada",
        "close_app": "Tancar Termia", "close_app_confirm": "Vols tancar Termia?",
        "font_size": "Tipus de lletra i mida", "terminal_font_size_changed": "Mida de la lletra del terminal: {size}", "foreground": "Primer pla", "background": "Fons", "palettes": "Paletes",
        "configuration": "Configuració", "connections_file": "Fitxer de connexions", "export_config": "Exportar configuració", "import_config": "Importar configuració",
        "summary": "{groups} grups · {subgroups} subgrups · {servers} servidors",
        "import_asbru": "Importar configuració d'Ásbrú", "clear_config": "Eliminar tota la configuració", "configure_terminal": "Configurar terminal", "local_terminal": "Terminal local",
        "statistics": "Estadístiques", "connections": "Connexions", "commands": "Ordres", "keystrokes": "Pulsacions",
        "global": "Global", "current_run": "Execució actual", "shortest_duration": "Durada més curta", "longest_duration": "Durada més llarga", "average_duration": "Durada mitjana",
        "copy": "Copiar", "paste": "Enganxar", "session_statistics": "Estadístiques de la sessió", "server_connections": "Connexions globals a aquest servidor",
        "clear_confirm": "Vols eliminar tots els grups i servidors? Aquesta acció no es pot desfer.", "rename_tab": "Canviar el nom de la pestanya", "duplicate_tab": "Duplicar pestanya", "detach_tab": "Moure a una finestra nova",
        "expand_all": "Expandir tots els grups", "collapse_all": "Contraure tots els grups",
        "help": "Ajuda", "about": "Quant a",
        "help_title": "Ajuda de Termia",
        "help_content": (
            "Termia és un gestor de connexions SSH amb terminals incrustats.\n\n"
            "Característiques principals:\n"
            "- Organitza servidors en grups i subgrups.\n"
            "- Crea, edita, elimina i filtra connexions SSH.\n"
            "- Obre diverses connexions al mateix servidor en pestanyes independents.\n"
            "- Obre terminals locals i permet canviar el nom de les pestanyes.\n"
            "- Mostra l'estat, el PID i el temps de connexió de cada sessió.\n"
            "- Desa estadístiques locals agregades i mostra estadístiques per terminal.\n"
            "- Permet enviar opcionalment la contrasenya desada amb Super+Shift+P.\n"
            "- Configura el tipus de lletra, la mida i els colors del terminal.\n"
            "- Importa i exporta configuracions, inclosa la importació bàsica des d'Ásbrú.\n\n"
            "Ús ràpid:\n"
            "Utilitza les icones del panell lateral per crear grups o servidors. Fes doble clic "
            "sobre un servidor per connectar i utilitza el botó dret per veure les accions disponibles."
        ),
        "about_content": "Gestor de connexions SSH amb terminals incrustats",
    },
    "en": {
        "servers": "Servers", "new_group": "New group", "new_server": "New server",
        "terminal": "Terminal", "preferences": "Preferences", "filter_servers": "Filter servers",
        "connect": "Connect", "edit_server": "Edit server", "delete_server": "Delete server", "clone_connection": "Clone connection",
        "edit_group": "Edit group", "delete_group": "Delete group", "no_group": "No group",
        "parent_group": "Parent group", "no_parent_group": "No parent group",
        "cancel": "Cancel", "close": "Close", "save": "Save", "name": "Name", "host": "IP or host",
        "ssh_user": "SSH user", "ssh_port": "SSH port", "group": "Group",
        "password": "Password", "public_key": "Private SSH key",
        "ssh_fingerprint_manual": "New host: answer the fingerprint prompt in this terminal. Then enter the password manually or with Super+Shift+P.",
        "password_warning": "Warning: the password will be stored as plain text in connections.json.",
        "theme": "Theme", "language": "Language", "restart_language": "The language will apply after restarting the application.",
        "close_tab": "Close tab", "disconnect": "Disconnect", "connecting": "Connecting",
        "close_tab_on_disconnect": "Close the tab when disconnecting a session",
        "confirm_disconnect": "Confirm before disconnecting", "confirm_close_app": "Confirm before closing Termia",
        "sudo_password_shortcut": "Send password with Super+Shift+P",
        "sudo_password_enter": "Send password and press Enter",
        "sudo_password_sent": "Saved password sent to the terminal",
        "sudo_password_unavailable": "This terminal does not have a saved password",
        "close_app": "Close Termia", "close_app_confirm": "Do you want to close Termia?",
        "font_size": "Font and size", "terminal_font_size_changed": "Terminal font size: {size}", "foreground": "Foreground", "background": "Background", "palettes": "Palettes",
        "configuration": "Configuration", "connections_file": "Connections file", "export_config": "Export configuration", "import_config": "Import configuration",
        "summary": "{groups} groups · {subgroups} subgroups · {servers} servers",
        "import_asbru": "Import Ásbrú configuration", "clear_config": "Delete all configuration", "configure_terminal": "Configure terminal", "local_terminal": "Local terminal",
        "statistics": "Statistics", "connections": "Connections", "commands": "Commands", "keystrokes": "Keystrokes",
        "global": "Global", "current_run": "Current run", "shortest_duration": "Shortest duration", "longest_duration": "Longest duration", "average_duration": "Average duration",
        "copy": "Copy", "paste": "Paste", "session_statistics": "Session statistics", "server_connections": "Global connections to this server",
        "clear_confirm": "Delete all groups and servers? This action cannot be undone.", "rename_tab": "Rename tab", "duplicate_tab": "Duplicate tab", "detach_tab": "Move to new window",
        "expand_all": "Expand all groups", "collapse_all": "Collapse all groups",
        "help": "Help", "about": "About",
        "help_title": "Termia Help",
        "help_content": (
            "Termia is an SSH connection manager with embedded terminals.\n\n"
            "Main features:\n"
            "- Organize servers into groups and subgroups.\n"
            "- Create, edit, delete and filter SSH connections.\n"
            "- Open multiple connections to the same server in independent tabs.\n"
            "- Open local terminals and rename tabs.\n"
            "- View the status, PID and connection time for each session.\n"
            "- Store aggregate local statistics and view per-terminal statistics.\n"
            "- Optionally send the saved password with Super+Shift+P.\n"
            "- Configure the terminal font, size and colors.\n"
            "- Import and export configurations, including basic imports from Ásbrú.\n\n"
            "Quick start:\n"
            "Use the sidebar icons to create groups or servers. Double-click a server to connect "
            "and use the right mouse button to view the available actions."
        ),
        "about_content": "SSH connection manager with embedded terminals",
    },
}


def parse_color(value: str, fallback: str) -> Gdk.RGBA:
    color = Gdk.RGBA()
    if not color.parse(value):
        color.parse(fallback)
    return color


@dataclass
class Server:
    id: str
    name: str
    host: str
    user: str
    port: int = 22
    group_id: str | None = None
    password: str = ""
    public_key: str = ""


@dataclass
class Group:
    id: str
    name: str
    parent_id: str | None = None


@dataclass
class TerminalSettings:
    font_family: str = "Ubuntu Mono"
    font_size: int = 13
    foreground: str = "#839496"
    background: str = "#002b36"
    ls_colors: str = DEFAULT_LS_COLORS
    ansi_palette: list[str] = field(default_factory=lambda: DEFAULT_ANSI_PALETTE.copy())


@dataclass
class AppSettings:
    theme: str = "system"
    language: str = field(default_factory=detect_system_language)
    close_tab_on_disconnect: bool = False
    confirm_disconnect: bool = True
    confirm_close_app: bool = False
    sudo_password_shortcut: bool = False
    sudo_password_enter: bool = False


@dataclass
class StatisticsSettings:
    connections: int = 0
    commands: int = 0
    keystrokes: int = 0
    completed_sessions: int = 0
    duration_total: float = 0.0
    duration_min: float | None = None
    duration_max: float = 0.0
    server_connections: dict[str, int] = field(default_factory=dict)


class StatisticsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = StatisticsSettings()
        self.load()

    def load(self) -> None:
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.data = StatisticsSettings(**payload)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(self.data), indent=2), encoding="utf-8")
        self.path.chmod(0o600)


@dataclass
class StoreData:
    groups: list[Group] = field(default_factory=list)
    servers: list[Server] = field(default_factory=list)
    terminal: TerminalSettings = field(default_factory=TerminalSettings)
    app: AppSettings = field(default_factory=AppSettings)
    statistics: StatisticsSettings = field(default_factory=StatisticsSettings)


class ConnectionStore:
    def __init__(self, path: Path, statistics_path: Path = STATISTICS_FILE) -> None:
        self.path = path
        self.statistics_store = StatisticsStore(statistics_path)
        self.data = StoreData(statistics=self.statistics_store.data)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.data = StoreData(statistics=self.statistics_store.data)
            return

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        legacy_statistics = payload.get("statistics")
        if legacy_statistics and not self.statistics_store.path.exists():
            self.statistics_store.data = StatisticsSettings(**legacy_statistics)
            self.statistics_store.save()
        self.data = StoreData(
            groups=[Group(**item) for item in payload.get("groups", [])],
            servers=[Server(**item) for item in payload.get("servers", [])],
            terminal=TerminalSettings(**payload.get("terminal", {})),
            app=AppSettings(**payload.get("app", {})),
            statistics=self.statistics_store.data,
        )
        if "statistics" in payload:
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "groups": [asdict(group) for group in self.data.groups],
            "servers": [asdict(server) for server in self.data.servers],
            "terminal": asdict(self.data.terminal),
            "app": asdict(self.data.app),
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.path.chmod(0o600)

    def save_statistics(self) -> None:
        self.statistics_store.data = self.data.statistics
        self.statistics_store.save()

    def add_group(self, name: str, parent_id: str | None = None) -> Group:
        group = Group(id=str(uuid4()), name=name.strip(), parent_id=parent_id)
        self.data.groups.append(group)
        self.save()
        return group

    def update_group(self, group_id: str, name: str, parent_id: str | None = None) -> None:
        for group in self.data.groups:
            if group.id == group_id:
                group.name = name.strip()
                group.parent_id = parent_id
                break
        self.save()

    def delete_group(self, group_id: str) -> None:
        group_ids = {group_id}
        pending = [group_id]
        while pending:
            parent_id = pending.pop()
            child_ids = [
                group.id for group in self.data.groups
                if group.parent_id == parent_id and group.id not in group_ids
            ]
            group_ids.update(child_ids)
            pending.extend(child_ids)
        self.data.groups = [group for group in self.data.groups if group.id not in group_ids]
        self.data.servers = [server for server in self.data.servers if server.group_id not in group_ids]
        self.save()

    def add_server(
        self,
        name: str,
        host: str,
        user: str,
        port: int,
        group_id: str | None,
        password: str = "",
        public_key: str = "",
    ) -> Server:
        server = Server(
            id=str(uuid4()),
            name=name.strip(),
            host=host.strip(),
            user=user.strip(),
            port=port,
            group_id=group_id,
            password=password,
            public_key=public_key,
        )
        self.data.servers.append(server)
        self.save()
        return server

    def update_server(
        self,
        server_id: str,
        name: str,
        host: str,
        user: str,
        port: int,
        group_id: str | None,
        password: str = "",
        public_key: str = "",
    ) -> None:
        for server in self.data.servers:
            if server.id == server_id:
                server.name = name.strip()
                server.host = host.strip()
                server.user = user.strip()
                server.port = port
                server.group_id = group_id
                server.password = password
                server.public_key = public_key
                break
        self.save()

    def delete_server(self, server_id: str) -> None:
        self.data.servers = [server for server in self.data.servers if server.id != server_id]
        self.save()

    def update_terminal_settings(
        self,
        font_family: str,
        font_size: int,
        foreground: str,
        background: str,
        ls_colors: str | None = None,
    ) -> None:
        self.data.terminal = TerminalSettings(
            font_family=font_family.strip() or "Monospace",
            font_size=max(6, min(font_size, 72)),
            foreground=foreground.strip() or "#f2f2f2",
            background=background.strip() or "#101010",
            ls_colors=ls_colors if ls_colors is not None else self.data.terminal.ls_colors,
            ansi_palette=self.data.terminal.ansi_palette or DEFAULT_ANSI_PALETTE.copy(),
        )
        self.save()

    def update_app_settings(
        self, theme: str, language: str, close_tab_on_disconnect: bool,
        confirm_disconnect: bool, confirm_close_app: bool,
        sudo_password_shortcut: bool, sudo_password_enter: bool,
    ) -> None:
        self.data.app = AppSettings(
            theme=theme if theme in APP_THEMES else "system",
            language=language if language in LANGUAGES else detect_system_language(),
            close_tab_on_disconnect=close_tab_on_disconnect,
            confirm_disconnect=confirm_disconnect,
            confirm_close_app=confirm_close_app,
            sudo_password_shortcut=sudo_password_shortcut,
            sudo_password_enter=sudo_password_enter,
        )
        self.save()


class RowObject(GObject.Object):
    def __init__(self, kind: str, item_id: str, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.kind = kind
        self.item_id = item_id
        self.title = title
        self.subtitle = subtitle


@dataclass
class TerminalSession:
    id: str
    server_id: str | None
    title: str
    terminal: Vte.Terminal
    page: Gtk.Widget
    tab_label: Gtk.Widget
    status_label: Gtk.Label
    timer_label: Gtk.Label
    disconnect_button: Gtk.Button
    started_at: float
    notebook: Gtk.Notebook | None = None
    detached_window: Gtk.Window | None = None
    timeout_id: int | None = None
    child_pid: int | None = None
    connected: bool = True
    disconnect_requested: bool = False
    keystrokes: int = 0
    commands: int = 0
    duration_recorded: bool = False


class TermiaWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="Termia")
        self.set_default_size(1000, 620)

        self.store = ConnectionStore(DATA_FILE)
        self.apply_app_theme()
        self.install_tree_styles()
        self.selected: RowObject | None = None
        self.selected_tree_widget: Gtk.Widget | None = None
        self.tree_widgets: dict[tuple[str, str], Gtk.Widget] = {}
        self.active_context_popover: Gtk.Popover | None = None
        self.model = Gio.ListStore(item_type=RowObject)
        self.open_tabs: dict[str, TerminalSession] = {}
        self.session_sequence = 0
        self.run_connections = 0
        self.run_commands = 0
        self.run_keystrokes = 0
        self.stats_save_id: int | None = None
        self.close_confirmation_pending = False
        self.connect("close-request", self.on_main_window_close_request)

        self.toast_label = Gtk.Label()
        self.toast_label.add_css_class("dim-label")

        self._build_ui()
        self.refresh_list()

    def t(self, key: str) -> str:
        language = self.store.data.app.language
        return TRANSLATIONS.get(language, TRANSLATIONS["es"]).get(key, key)

    def on_main_window_close_request(self, _window: Gtk.Window) -> bool:
        if not self.store.data.app.confirm_close_app:
            self.save_statistics_before_close()
            return False
        if self.close_confirmation_pending:
            return True
        self.close_confirmation_pending = True
        dialog = Gtk.AlertDialog(message=self.t("close_app"), detail=self.t("close_app_confirm"))
        dialog.set_buttons([self.t("cancel"), self.t("close_app")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_main_window_close_confirmed, dialog)
        return True

    def on_main_window_close_confirmed(
        self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, _data: Gtk.AlertDialog
    ) -> None:
        self.close_confirmation_pending = False
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response == 1:
            self.save_statistics_before_close()
            application = self.get_application()
            if application is not None:
                application.quit()

    def apply_app_theme(self) -> None:
        settings = Gtk.Settings.get_default()
        if settings is None:
            return
        theme = self.store.data.app.theme
        settings.set_property("gtk-application-prefer-dark-theme", theme == "dark")

    def install_tree_styles(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        provider = Gtk.CssProvider()
        provider.load_from_data(
            b".termia-tree-item { border-radius: 4px; } "
            b".termia-server-item { padding-top: 2px; padding-bottom: 2px; } "
            b".termia-tree-item.selected { "
            b"background-color: @theme_selected_bg_color; "
            b"color: @theme_selected_fg_color; }"
        )
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(root)

        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        toggle_sidebar = Gtk.Button(icon_name="sidebar-hide-symbolic")
        toggle_sidebar.set_tooltip_text(self.t("servers"))
        toggle_sidebar.connect("clicked", self.on_toggle_sidebar)
        header.pack_start(toggle_sidebar)

        local_terminal_btn = Gtk.Button(label=self.t("local_terminal"))
        local_terminal_btn.connect("clicked", self.on_open_local_terminal)
        header.pack_start(local_terminal_btn)

        config_btn = Gtk.MenuButton(label=self.t("configuration"))
        config_btn.set_popover(self.build_configuration_menu())
        header.pack_start(config_btn)

        stats_btn = Gtk.MenuButton(label=self.t("statistics"))
        stats_btn.set_popover(self.build_statistics_menu())
        stats_btn.connect("notify::active", self.on_statistics_menu_active)
        header.pack_start(stats_btn)

        help_btn = Gtk.Button(label=self.t("help"))
        help_btn.connect("clicked", self.on_help)
        header.pack_start(help_btn)

        about_btn = Gtk.Button(label=self.t("about"))
        about_btn.connect("clicked", self.on_about)
        header.pack_start(about_btn)

        body = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        body.set_position(280)
        body.set_wide_handle(True)
        self.body = body
        self.sidebar_visible = True
        self.sidebar_width = 280
        root.append(body)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar.set_size_request(120, -1)
        sidebar.set_margin_top(12)
        sidebar.set_margin_bottom(12)
        sidebar.set_margin_start(12)
        sidebar.set_margin_end(12)
        self.sidebar = sidebar
        body.set_start_child(sidebar)
        body.set_resize_start_child(False)
        body.set_shrink_start_child(True)
        body.set_resize_end_child(True)
        body.set_shrink_end_child(False)

        sidebar_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add_group = Gtk.Button(icon_name="folder-new-symbolic")
        add_group.set_tooltip_text(self.t("new_group"))
        add_group.connect("clicked", self.on_add_group)
        add_server = Gtk.Button(icon_name="list-add-symbolic")
        add_server.set_tooltip_text(self.t("new_server"))
        add_server.connect("clicked", self.on_add_server)
        expand_all = Gtk.Button(icon_name="pan-down-symbolic")
        expand_all.set_tooltip_text(self.t("expand_all"))
        expand_all.connect("clicked", lambda _button: self.set_all_groups_expanded(True))
        collapse_all = Gtk.Button(icon_name="pan-up-symbolic")
        collapse_all.set_tooltip_text(self.t("collapse_all"))
        collapse_all.connect("clicked", lambda _button: self.set_all_groups_expanded(False))
        sidebar_actions.append(add_group)
        sidebar_actions.append(add_server)
        sidebar_actions.append(expand_all)
        sidebar_actions.append(collapse_all)
        sidebar.append(sidebar_actions)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(self.t("filter_servers"))
        self.search_entry.connect("search-changed", lambda _entry: self.refresh_list())
        sidebar.append(self.search_entry)

        self.server_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.server_list.set_focusable(False)

        scroller = Gtk.ScrolledWindow()
        self.server_scroller = scroller
        self.scroll_restore_id: int | None = None
        scroller.set_child(self.server_list)
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)
        scroller.set_min_content_width(80)
        sidebar.append(scroller)

        self.summary_label = Gtk.Label()
        self.summary_label.set_xalign(0)
        self.summary_label.add_css_class("dim-label")
        sidebar.append(self.summary_label)

        detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        detail.set_margin_top(0)
        detail.set_margin_bottom(0)
        detail.set_margin_start(0)
        detail.set_margin_end(0)
        detail.set_hexpand(True)
        detail.set_vexpand(True)
        body.set_end_child(detail)

        self.title_label = Gtk.Label(label="Selecciona un servidor")
        self.title_label.set_xalign(0)
        self.title_label.add_css_class("title-2")

        self.info_label = Gtk.Label(label="Crea grupos y servidores desde la barra superior.")
        self.info_label.set_xalign(0)
        self.info_label.set_wrap(True)

        self.notebook = Gtk.Notebook()
        self.notebook.set_vexpand(True)
        self.notebook.set_hexpand(True)
        self.notebook.set_scrollable(True)
        self.notebook.set_group_name("termia-terminals")
        detail.append(self.notebook)

        self.update_actions()

    def build_statistics_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(12)
        content.set_margin_end(12)
        self.statistics_labels: dict[str, Gtk.Label] = {}
        for key in ("connections", "commands", "durations", "keystrokes"):
            label = Gtk.Label()
            label.set_xalign(0)
            label.set_selectable(True)
            content.append(label)
            self.statistics_labels[key] = label
        popover.set_child(content)
        self.refresh_statistics_menu()
        return popover

    def on_statistics_menu_active(self, button: Gtk.MenuButton, _param: GObject.ParamSpec) -> None:
        if button.get_active():
            self.refresh_statistics_menu()
            GLib.idle_add(self.clear_statistics_label_selection)

    def clear_statistics_label_selection(self) -> bool:
        if hasattr(self, "statistics_labels"):
            for label in self.statistics_labels.values():
                label.select_region(0, 0)
        return GLib.SOURCE_REMOVE

    def refresh_statistics_menu(self) -> None:
        if not hasattr(self, "statistics_labels"):
            return
        stats = self.store.data.statistics
        self.statistics_labels["connections"].set_label(
            f"{self.t('connections')}: {self.t('global')} {stats.connections} · {self.t('current_run')} {self.run_connections}"
        )
        self.statistics_labels["commands"].set_label(
            f"{self.t('commands')}: {self.t('global')} {stats.commands} · {self.t('current_run')} {self.run_commands}"
        )
        self.statistics_labels["durations"].set_label(
            f"{self.t('shortest_duration')}: {self.format_duration(stats.duration_min)}\n"
            f"{self.t('longest_duration')}: {self.format_duration(stats.duration_max if stats.completed_sessions else None)}\n"
            f"{self.t('average_duration')}: {self.format_duration(stats.duration_total / stats.completed_sessions if stats.completed_sessions else None)}"
        )
        self.statistics_labels["keystrokes"].set_label(
            f"{self.t('keystrokes')}: {self.t('global')} {stats.keystrokes} · {self.t('current_run')} {self.run_keystrokes}"
        )
        self.clear_statistics_label_selection()

    def format_duration(self, seconds: float | None) -> str:
        if seconds is None:
            return "--:--:--"
        total = max(0, int(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def build_configuration_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        preferences = Gtk.Button(label=self.t("preferences"))
        preferences.set_halign(Gtk.Align.FILL)
        preferences.connect("clicked", lambda _button: self.on_app_preferences(None))
        menu.append(preferences)

        connections_file = Gtk.MenuButton(label=self.t("connections_file"))
        connections_file.set_halign(Gtk.Align.FILL)
        connections_file.set_popover(self.build_connections_file_menu())
        menu.append(connections_file)
        popover.set_child(menu)
        return popover

    def add_dialog_action_button(
        self, dialog: Gtk.Dialog, label: str, response: Gtk.ResponseType, *, last: bool = False
    ) -> Gtk.Button:
        button = dialog.add_button(label, response)
        button.set_margin_end(12 if last else 6)
        button.set_margin_bottom(12)
        return button

    def add_dialog_action_buttons(
        self, dialog: Gtk.Dialog, confirm_label: str, confirm_response: Gtk.ResponseType = Gtk.ResponseType.OK
    ) -> tuple[Gtk.Button, Gtk.Button]:
        cancel = self.add_dialog_action_button(dialog, self.t("cancel"), Gtk.ResponseType.CANCEL)
        confirm = self.add_dialog_action_button(dialog, confirm_label, confirm_response, last=True)
        return cancel, confirm

    def on_help(self, _button: Gtk.Button) -> None:
        dialog = Gtk.Dialog(title=self.t("help_title"), transient_for=self, modal=True)
        dialog.set_default_size(620, 440)
        self.add_dialog_action_button(dialog, self.t("close"), Gtk.ResponseType.CLOSE, last=True)
        dialog.connect("response", lambda source, _response: source.destroy())

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        label = Gtk.Label(label=self.t("help_content"))
        label.set_xalign(0)
        label.set_yalign(0)
        label.set_wrap(True)
        label.set_selectable(True)
        scroller.set_child(label)
        content.append(scroller)
        dialog.present()

    def on_about(self, _button: Gtk.Button) -> None:
        dialog = Gtk.AboutDialog(transient_for=self, modal=True)
        dialog.set_program_name("Termia")
        dialog.set_version("0.1.0")
        dialog.set_copyright("Copyright © 2026 Jordi Pons")
        dialog.set_license_type(Gtk.License.MIT_X11)
        dialog.set_comments(self.t("about_content"))
        if ABOUT_IMAGE.exists():
            dialog.set_logo(Gdk.Texture.new_from_filename(str(ABOUT_IMAGE)))
        dialog.present()

    def build_connections_file_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        menu = Gtk.ListBox()
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)
        self.add_context_menu_item(menu, self.t("export_config"), self.on_export_config)
        self.add_context_menu_item(menu, self.t("import_config"), self.on_import_config)
        self.add_context_menu_item(menu, self.t("import_asbru"), self.on_import_asbru_config)
        self.add_context_menu_item(menu, self.t("clear_config"), self.on_request_clear_config, destructive=True)
        popover.set_child(menu)
        return popover

    def on_toggle_sidebar(self, _button: Gtk.Button) -> None:
        if self.sidebar_visible:
            self.sidebar_width = max(self.body.get_position(), 180)
            self.sidebar.set_visible(False)
            self.body.set_position(0)
            self.sidebar_visible = False
            _button.set_icon_name("sidebar-show-symbolic")
        else:
            self.sidebar.set_visible(True)
            self.body.set_position(self.sidebar_width)
            self.sidebar_visible = True
            _button.set_icon_name("sidebar-hide-symbolic")

    def setup_row(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        title = Gtk.Label()
        title.set_xalign(0)
        title.add_css_class("heading")
        box.append(title)

        subtitle = Gtk.Label()
        subtitle.set_xalign(0)
        subtitle.add_css_class("dim-label")
        box.append(subtitle)

        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_row_right_click, item, box)
        box.add_controller(right_click)

        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        left_click.connect("pressed", self.on_row_left_click, item)
        box.add_controller(left_click)

        item.set_child(box)

    def bind_row(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        obj = item.get_item()
        box = item.get_child()
        title = box.get_first_child()
        subtitle = title.get_next_sibling()
        title.set_label(obj.title)
        subtitle.set_label(obj.subtitle)

    def on_row_left_click(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        item: Gtk.ListItem,
    ) -> None:
        if n_press != 2:
            return
        row = item.get_item()
        if row is None or row.kind != "server":
            return
        server = self.find_server(row.item_id)
        if server:
            self.open_terminal_tab(server)

    def on_row_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        item: Gtk.ListItem,
        parent: Gtk.Widget,
    ) -> None:
        row = item.get_item()
        if row is None:
            return

        self.selected = row
        position = item.get_position()
        if position != Gtk.INVALID_LIST_POSITION:
            self.selection.set_selected(position)

        popover = Gtk.Popover()
        popover.set_parent(parent)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        if row.kind == "server":
            connect_button = Gtk.Button(label="Conectar")
            connect_button.add_css_class("suggested-action")
            connect_button.connect("clicked", self.on_server_context_connect, popover, row.item_id)
            edit_button = Gtk.Button(label="Editar servidor")
            edit_button.connect("clicked", self.on_server_context_edit, popover, row.item_id)
            delete_button = Gtk.Button(label="Eliminar servidor")
            delete_button.add_css_class("destructive-action")
            delete_button.connect("clicked", self.on_server_context_delete, popover, row.item_id)
            for button in (connect_button, edit_button, delete_button):
                menu.append(button)
        elif row.kind == "group" and row.item_id:
            edit_button = Gtk.Button(label="Editar grupo")
            edit_button.connect("clicked", self.on_group_context_edit, popover, row.item_id)
            delete_button = Gtk.Button(label="Eliminar grupo")
            delete_button.add_css_class("destructive-action")
            delete_button.connect("clicked", self.on_group_context_delete, popover, row.item_id)
            menu.append(edit_button)
            menu.append(delete_button)
        else:
            return

        popover.set_child(menu)
        popover.popup()

    def on_server_context_connect(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        server = self.find_server(server_id)
        if server:
            self.open_terminal_tab(server)

    def on_server_context_edit(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        server = self.find_server(server_id)
        if server:
            self.show_server_dialog(server)

    def on_server_context_delete(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        server = self.find_server(server_id)
        if server:
            self.store.delete_server(server_id)
            self.selected = None
            self.toast_label.set_label(f"Servidor eliminado: {server.name}")
            self.refresh_list()
            self.render_detail()

    def on_server_context_clone(self, _button: Gtk.Button, popover: Gtk.Popover, server_id: str) -> None:
        popover.popdown()
        server = self.find_server(server_id)
        if server is None:
            return
        clone = self.store.add_server(
            self.unique_server_clone_name(server.name),
            server.host,
            server.user,
            server.port,
            server.group_id,
            server.password,
            server.public_key,
        )
        self.selected = RowObject("server", clone.id, clone.name)
        self.toast_label.set_label(f"Conexión clonada: {clone.name}")
        self.refresh_list()
        self.render_detail()

    def unique_server_clone_name(self, name: str) -> str:
        existing_names = {server.name for server in self.store.data.servers}
        base_name = f"{name}-clone"
        if base_name not in existing_names:
            return base_name
        index = 2
        while f"{base_name}-{index}" in existing_names:
            index += 1
        return f"{base_name}-{index}"

    def on_group_context_edit(self, _button: Gtk.Button, popover: Gtk.Popover, group_id: str) -> None:
        popover.popdown()
        group = self.find_group(group_id)
        if group:
            self.show_group_dialog(group)

    def on_group_context_delete(self, _button: Gtk.Button, popover: Gtk.Popover, group_id: str) -> None:
        popover.popdown()
        group = self.find_group(group_id)
        if group:
            self.store.delete_group(group_id)
            self.selected = None
            self.toast_label.set_label(f"Grupo eliminado: {group.name}")
            self.refresh_list()
            self.render_detail()

    def set_all_groups_expanded(self, expanded: bool) -> None:
        for expander in self.group_expanders:
            expander.set_expanded(expanded)

    def refresh_list(self) -> None:
        query = self.search_entry.get_text().lower().strip() if hasattr(self, "search_entry") else ""
        if not hasattr(self, "server_list"):
            return

        while child := self.server_list.get_first_child():
            self.server_list.remove(child)
        self.group_expanders: list[Gtk.Expander] = []
        self.tree_widgets = {}
        self.selected_tree_widget = None

        children_by_parent: dict[str | None, list[Group]] = {}
        for group in self.store.data.groups:
            children_by_parent.setdefault(group.parent_id, []).append(group)
        servers_by_group: dict[str | None, list[Server]] = {}
        for server in self.store.data.servers:
            if self.matches_query(server, query):
                servers_by_group.setdefault(server.group_id, []).append(server)

        for group in sorted(children_by_parent.get(None, []), key=lambda item: item.name.lower()):
            widget = self.build_group_widget(group, children_by_parent, servers_by_group, query)
            if widget is not None:
                self.server_list.append(widget)

        ungrouped = servers_by_group.get(None, [])
        if ungrouped:
            self.server_list.append(self.build_ungrouped_widget(ungrouped))

        root_groups = len([group for group in self.store.data.groups if group.parent_id is None])
        subgroups = len(self.store.data.groups) - root_groups
        self.summary_label.set_label(
            self.t("summary").format(groups=root_groups, subgroups=subgroups, servers=len(self.store.data.servers))
        )

    def build_group_widget(
        self,
        group: Group,
        children_by_parent: dict[str | None, list[Group]],
        servers_by_group: dict[str | None, list[Server]],
        query: str,
    ) -> Gtk.Widget | None:
        child_groups = children_by_parent.get(group.id, [])
        servers = servers_by_group.get(group.id, [])
        child_widgets = [
            widget
            for child in sorted(child_groups, key=lambda item: item.name.lower())
            if (widget := self.build_group_widget(child, children_by_parent, servers_by_group, query)) is not None
        ]
        if query and not servers and not child_widgets:
            return None

        descendant_servers = len(servers) + sum(
            int(getattr(widget, "server_count", 0)) for widget in child_widgets
        )
        expander = Gtk.Expander()
        group_label = self.build_group_label(f"{group.name} ({descendant_servers})")
        expander.set_label_widget(group_label)
        self.group_expanders.append(expander)
        expander.server_count = descendant_servers
        expander.set_expanded(True)
        expander.set_margin_top(3)
        expander.set_margin_bottom(3)
        expander.set_margin_start(4)
        expander.set_margin_end(2)

        group_row = RowObject("group", group.id, group.name, f"{descendant_servers} servidor(es)")
        self.register_tree_widget(group_row, group_label)
        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        left_click.connect("pressed", self.on_group_widget_left_click, group_row, group_label)
        group_label.add_controller(left_click)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_group_widget_right_click, group_row, group_label)
        group_label.add_controller(right_click)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for widget in child_widgets:
            widget.set_margin_start(widget.get_margin_start() + 10)
            content.append(widget)
        for server in sorted(servers, key=lambda item: item.name.lower()):
            content.append(self.build_server_widget(server))
        expander.set_child(content)
        return expander

    def build_group_label(self, text: str) -> Gtk.Widget:
        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label_box.append(Gtk.Image.new_from_icon_name("folder-symbolic"))
        label = Gtk.Label(label=text)
        label.add_css_class("heading")
        label_box.append(label)
        return label_box

    def build_ungrouped_widget(self, servers: list[Server]) -> Gtk.Widget:
        expander = Gtk.Expander()
        expander.set_label_widget(self.build_group_label(f"{self.t('no_group')} ({len(servers)})"))
        self.group_expanders.append(expander)
        expander.set_expanded(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for server in sorted(servers, key=lambda item: item.name.lower()):
            content.append(self.build_server_widget(server))
        expander.set_child(content)
        return expander

    def build_server_widget(self, server: Server) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        row.set_focusable(False)
        row.set_margin_top(0)
        row.set_margin_bottom(0)
        row.set_margin_start(18)
        row.set_margin_end(6)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_box.append(Gtk.Image.new_from_icon_name("network-server-symbolic"))
        title = Gtk.Label(label=server.name)
        title.set_xalign(0)
        title_box.append(title)
        row.append(title_box)

        connection = f"{server.user}@{server.host}:{server.port}" if server.user else f"{server.host}:{server.port}"
        row.set_tooltip_text(connection)
        row_obj = RowObject("server", server.id, server.name, connection)
        self.register_tree_widget(row_obj, row)
        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        left_click.connect("pressed", self.on_server_widget_left_click, row_obj)
        row.add_controller(left_click)

        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_server_widget_right_click, row_obj, row)
        row.add_controller(right_click)
        return row

    def register_tree_widget(self, row: RowObject, widget: Gtk.Widget) -> None:
        widget.add_css_class("termia-tree-item")
        if row.kind == "server":
            widget.add_css_class("termia-server-item")
        widget.set_focusable(False)
        self.tree_widgets[(row.kind, row.item_id)] = widget
        if self.selected and self.selected.kind == row.kind and self.selected.item_id == row.item_id:
            widget.add_css_class("selected")
            self.selected_tree_widget = widget

    def select_tree_row(self, row: RowObject, widget: Gtk.Widget) -> None:
        self.preserve_sidebar_scroll()
        if self.selected_tree_widget is not None and self.selected_tree_widget is not widget:
            self.selected_tree_widget.remove_css_class("selected")
        self.selected = row
        self.selected_tree_widget = widget
        widget.add_css_class("selected")
        self.render_detail()
        self.update_actions()

    def get_sidebar_scroll_values(self) -> tuple[float, float]:
        return (
            self.server_scroller.get_vadjustment().get_value(),
            self.server_scroller.get_hadjustment().get_value(),
        )

    def preserve_sidebar_scroll(
        self, vertical_value: float | None = None, horizontal_value: float | None = None
    ) -> None:
        vertical = self.server_scroller.get_vadjustment()
        horizontal = self.server_scroller.get_hadjustment()
        if vertical_value is None:
            vertical_value = vertical.get_value()
        if horizontal_value is None:
            horizontal_value = horizontal.get_value()
        if self.scroll_restore_id is not None:
            GLib.source_remove(self.scroll_restore_id)
        self.scroll_restore_id = GLib.idle_add(
            self.restore_sidebar_scroll, vertical, vertical_value, horizontal, horizontal_value
        )

    def restore_sidebar_scroll(
        self, vertical: Gtk.Adjustment, vertical_value: float,
        horizontal: Gtk.Adjustment, horizontal_value: float,
    ) -> bool:
        self.set_sidebar_scroll_value(vertical, vertical_value)
        self.set_sidebar_scroll_value(horizontal, horizontal_value)
        self.scroll_restore_id = GLib.timeout_add(
            50, self.finish_sidebar_scroll_restore, vertical, vertical_value, horizontal, horizontal_value
        )
        return GLib.SOURCE_REMOVE

    def finish_sidebar_scroll_restore(
        self, vertical: Gtk.Adjustment, vertical_value: float,
        horizontal: Gtk.Adjustment, horizontal_value: float,
    ) -> bool:
        self.set_sidebar_scroll_value(vertical, vertical_value)
        self.set_sidebar_scroll_value(horizontal, horizontal_value)
        self.scroll_restore_id = None
        return GLib.SOURCE_REMOVE

    def set_sidebar_scroll_value(self, adjustment: Gtk.Adjustment, value: float) -> None:
        maximum = max(adjustment.get_lower(), adjustment.get_upper() - adjustment.get_page_size())
        adjustment.set_value(min(max(value, adjustment.get_lower()), maximum))

    def on_group_widget_left_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        row: RowObject,
        widget: Gtk.Widget,
    ) -> None:
        self.select_tree_row(row, widget)

    def on_server_widget_left_click(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        row: RowObject,
    ) -> None:
        self.select_tree_row(row, self.tree_widgets[(row.kind, row.item_id)])
        if n_press == 2:
            server = self.find_server(row.item_id)
            if server:
                self.open_terminal_tab(server)

    def on_server_widget_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        row: RowObject,
        parent: Gtk.Widget,
    ) -> None:
        scroll_values = self.get_sidebar_scroll_values()
        self.close_active_context_menu()
        self.select_tree_row(row, parent)
        self.show_row_context_menu(row, parent, _x, _y)
        self.preserve_sidebar_scroll(*scroll_values)

    def on_group_widget_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        row: RowObject,
        parent: Gtk.Widget,
    ) -> None:
        scroll_values = self.get_sidebar_scroll_values()
        self.close_active_context_menu()
        self.select_tree_row(row, parent)
        self.show_row_context_menu(row, parent, _x, _y)
        self.preserve_sidebar_scroll(*scroll_values)

    def close_active_context_menu(self) -> None:
        popover = self.active_context_popover
        if popover is None:
            return
        scroll_values = self.get_sidebar_scroll_values()
        self.active_context_popover = None
        popover.popdown()
        if popover.get_parent() is not None:
            popover.unparent()
        self.preserve_sidebar_scroll(*scroll_values)

    def on_context_menu_closed(self, popover: Gtk.Popover) -> None:
        scroll_values = self.get_sidebar_scroll_values()
        if self.active_context_popover is popover:
            self.active_context_popover = None
        if popover.get_parent() is not None:
            popover.unparent()
        self.preserve_sidebar_scroll(*scroll_values)

    def show_row_context_menu(
        self, row: RowObject, parent: Gtk.Widget, x: float, y: float
    ) -> None:
        if row.kind == "group" and row.item_id == "":
            return

        popover = Gtk.Popover()
        popover.set_parent(parent)
        pointing_rectangle = Gdk.Rectangle()
        pointing_rectangle.x = int(x)
        pointing_rectangle.y = int(y)
        pointing_rectangle.width = 1
        pointing_rectangle.height = 1
        popover.set_pointing_to(pointing_rectangle)
        popover.set_position(Gtk.PositionType.RIGHT)
        popover.connect("closed", self.on_context_menu_closed)
        self.active_context_popover = popover
        menu = Gtk.ListBox()
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        if row.kind == "server":
            self.add_context_menu_item(
                menu,
                self.t("connect"),
                lambda: self.on_server_context_connect(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("edit_server"),
                lambda: self.on_server_context_edit(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("clone_connection"),
                lambda: self.on_server_context_clone(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("delete_server"),
                lambda: self.on_server_context_delete(None, popover, row.item_id),
                destructive=True,
            )
        elif row.kind == "group":
            self.add_context_menu_item(
                menu,
                self.t("edit_group"),
                lambda: self.on_group_context_edit(None, popover, row.item_id),
            )
            self.add_context_menu_item(
                menu,
                self.t("delete_group"),
                lambda: self.on_group_context_delete(None, popover, row.item_id),
                destructive=True,
            )

        popover.set_child(menu)
        popover.popup()
        self.preserve_sidebar_scroll()

    def add_context_menu_item(
        self,
        menu: Gtk.ListBox,
        label_text: str,
        callback: Any,
        destructive: bool = False,
    ) -> None:
        row = Gtk.ListBoxRow()
        label = Gtk.Label(label=label_text)
        label.set_xalign(0)
        label.set_margin_top(8)
        label.set_margin_bottom(8)
        label.set_margin_start(12)
        label.set_margin_end(36)
        if destructive:
            label.add_css_class("error")
        row.set_child(label)

        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect("released", lambda *_args: callback())
        row.add_controller(click)
        menu.append(row)

    def matches_query(self, server: Server, query: str) -> bool:
        if not query:
            return True
        return query in " ".join([server.name, server.host, server.user]).lower()

    def server_row(self, server: Server, groups_by_id: dict[str, Group]) -> RowObject:
        group_name = groups_by_id.get(server.group_id).name if server.group_id in groups_by_id else "Sin grupo"
        return RowObject("server", server.id, server.name, f"{server.user}@{server.host}:{server.port} · {group_name}")

    def on_selection_changed(self, selection: Gtk.SingleSelection, _position: int, _n_items: int) -> None:
        self.selected = selection.get_selected_item()
        self.render_detail()
        self.update_actions()

    def render_detail(self) -> None:
        if self.selected is None:
            self.title_label.set_label("Selecciona un servidor")
            self.info_label.set_label("Crea grupos y servidores desde la barra superior.")
            return

        if self.selected.kind == "group":
            group = self.find_group(self.selected.item_id)
            title = group.name if group else "Sin grupo"
            count = len([server for server in self.store.data.servers if server.group_id == self.selected.item_id])
            self.title_label.set_label(title)
            self.info_label.set_label(
                f"{count} servidor(es) en este grupo. "
                "Usa Editar grupo o Eliminar grupo para gestionarlo."
            )
            return

        server = self.find_server(self.selected.item_id)
        if server is None:
            return
        group = self.find_group(server.group_id) if server.group_id else None
        self.title_label.set_label(server.name)
        self.info_label.set_label(
            f"SSH: {server.user}@{server.host}\n"
            f"Puerto: {server.port}\n"
            f"Grupo: {group.name if group else 'Sin grupo'}"
        )

    def update_actions(self) -> None:
        return

    def find_server(self, server_id: str) -> Server | None:
        return next((server for server in self.store.data.servers if server.id == server_id), None)

    def find_group(self, group_id: str | None) -> Group | None:
        return next((group for group in self.store.data.groups if group.id == group_id), None)

    def on_add_group(self, _button: Gtk.Button) -> None:
        self.show_group_dialog()

    def on_add_server(self, _button: Gtk.Button) -> None:
        self.show_server_dialog()

    def on_edit(self, _button: Gtk.Button) -> None:
        if self.selected is None:
            return
        if self.selected.kind == "group":
            group = self.find_group(self.selected.item_id)
            if group:
                self.show_group_dialog(group)
        elif self.selected.kind == "server":
            server = self.find_server(self.selected.item_id)
            if server:
                self.show_server_dialog(server)

    def on_delete(self, _button: Gtk.Button) -> None:
        if self.selected is None:
            return
        if self.selected.kind == "group" and self.selected.item_id:
            group = self.find_group(self.selected.item_id)
            self.store.delete_group(self.selected.item_id)
            self.toast_label.set_label(
                f"Grupo eliminado: {group.name}" if group else "Grupo eliminado"
            )
            self.selected = None
        elif self.selected.kind == "server":
            server = self.find_server(self.selected.item_id)
            self.store.delete_server(self.selected.item_id)
            self.toast_label.set_label(
                f"Servidor eliminado: {server.name}" if server else "Servidor eliminado"
            )
            self.selected = None
        self.refresh_list()
        self.render_detail()

    def on_connect(self, _button: Gtk.Button) -> None:
        if self.selected is None or self.selected.kind != "server":
            return
        server = self.find_server(self.selected.item_id)
        if server is None:
            return

        self.open_terminal_tab(server)

    def on_open_local_terminal(self, _button: Gtk.Button) -> None:
        shell = os.environ.get("SHELL") or GLib.find_program_in_path("bash") or "/bin/sh"
        self.open_process_terminal_tab(self.t("local_terminal"), [shell], None, working_directory=str(Path.home()))

    def open_process_terminal_tab(
        self,
        title: str,
        command: list[str],
        server_id: str | None,
        envv: list[str] | None = None,
        working_directory: str | None = None,
    ) -> None:
        session_id = str(uuid4())
        self.session_sequence += 1
        tab_title = f"{title} #{self.session_sequence}"
        terminal = Vte.Terminal()
        terminal.set_hexpand(True)
        terminal.set_vexpand(True)
        terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.ON)
        terminal.set_scrollback_lines(10000)
        self.apply_terminal_settings(terminal)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        status_label = Gtk.Label(label=self.t("connecting"))
        status_label.set_xalign(0)
        status_label.add_css_class("dim-label")
        timer_label = Gtk.Label(label="00:00:00")
        disconnect_button = Gtk.Button(label=self.t("disconnect"))
        disconnect_button.add_css_class("destructive-action")
        disconnect_button.set_size_request(-1, 22)
        toolbar.append(status_label)
        toolbar.append(Gtk.Box(hexpand=True))
        toolbar.append(timer_label)
        toolbar.append(disconnect_button)

        scroller = Gtk.ScrolledWindow()
        scroller.set_child(terminal)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.append(toolbar)
        page.append(scroller)
        page.set_hexpand(True)
        page.set_vexpand(True)

        tab_label = self.build_tab_label(tab_title, session_id, page)
        page_num = self.notebook.append_page(page, tab_label)
        self.configure_notebook_tab(self.notebook, page)
        session = TerminalSession(
            id=session_id, server_id=server_id, title=tab_title, terminal=terminal, page=page,
            tab_label=tab_label, status_label=status_label, timer_label=timer_label,
            disconnect_button=disconnect_button, started_at=time.monotonic(), notebook=self.notebook,
        )
        disconnect_button.connect("clicked", self.on_request_disconnect_session, session)
        self.configure_terminal_interactions(terminal, session)
        self.open_tabs[session_id] = session
        self.notebook.set_current_page(page_num)
        terminal.grab_focus()
        try:
            _ok, child_pid = terminal.spawn_sync(
                Vte.PtyFlags.DEFAULT, working_directory, command, envv or self.build_terminal_environment(),
                GLib.SpawnFlags.DEFAULT, None, None, None,
            )
        except GLib.Error as exc:
            terminal.feed(f"No se pudo iniciar el proceso: {exc.message}\r\n".encode())
            status_label.set_label("Error")
            session.connected = False
            disconnect_button.set_sensitive(False)
            return
        session.child_pid = child_pid
        session.timeout_id = GLib.timeout_add_seconds(1, self.update_session_timer, session)
        terminal.connect("child-exited", self.on_process_terminal_exited, session)
        status_label.set_label(f"{title} · PID {child_pid}")

    def on_process_terminal_exited(self, _terminal: Vte.Terminal, _status: int, session: TerminalSession) -> None:
        self.record_session_duration(session)
        self.save_statistics_now()
        session.connected = False
        session.disconnect_button.set_sensitive(False)
        self.open_tabs.pop(session.id, None)
        if session.disconnect_requested:
            session.status_label.set_label(f"Desconectada: {session.title}")
            return
        session.status_label.set_label(f"Cerrada: {session.title}")
        label = session.tab_label.get_first_child()
        if isinstance(label, Gtk.Label):
            label.set_label(f"{session.title} (cerrada)")

    def open_terminal_tab(self, server: Server) -> None:
        session_id = str(uuid4())
        self.session_sequence += 1
        tab_title = f"{server.name} #{self.session_sequence}"
        terminal = Vte.Terminal()
        terminal.set_hexpand(True)
        terminal.set_vexpand(True)
        terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.ON)
        terminal.set_scrollback_lines(10000)
        self.apply_terminal_settings(terminal)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_top(0)
        toolbar.set_margin_bottom(0)
        toolbar.set_margin_start(4)
        toolbar.set_margin_end(4)

        status_label = Gtk.Label(label=self.t("connecting"))
        status_label.set_xalign(0)
        status_label.add_css_class("dim-label")
        timer_label = Gtk.Label(label="00:00:00")
        disconnect_button = Gtk.Button(label=self.t("disconnect"))
        disconnect_button.add_css_class("destructive-action")
        disconnect_button.set_size_request(-1, 22)

        toolbar.append(status_label)
        toolbar.append(Gtk.Box(hexpand=True))
        toolbar.append(timer_label)
        toolbar.append(disconnect_button)

        scroller = Gtk.ScrolledWindow()
        scroller.set_child(terminal)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.append(toolbar)
        page.append(scroller)
        page.set_hexpand(True)
        page.set_vexpand(True)

        tab_label = self.build_tab_label(tab_title, session_id, page)
        page_num = self.notebook.append_page(page, tab_label)
        self.configure_notebook_tab(self.notebook, page)
        session = TerminalSession(
            id=session_id,
            server_id=server.id,
            title=tab_title,
            terminal=terminal,
            page=page,
            tab_label=tab_label,
            status_label=status_label,
            timer_label=timer_label,
            disconnect_button=disconnect_button,
            started_at=time.monotonic(),
            notebook=self.notebook,
        )
        disconnect_button.connect("clicked", self.on_request_disconnect_session, session)
        self.configure_terminal_interactions(terminal, session)
        self.open_tabs[session_id] = session
        self.notebook.set_current_page(page_num)

        ssh_path = GLib.find_program_in_path("ssh")
        if ssh_path is None:
            terminal.feed(b"No se encontro el cliente ssh en el PATH.\r\n")
            status_label.set_label("Sin ssh")
            session.connected = False
            disconnect_button.set_sensitive(False)
            self.toast_label.set_label("No se encontro ssh en el PATH")
            return

        ssh_target = f"{server.user}@{server.host}"
        command = [ssh_path, "-p", str(server.port)]
        if server.public_key:
            command.extend(["-i", str(Path(server.public_key).expanduser())])
        command.append(ssh_target)
        envv = self.build_terminal_environment(server.password)
        use_sshpass = bool(server.password)
        if server.password and not self.has_known_host_key(server.host, server.port):
            use_sshpass = False
            message = self.t("ssh_fingerprint_manual")
            terminal.feed(f"{message}\r\n\r\n".encode())
            self.toast_label.set_label(message)
        if use_sshpass:
            sshpass_path = GLib.find_program_in_path("sshpass")
            if sshpass_path is None:
                terminal.feed(b"No se encontro sshpass. Instala sshpass o deja la contrasena vacia.\r\n")
                status_label.set_label("Sin sshpass")
                session.connected = False
                disconnect_button.set_sensitive(False)
                return
            command = [sshpass_path, "-e", *command]
        terminal.feed(f"Conectando: {' '.join(command)}\r\n\r\n".encode())
        terminal.grab_focus()
        try:
            _ok, child_pid = terminal.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                None,
                command,
                envv,
                GLib.SpawnFlags.DEFAULT,
                None,
                None,
                None,
            )
        except GLib.Error as exc:
            terminal.feed(f"No se pudo iniciar ssh: {exc.message}\r\n".encode())
            status_label.set_label("Error")
            session.connected = False
            disconnect_button.set_sensitive(False)
            self.open_tabs.pop(session.id, None)
            self.toast_label.set_label(f"No se pudo iniciar ssh para {server.name}")
            return

        session.child_pid = child_pid
        session.timeout_id = GLib.timeout_add_seconds(1, self.update_session_timer, session)
        terminal.connect("child-exited", self.on_terminal_exited, server, session)
        self.record_connection(server.id)
        status_label.set_label(f"{server.name} · PID {child_pid}")
        self.toast_label.set_label(f"Sesion abierta: {session.title}")

    def has_known_host_key(self, host: str, port: int) -> bool:
        ssh_keygen = GLib.find_program_in_path("ssh-keygen")
        if ssh_keygen is None:
            return False
        lookup_host = f"[{host}]:{port}" if port != 22 else host
        known_hosts_files = [Path.home() / ".ssh" / "known_hosts", Path.home() / ".ssh" / "known_hosts2"]
        for known_hosts in known_hosts_files:
            if not known_hosts.exists():
                continue
            result = subprocess.run(
                [ssh_keygen, "-F", lookup_host, "-f", str(known_hosts)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode == 0:
                return True
        return False

    def schedule_statistics_save(self) -> None:
        if self.stats_save_id is None:
            self.stats_save_id = GLib.timeout_add_seconds(30, self.flush_statistics)

    def save_statistics_before_close(self) -> None:
        for session in tuple(self.open_tabs.values()):
            self.record_session_duration(session)
        if self.stats_save_id is not None:
            GLib.source_remove(self.stats_save_id)
            self.stats_save_id = None
        self.store.save_statistics()

    def flush_statistics(self) -> bool:
        self.stats_save_id = None
        self.store.save_statistics()
        return GLib.SOURCE_REMOVE

    def save_statistics_now(self) -> None:
        if self.stats_save_id is not None:
            GLib.source_remove(self.stats_save_id)
            self.stats_save_id = None
        self.store.save_statistics()

    def record_connection(self, server_id: str) -> None:
        stats = self.store.data.statistics
        stats.connections += 1
        stats.server_connections[server_id] = stats.server_connections.get(server_id, 0) + 1
        self.run_connections += 1
        self.schedule_statistics_save()
        self.refresh_statistics_menu()

    def record_session_duration(self, session: TerminalSession) -> None:
        if session.duration_recorded or session.child_pid is None:
            return
        session.duration_recorded = True
        duration = max(0.0, time.monotonic() - session.started_at)
        stats = self.store.data.statistics
        stats.completed_sessions += 1
        stats.duration_total += duration
        stats.duration_min = duration if stats.duration_min is None else min(stats.duration_min, duration)
        stats.duration_max = max(stats.duration_max, duration)
        self.schedule_statistics_save()
        self.refresh_statistics_menu()

    def configure_terminal_interactions(self, terminal: Vte.Terminal, session: TerminalSession) -> None:
        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self.on_terminal_key_pressed, session)
        terminal.add_controller(keys)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_terminal_right_click, session, terminal)
        terminal.add_controller(right_click)

    def on_terminal_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
        session: TerminalSession,
    ) -> bool:
        stats = self.store.data.statistics
        session.keystrokes += 1
        stats.keystrokes += 1
        self.run_keystrokes += 1
        enter_keys = {Gdk.KEY_Return, Gdk.KEY_KP_Enter, getattr(Gdk, "KEY_ISO_Enter", Gdk.KEY_Return)}
        if keyval in enter_keys:
            session.commands += 1
            stats.commands += 1
            self.run_commands += 1
        self.schedule_statistics_save()
        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
                self.change_terminal_font_size(1)
                return True
            if keyval in (Gdk.KEY_minus, Gdk.KEY_underscore, Gdk.KEY_KP_Subtract):
                self.change_terminal_font_size(-1)
                return True
        required_modifiers = Gdk.ModifierType.SUPER_MASK | Gdk.ModifierType.SHIFT_MASK
        if (
            self.store.data.app.sudo_password_shortcut
            and keyval in (Gdk.KEY_p, Gdk.KEY_P)
            and state & required_modifiers == required_modifiers
        ):
            self.send_saved_password(session)
            return True
        return False

    def change_terminal_font_size(self, delta: int) -> None:
        settings = self.store.data.terminal
        new_size = max(6, min(settings.font_size + delta, 72))
        if new_size == settings.font_size:
            return
        self.store.update_terminal_settings(
            settings.font_family,
            new_size,
            settings.foreground,
            settings.background,
            settings.ls_colors,
        )
        self.apply_terminal_settings_to_open_tabs()
        self.toast_label.set_label(self.t("terminal_font_size_changed").format(size=new_size))

    def send_saved_password(self, session: TerminalSession) -> None:
        server = self.find_server(session.server_id) if session.server_id is not None else None
        if not session.connected or server is None or not server.password:
            self.toast_label.set_label(self.t("sudo_password_unavailable"))
            return
        payload = server.password.encode()
        if self.store.data.app.sudo_password_enter:
            payload += b"\r"
        session.terminal.feed_child(payload)
        self.toast_label.set_label(self.t("sudo_password_sent"))

    def on_terminal_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
        session: TerminalSession,
        terminal: Vte.Terminal,
    ) -> None:
        popover = Gtk.Popover()
        popover.set_parent(terminal)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        menu = Gtk.ListBox()
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)
        self.add_context_menu_item(menu, self.t("duplicate_tab"), lambda: self.duplicate_tab(popover, session))
        self.add_context_menu_item(menu, self.t("disconnect"), lambda: self.disconnect_from_terminal_menu(popover, session))
        self.add_context_menu_item(menu, self.t("copy"), lambda: self.copy_terminal_selection(popover, terminal))
        self.add_context_menu_item(menu, self.t("paste"), lambda: self.paste_terminal_clipboard(popover, terminal))
        self.add_context_menu_item(menu, self.t("session_statistics"), lambda: self.show_session_statistics(popover, session))
        popover.set_child(menu)
        popover.popup()

    def disconnect_from_terminal_menu(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        self.on_request_disconnect_session(None, session)

    def copy_terminal_selection(self, popover: Gtk.Popover, terminal: Vte.Terminal) -> None:
        popover.popdown()
        terminal.copy_clipboard_format(Vte.Format.TEXT)

    def paste_terminal_clipboard(self, popover: Gtk.Popover, terminal: Vte.Terminal) -> None:
        popover.popdown()
        terminal.paste_clipboard()

    def show_session_statistics(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        server_connections = 0
        if session.server_id is not None:
            server_connections = self.store.data.statistics.server_connections.get(session.server_id, 0)
        dialog = Gtk.Dialog(title=self.t("session_statistics"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        self.add_dialog_action_button(dialog, self.t("close"), Gtk.ResponseType.CLOSE, last=True)
        label = Gtk.Label(
            label=(
                f"{self.t('keystrokes')}: {session.keystrokes}\n"
                f"{self.t('commands')}: {session.commands}\n"
                f"{self.t('server_connections')}: {server_connections}"
            )
        )
        label.set_xalign(0)
        label.set_selectable(True)
        label.set_margin_top(12)
        label.set_margin_bottom(12)
        label.set_margin_start(12)
        label.set_margin_end(12)
        dialog.get_content_area().append(label)
        dialog.connect("response", lambda current, _response: current.destroy())
        dialog.present()

    def configure_notebook_tab(self, notebook: Gtk.Notebook, page: Gtk.Widget) -> None:
        notebook.set_tab_reorderable(page, True)

    def build_terminal_environment(self, password: str = "") -> list[str]:
        env = dict(os.environ)
        env["LS_COLORS"] = self.store.data.terminal.ls_colors
        if password:
            env["SSHPASS"] = password
        env.setdefault("COLORTERM", "truecolor")
        env.setdefault("TERM", "xterm-256color")
        return [f"{key}={value}" for key, value in env.items()]

    def apply_terminal_settings(self, terminal: Vte.Terminal) -> None:
        settings = self.store.data.terminal
        font = Pango.FontDescription(f"{settings.font_family} {settings.font_size}")
        foreground = parse_color(settings.foreground, "#f2f2f2")
        background = parse_color(settings.background, "#101010")
        palette_values = settings.ansi_palette or DEFAULT_ANSI_PALETTE
        palette = [parse_color(color, fallback) for color, fallback in zip(palette_values, DEFAULT_ANSI_PALETTE)]
        terminal.set_font(font)
        terminal.set_colors(foreground, background, palette)

    def apply_terminal_settings_to_open_tabs(self) -> None:
        for session in self.open_tabs.values():
            self.apply_terminal_settings(session.terminal)

    def update_session_timer(self, session: TerminalSession) -> bool:
        if not session.connected:
            return GLib.SOURCE_REMOVE
        elapsed = int(time.monotonic() - session.started_at)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        session.timer_label.set_label(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        return GLib.SOURCE_CONTINUE

    def build_tab_label(self, title: str, session_id: str, page: Gtk.Widget) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        box.set_margin_start(0)
        box.set_margin_end(0)
        label = Gtk.Label(label=title)
        label.set_margin_start(2)
        label.set_margin_end(1)
        close_button = Gtk.Button(label="×")
        close_button.set_has_frame(False)
        close_button.set_tooltip_text(self.t("close_tab"))
        close_button.set_size_request(26, 24)
        close_button.connect("clicked", self.on_request_close_tab, session_id, page)
        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self.on_tab_right_click, session_id, box)
        box.add_controller(right_click)
        box.append(label)
        box.append(close_button)
        return box

    def on_tab_right_click(
        self,
        _gesture: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
        session_id: str,
        parent: Gtk.Widget,
    ) -> None:
        session = self.open_tabs.get(session_id)
        if session is None:
            return
        popover = Gtk.Popover()
        popover.set_parent(parent)
        menu = Gtk.ListBox()
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)
        self.add_context_menu_item(menu, self.t("duplicate_tab"), lambda: self.duplicate_tab(popover, session))
        self.add_context_menu_item(menu, self.t("detach_tab"), lambda: self.detach_tab(popover, session))
        self.add_context_menu_item(menu, self.t("rename_tab"), lambda: self.show_rename_tab_dialog(popover, session))
        popover.set_child(menu)
        popover.popup()

    def duplicate_tab(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        if session.server_id is not None:
            server = self.find_server(session.server_id)
            if server is not None:
                self.open_terminal_tab(server)
            return
        shell = os.environ.get("SHELL") or GLib.find_program_in_path("bash") or "/bin/sh"
        self.open_process_terminal_tab(
            self.t("local_terminal"), [shell], None, working_directory=str(Path.home())
        )

    def detach_tab(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        notebook = session.notebook or self.notebook
        if notebook is not self.notebook or notebook.page_num(session.page) < 0:
            return
        notebook.remove_page(notebook.page_num(session.page))
        window = Gtk.Window(title=session.title, transient_for=self)
        window.set_default_size(860, 520)
        detached_notebook = Gtk.Notebook()
        detached_notebook.set_scrollable(True)
        detached_notebook.set_group_name("termia-terminals")
        detached_notebook.append_page(session.page, session.tab_label)
        self.configure_notebook_tab(detached_notebook, session.page)
        session.notebook = detached_notebook
        session.detached_window = window
        window.set_child(detached_notebook)
        window.connect("close-request", self.on_detached_window_close, session)
        window.present()

    def on_detached_window_close(self, window: Gtk.Window, session: TerminalSession) -> bool:
        notebook = session.notebook
        if notebook is not None and notebook is not self.notebook:
            page_num = notebook.page_num(session.page)
            if page_num >= 0:
                notebook.remove_page(page_num)
                page_num = self.notebook.append_page(session.page, session.tab_label)
                self.configure_notebook_tab(self.notebook, session.page)
                self.notebook.set_current_page(page_num)
        session.notebook = self.notebook
        session.detached_window = None
        return False

    def show_rename_tab_dialog(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        dialog = Gtk.Dialog(title=self.t("rename_tab"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        self.add_dialog_action_buttons(dialog, self.t("save"))
        entry = Gtk.Entry(text=session.title)
        entry.set_margin_top(12)
        entry.set_margin_bottom(12)
        entry.set_margin_start(12)
        entry.set_margin_end(12)
        dialog.get_content_area().append(entry)
        dialog.connect("response", self.on_rename_tab_response, entry, session)
        dialog.present()

    def on_rename_tab_response(
        self, dialog: Gtk.Dialog, response: Gtk.ResponseType, entry: Gtk.Entry, session: TerminalSession
    ) -> None:
        title = entry.get_text().strip()
        if response == Gtk.ResponseType.OK and title:
            session.title = title
            label = session.tab_label.get_first_child()
            if isinstance(label, Gtk.Label):
                label.set_label(title)
        dialog.destroy()

    def on_request_disconnect_session(self, _button: Gtk.Button, session: TerminalSession) -> None:
        if not session.connected:
            return
        if not self.store.data.app.confirm_disconnect:
            self.disconnect_session(session)
            return
        self.confirm_session_action(
            session,
            "Desconectar sesion",
            f"Quieres desconectar {session.title}?",
            "Desconectar",
            lambda: self.disconnect_session(session),
        )

    def disconnect_session(self, session: TerminalSession) -> None:
        if not session.connected:
            return
        session.disconnect_requested = True
        if session.child_pid is not None:
            try:
                os.kill(session.child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError:
                session.terminal.feed(b"No se pudo enviar SIGTERM al proceso ssh.\r\n")
                self.toast_label.set_label(f"No se pudo desconectar {session.title}")
                return
        self.record_session_duration(session)
        self.save_statistics_now()
        session.connected = False
        session.disconnect_button.set_sensitive(False)
        session.status_label.set_label(f"Desconectada: {session.title}")
        session.terminal.feed(b"\r\nSesion desconectada.\r\n")
        label = session.tab_label.get_first_child()
        if isinstance(label, Gtk.Label):
            label.set_label(f"{session.title} (desconectada)")
        self.toast_label.set_label(f"Sesion desconectada: {session.title}")
        if self.store.data.app.close_tab_on_disconnect:
            self.close_tab(session.id, session.page, disconnect=False)

    def confirm_session_action(
        self,
        session: TerminalSession,
        title: str,
        message: str,
        confirm_label: str,
        on_confirm: Any,
    ) -> None:
        dialog = Gtk.AlertDialog(message=title, detail=message)
        dialog.set_buttons(["Cancelar", confirm_label])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_confirm_session_action, (dialog, session, on_confirm))

    def on_confirm_session_action(
        self,
        _source: Gtk.AlertDialog,
        result: Gio.AsyncResult,
        data: tuple[Gtk.AlertDialog, TerminalSession, Any],
    ) -> None:
        dialog, session, on_confirm = data
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response == 1:
            on_confirm()

    def on_terminal_exited(
        self,
        _terminal: Vte.Terminal,
        _status: int,
        server: Server,
        session: TerminalSession,
    ) -> None:
        self.record_session_duration(session)
        self.save_statistics_now()
        session.connected = False
        session.disconnect_button.set_sensitive(False)
        self.open_tabs.pop(session.id, None)
        if session.disconnect_requested:
            session.status_label.set_label(f"Desconectada: {session.title}")
            self.toast_label.set_label(f"Sesion desconectada: {session.title}")
            return
        session.status_label.set_label(f"Cerrada: {session.title}")
        label = session.tab_label.get_first_child()
        if isinstance(label, Gtk.Label):
            label.set_label(f"{session.title} (cerrada)")
        self.toast_label.set_label(f"Sesion cerrada: {server.name}")

    def on_request_close_tab(self, _button: Gtk.Button, session_id: str, page: Gtk.Widget) -> None:
        session = self.open_tabs.get(session_id)
        if session and session.page == page and session.connected:
            self.confirm_session_action(
                session,
                "Cerrar pestanya",
                f"Quieres cerrar {session.title}? La sesion SSH se desconectara.",
                "Cerrar",
                lambda: self.close_tab(session_id, page, disconnect=True),
            )
            return
        self.close_tab(session_id, page, disconnect=False)

    def close_tab(self, session_id: str, page: Gtk.Widget, disconnect: bool) -> None:
        session = self.open_tabs.get(session_id)
        if disconnect and session and session.page == page and session.connected:
            self.disconnect_session(session)
        notebook = session.notebook if session and session.notebook is not None else self.notebook
        page_num = notebook.page_num(page)
        if page_num >= 0:
            notebook.remove_page(page_num)
        if session and session.detached_window is not None:
            window = session.detached_window
            session.detached_window = None
            window.destroy()
        self.open_tabs.pop(session_id, None)

    def on_request_clear_config(self) -> None:
        dialog = Gtk.AlertDialog(message=self.t("clear_config"), detail=self.t("clear_confirm"))
        dialog.set_buttons([self.t("cancel"), self.t("clear_config")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_clear_config_confirmed)

    def on_clear_config_confirmed(self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 1:
            return
        self.store.data.groups = []
        self.store.data.servers = []
        self.store.save()
        self.selected = None
        self.refresh_list()
        self.toast_label.set_label(self.t("clear_config"))

    def on_export_config(self) -> None:
        dialog = Gtk.FileDialog(title=self.t("export_config"))
        dialog.set_initial_name("termia.json")
        dialog.save(self, None, self.on_export_config_selected)

    def on_export_config_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        if file and file.get_path():
            self.store.save()
            Path(file.get_path()).write_text(self.store.path.read_text(encoding="utf-8"), encoding="utf-8")
            Path(file.get_path()).chmod(0o600)
            self.toast_label.set_label("Configuración exportada")

    def on_import_config(self) -> None:
        dialog = Gtk.FileDialog(title=self.t("import_config"))
        dialog.open(self, None, self.on_import_config_selected)

    def on_import_config_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if file and file.get_path():
            try:
                payload = json.loads(Path(file.get_path()).read_text(encoding="utf-8"))
                imported = StoreData(
                    groups=[Group(**item) for item in payload.get("groups", [])],
                    servers=[Server(**item) for item in payload.get("servers", [])],
                    terminal=TerminalSettings(**payload.get("terminal", {})),
                    app=AppSettings(**payload.get("app", {})),
                    statistics=self.store.data.statistics,
                )
            except (OSError, ValueError, TypeError) as exc:
                self.toast_label.set_label(f"No se pudo importar JSON: {exc}")
                return
            self.store.data = imported
            self.store.save()
            self.apply_app_theme()
            self.refresh_list()
            self.toast_label.set_label("Configuración importada")

    def on_import_asbru_config(self) -> None:
        dialog = Gtk.FileDialog(title=self.t("import_asbru"))
        dialog.open(self, None, self.on_import_asbru_config_selected)

    def on_import_asbru_config_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if not file or not file.get_path():
            return
        try:
            payload = yaml.safe_load(Path(file.get_path()).read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.toast_label.set_label(f"No se pudo importar YAML de Ásbrú: {exc}")
            return
        if not isinstance(payload, dict):
            self.toast_label.set_label("El YAML de Ásbrú no tiene un formato compatible")
            return
        if "__PAC__EXPORTED__PARTIAL_CONF" in payload:
            payload = payload["__PAC__EXPORTED__PARTIAL_CONF"]
        imported_groups, imported_servers = self.extract_asbru_connections(payload)
        added_groups, added_servers = self.merge_asbru_connections(imported_groups, imported_servers)
        self.store.save()
        self.refresh_list()
        self.toast_label.set_label(f"Ásbrú: {added_groups} grupos y {added_servers} servidores importados")

    def normalize_asbru_name(self, value: str) -> str:
        name = value.strip()
        suffix = " - copy"
        while name.lower().endswith(suffix):
            name = name[:-len(suffix)].rstrip()
        return name

    def extract_asbru_connections(
        self,
        payload: Any,
    ) -> tuple[list[tuple[str, str, str | None]], list[tuple[str, str, str, int, str | None, str]]]:
        environments = payload.get("environments", payload) if isinstance(payload, dict) else {}
        if not isinstance(environments, dict):
            return [], []

        groups: list[tuple[str, str, str | None]] = []
        servers: list[tuple[str, str, str, int, str | None, str]] = []
        group_uuids = {
            str(uuid)
            for uuid, node in environments.items()
            if isinstance(node, dict) and bool(node.get("_is_group"))
        }

        for uuid, node in environments.items():
            if not isinstance(node, dict):
                continue
            node_id = str(uuid)
            name = self.normalize_asbru_name(str(node.get("name") or node.get("description") or node_id))
            parent_uuid = str(node.get("parent")) if node.get("parent") in group_uuids else None
            if node_id in group_uuids:
                groups.append((node_id, name, parent_uuid))
                continue

            method = str(node.get("method") or node.get("protocol") or "ssh").lower()
            host = str(node.get("ip") or node.get("host") or node.get("hostname") or "").strip()
            if not host or method not in ("", "ssh"):
                continue
            user = str(node.get("user") or node.get("username") or node.get("passphrase user") or "").strip()
            if "@" in host and not user:
                user, host = host.split("@", 1)
            try:
                port = int(node.get("port") or node.get("ssh_port") or 22)
            except (TypeError, ValueError):
                port = 22
            public_key = str(node.get("public key") or "").strip()
            servers.append((name, host, user, port, parent_uuid, public_key))
        return groups, servers

    def merge_asbru_connections(
        self,
        groups: list[tuple[str, str, str | None]],
        servers: list[tuple[str, str, str, int, str | None, str]],
    ) -> tuple[int, int]:
        groups_by_path: dict[tuple[str | None, str], Group] = {
            (group.parent_id, group.name): group for group in self.store.data.groups
        }
        imported_ids: dict[str, str] = {}
        pending = groups.copy()
        added_groups = 0
        while pending:
            progressed = False
            for source_id, name, source_parent in pending[:]:
                if source_parent and source_parent not in imported_ids:
                    continue
                parent_id = imported_ids.get(source_parent)
                key = (parent_id, name)
                group = groups_by_path.get(key)
                if group is None:
                    group = Group(id=str(uuid4()), name=name, parent_id=parent_id)
                    self.store.data.groups.append(group)
                    groups_by_path[key] = group
                    added_groups += 1
                imported_ids[source_id] = group.id
                pending.remove((source_id, name, source_parent))
                progressed = True
            if not progressed:
                source_id, name, _source_parent = pending.pop(0)
                key = (None, name)
                group = groups_by_path.get(key)
                if group is None:
                    group = Group(id=str(uuid4()), name=name)
                    self.store.data.groups.append(group)
                    groups_by_path[key] = group
                    added_groups += 1
                imported_ids[source_id] = group.id

        existing = {(server.host, server.user, server.port, server.group_id) for server in self.store.data.servers}
        added_servers = 0
        for name, host, user, port, source_group_id, public_key in servers:
            group_id = imported_ids.get(source_group_id)
            key = (host, user, port, group_id)
            if key in existing:
                continue
            self.store.data.servers.append(
                Server(
                    id=str(uuid4()), name=self.normalize_asbru_name(name), host=host,
                    user=user, port=port, group_id=group_id, public_key=public_key,
                )
            )
            existing.add(key)
            added_servers += 1
        return added_groups, added_servers

    def on_app_preferences(self, _button: Gtk.Button) -> None:
        dialog = Gtk.Dialog(title=self.t("preferences"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(380, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        theme_combo = Gtk.ComboBoxText()
        for theme_id, label in APP_THEMES.items():
            theme_combo.append(theme_id, label)
        theme_combo.set_active_id(self.store.data.app.theme)

        language_combo = Gtk.ComboBoxText()
        for language_id, label in LANGUAGES.items():
            language_combo.append(language_id, label)
        language_combo.set_active_id(self.store.data.app.language)

        terminal_button = Gtk.Button(label=self.t("configure_terminal"))
        terminal_button.connect("clicked", self.on_terminal_settings)
        close_tab_on_disconnect = Gtk.CheckButton(label=self.t("close_tab_on_disconnect"))
        close_tab_on_disconnect.set_active(self.store.data.app.close_tab_on_disconnect)
        close_tab_on_disconnect.set_halign(Gtk.Align.START)
        confirm_disconnect = Gtk.CheckButton(label=self.t("confirm_disconnect"))
        confirm_disconnect.set_active(self.store.data.app.confirm_disconnect)
        confirm_disconnect.set_halign(Gtk.Align.START)
        confirm_close_app = Gtk.CheckButton(label=self.t("confirm_close_app"))
        confirm_close_app.set_active(self.store.data.app.confirm_close_app)
        confirm_close_app.set_halign(Gtk.Align.START)
        sudo_password_shortcut = Gtk.CheckButton(label=self.t("sudo_password_shortcut"))
        sudo_password_shortcut.set_active(self.store.data.app.sudo_password_shortcut)
        sudo_password_shortcut.set_halign(Gtk.Align.START)
        sudo_password_enter = Gtk.CheckButton(label=self.t("sudo_password_enter"))
        sudo_password_enter.set_active(self.store.data.app.sudo_password_enter)
        sudo_password_enter.set_halign(Gtk.Align.START)
        sudo_password_enter.set_sensitive(sudo_password_shortcut.get_active())
        sudo_password_shortcut.connect(
            "toggled", lambda current: sudo_password_enter.set_sensitive(current.get_active())
        )
        rows: list[tuple[str, Gtk.Widget]] = [
            (self.t("theme"), theme_combo),
            (self.t("language"), language_combo),
            (self.t("terminal"), terminal_button),
            ("", close_tab_on_disconnect),
            ("", confirm_disconnect),
            ("", confirm_close_app),
            ("", sudo_password_shortcut),
            ("", sudo_password_enter),
        ]
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            widget.set_hexpand(True)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)

        dialog.get_content_area().append(grid)
        dialog.connect(
            "response", self.on_app_preferences_response, theme_combo, language_combo,
            close_tab_on_disconnect, confirm_disconnect, confirm_close_app,
            sudo_password_shortcut, sudo_password_enter
        )
        dialog.present()

    def on_app_preferences_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        theme_combo: Gtk.ComboBoxText,
        language_combo: Gtk.ComboBoxText,
        close_tab_on_disconnect: Gtk.CheckButton,
        confirm_disconnect: Gtk.CheckButton,
        confirm_close_app: Gtk.CheckButton,
        sudo_password_shortcut: Gtk.CheckButton,
        sudo_password_enter: Gtk.CheckButton,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            previous_language = self.store.data.app.language
            self.store.update_app_settings(
                theme_combo.get_active_id() or "system",
                language_combo.get_active_id() or detect_system_language(),
                close_tab_on_disconnect.get_active(),
                confirm_disconnect.get_active(),
                confirm_close_app.get_active(),
                sudo_password_shortcut.get_active(),
                sudo_password_enter.get_active(),
            )
            self.apply_app_theme()
            if previous_language != self.store.data.app.language:
                self.toast_label.set_label(self.t("restart_language"))
        dialog.destroy()

    def on_terminal_settings(self, _button: Gtk.Button) -> None:
        dialog = Gtk.Dialog(title=self.t("terminal"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(540, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        settings = self.store.data.terminal
        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(14)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)

        font_button = Gtk.FontButton()
        font_button.set_font(f"{settings.font_family} {settings.font_size}")
        font_button.set_use_font(True)
        font_button.set_use_size(True)

        foreground_button = Gtk.ColorButton()
        foreground_button.set_rgba(parse_color(settings.foreground, "#f2f2f2"))
        foreground_button.set_title("Foreground")

        background_button = Gtk.ColorButton()
        background_button.set_rgba(parse_color(settings.background, "#101010"))
        background_button.set_title("Background")

        preview = Gtk.Label(label="usuario@servidor:~$ ssh ejemplo\nSalida de terminal")
        preview.set_xalign(0)
        preview.set_margin_top(10)
        preview.set_margin_bottom(10)
        preview.set_margin_start(12)
        preview.set_margin_end(12)
        preview.set_css_classes(["terminal-preview"])

        palette_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for palette_name, (foreground, background) in TERMINAL_PALETTES.items():
            palette_button = Gtk.Button(label=palette_name)
            palette_button.connect(
                "clicked",
                self.on_terminal_palette_clicked,
                foreground_button,
                background_button,
                foreground,
                background,
            )
            palette_box.append(palette_button)

        rows: list[tuple[str, Gtk.Widget]] = [
            (self.t("font_size"), font_button),
            (self.t("foreground"), foreground_button),
            (self.t("background"), background_button),
            (self.t("palettes"), palette_box),
        ]
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)

        content.append(grid)
        content.append(preview)

        self.update_terminal_preview(preview, font_button, foreground_button, background_button)
        font_button.connect(
            "notify::font",
            lambda *_args: self.update_terminal_preview(
                preview, font_button, foreground_button, background_button
            ),
        )
        foreground_button.connect(
            "notify::rgba",
            lambda *_args: self.update_terminal_preview(
                preview, font_button, foreground_button, background_button
            ),
        )
        background_button.connect(
            "notify::rgba",
            lambda *_args: self.update_terminal_preview(
                preview, font_button, foreground_button, background_button
            ),
        )

        dialog.connect(
            "response",
            self.on_terminal_settings_response,
            font_button,
            foreground_button,
            background_button,
        )
        dialog.present()

    def on_terminal_palette_clicked(
        self,
        _button: Gtk.Button,
        foreground_button: Gtk.ColorButton,
        background_button: Gtk.ColorButton,
        foreground: str,
        background: str,
    ) -> None:
        foreground_button.set_rgba(parse_color(foreground, "#f2f2f2"))
        background_button.set_rgba(parse_color(background, "#101010"))

    def update_terminal_preview(
        self,
        preview: Gtk.Label,
        font_button: Gtk.FontButton,
        foreground_button: Gtk.ColorButton,
        background_button: Gtk.ColorButton,
    ) -> None:
        font = Pango.FontDescription(font_button.get_font() or "Monospace 11")
        foreground = foreground_button.get_rgba().to_string()
        background = background_button.get_rgba().to_string()
        css = (
            ".terminal-preview {"
            f"font-family: '{font.get_family() or 'Monospace'}';"
            f"font-size: {max(font.get_size() // Pango.SCALE, 6)}pt;"
            f"color: {foreground};"
            f"background: {background};"
            "border-radius: 6px;"
            "}"
        )
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            preview.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def on_terminal_settings_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        font_button: Gtk.FontButton,
        foreground_button: Gtk.ColorButton,
        background_button: Gtk.ColorButton,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            font = Pango.FontDescription(font_button.get_font() or "Monospace 11")
            self.store.update_terminal_settings(
                font.get_family() or "Monospace",
                max(font.get_size() // Pango.SCALE, 6),
                foreground_button.get_rgba().to_string(),
                background_button.get_rgba().to_string(),
            )
            self.apply_terminal_settings_to_open_tabs()
            self.toast_label.set_label("Preferencias de terminal guardadas")
        dialog.destroy()

    def group_descendant_ids(self, group_id: str) -> set[str]:
        descendants: set[str] = set()
        pending = [group_id]
        while pending:
            parent_id = pending.pop()
            children = [group.id for group in self.store.data.groups if group.parent_id == parent_id]
            descendants.update(children)
            pending.extend(children)
        return descendants

    def group_path_labels(self) -> list[tuple[Group, str]]:
        groups_by_id = {group.id: group for group in self.store.data.groups}

        def path_label(group: Group) -> str:
            names = [group.name]
            visited = {group.id}
            parent_id = group.parent_id
            while parent_id and parent_id in groups_by_id and parent_id not in visited:
                parent = groups_by_id[parent_id]
                names.append(parent.name)
                visited.add(parent_id)
                parent_id = parent.parent_id
            return " / ".join(reversed(names))

        return sorted(
            ((group, path_label(group)) for group in self.store.data.groups),
            key=lambda item: item[1].lower(),
        )

    def show_group_dialog(self, group: Group | None = None) -> None:
        dialog = Gtk.Dialog(title=self.t("edit_group") if group else self.t("new_group"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(360, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        entry = Gtk.Entry()
        entry.set_placeholder_text(self.t("name"))
        parent_combo = Gtk.ComboBoxText()
        parent_combo.append("", self.t("no_parent_group"))
        excluded_ids = self.group_descendant_ids(group.id) | {group.id} if group else set()
        for candidate, path_label in self.group_path_labels():
            if candidate.id not in excluded_ids:
                parent_combo.append(candidate.id, path_label)
        parent_combo.set_active_id(group.parent_id if group and group.parent_id not in excluded_ids else "")
        if group:
            entry.set_text(group.name)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.attach(Gtk.Label(label=self.t("name"), xalign=0), 0, 0, 1, 1)
        grid.attach(entry, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label=self.t("parent_group"), xalign=0), 0, 1, 1, 1)
        grid.attach(parent_combo, 1, 1, 1, 1)
        entry.set_hexpand(True)
        parent_combo.set_hexpand(True)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.append(grid)

        dialog.connect("response", self.on_group_dialog_response, entry, parent_combo, group)
        dialog.present()

    def on_group_dialog_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        entry: Gtk.Entry,
        parent_combo: Gtk.ComboBoxText,
        group: Group | None,
    ) -> None:
        name = entry.get_text().strip()
        parent_id = parent_combo.get_active_id() or None
        if response == Gtk.ResponseType.OK and name:
            if group:
                self.store.update_group(group.id, name, parent_id)
            else:
                self.store.add_group(name, parent_id)
            self.refresh_list()
        dialog.destroy()

    def show_server_dialog(self, server: Server | None = None) -> None:
        dialog = Gtk.Dialog(title=self.t("edit_server") if server else self.t("new_server"), transient_for=self, modal=True)
        dialog.set_resizable(False)
        dialog.set_default_size(460, -1)
        self.add_dialog_action_buttons(dialog, self.t("save"))

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        name_entry = Gtk.Entry()
        host_entry = Gtk.Entry()
        user_entry = Gtk.Entry()
        port_spin = Gtk.SpinButton.new_with_range(1, 65535, 1)
        group_combo = Gtk.ComboBoxText()
        password_entry = Gtk.PasswordEntry()
        password_entry.set_show_peek_icon(True)
        public_key_entry = Gtk.Entry()
        for widget in (name_entry, host_entry, user_entry, port_spin, group_combo, password_entry, public_key_entry):
            widget.set_hexpand(True)
            widget.set_size_request(260, -1)

        group_combo.append("", self.t("no_group"))
        for group, path_label in self.group_path_labels():
            group_combo.append(group.id, path_label)
        group_combo.set_active_id("")

        if server:
            name_entry.set_text(server.name)
            host_entry.set_text(server.host)
            user_entry.set_text(server.user)
            port_spin.set_value(server.port)
            group_combo.set_active_id(server.group_id or "")
            password_entry.set_text(server.password)
            public_key_entry.set_text(server.public_key)
        else:
            port_spin.set_value(22)

        rows: list[tuple[str, Gtk.Widget]] = [
            (self.t("name"), name_entry),
            (self.t("host"), host_entry),
            (self.t("ssh_user"), user_entry),
            (self.t("ssh_port"), port_spin),
            (self.t("group"), group_combo),
            (self.t("password"), password_entry),
            (self.t("public_key"), public_key_entry),
        ]
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)

        dialog.get_content_area().append(grid)
        warning = Gtk.Label(label=self.t("password_warning"))
        warning.set_wrap(True)
        warning.set_xalign(0)
        warning.add_css_class("warning")
        dialog.get_content_area().append(warning)
        dialog.connect(
            "response",
            self.on_server_dialog_response,
            {
                "name": name_entry,
                "host": host_entry,
                "user": user_entry,
                "port": port_spin,
                "group": group_combo,
                "password": password_entry,
                "public_key": public_key_entry,
            },
            server,
        )
        dialog.present()

    def on_server_dialog_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        widgets: dict[str, Any],
        server: Server | None,
    ) -> None:
        name = widgets["name"].get_text().strip()
        host = widgets["host"].get_text().strip()
        user = widgets["user"].get_text().strip()
        port = int(widgets["port"].get_value())
        group_id = widgets["group"].get_active_id() or None
        password = widgets["password"].get_text()
        public_key = widgets["public_key"].get_text().strip()

        if response == Gtk.ResponseType.OK and name and host and user:
            if server:
                self.store.update_server(server.id, name, host, user, port, group_id, password, public_key)
            else:
                self.store.add_server(name, host, user, port, group_id, password, public_key)
            self.refresh_list()
        dialog.destroy()


class TermiaApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = TermiaWindow(self)
        window.present()


def main() -> int:
    app = TermiaApp()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
