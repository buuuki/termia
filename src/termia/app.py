#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import locale
import os
import signal
import shlex
import subprocess
import time
from urllib.parse import unquote, urlparse

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
ABOUT_IMAGE = APP_DIR / "assets" / "termia.svg"
ISSUES_URL = "https://github.com/buuuki/termia/issues"

DEFAULT_LS_COLORS = 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=00:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.avif=01;35:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.webp=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:*~=00;90:*#=00;90:*.bak=00;90:*.crdownload=00;90:*.dpkg-dist=00;90:*.dpkg-new=00;90:*.dpkg-old=00;90:*.dpkg-tmp=00;90:*.old=00;90:*.orig=00;90:*.part=00;90:*.rej=00;90:*.rpmnew=00;90:*.rpmorig=00;90:*.rpmsave=00;90:*.swp=00;90:*.tmp=00;90:*.ucf-dist=00;90:*.ucf-new=00;90:*.ucf-old=00;90:'
LEGACY_ANSI_PALETTE = ['#2e3436', '#cc0000', '#4e9a06', '#c4a000', '#3465a4', '#75507b', '#06989a', '#d3d7cf', '#555753', '#ef2929', '#8ae234', '#fce94f', '#729fcf', '#ad7fa8', '#34e2e2', '#eeeeec']
DEFAULT_ANSI_PALETTE = ['#2e3436', '#b45d58', '#6f8f5f', '#aa8750', '#5f7f9f', '#8a6f8f', '#5f9292', '#c9c9c9', '#646b70', '#cf6f68', '#8fbf77', '#d2b45f', '#82a8c9', '#aa8aaa', '#83c4c4', '#eeeeec']
TERMINAL_PALETTES = {
    "Ubuntu": ("#eeeeec", "#300a24"),
    "Polaris": ("#d8dee9", "#1f2430"),
    "Solarized": ("#839496", "#002b36"),
    "Tango": ("#eeeeec", "#2e3436"),
    "Claro": ("#2e3436", "#f6f5f4"),
}
PROMPT_PRESETS = {
    "Verde": (r"\u@\h:\w\$ ", "#8ae234"),
    "Azul": (r"\u@\h:\w\$ ", "#729fcf"),
    "Ambar": (r"\u@\h:\w\$ ", "#fce94f"),
    "Rojo": (r"\u@\h \W \$ ", "#ef2929"),
    "Blanco": (r"\u@\h:\w\$ ", "#eeeeec"),
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
        "servers": "Mostrar u ocultar listado de servidores", "new_group": "Nuevo grupo", "new_server": "Nuevo servidor",
        "terminal": "Terminal", "prompt": "Prompt", "general": "General", "preferences": "Preferencias", "filter_servers": "Filtrar servidores",
        "connect": "Conectar", "edit_server": "Editar servidor", "delete_server": "Eliminar servidor", "clone_connection": "Clonar conexión",
        "edit_group": "Editar grupo", "delete_group": "Eliminar grupo", "no_group": "Sin grupo",
        "parent_group": "Grupo padre", "no_parent_group": "Sin grupo padre",
        "cancel": "Cancelar", "close": "Cerrar", "save": "Guardar", "name": "Nombre", "host": "IP o host",
        "ssh_user": "Usuario SSH", "ssh_port": "Puerto SSH", "group": "Grupo",
        "password": "Contraseña", "public_key": "Clave SSH privada",
        "ssh_fingerprint_manual": "Host nuevo: responde al fingerprint en esta terminal. Después introduce la contraseña manualmente o con Super+Shift+P.",
        "password_warning": "Aviso: la contraseña se guardará en texto plano en connections.json.",
        "server_required_fields": "Nombre, host y usuario SSH son obligatorios.",
        "required_field": "* Campo obligatorio",
        "reconnect_prompt": "Pulsa Enter para reconectar.",
        "close_tab_on_ssh_exit": "Cerrar la pestaña al salir de una sesión SSH con exit",
        "open_local_terminal_on_startup": "Abrir terminal local al iniciar Termia",
        "delete_group_confirm": "Eliminar grupo",
        "delete_group_confirm_detail": "¿Quieres eliminar {name}? También se eliminarán todos sus subgrupos y servidores. Esta acción no se puede deshacer.",
        "group_deleted": "Grupo eliminado: {name}",
        "theme": "Tema", "language": "Idioma", "restart_language": "El idioma se aplicará al reiniciar la aplicación.",
        "close_tab": "Cerrar pestaña", "disconnect": "Desconectar", "connecting": "Conectando",
        "close_session_title": "Cerrar sesión", "close_ssh_session_confirm": "¿Quieres cerrar esta sesión SSH? La conexión se desconectará.", "close_local_session_confirm": "¿Quieres cerrar este terminal local? El proceso en ejecución se finalizará.",
        "close_tab_on_disconnect": "Cerrar la pestaña al desconectar una sesión",
        "show_session_status_bar": "Mostrar barra de estado de la sesión", "hide_status_bar": "Ocultar",
        "confirm_disconnect": "Confirmar antes de desconectar o cerrar una sesión activa", "confirm_close_app": "Confirmar para cerrar Termia",
        "sudo_password_shortcut": "Enviar contraseña con Super+Shift+P",
        "sudo_password_enter": "Enviar contraseña y pulsar Enter",
        "sudo_password_sent": "Contraseña guardada enviada a la terminal",
        "sudo_password_unavailable": "Esta terminal no tiene una contraseña guardada",
        "close_app": "Cerrar Termia", "close_app_confirm": "¿Quieres cerrar Termia?",
        "font_size": "Fuente y tamaño", "custom_prompt": "Personalizar prompt local", "prompt_template": "Plantilla PS1", "prompt_color": "Color del prompt", "prompt_presets": "Temas de prompt", "prompt_datetime": "Fecha y hora", "prompt_datetime_none": "Sin fecha/hora", "prompt_datetime_time": "Hora", "prompt_datetime_time_seconds": "Hora y segundos", "prompt_datetime_date": "Fecha", "prompt_datetime_both": "Fecha y hora", "prompt_settings_saved": "Configuración de prompt guardada", "terminal_settings_saved": "Preferencias de terminal guardadas", "terminal_font_size_changed": "Tamaño de fuente del terminal: {size}", "foreground": "Foreground", "background": "Background", "palettes": "Paletas",
        "configuration": "Configuración", "connections_file": "Importar/Exportar", "export_config": "Exportar configuración", "import_config": "Importar configuración",
        "summary": "{groups} grupos · {subgroups} subgrupos · {servers} servidores",
        "import_asbru": "Importar configuración de Ásbrú", "clear_config": "Eliminar toda la configuración", "configure_terminal": "Configurar terminal", "local_terminal": "Terminal local", "new_tab": "Nueva pestaña",
        "statistics": "Estadísticas", "statistics_title": "Estadísticas", "top_servers": "Servidores más usados", "no_statistics": "Sin estadísticas todavía", "sessions": "Sesiones", "duration": "Duración", "connections": "Conexiones", "commands": "Comandos", "keystrokes": "Pulsaciones",
        "global": "Global", "current_run": "Ejecución actual", "shortest_duration": "Duración más corta", "longest_duration": "Duración más larga", "average_duration": "Duración media",
        "copy": "Copiar", "paste": "Pegar", "session_statistics": "Estadísticas de la sesión", "server_connections": "Conexiones globales a este servidor",
        "clear_confirm": "¿Quieres eliminar todos los grupos y servidores? Esta acción no se puede deshacer.", "rename_tab": "Renombrar pestaña", "duplicate_tab": "Duplicar pestaña", "detach_tab": "Mover a nueva ventana",
        "expand_all": "Expandir todos los grupos", "collapse_all": "Contraer todos los grupos",
        "help": "Ayuda", "about": "Acerca de", "report_issue": "Informar de un problema",
        "main_menu": "Menú principal",
        "help_title": "Ayuda de Termia",
        "help_content": (
            "Termia es un gestor de conexiones SSH con terminales embebidas.\n\n"
            "Características principales:\n"
            "- Organiza servidores en grupos y subgrupos.\n"
            "- Crea, edita, elimina, clona y filtra conexiones SSH.\n"
            "- Abre conexiones y terminales locales en pestañas embebidas, compactas y desacoplables.\n"
            "- Muestra un dashboard de estadísticas con métricas globales, duración y servidores más usados, además de estadísticas por sesión.\n"
            "- La barra de estado de sesión muestra estado, PID, tiempo y desconexión; puede mostrarse desde General, ocultarse por sesión y restaurarse desde el menú contextual.\n"
            "- Permite enviar opcionalmente la contraseña guardada con Super+Shift+P.\n"
            "- Configura por separado opciones generales, terminal VTE y prompt PS1.\n"
            "- El prompt local permite color, temas predefinidos, hora, fecha y previsualización sin modificar sesiones remotas.\n"
            "- Importa y exporta configuraciones, incluida la importación básica desde Ásbrú.\n\n"
            "Uso rápido:\n"
            "Utiliza los iconos del panel lateral para crear grupos o servidores. Haz doble clic "
            "sobre un servidor para conectar. Usa el botón derecho en servidores, pestañas o terminales "
            "para ver acciones contextuales como duplicar, desconectar, copiar, pegar, mostrar la barra "
            "de estado o ver estadísticas."
        ),
        "about_content": "Gestor de conexiones SSH con terminales embebidas",
    },
    "ca": {
        "servers": "Mostrar o amagar el llistat de servidors", "new_group": "Nou grup", "new_server": "Nou servidor",
        "terminal": "Terminal", "prompt": "Prompt", "general": "General", "preferences": "Preferències", "filter_servers": "Filtrar servidors",
        "connect": "Connectar", "edit_server": "Editar servidor", "delete_server": "Eliminar servidor", "clone_connection": "Clonar connexió",
        "edit_group": "Editar grup", "delete_group": "Eliminar grup", "no_group": "Sense grup",
        "parent_group": "Grup pare", "no_parent_group": "Sense grup pare",
        "cancel": "Cancel·lar", "close": "Tancar", "save": "Desar", "name": "Nom", "host": "IP o host",
        "ssh_user": "Usuari SSH", "ssh_port": "Port SSH", "group": "Grup",
        "password": "Contrasenya", "public_key": "Clau SSH privada",
        "ssh_fingerprint_manual": "Host nou: respon al fingerprint en aquest terminal. Després introdueix la contrasenya manualment o amb Super+Shift+P.",
        "password_warning": "Avís: la contrasenya es desarà en text pla a connections.json.",
        "server_required_fields": "El nom, el host i l'usuari SSH són obligatoris.",
        "required_field": "* Camp obligatori",
        "reconnect_prompt": "Prem Enter per reconnectar.",
        "close_tab_on_ssh_exit": "Tancar la pestanya en sortir d'una sessió SSH amb exit",
        "open_local_terminal_on_startup": "Obrir un terminal local en iniciar Termia",
        "delete_group_confirm": "Eliminar grup",
        "delete_group_confirm_detail": "Vols eliminar {name}? També s'eliminaran tots els subgrups i servidors. Aquesta acció no es pot desfer.",
        "group_deleted": "Grup eliminat: {name}",
        "theme": "Tema", "language": "Idioma", "restart_language": "L'idioma s'aplicarà en reiniciar l'aplicació.",
        "close_tab": "Tancar pestanya", "disconnect": "Desconnectar", "connecting": "Connectant",
        "close_session_title": "Tancar sessió", "close_ssh_session_confirm": "Vols tancar aquesta sessió SSH? La connexió es desconnectarà.", "close_local_session_confirm": "Vols tancar aquest terminal local? El procés en execució es finalitzarà.",
        "close_tab_on_disconnect": "Tancar la pestanya en desconnectar una sessió",
        "show_session_status_bar": "Mostrar barra d'estat de la sessió", "hide_status_bar": "Amagar",
        "confirm_disconnect": "Confirmar abans de desconnectar o tancar una sessió activa", "confirm_close_app": "Confirmar per tancar Termia",
        "sudo_password_shortcut": "Enviar contrasenya amb Super+Shift+P",
        "sudo_password_enter": "Enviar contrasenya i prémer Enter",
        "sudo_password_sent": "Contrasenya desada enviada al terminal",
        "sudo_password_unavailable": "Aquest terminal no té cap contrasenya desada",
        "close_app": "Tancar Termia", "close_app_confirm": "Vols tancar Termia?",
        "font_size": "Tipus de lletra i mida", "custom_prompt": "Personalitzar prompt local", "prompt_template": "Plantilla PS1", "prompt_color": "Color del prompt", "prompt_presets": "Temes de prompt", "prompt_datetime": "Data i hora", "prompt_datetime_none": "Sense data/hora", "prompt_datetime_time": "Hora", "prompt_datetime_time_seconds": "Hora i segons", "prompt_datetime_date": "Data", "prompt_datetime_both": "Data i hora", "prompt_settings_saved": "Configuració del prompt desada", "terminal_settings_saved": "Preferències del terminal desades", "terminal_font_size_changed": "Mida de la lletra del terminal: {size}", "foreground": "Primer pla", "background": "Fons", "palettes": "Paletes",
        "configuration": "Configuració", "connections_file": "Importar/Exportar", "export_config": "Exportar configuració", "import_config": "Importar configuració",
        "summary": "{groups} grups · {subgroups} subgrups · {servers} servidors",
        "import_asbru": "Importar configuració d'Ásbrú", "clear_config": "Eliminar tota la configuració", "configure_terminal": "Configurar terminal", "local_terminal": "Terminal local", "new_tab": "Pestanya nova",
        "statistics": "Estadístiques", "statistics_title": "Estadístiques", "top_servers": "Servidors més usats", "no_statistics": "Encara no hi ha estadístiques", "sessions": "Sessions", "duration": "Durada", "connections": "Connexions", "commands": "Ordres", "keystrokes": "Pulsacions",
        "global": "Global", "current_run": "Execució actual", "shortest_duration": "Durada més curta", "longest_duration": "Durada més llarga", "average_duration": "Durada mitjana",
        "copy": "Copiar", "paste": "Enganxar", "session_statistics": "Estadístiques de la sessió", "server_connections": "Connexions globals a aquest servidor",
        "clear_confirm": "Vols eliminar tots els grups i servidors? Aquesta acció no es pot desfer.", "rename_tab": "Canviar el nom de la pestanya", "duplicate_tab": "Duplicar pestanya", "detach_tab": "Moure a una finestra nova",
        "expand_all": "Expandir tots els grups", "collapse_all": "Contraure tots els grups",
        "help": "Ajuda", "about": "Quant a", "report_issue": "Informar d'un problema",
        "main_menu": "Menú principal",
        "help_title": "Ajuda de Termia",
        "help_content": (
            "Termia és un gestor de connexions SSH amb terminals incrustats.\n\n"
            "Característiques principals:\n"
            "- Organitza servidors en grups i subgrups.\n"
            "- Crea, edita, elimina, clona i filtra connexions SSH.\n"
            "- Obre connexions i terminals locals en pestanyes incrustades, compactes i desacoblables.\n"
            "- Mostra un dashboard d'estadístiques amb mètriques globals, durada i servidors més usats, a més d'estadístiques per sessió.\n"
            "- La barra d'estat de sessió mostra estat, PID, temps i desconnexió; es pot mostrar des de General, amagar per sessió i restaurar des del menú contextual.\n"
            "- Permet enviar opcionalment la contrasenya desada amb Super+Shift+P.\n"
            "- Configura per separat opcions generals, terminal VTE i prompt PS1.\n"
            "- El prompt local permet color, temes predefinits, hora, data i previsualització sense modificar sessions remotes.\n"
            "- Importa i exporta configuracions, inclosa la importació bàsica des d'Ásbrú.\n\n"
            "Ús ràpid:\n"
            "Utilitza les icones del panell lateral per crear grups o servidors. Fes doble clic "
            "sobre un servidor per connectar. Utilitza el botó dret en servidors, pestanyes o terminals "
            "per veure accions contextuals com duplicar, desconnectar, copiar, enganxar, mostrar la barra "
            "d'estat o veure estadístiques."
        ),
        "about_content": "Gestor de connexions SSH amb terminals incrustats",
    },
    "en": {
        "servers": "Show or hide server list", "new_group": "New group", "new_server": "New server",
        "terminal": "Terminal", "prompt": "Prompt", "general": "General", "preferences": "Preferences", "filter_servers": "Filter servers",
        "connect": "Connect", "edit_server": "Edit server", "delete_server": "Delete server", "clone_connection": "Clone connection",
        "edit_group": "Edit group", "delete_group": "Delete group", "no_group": "No group",
        "parent_group": "Parent group", "no_parent_group": "No parent group",
        "cancel": "Cancel", "close": "Close", "save": "Save", "name": "Name", "host": "IP or host",
        "ssh_user": "SSH user", "ssh_port": "SSH port", "group": "Group",
        "password": "Password", "public_key": "Private SSH key",
        "ssh_fingerprint_manual": "New host: answer the fingerprint prompt in this terminal. Then enter the password manually or with Super+Shift+P.",
        "password_warning": "Warning: the password will be stored as plain text in connections.json.",
        "server_required_fields": "Name, host, and SSH user are required.",
        "required_field": "* Required field",
        "reconnect_prompt": "Press Enter to reconnect.",
        "close_tab_on_ssh_exit": "Close the tab when leaving an SSH session with exit",
        "open_local_terminal_on_startup": "Open a local terminal when Termia starts",
        "delete_group_confirm": "Delete group",
        "delete_group_confirm_detail": "Delete {name}? All nested subgroups and servers will also be deleted. This action cannot be undone.",
        "group_deleted": "Group deleted: {name}",
        "theme": "Theme", "language": "Language", "restart_language": "The language will apply after restarting the application.",
        "close_tab": "Close tab", "disconnect": "Disconnect", "connecting": "Connecting",
        "close_session_title": "Close session", "close_ssh_session_confirm": "Do you want to close this SSH session? The connection will be disconnected.", "close_local_session_confirm": "Do you want to close this local terminal? The running process will be terminated.",
        "close_tab_on_disconnect": "Close the tab when disconnecting a session",
        "show_session_status_bar": "Show session status bar", "hide_status_bar": "Hide",
        "confirm_disconnect": "Confirm before disconnecting or closing an active session", "confirm_close_app": "Confirm before closing Termia",
        "sudo_password_shortcut": "Send password with Super+Shift+P",
        "sudo_password_enter": "Send password and press Enter",
        "sudo_password_sent": "Saved password sent to the terminal",
        "sudo_password_unavailable": "This terminal does not have a saved password",
        "close_app": "Close Termia", "close_app_confirm": "Do you want to close Termia?",
        "font_size": "Font and size", "custom_prompt": "Customize local prompt", "prompt_template": "PS1 template", "prompt_color": "Prompt color", "prompt_presets": "Prompt themes", "prompt_datetime": "Date and time", "prompt_datetime_none": "No date/time", "prompt_datetime_time": "Time", "prompt_datetime_time_seconds": "Time with seconds", "prompt_datetime_date": "Date", "prompt_datetime_both": "Date and time", "prompt_settings_saved": "Prompt settings saved", "terminal_settings_saved": "Terminal preferences saved", "terminal_font_size_changed": "Terminal font size: {size}", "foreground": "Foreground", "background": "Background", "palettes": "Palettes",
        "configuration": "Configuration", "connections_file": "Import/Export", "export_config": "Export configuration", "import_config": "Import configuration",
        "summary": "{groups} groups · {subgroups} subgroups · {servers} servers",
        "import_asbru": "Import Ásbrú configuration", "clear_config": "Delete all configuration", "configure_terminal": "Configure terminal", "local_terminal": "Local terminal", "new_tab": "New tab",
        "statistics": "Statistics", "statistics_title": "Statistics", "top_servers": "Most used servers", "no_statistics": "No statistics yet", "sessions": "Sessions", "duration": "Duration", "connections": "Connections", "commands": "Commands", "keystrokes": "Keystrokes",
        "global": "Global", "current_run": "Current run", "shortest_duration": "Shortest duration", "longest_duration": "Longest duration", "average_duration": "Average duration",
        "copy": "Copy", "paste": "Paste", "session_statistics": "Session statistics", "server_connections": "Global connections to this server",
        "clear_confirm": "Delete all groups and servers? This action cannot be undone.", "rename_tab": "Rename tab", "duplicate_tab": "Duplicate tab", "detach_tab": "Move to new window",
        "expand_all": "Expand all groups", "collapse_all": "Collapse all groups",
        "help": "Help", "about": "About", "report_issue": "Report an issue",
        "main_menu": "Main menu",
        "help_title": "Termia Help",
        "help_content": (
            "Termia is an SSH connection manager with embedded terminals.\n\n"
            "Main features:\n"
            "- Organize servers into groups and subgroups.\n"
            "- Create, edit, delete, clone and filter SSH connections.\n"
            "- Open connections and local terminals in embedded, compact and detachable tabs.\n"
            "- View a statistics dashboard with global metrics, durations and most used servers, plus per-session statistics.\n"
            "- The session status bar shows status, PID, duration and disconnect controls; it can be enabled from General, hidden per session and restored from the context menu.\n"
            "- Optionally send the saved password with Super+Shift+P.\n"
            "- Configure general options, the VTE terminal and the PS1 prompt separately.\n"
            "- The local prompt supports color, presets, time, date and live preview without modifying remote sessions.\n"
            "- Import and export configurations, including basic imports from Ásbrú.\n\n"
            "Quick start:\n"
            "Use the sidebar icons to create groups or servers. Double-click a server to connect. "
            "Right-click servers, tabs or terminals to access contextual actions such as duplicate, "
            "disconnect, copy, paste, show the status bar or view statistics."
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
    font_family: str = "JetBrains Mono"
    font_size: int = 13
    foreground: str = "#eeeeec"
    background: str = "#2e3436"
    ls_colors: str = DEFAULT_LS_COLORS
    ansi_palette: list[str] = field(default_factory=lambda: DEFAULT_ANSI_PALETTE.copy())
    prompt_enabled: bool = False
    prompt_template: str = r"\u@\h:\w\$ "
    prompt_color: str = "#8ae234"


@dataclass
class AppSettings:
    theme: str = "dark"
    language: str = field(default_factory=detect_system_language)
    close_tab_on_disconnect: bool = False
    close_tab_on_ssh_exit: bool = False
    open_local_terminal_on_startup: bool = True
    show_session_status_bar: bool = True
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
        app_payload = payload.get("app", {})
        app_fields = AppSettings.__dataclass_fields__
        terminal = TerminalSettings(**payload.get("terminal", {}))
        repaired = False
        if (
            terminal.font_family == "Ubuntu Mono"
            and terminal.font_size == 13
            and terminal.foreground == "#839496"
            and terminal.background == "#002b36"
        ):
            terminal.font_family = "JetBrains Mono"
            terminal.foreground = "#eeeeec"
            terminal.background = "#2e3436"
            repaired = True
        if terminal.ansi_palette == LEGACY_ANSI_PALETTE:
            terminal.ansi_palette = DEFAULT_ANSI_PALETTE.copy()
            repaired = True
        self.data = StoreData(
            groups=[Group(**item) for item in payload.get("groups", [])],
            servers=[Server(**item) for item in payload.get("servers", [])],
            terminal=terminal,
            app=AppSettings(**{key: value for key, value in app_payload.items() if key in app_fields}),
            statistics=self.statistics_store.data,
        )
        repaired = self.repair_references() or repaired
        if "statistics" in payload or repaired:
            self.save()

    def repair_references(self) -> bool:
        group_ids = {group.id for group in self.data.groups}
        repaired = False
        for group in self.data.groups:
            if group.parent_id is not None and group.parent_id not in group_ids:
                group.parent_id = None
                repaired = True
        for server in self.data.servers:
            if server.group_id is not None and server.group_id not in group_ids:
                server.group_id = None
                repaired = True
        return repaired

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
        prompt_enabled: bool | None = None,
        prompt_template: str | None = None,
        prompt_color: str | None = None,
    ) -> None:
        current = self.data.terminal
        self.data.terminal = TerminalSettings(
            font_family=font_family.strip() or "Monospace",
            font_size=max(6, min(font_size, 72)),
            foreground=foreground.strip() or "#f2f2f2",
            background=background.strip() or "#101010",
            ls_colors=ls_colors if ls_colors is not None else current.ls_colors,
            ansi_palette=current.ansi_palette or DEFAULT_ANSI_PALETTE.copy(),
            prompt_enabled=current.prompt_enabled if prompt_enabled is None else prompt_enabled,
            prompt_template=(prompt_template if prompt_template is not None else current.prompt_template) if (prompt_template if prompt_template is not None else current.prompt_template).strip() else r"\u@\h:\w\$ ",
            prompt_color=(prompt_color if prompt_color is not None else current.prompt_color).strip() or "#8ae234",
        )
        self.save()

    def update_prompt_settings(self, enabled: bool, template: str, color: str) -> None:
        current = self.data.terminal
        self.data.terminal = TerminalSettings(
            font_family=current.font_family,
            font_size=current.font_size,
            foreground=current.foreground,
            background=current.background,
            ls_colors=current.ls_colors,
            ansi_palette=current.ansi_palette or DEFAULT_ANSI_PALETTE.copy(),
            prompt_enabled=enabled,
            prompt_template=template if template.strip() else r"\u@\h:\w\$ ",
            prompt_color=color.strip() or "#8ae234",
        )
        self.save()

    def update_app_settings(
        self, theme: str, language: str, close_tab_on_disconnect: bool,
        confirm_disconnect: bool, confirm_close_app: bool,
        sudo_password_shortcut: bool, sudo_password_enter: bool, close_tab_on_ssh_exit: bool,
        open_local_terminal_on_startup: bool, show_session_status_bar: bool,
    ) -> None:
        self.data.app = AppSettings(
            theme=theme if theme in APP_THEMES else "system",
            language=language if language in LANGUAGES else detect_system_language(),
            close_tab_on_disconnect=close_tab_on_disconnect,
            close_tab_on_ssh_exit=close_tab_on_ssh_exit,
            open_local_terminal_on_startup=open_local_terminal_on_startup,
            show_session_status_bar=show_session_status_bar,
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
    status_bar: Gtk.Widget
    started_at: float
    title_locked: bool = False
    last_directory_title: str = ""
    detached_window: Gtk.Window | None = None
    timeout_id: int | None = None
    child_pid: int | None = None
    connected: bool = True
    disconnect_requested: bool = False
    pending_reconnect: bool = False
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
        self.group_expanded_state: dict[str, bool] = {}
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
        if self.store.data.app.open_local_terminal_on_startup:
            GLib.idle_add(self.open_startup_local_terminal)

    def open_startup_local_terminal(self) -> bool:
        if not self.open_tabs:
            self.on_open_local_terminal(None)
        return GLib.SOURCE_REMOVE

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
        gtk_settings = Gtk.Settings.get_default()
        prefer_dark = bool(
            gtk_settings.get_property("gtk-application-prefer-dark-theme")
        ) if gtk_settings is not None else False
        menu_bg = b"#3a3a3a" if self.store.data.app.theme == "dark" or prefer_dark else b"#f6f6f6"
        provider = Gtk.CssProvider()
        provider.load_from_data(
            b"@define-color termia_menu_bg " + menu_bg + b"; "
            b".termia-tree-item { border-radius: 4px; } "
            b".termia-server-item { padding-top: 2px; padding-bottom: 2px; } "
            b".prompt-preset-button { padding: 1px 6px; min-height: 24px; } "
            b"headerbar { background: @headerbar_backdrop_color; border-bottom-width: 0; box-shadow: none; } "
            b"headerbar:backdrop { background: @headerbar_backdrop_color; } "
            b".termia-session-tabs { background: @headerbar_backdrop_color; padding: 4px 4px 3px 4px; "
            b"border: 0; box-shadow: none; } "
            b".termia-terminal-stack { border: 0; box-shadow: none; } "
            b"popover.termia-menu-popover > contents { background: @termia_menu_bg; "
            b"background-color: @termia_menu_bg; background-image: none; opacity: 1; } "
            b".termia-menu-panel { background: @termia_menu_bg; "
            b"background-color: @termia_menu_bg; background-image: none; opacity: 1; } "
            b".termia-menu-panel list { background: transparent; background-color: transparent; } "
            b".termia-tab-label { padding: 7px 10px; margin: 0 2px; border-radius: 8px; "
            b"background: transparent; border: 0; box-shadow: none; } "
            b".termia-tab-label:hover { background: alpha(@theme_fg_color, 0.06); } "
            b".termia-tab-label.active { background: alpha(@theme_fg_color, 0.13); } "
            b".termia-tab-title { font-size: 1.05em; } "
            b".termia-tab-close { padding: 0; min-width: 18px; min-height: 18px; } "
            b".termia-status-hide { padding: 0 6px; min-height: 18px; font-size: 0.85em; } "
            b".termia-disconnect-button { padding: 0 6px; min-height: 18px; font-size: 0.85em; } "
            b".stat-card { padding: 10px 12px; border: 1px solid @borders; border-radius: 6px; "
            b"background: alpha(@theme_bg_color, 0.58); } "
            b".stat-card-title { font-size: 0.82em; } "
            b".stat-card-value { font-size: 1.55em; font-weight: 700; } "
            b".stat-card-subtitle { font-size: 0.82em; } "
            b".stat-row { padding: 6px 8px; border-bottom: 1px solid alpha(@borders, 0.55); } "
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
        self.toggle_sidebar_button = toggle_sidebar
        toggle_sidebar.set_tooltip_text(self.t("servers"))
        toggle_sidebar.connect("clicked", self.on_toggle_sidebar)
        header.pack_start(toggle_sidebar)

        new_tab_button = Gtk.Button(icon_name="tab-new-symbolic")
        new_tab_button.set_tooltip_text(self.t("new_tab"))
        new_tab_button.connect("clicked", self.on_open_local_terminal)
        header.pack_start(new_tab_button)

        menu_button = Gtk.MenuButton()
        menu_button.set_tooltip_text(self.t("main_menu"))
        menu_button.set_popover(self.build_main_menu())
        menu_button.set_child(Gtk.Image.new_from_icon_name("open-menu-symbolic"))
        header.pack_start(menu_button)

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

        self.session_tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.session_tab_bar.set_homogeneous(True)
        self.session_tab_bar.add_css_class("termia-session-tabs")
        self.session_tab_bar.set_hexpand(True)
        self.session_tab_bar.set_visible(False)
        detail.append(self.session_tab_bar)

        self.terminal_stack = Gtk.Stack()
        self.terminal_stack.add_css_class("termia-terminal-stack")
        self.terminal_stack.set_hexpand(True)
        self.terminal_stack.set_vexpand(True)
        detail.append(self.terminal_stack)

        self.update_actions()

    def on_statistics_dashboard(self, _button: Gtk.Button) -> None:
        dialog = Gtk.Dialog(title=self.t("statistics_title"), transient_for=self, modal=True)
        dialog.set_resizable(True)
        dialog.set_default_size(620, 520)
        self.add_dialog_action_button(dialog, self.t("close"), Gtk.ResponseType.CLOSE, last=True)

        content = dialog.get_content_area()
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_spacing(14)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        dashboard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        scroller.set_child(dashboard)
        content.append(scroller)

        stats = self.store.data.statistics
        average_duration = stats.duration_total / stats.completed_sessions if stats.completed_sessions else None
        cards = Gtk.Grid()
        cards.set_column_spacing(10)
        cards.set_row_spacing(10)
        cards.attach(
            self.build_stat_card(
                self.t("connections"), str(stats.connections), f"{self.t('current_run')} {self.run_connections}"
            ),
            0, 0, 1, 1
        )
        cards.attach(
            self.build_stat_card(self.t("commands"), str(stats.commands), f"{self.t('current_run')} {self.run_commands}"),
            1, 0, 1, 1
        )
        cards.attach(
            self.build_stat_card(
                self.t("keystrokes"), str(stats.keystrokes), f"{self.t('current_run')} {self.run_keystrokes}"
            ),
            2, 0, 1, 1
        )
        cards.attach(
            self.build_stat_card(self.t("sessions"), str(stats.completed_sessions), self.t("global")),
            0, 1, 1, 1
        )
        cards.attach(
            self.build_stat_card(self.t("average_duration"), self.format_duration(average_duration), self.t("duration")),
            1, 1, 1, 1
        )
        cards.attach(
            self.build_stat_card(
                self.t("longest_duration"),
                self.format_duration(stats.duration_max if stats.completed_sessions else None),
                f"{self.t('shortest_duration')}: {self.format_duration(stats.duration_min)}",
            ),
            2, 1, 1, 1
        )
        for card in self.iter_grid_children(cards):
            card.set_hexpand(True)
        dashboard.append(cards)

        title = Gtk.Label(label=self.t("top_servers"))
        title.set_xalign(0)
        title.add_css_class("heading")
        dashboard.append(title)
        dashboard.append(self.build_top_servers_list())

        dialog.connect("response", lambda current, _response: current.destroy())
        dialog.present()

    def build_stat_card(self, title: str, value: str, subtitle: str = "") -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        card.add_css_class("stat-card")
        title_label = Gtk.Label(label=title)
        title_label.set_xalign(0)
        title_label.add_css_class("stat-card-title")
        title_label.add_css_class("dim-label")
        value_label = Gtk.Label(label=value)
        value_label.set_xalign(0)
        value_label.add_css_class("stat-card-value")
        subtitle_label = Gtk.Label(label=subtitle)
        subtitle_label.set_xalign(0)
        subtitle_label.add_css_class("stat-card-subtitle")
        subtitle_label.add_css_class("dim-label")
        card.append(title_label)
        card.append(value_label)
        card.append(subtitle_label)
        return card

    def iter_grid_children(self, grid: Gtk.Grid) -> list[Gtk.Widget]:
        children: list[Gtk.Widget] = []
        child = grid.get_first_child()
        while child is not None:
            children.append(child)
            child = child.get_next_sibling()
        return children

    def build_top_servers_list(self) -> Gtk.Widget:
        stats = self.store.data.statistics
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        if not stats.server_connections:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=self.t("no_statistics"))
            label.set_xalign(0)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(8)
            label.set_margin_end(8)
            row.set_child(label)
            list_box.append(row)
            return list_box

        servers_by_id = {server.id: server for server in self.store.data.servers}
        ranked = sorted(stats.server_connections.items(), key=lambda item: item[1], reverse=True)[:10]
        max_count = max((count for _server_id, count in ranked), default=1)
        for index, (server_id, count) in enumerate(ranked, start=1):
            server = servers_by_id.get(server_id)
            name = server.name if server is not None else server_id
            subtitle = f"{server.user}@{server.host}:{server.port}" if server is not None else ""
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            row_box.add_css_class("stat-row")
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            name_label = Gtk.Label(label=f"{index}. {name}")
            name_label.set_xalign(0)
            name_label.set_hexpand(True)
            count_label = Gtk.Label(label=str(count))
            count_label.set_xalign(1)
            count_label.add_css_class("heading")
            header.append(name_label)
            header.append(count_label)
            row_box.append(header)
            if subtitle:
                subtitle_label = Gtk.Label(label=subtitle)
                subtitle_label.set_xalign(0)
                subtitle_label.add_css_class("dim-label")
                row_box.append(subtitle_label)
            progress = Gtk.LevelBar.new_for_interval(0, max_count)
            progress.set_value(count)
            progress.set_hexpand(True)
            row_box.append(progress)
            row.set_child(row_box)
            list_box.append(row)
        return list_box

    def format_duration(self, seconds: float | None) -> str:
        if seconds is None:
            return "--:--:--"
        total = max(0, int(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def refresh_statistics_menu(self) -> None:
        return

    def build_configuration_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        general = Gtk.Button(label=self.t("general"))
        general.set_halign(Gtk.Align.FILL)
        general.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_app_preferences))
        menu.append(general)

        terminal = Gtk.Button(label=self.t("terminal"))
        terminal.set_halign(Gtk.Align.FILL)
        terminal.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_terminal_settings))
        menu.append(terminal)

        prompt = Gtk.Button(label=self.t("prompt"))
        prompt.set_halign(Gtk.Align.FILL)
        prompt.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_prompt_settings))
        menu.append(prompt)

        connections_file = Gtk.MenuButton(label=self.t("connections_file"))
        connections_file.set_halign(Gtk.Align.FILL)
        connections_file.set_popover(self.build_connections_file_menu())
        menu.append(connections_file)
        popover.set_child(menu)
        return popover

    def build_main_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_child(self.build_main_menu_content(popover))
        return popover

    def build_main_menu_content(self, popover: Gtk.Popover) -> Gtk.Widget:
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        general = Gtk.Button(label=self.t("general"))
        general.set_halign(Gtk.Align.FILL)
        general.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_app_preferences))
        menu.append(general)

        terminal = Gtk.Button(label=self.t("terminal"))
        terminal.set_halign(Gtk.Align.FILL)
        terminal.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_terminal_settings))
        menu.append(terminal)

        prompt = Gtk.Button(label=self.t("prompt"))
        prompt.set_halign(Gtk.Align.FILL)
        prompt.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_prompt_settings))
        menu.append(prompt)

        connections_file = Gtk.Button(label=self.t("connections_file"))
        connections_file.set_halign(Gtk.Align.FILL)
        connections_file.connect("clicked", lambda _button: popover.set_child(self.build_main_connections_menu(popover)))
        menu.append(connections_file)

        statistics = Gtk.Button(label=self.t("statistics"))
        statistics.set_halign(Gtk.Align.FILL)
        statistics.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_statistics_dashboard))
        menu.append(statistics)

        help_btn = Gtk.Button(label=self.t("help"))
        help_btn.set_halign(Gtk.Align.FILL)
        help_btn.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_help))
        menu.append(help_btn)

        about_btn = Gtk.Button(label=self.t("about"))
        about_btn.set_halign(Gtk.Align.FILL)
        about_btn.connect("clicked", lambda _button: self.run_after_popover_closed(popover, self.on_about))
        menu.append(about_btn)
        return menu

    def build_main_connections_menu(self, popover: Gtk.Popover) -> Gtk.Widget:
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)

        back = Gtk.Button(label=self.t("main_menu"))
        back.set_halign(Gtk.Align.FILL)
        back.connect("clicked", lambda _button: popover.set_child(self.build_main_menu_content(popover)))
        menu.append(back)

        export_config = Gtk.Button(label=self.t("export_config"))
        export_config.set_halign(Gtk.Align.FILL)
        export_config.connect("clicked", lambda _button: self.run_action_after_popover_closed(popover, self.on_export_config))
        menu.append(export_config)

        import_config = Gtk.Button(label=self.t("import_config"))
        import_config.set_halign(Gtk.Align.FILL)
        import_config.connect("clicked", lambda _button: self.run_action_after_popover_closed(popover, self.on_import_config))
        menu.append(import_config)

        import_asbru = Gtk.Button(label=self.t("import_asbru"))
        import_asbru.set_halign(Gtk.Align.FILL)
        import_asbru.connect("clicked", lambda _button: self.run_action_after_popover_closed(popover, self.on_import_asbru_config))
        menu.append(import_asbru)

        clear_config = Gtk.Button(label=self.t("clear_config"))
        clear_config.set_halign(Gtk.Align.FILL)
        clear_config.add_css_class("destructive-action")
        clear_config.connect("clicked", lambda _button: self.run_action_after_popover_closed(popover, self.on_request_clear_config))
        menu.append(clear_config)
        return menu

    def run_after_popover_closed(self, popover: Gtk.Popover, callback: Any) -> None:
        popover.popdown()

        def run_callback() -> bool:
            callback(None)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(run_callback)

    def run_action_after_popover_closed(self, popover: Gtk.Popover, callback: Any) -> None:
        popover.popdown()

        def run_callback() -> bool:
            callback()
            return GLib.SOURCE_REMOVE

        GLib.idle_add(run_callback)

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
        dialog.set_license_type(Gtk.License.GPL_3_0)
        dialog.set_comments(self.t("about_content"))
        dialog.set_website(ISSUES_URL)
        dialog.set_website_label(self.t("report_issue"))
        if ABOUT_IMAGE.exists():
            dialog.set_logo(Gdk.Texture.new_from_filename(str(ABOUT_IMAGE)))
        dialog.present()
        GLib.idle_add(self.clear_about_dialog_selection, dialog)

    def clear_about_dialog_selection(self, widget: Gtk.Widget) -> bool:
        if isinstance(widget, Gtk.Label):
            widget.set_selectable(False)
        child = widget.get_first_child()
        while child is not None:
            self.clear_about_dialog_selection(child)
            child = child.get_next_sibling()
        return GLib.SOURCE_REMOVE

    def build_connections_file_menu(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        menu = Gtk.ListBox()
        menu.add_css_class("termia-menu-panel")
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
        self.set_sidebar_visible(not self.sidebar_visible)

    def set_sidebar_visible(self, visible: bool) -> None:
        if visible == self.sidebar_visible:
            return
        if visible:
            self.sidebar.set_visible(True)
            self.body.set_position(self.sidebar_width)
            self.sidebar_visible = True
            self.toggle_sidebar_button.set_icon_name("sidebar-hide-symbolic")
        else:
            self.sidebar_width = max(self.body.get_position(), 180)
            self.sidebar.set_visible(False)
            self.body.set_position(0)
            self.sidebar_visible = False
            self.toggle_sidebar_button.set_icon_name("sidebar-show-symbolic")

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
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_parent(parent)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.add_css_class("termia-menu-panel")
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
        self.request_delete_group(group_id)

    def request_delete_group(self, group_id: str) -> None:
        group = self.find_group(group_id)
        if group is None:
            return
        dialog = Gtk.AlertDialog(
            message=self.t("delete_group_confirm"),
            detail=self.t("delete_group_confirm_detail").format(name=group.name),
        )
        dialog.set_buttons([self.t("cancel"), self.t("delete_group")])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)
        dialog.choose(self, None, self.on_delete_group_confirmed, (dialog, group_id, group.name))

    def on_delete_group_confirmed(
        self, dialog: Gtk.AlertDialog, result: Gio.AsyncResult, data: tuple[Gtk.AlertDialog, str, str]
    ) -> None:
        _dialog, group_id, group_name = data
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 1:
            return
        self.store.delete_group(group_id)
        self.selected = None
        self.toast_label.set_label(self.t("group_deleted").format(name=group_name))
        self.refresh_list()
        self.render_detail()

    def set_all_groups_expanded(self, expanded: bool) -> None:
        for expander in self.group_expanders:
            expander.set_expanded(expanded)
            group_id = getattr(expander, "group_id", None)
            if group_id:
                self.group_expanded_state[group_id] = expanded

    def get_group_expanded(self, group_id: str, query: str) -> bool:
        if query:
            return True
        return self.group_expanded_state.get(group_id, True)

    def on_group_expanded_changed(self, expander: Gtk.Expander, _param: Any) -> None:
        group_id = getattr(expander, "group_id", None)
        if group_id:
            self.group_expanded_state[group_id] = expander.get_expanded()

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
            self.server_list.append(self.build_ungrouped_widget(ungrouped, query))

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
        group_matches = self.matches_group_query(group, query)
        if query and not group_matches and not servers and not child_widgets:
            return None

        descendant_servers = len(servers) + sum(
            int(getattr(widget, "server_count", 0)) for widget in child_widgets
        )
        expander = Gtk.Expander()
        group_label = self.build_group_label(f"{group.name} ({descendant_servers})")
        expander.set_label_widget(group_label)
        self.group_expanders.append(expander)
        expander.group_id = group.id
        expander.server_count = descendant_servers
        expander.set_expanded(self.get_group_expanded(group.id, query))
        expander.connect("notify::expanded", self.on_group_expanded_changed)
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

    def build_ungrouped_widget(self, servers: list[Server], query: str) -> Gtk.Widget:
        expander = Gtk.Expander()
        expander.set_label_widget(self.build_group_label(f"{self.t('no_group')} ({len(servers)})"))
        self.group_expanders.append(expander)
        expander.group_id = "__ungrouped__"
        expander.set_expanded(self.get_group_expanded("__ungrouped__", query))
        expander.connect("notify::expanded", self.on_group_expanded_changed)
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
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
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
        menu.add_css_class("termia-menu-panel")
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

    def matches_group_query(self, group: Group, query: str) -> bool:
        if not query:
            return True
        return query in group.name.lower()

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
            self.request_delete_group(self.selected.item_id)
            return
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
        command = [shell]
        if self.store.data.terminal.prompt_enabled:
            bash_path = GLib.find_program_in_path("bash")
            if bash_path is not None:
                command = self.build_local_prompt_shell_command(bash_path)
        self.open_process_terminal_tab(self.local_directory_title(Path.home()), command, None, working_directory=str(Path.home()))

    def open_process_terminal_tab(
        self,
        title: str,
        command: list[str],
        server_id: str | None,
        envv: list[str] | None = None,
        working_directory: str | None = None,
    ) -> None:
        session_id = str(uuid4())
        tab_title = title
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
        focus_button = Gtk.Button(label=self.t("hide_status_bar"))
        focus_button.add_css_class("termia-status-hide")
        focus_button.set_size_request(-1, 18)
        disconnect_button = Gtk.Button(label=self.t("disconnect"))
        disconnect_button.add_css_class("destructive-action")
        disconnect_button.add_css_class("termia-disconnect-button")
        disconnect_button.set_size_request(-1, 18)
        toolbar.set_visible(self.should_show_session_status_bar())
        toolbar.append(status_label)
        toolbar.append(focus_button)
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
        session = TerminalSession(
            id=session_id, server_id=server_id, title=tab_title, terminal=terminal, page=page,
            tab_label=tab_label, status_label=status_label, timer_label=timer_label,
            disconnect_button=disconnect_button, status_bar=toolbar,
            started_at=time.monotonic(),
        )
        focus_button.connect("clicked", self.on_hide_session_status_bar, session)
        disconnect_button.connect("clicked", self.on_request_disconnect_session, session)
        self.configure_terminal_interactions(terminal, session)
        self.open_tabs[session_id] = session
        self.add_session_to_main_view(session)
        self.update_local_session_directory_title(session)
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
        self.update_local_session_directory_title(session)
        session.timeout_id = GLib.timeout_add_seconds(1, self.update_session_timer, session)
        terminal.connect("child-exited", self.on_process_terminal_exited, session)
        status_label.set_label(f"{title} · PID {child_pid}")

    def on_process_terminal_exited(self, _terminal: Vte.Terminal, _status: int, session: TerminalSession) -> None:
        self.record_session_duration(session)
        self.save_statistics_now()
        session.connected = False
        session.disconnect_button.set_sensitive(False)
        if session.disconnect_requested:
            session.status_label.set_label(f"Desconectada: {session.title}")
            return
        if self.child_status_successful(_status) and self.store.data.app.close_tab_on_ssh_exit:
            self.close_tab(session.id, session.page, disconnect=False)
            self.toast_label.set_label(f"Sesion cerrada: {session.title}")
            return
        session.status_label.set_label(f"Cerrada: {session.title}")
        self.update_session_tab_title(session, f"{session.title} (cerrada)")

    def open_terminal_tab(self, server: Server) -> None:
        session_id = str(uuid4())
        tab_title = server.name
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
        focus_button = Gtk.Button(label=self.t("hide_status_bar"))
        focus_button.add_css_class("termia-status-hide")
        focus_button.set_size_request(-1, 18)
        disconnect_button = Gtk.Button(label=self.t("disconnect"))
        disconnect_button.add_css_class("destructive-action")
        disconnect_button.add_css_class("termia-disconnect-button")
        disconnect_button.set_size_request(-1, 18)
        toolbar.set_visible(self.should_show_session_status_bar())

        toolbar.append(status_label)
        toolbar.append(focus_button)
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
            status_bar=toolbar,
            started_at=time.monotonic(),
        )
        focus_button.connect("clicked", self.on_hide_session_status_bar, session)
        disconnect_button.connect("clicked", self.on_request_disconnect_session, session)
        self.configure_terminal_interactions(terminal, session)
        self.open_tabs[session_id] = session
        self.add_session_to_main_view(session)

        self.start_ssh_session(server, session)

    def start_ssh_session(self, server: Server, session: TerminalSession) -> None:
        terminal = session.terminal
        session.started_at = time.monotonic()
        session.duration_recorded = False
        session.disconnect_requested = False
        session.pending_reconnect = False
        session.child_pid = None
        session.connected = True
        session.disconnect_button.set_sensitive(True)
        session.status_label.set_label(self.t("connecting"))

        ssh_path = GLib.find_program_in_path("ssh")
        if ssh_path is None:
            terminal.feed(b"No se encontro el cliente ssh en el PATH.\r\n")
            session.status_label.set_label("Sin ssh")
            self.mark_session_for_reconnect(session, server, "No se encontro ssh en el PATH")
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
                session.status_label.set_label("Sin sshpass")
                self.mark_session_for_reconnect(session, server, "No se encontro sshpass")
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
            session.status_label.set_label("Error")
            self.mark_session_for_reconnect(session, server, f"No se pudo iniciar ssh para {server.name}")
            return

        session.child_pid = child_pid
        session.timeout_id = GLib.timeout_add_seconds(1, self.update_session_timer, session)
        terminal.connect("child-exited", self.on_terminal_exited, server, session)
        self.record_connection(server.id)
        session.status_label.set_label(f"{server.name} · PID {child_pid}")
        self.toast_label.set_label(f"Sesion abierta: {session.title}")

    def mark_session_for_reconnect(self, session: TerminalSession, server: Server, toast: str) -> None:
        session.connected = False
        session.pending_reconnect = True
        session.disconnect_button.set_sensitive(False)
        self.toast_label.set_label(toast)
        prompt = f"  {self.t('reconnect_prompt')}  "
        session.terminal.feed(f"\r\n\x1b[1;30;48;2;255;213;79m{prompt}\x1b[0m\r\n".encode())
        self.update_session_tab_title(session, f"{session.title} (error)")

    def reconnect_session(self, session: TerminalSession) -> None:
        if not session.pending_reconnect or session.server_id is None:
            return
        server = self.find_server(session.server_id)
        if server is None:
            session.pending_reconnect = False
            self.toast_label.set_label("No se encontro el servidor para reconectar")
            return
        session.pending_reconnect = False
        self.close_tab(session.id, session.page, disconnect=False)
        self.open_terminal_tab(server)

    def child_status_successful(self, status: int) -> bool:
        if status == 0:
            return True
        try:
            return os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
        except ValueError:
            return False

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
        if keyval in enter_keys and session.pending_reconnect:
            self.schedule_statistics_save()
            self.reconnect_session(session)
            return True
        if keyval in enter_keys:
            session.commands += 1
            stats.commands += 1
            self.run_commands += 1
        self.schedule_statistics_save()
        if state & Gdk.ModifierType.CONTROL_MASK:
            if keyval in (Gdk.KEY_Page_Up, Gdk.KEY_KP_Page_Up):
                self.move_terminal_tab_focus(session, -1)
                return True
            if keyval in (Gdk.KEY_Page_Down, Gdk.KEY_KP_Page_Down):
                self.move_terminal_tab_focus(session, 1)
                return True
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

    def move_terminal_tab_focus(self, session: TerminalSession, delta: int) -> None:
        sessions = [item for item in self.open_tabs.values() if item.detached_window is None]
        if len(sessions) <= 1:
            return
        visible = self.terminal_stack.get_visible_child()
        current = 0
        for index, item in enumerate(sessions):
            if item.page is visible or item.id == session.id:
                current = index
                break
        self.set_active_session(sessions[(current + delta) % len(sessions)].id)

    def focus_current_terminal_page_later(self) -> bool:
        visible = self.terminal_stack.get_visible_child()
        for session in self.open_tabs.values():
            if session.page is visible:
                session.terminal.grab_focus()
                break
        return GLib.SOURCE_REMOVE

    def should_show_session_status_bar(self) -> bool:
        return self.store.data.app.show_session_status_bar

    def on_hide_session_status_bar(self, _button: Gtk.Button, session: TerminalSession) -> None:
        session.status_bar.set_visible(False)
        session.terminal.grab_focus()

    def apply_session_status_bar_visibility_to_open_tabs(self) -> None:
        visible = self.should_show_session_status_bar()
        for session in self.open_tabs.values():
            session.status_bar.set_visible(visible)

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
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_parent(terminal)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        menu = Gtk.ListBox()
        menu.add_css_class("termia-menu-panel")
        menu.set_selection_mode(Gtk.SelectionMode.NONE)
        menu.set_margin_top(6)
        menu.set_margin_bottom(6)
        menu.set_margin_start(6)
        menu.set_margin_end(6)
        self.add_context_menu_item(menu, self.t("duplicate_tab"), lambda: self.duplicate_tab(popover, session))
        self.add_context_menu_item(menu, self.t("disconnect"), lambda: self.disconnect_from_terminal_menu(popover, session))
        if not session.status_bar.get_visible():
            self.add_context_menu_item(
                menu, self.t("show_session_status_bar"), lambda: self.show_session_status_bar_from_menu(popover, session)
            )
        self.add_context_menu_item(menu, self.t("copy"), lambda: self.copy_terminal_selection(popover, terminal))
        self.add_context_menu_item(menu, self.t("paste"), lambda: self.paste_terminal_clipboard(popover, terminal))
        self.add_context_menu_item(menu, self.t("configure_terminal"), lambda: self.configure_terminal_from_menu(popover))
        self.add_context_menu_item(menu, self.t("session_statistics"), lambda: self.show_session_statistics(popover, session))
        popover.set_child(menu)
        popover.popup()

    def show_session_status_bar_from_menu(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        session.status_bar.set_visible(True)
        session.terminal.grab_focus()

    def disconnect_from_terminal_menu(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        self.on_request_disconnect_session(None, session)

    def copy_terminal_selection(self, popover: Gtk.Popover, terminal: Vte.Terminal) -> None:
        popover.popdown()
        terminal.copy_clipboard_format(Vte.Format.TEXT)

    def paste_terminal_clipboard(self, popover: Gtk.Popover, terminal: Vte.Terminal) -> None:
        popover.popdown()
        terminal.paste_clipboard()

    def configure_terminal_from_menu(self, popover: Gtk.Popover) -> None:
        popover.popdown()
        self.on_terminal_settings(None)

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

    def local_directory_title(self, path: Path) -> str:
        try:
            resolved = path.resolve()
            if resolved == Path.home().resolve():
                return "~"
            return str(resolved)
        except OSError:
            return str(path)

    def directory_title_from_uri(self, uri: str | None) -> str:
        if not uri:
            return ""
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            return ""
        path = Path(unquote(parsed.path))
        return self.local_directory_title(path)

    def local_session_cwd_title(self, session: TerminalSession) -> str:
        if session.child_pid is not None:
            try:
                return self.local_directory_title(Path(os.readlink(f"/proc/{session.child_pid}/cwd")))
            except OSError:
                pass
        return self.directory_title_from_uri(session.terminal.get_current_directory_uri())

    def update_local_session_directory_title(self, session: TerminalSession) -> None:
        if session.server_id is not None or session.title_locked:
            return
        title = self.local_session_cwd_title(session)
        if not title or title == session.last_directory_title:
            return
        session.last_directory_title = title
        session.title = title
        self.update_session_tab_title(session, title)

    def add_session_to_main_view(self, session: TerminalSession) -> None:
        self.terminal_stack.add_named(session.page, session.id)
        self.session_tab_bar.append(session.tab_label)
        self.update_session_tab_bar_visibility()
        self.set_active_session(session.id)

    def set_active_session(self, session_id: str) -> None:
        session = self.open_tabs.get(session_id)
        if session is None or session.detached_window is not None:
            return
        self.terminal_stack.set_visible_child(session.page)
        self.update_session_tab_states()
        session.terminal.grab_focus()

    def update_session_tab_states(self) -> None:
        visible_page = self.terminal_stack.get_visible_child()
        for session in self.open_tabs.values():
            session.tab_label.remove_css_class("active")
            if visible_page is session.page and session.detached_window is None:
                session.tab_label.add_css_class("active")

    def remove_session_from_main_view(self, session: TerminalSession) -> None:
        if session.detached_window is None:
            parent = session.tab_label.get_parent()
            if parent is self.session_tab_bar:
                self.session_tab_bar.remove(session.tab_label)
            try:
                self.terminal_stack.remove(session.page)
            except Exception:
                pass
        self.update_session_tab_states()
        self.update_session_tab_bar_visibility()

    def update_session_tab_bar_visibility(self) -> None:
        visible_sessions = [session for session in self.open_tabs.values() if session.detached_window is None]
        self.session_tab_bar.set_visible(len(visible_sessions) > 1)

    def focus_available_session_after_close(self, closed_session_id: str) -> None:
        for session_id, session in self.open_tabs.items():
            if session_id != closed_session_id and session.detached_window is None:
                self.set_active_session(session_id)
                return

    def update_session_tab_title(self, session: TerminalSession, title: str) -> None:
        child = session.tab_label.get_first_child()
        if isinstance(child, Gtk.Label):
            child.set_label(title)
            return
        if isinstance(child, Gtk.Box):
            label = child.get_first_child()
            if isinstance(label, Gtk.Label):
                label.set_label(title)

    def build_terminal_environment(self, password: str = "") -> list[str]:
        env = dict(os.environ)
        env["LS_COLORS"] = self.store.data.terminal.ls_colors
        if password:
            env["SSHPASS"] = password
        env.setdefault("COLORTERM", "truecolor")
        env.setdefault("TERM", "xterm-256color")
        return [f"{key}={value}" for key, value in env.items()]

    def rgba_to_hex(self, rgba: Gdk.RGBA) -> str:
        red = max(0, min(round(rgba.red * 255), 255))
        green = max(0, min(round(rgba.green * 255), 255))
        blue = max(0, min(round(rgba.blue * 255), 255))
        return f"#{red:02x}{green:02x}{blue:02x}"

    def build_prompt_ps1(self) -> str:
        settings = self.store.data.terminal
        color = parse_color(settings.prompt_color, "#8ae234")
        red = max(0, min(round(color.red * 255), 255))
        green = max(0, min(round(color.green * 255), 255))
        blue = max(0, min(round(color.blue * 255), 255))
        template = self.normalized_prompt_template(settings.prompt_template)
        return f"\\[\\033[38;2;{red};{green};{blue}m\\]{template}\\[\\033[0m\\]"

    def normalized_prompt_template(self, template: str) -> str:
        value = template if template.strip() else r"\u@\h:\w\$ "
        if value == r"\w \$ ":
            return r"\u@\h:\w\$ "
        return value

    def build_local_prompt_shell_command(self, bash_path: str) -> list[str]:
        quoted_ps1 = shlex.quote(self.build_prompt_ps1())
        script = (
            f"export TERMIA_PS1={quoted_ps1}; "
            "exec bash --rcfile <(printf '%s\\n' "
            "'test -r ~/.bashrc && . ~/.bashrc' "
            "'PS1=\"$TERMIA_PS1\"' "
            "'export PS1') -i"
        )
        return [bash_path, "-lc", script]

    def apply_terminal_settings(self, terminal: Vte.Terminal) -> None:
        settings = self.store.data.terminal
        font_family = self.resolved_terminal_font_family(settings.font_family)
        font = Pango.FontDescription(f"{font_family} {settings.font_size}")
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
        self.update_local_session_directory_title(session)
        return GLib.SOURCE_CONTINUE

    def build_tab_label(self, title: str, session_id: str, page: Gtk.Widget) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        box.add_css_class("termia-tab-label")
        box.set_hexpand(True)
        box.set_margin_start(0)
        box.set_margin_end(0)
        label = Gtk.Label(label=title)
        label.add_css_class("termia-tab-title")
        label.set_hexpand(True)
        label.set_single_line_mode(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_width_chars(1)
        label.set_max_width_chars(36)
        label.set_tooltip_text(title)
        label.set_margin_start(4)
        label.set_margin_end(4)
        close_button = Gtk.Button(icon_name="window-close-symbolic")
        close_button.add_css_class("termia-tab-close")
        close_button.set_has_frame(False)
        close_button.set_tooltip_text(self.t("close_tab"))
        close_button.connect("clicked", self.on_request_close_tab, session_id, page)
        left_click = Gtk.GestureClick.new()
        left_click.set_button(1)
        left_click.connect("released", lambda *_args: self.set_active_session(session_id))
        box.add_controller(left_click)
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
        popover.add_css_class("termia-menu-popover")
        popover.set_has_arrow(False)
        popover.set_parent(parent)
        menu = Gtk.ListBox()
        menu.add_css_class("termia-menu-panel")
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
            self.local_directory_title(Path.home()), [shell], None, working_directory=str(Path.home())
        )

    def detach_tab(self, popover: Gtk.Popover, session: TerminalSession) -> None:
        popover.popdown()
        if session.detached_window is not None:
            return
        self.remove_session_from_main_view(session)
        self.focus_available_session_after_close(session.id)
        window = Gtk.Window(title=session.title, transient_for=self)
        window.set_default_size(860, 520)
        window.set_child(session.page)
        session.detached_window = window
        self.update_session_tab_bar_visibility()
        window.connect("close-request", self.on_detached_window_close, session)
        window.present()

    def on_detached_window_close(self, window: Gtk.Window, session: TerminalSession) -> bool:
        window.set_child(None)
        session.detached_window = None
        if session.id in self.open_tabs:
            self.add_session_to_main_view(session)
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
            session.title_locked = True
            self.update_session_tab_title(session, title)
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
        self.update_session_tab_title(session, f"{session.title} (desconectada)")
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
        if session.disconnect_requested:
            session.status_label.set_label(f"Desconectada: {session.title}")
            self.toast_label.set_label(f"Sesion desconectada: {session.title}")
            return
        if self.child_status_successful(_status):
            if self.store.data.app.close_tab_on_ssh_exit:
                self.close_tab(session.id, session.page, disconnect=False)
                self.toast_label.set_label(f"Sesion cerrada: {server.name}")
                return
            session.status_label.set_label(f"Cerrada: {session.title}")
            self.update_session_tab_title(session, f"{session.title} (cerrada)")
            self.toast_label.set_label(f"Sesion cerrada: {server.name}")
            return
        session.status_label.set_label(f"Error: {session.title}")
        self.mark_session_for_reconnect(session, server, f"Fallo de conexion: {server.name}")

    def on_request_close_tab(self, _button: Gtk.Button, session_id: str, page: Gtk.Widget) -> None:
        session = self.open_tabs.get(session_id)
        if session and session.page == page and session.connected:
            if not self.store.data.app.confirm_disconnect:
                self.close_tab(session_id, page, disconnect=True)
                return
            detail = self.t("close_ssh_session_confirm") if session.server_id is not None else self.t("close_local_session_confirm")
            self.confirm_session_action(
                session,
                self.t("close_session_title"),
                detail,
                self.t("close"),
                lambda: self.close_tab(session_id, page, disconnect=True),
            )
            return
        self.close_tab(session_id, page, disconnect=False)

    def close_tab(self, session_id: str, page: Gtk.Widget, disconnect: bool) -> None:
        session = self.open_tabs.get(session_id)
        if disconnect and session and session.page == page and session.connected:
            self.disconnect_session(session)
            session = self.open_tabs.get(session_id)
        if session is None:
            return
        if session.detached_window is not None:
            window = session.detached_window
            session.detached_window = None
            window.set_child(None)
            window.destroy()
        else:
            self.remove_session_from_main_view(session)
        self.open_tabs.pop(session_id, None)
        self.update_session_tab_bar_visibility()
        self.focus_available_session_after_close(session_id)

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
        dialog = Gtk.Dialog(title=self.t("general"), transient_for=self, modal=True)
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

        close_tab_on_disconnect = Gtk.CheckButton(label=self.t("close_tab_on_disconnect"))
        close_tab_on_disconnect.set_active(self.store.data.app.close_tab_on_disconnect)
        close_tab_on_disconnect.set_halign(Gtk.Align.START)
        close_tab_on_ssh_exit = Gtk.CheckButton(label=self.t("close_tab_on_ssh_exit"))
        close_tab_on_ssh_exit.set_active(self.store.data.app.close_tab_on_ssh_exit)
        close_tab_on_ssh_exit.set_halign(Gtk.Align.START)
        open_local_terminal_on_startup = Gtk.CheckButton(label=self.t("open_local_terminal_on_startup"))
        open_local_terminal_on_startup.set_active(self.store.data.app.open_local_terminal_on_startup)
        open_local_terminal_on_startup.set_halign(Gtk.Align.START)
        show_session_status_bar = Gtk.CheckButton(label=self.t("show_session_status_bar"))
        show_session_status_bar.set_active(self.store.data.app.show_session_status_bar)
        show_session_status_bar.set_halign(Gtk.Align.START)
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
            ("", close_tab_on_disconnect),
            ("", close_tab_on_ssh_exit),
            ("", open_local_terminal_on_startup),
            ("", show_session_status_bar),
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
            close_tab_on_disconnect, close_tab_on_ssh_exit, open_local_terminal_on_startup,
            show_session_status_bar, confirm_disconnect, confirm_close_app,
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
        close_tab_on_ssh_exit: Gtk.CheckButton,
        open_local_terminal_on_startup: Gtk.CheckButton,
        show_session_status_bar: Gtk.CheckButton,
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
                close_tab_on_ssh_exit.get_active(),
                open_local_terminal_on_startup.get_active(),
                show_session_status_bar.get_active(),
            )
            self.apply_app_theme()
            self.install_tree_styles()
            self.apply_session_status_bar_visibility_to_open_tabs()
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

        font_combo = Gtk.ComboBoxText()
        font_families = self.terminal_font_families()
        for font_family in font_families:
            font_combo.append_text(font_family)
        active_font = self.resolved_terminal_font_family(settings.font_family)
        font_combo.set_active(font_families.index(active_font) if active_font in font_families else 0)

        font_size_spin = Gtk.SpinButton.new_with_range(6, 72, 1)
        font_size_spin.set_value(settings.font_size)

        foreground_button = Gtk.ColorButton()
        foreground_button.set_rgba(parse_color(settings.foreground, "#f2f2f2"))
        foreground_button.set_title("Foreground")

        background_button = Gtk.ColorButton()
        background_button.set_rgba(parse_color(settings.background, "#101010"))
        background_button.set_title("Background")

        preview = Gtk.Label()
        preview.set_use_markup(True)
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
            (self.t("font_size"), font_combo),
            ("", font_size_spin),
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

        self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button)
        font_combo.connect(
            "changed",
            lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button),
        )
        font_size_spin.connect(
            "value-changed",
            lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button),
        )
        foreground_button.connect(
            "notify::rgba",
            lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button),
        )
        background_button.connect(
            "notify::rgba",
            lambda *_args: self.update_terminal_preview(preview, font_combo, font_size_spin, foreground_button, background_button),
        )

        dialog.connect(
            "response",
            self.on_terminal_settings_response,
            font_combo,
            font_size_spin,
            foreground_button,
            background_button,
        )
        dialog.present()

    def on_prompt_settings(self, _button: Gtk.Button) -> None:
        dialog = Gtk.Dialog(title=self.t("prompt"), transient_for=self, modal=True)
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

        prompt_enabled = Gtk.CheckButton(label=self.t("custom_prompt"))
        prompt_enabled.set_active(settings.prompt_enabled)
        prompt_enabled.set_halign(Gtk.Align.START)

        prompt_datetime_id, prompt_base_template = self.split_prompt_datetime_template(settings.prompt_template)
        prompt_datetime_combo = Gtk.ComboBoxText()
        prompt_datetime_combo.append("none", self.t("prompt_datetime_none"))
        prompt_datetime_combo.append("time", self.t("prompt_datetime_time"))
        prompt_datetime_combo.append("time_seconds", self.t("prompt_datetime_time_seconds"))
        prompt_datetime_combo.append("date", self.t("prompt_datetime_date"))
        prompt_datetime_combo.append("both", self.t("prompt_datetime_both"))
        prompt_datetime_combo.set_active_id(prompt_datetime_id)

        prompt_template_entry = Gtk.Entry()
        prompt_template_entry.set_text(prompt_base_template)
        prompt_template_entry.set_placeholder_text(r"\u@\h:\w\$ ")

        prompt_color_button = Gtk.ColorButton()
        prompt_color_button.set_rgba(parse_color(settings.prompt_color, "#8ae234"))
        prompt_color_button.set_title(self.t("prompt_color"))

        prompt_preset_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        for preset_name, (template, color) in PROMPT_PRESETS.items():
            preset_button = Gtk.Button(label=preset_name)
            preset_button.add_css_class("prompt-preset-button")
            preset_button.set_size_request(-1, 24)
            preset_button.connect(
                "clicked",
                self.on_prompt_preset_clicked,
                prompt_template_entry,
                prompt_color_button,
                template,
                color,
            )
            prompt_preset_box.append(preset_button)

        prompt_controls = (prompt_datetime_combo, prompt_template_entry, prompt_color_button, prompt_preset_box)
        for prompt_widget in prompt_controls:
            prompt_widget.set_sensitive(prompt_enabled.get_active())
        prompt_enabled.connect(
            "toggled",
            lambda current: [widget.set_sensitive(current.get_active()) for widget in prompt_controls],
        )

        rows: list[tuple[str, Gtk.Widget]] = [
            ("", prompt_enabled),
            (self.t("prompt_datetime"), prompt_datetime_combo),
            (self.t("prompt_template"), prompt_template_entry),
            (self.t("prompt_color"), prompt_color_button),
            (self.t("prompt_presets"), prompt_preset_box),
        ]
        for index, (label_text, widget) in enumerate(rows):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            grid.attach(label, 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)

        preview = Gtk.Label()
        preview.set_use_markup(True)
        preview.set_xalign(0)
        preview.set_margin_top(10)
        preview.set_margin_bottom(10)
        preview.set_margin_start(12)
        preview.set_margin_end(12)
        preview.set_css_classes(["terminal-preview"])

        content.append(grid)
        content.append(preview)

        self.update_prompt_preview(
            preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
        )
        prompt_enabled.connect(
            "toggled",
            lambda *_args: self.update_prompt_preview(
                preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
            ),
        )
        prompt_datetime_combo.connect(
            "changed",
            lambda *_args: self.update_prompt_preview(
                preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
            ),
        )
        prompt_template_entry.connect(
            "changed",
            lambda *_args: self.update_prompt_preview(
                preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
            ),
        )
        prompt_color_button.connect(
            "notify::rgba",
            lambda *_args: self.update_prompt_preview(
                preview, prompt_enabled, prompt_datetime_combo, prompt_template_entry, prompt_color_button
            ),
        )

        dialog.connect(
            "response",
            self.on_prompt_settings_response,
            prompt_enabled,
            prompt_datetime_combo,
            prompt_template_entry,
            prompt_color_button,
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

    def on_prompt_preset_clicked(
        self,
        _button: Gtk.Button,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
        template: str,
        color: str,
    ) -> None:
        prompt_template_entry.set_text(template)
        prompt_color_button.set_rgba(parse_color(color, "#8ae234"))

    def terminal_font_families(self) -> list[str]:
        families = [
            family.get_name()
            for family in self.get_pango_context().list_families()
            if family.is_monospace()
        ]
        names = sorted(set(families), key=str.lower)
        if "Monospace" not in names:
            names.insert(0, "Monospace")
        return names or ["Monospace"]

    def resolved_terminal_font_family(self, preferred: str) -> str:
        font_families = self.terminal_font_families()
        if preferred in font_families:
            return preferred
        for fallback in ("JetBrains Mono", "Ubuntu Mono", "Monospace"):
            if fallback in font_families:
                return fallback
        return font_families[0] if font_families else "Monospace"

    def selected_terminal_font_family(self, font_combo: Gtk.ComboBoxText) -> str:
        return font_combo.get_active_text() or "Monospace"

    def update_terminal_preview(
        self,
        preview: Gtk.Label,
        font_combo: Gtk.ComboBoxText,
        font_size_spin: Gtk.SpinButton,
        foreground_button: Gtk.ColorButton,
        background_button: Gtk.ColorButton,
    ) -> None:
        font_family = self.selected_terminal_font_family(font_combo)
        font_size = int(font_size_spin.get_value())
        foreground = foreground_button.get_rgba().to_string()
        background = background_button.get_rgba().to_string()
        preview.set_markup(GLib.markup_escape_text("usuario@servidor:~$ ssh ejemplo\nSalida de terminal"))
        css = (
            ".terminal-preview {"
            f"font-family: '{font_family}';"
            f"font-size: {font_size}pt;"
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

    def update_prompt_preview(
        self,
        preview: Gtk.Label,
        prompt_enabled: Gtk.CheckButton,
        prompt_datetime_combo: Gtk.ComboBoxText,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
    ) -> None:
        command_markup = GLib.markup_escape_text("ssh ejemplo\nSalida de terminal")
        if prompt_enabled.get_active():
            prompt_text = self.render_prompt_preview(
                self.prompt_template_with_datetime(
                    prompt_template_entry.get_text(), prompt_datetime_combo.get_active_id() or "none"
                )
            )
            prompt_markup = GLib.markup_escape_text(prompt_text)
            prompt_color = self.rgba_to_hex(prompt_color_button.get_rgba())
            preview.set_markup(f'<span foreground="{prompt_color}">{prompt_markup}</span>{command_markup}')
        else:
            preview.set_markup(GLib.markup_escape_text("usuario@servidor:~$ ssh ejemplo\nSalida de terminal"))

        settings = self.store.data.terminal
        css = (
            ".terminal-preview {"
            f"font-family: '{settings.font_family}';"
            f"font-size: {settings.font_size}pt;"
            f"color: {settings.foreground};"
            f"background: {settings.background};"
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

    def split_prompt_datetime_template(self, template: str) -> tuple[str, str]:
        prefixes = [
            ("both", r"[\d \A] "),
            ("date", r"[\d] "),
            ("time_seconds", r"[\t] "),
            ("time", r"[\A] "),
        ]
        for option_id, prefix in prefixes:
            if template.startswith(prefix):
                return option_id, template[len(prefix):]
        return "none", template

    def prompt_template_with_datetime(self, template: str, option_id: str) -> str:
        base_template = self.normalized_prompt_template(template)
        prefixes = {
            "time": r"[\A] ",
            "time_seconds": r"[\t] ",
            "date": r"[\d] ",
            "both": r"[\d \A] ",
        }
        return f"{prefixes.get(option_id, '')}{base_template}"

    def render_prompt_preview(self, template: str) -> str:
        text = self.normalized_prompt_template(template)
        replacements = {
            r"\u": "usuario",
            r"\h": "servidor",
            r"\H": "servidor.local",
            r"\w": "~/proyecto",
            r"\W": "proyecto",
            r"\$": "$",
            r"\A": "14:35",
            r"\t": "14:35:08",
            r"\d": "dom jun 07",
            r"\n": "\n",
        }
        for marker, value in replacements.items():
            text = text.replace(marker, value)
        return text

    def on_prompt_settings_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        prompt_enabled: Gtk.CheckButton,
        prompt_datetime_combo: Gtk.ComboBoxText,
        prompt_template_entry: Gtk.Entry,
        prompt_color_button: Gtk.ColorButton,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            self.store.update_prompt_settings(
                prompt_enabled.get_active(),
                self.prompt_template_with_datetime(
                    prompt_template_entry.get_text(), prompt_datetime_combo.get_active_id() or "none"
                ),
                self.rgba_to_hex(prompt_color_button.get_rgba()),
            )
            self.toast_label.set_label(self.t("prompt_settings_saved"))
        dialog.destroy()

    def on_terminal_settings_response(
        self,
        dialog: Gtk.Dialog,
        response: Gtk.ResponseType,
        font_combo: Gtk.ComboBoxText,
        font_size_spin: Gtk.SpinButton,
        foreground_button: Gtk.ColorButton,
        background_button: Gtk.ColorButton,
    ) -> None:
        if response == Gtk.ResponseType.OK:
            self.store.update_terminal_settings(
                self.selected_terminal_font_family(font_combo),
                int(font_size_spin.get_value()),
                foreground_button.get_rgba().to_string(),
                background_button.get_rgba().to_string(),
            )
            self.apply_terminal_settings_to_open_tabs()
            self.toast_label.set_label(self.t("terminal_settings_saved"))
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

    def build_form_label(self, label_text: str, required: bool = False) -> Gtk.Label:
        label = Gtk.Label()
        label.set_xalign(0)
        if required:
            escaped = GLib.markup_escape_text(label_text)
            label.set_markup(f"{escaped} <span foreground='#c01c28'><b>*</b></span>")
        else:
            label.set_text(label_text)
        return label

    def build_required_hint(self) -> Gtk.Label:
        label = Gtk.Label()
        label.set_xalign(0)
        label.set_markup(
            f"<span size='small' foreground='#c01c28'><i>{GLib.markup_escape_text(self.t('required_field'))}</i></span>"
        )
        return label

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

        rows: list[tuple[str, Gtk.Widget, bool]] = [
            (self.t("name"), name_entry, True),
            (self.t("host"), host_entry, True),
            (self.t("ssh_user"), user_entry, True),
            (self.t("ssh_port"), port_spin, False),
            (self.t("group"), group_combo, False),
            (self.t("password"), password_entry, False),
            (self.t("public_key"), public_key_entry, False),
        ]
        for index, (label_text, widget, required) in enumerate(rows):
            grid.attach(self.build_form_label(label_text, required), 0, index, 1, 1)
            grid.attach(widget, 1, index, 1, 1)
        grid.attach(self.build_required_hint(), 1, len(rows), 1, 1)

        dialog.get_content_area().append(grid)
        warning = Gtk.Label()
        warning.set_markup(f"<i>{GLib.markup_escape_text(self.t('password_warning'))}</i>")
        warning.set_wrap(True)
        warning.set_xalign(0)
        warning.set_margin_start(16)
        warning.set_margin_end(16)
        warning.set_margin_bottom(14)
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

        if response == Gtk.ResponseType.OK:
            if not name or not host or not user:
                self.toast_label.set_label(self.t("server_required_fields"))
                for widget in (widgets["name"], widgets["host"], widgets["user"]):
                    if not widget.get_text().strip():
                        widget.grab_focus()
                        break
                return
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
