# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import locale
import os

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
        "terminal": "Terminal", "prompt": "Prompt", "keybindings": "Atajos", "security": "Seguridad", "general": "General", "preferences": "Preferencias", "filter_servers": "Filtrar servidores",
        "connect": "Conectar", "edit_server": "Editar servidor", "delete_server": "Eliminar servidor", "clone_connection": "Clonar conexión",
        "edit_group": "Editar grupo", "delete_group": "Eliminar grupo", "no_group": "Sin grupo",
        "parent_group": "Grupo padre", "no_parent_group": "Sin grupo padre",
        "cancel": "Cancelar", "close": "Cerrar", "save": "Guardar", "name": "Nombre", "host": "IP o host",
        "ssh_user": "Usuario SSH", "ssh_port": "Puerto SSH", "group": "Grupo",
        "password": "Contraseña", "public_key": "Clave SSH privada",
        "ssh_fingerprint_manual": "Host nuevo: responde al fingerprint en esta terminal. Después introduce la contraseña manualmente o con Ctrl+P.",
        "password_warning": "Aviso: la contraseña se guardará en connections.json. Puedes cambiar entre texto plano y ofuscado desde Seguridad.",
        "server_required_fields": "Nombre, host y usuario SSH son obligatorios.",
        "required_field": "* Campo obligatorio",
        "reconnect_prompt": "Pulsa Enter para reconectar.",
        "close_tab_on_ssh_exit": "Cerrar la pestaña al salir de una sesión SSH con exit",
        "open_local_terminal_on_startup": "Abrir terminal local al iniciar Termia",
        "show_sidebar_on_startup": "Mostrar listado de servidores al iniciar Termia",
        "delete_group_confirm": "Eliminar grupo",
        "delete_group_confirm_detail": "¿Quieres eliminar {name}? También se eliminarán todos sus subgrupos y servidores. Esta acción no se puede deshacer.",
        "group_deleted": "Grupo eliminado: {name}",
        "theme": "Tema", "language": "Idioma", "restart_language": "El idioma se aplicará al reiniciar la aplicación.",
        "close_tab": "Cerrar pestaña", "disconnect": "Desconectar", "connecting": "Conectando",
        "close_session_title": "Cerrar sesión", "close_ssh_session_confirm": "¿Quieres cerrar esta sesión SSH? La conexión se desconectará.", "close_local_session_confirm": "¿Quieres cerrar este terminal local? El proceso en ejecución se finalizará.",
        "close_tab_on_disconnect": "Cerrar la pestaña al desconectar una sesión",
        "show_session_status_bar": "Mostrar barra de estado de la sesión", "hide_status_bar": "Ocultar",
        "statistics_enabled": "Registrar estadísticas locales de conexiones y duración",
        "confirm_disconnect": "Confirmar antes de desconectar o cerrar una sesión activa", "confirm_close_app": "Confirmar para cerrar Termia",
        "sudo_password_shortcut": "Permitir enviar contraseña con atajo",
        "sudo_password_enter": "Enviar contraseña y pulsar Enter",
        "sudo_password_sent": "Contraseña guardada enviada a la terminal",
        "sudo_password_unavailable": "Esta terminal no tiene una contraseña guardada",
        "keybindings_description": "Configura atajos activos dentro del terminal. Deja una acción desactivada para que la combinación llegue al shell remoto.",
        "keybindings_restore_defaults": "Restaurar valores",
        "keybindings_settings_saved": "Atajos guardados",
        "keybinding_disabled": "Desactivado",
        "keybinding_action_copy": "Copiar selección",
        "keybinding_action_paste": "Pegar portapapeles",
        "keybinding_action_previous_tab": "Pestaña anterior",
        "keybinding_action_next_tab": "Pestaña siguiente",
        "keybinding_action_font_increase": "Aumentar fuente",
        "keybinding_action_font_decrease": "Reducir fuente",
        "keybinding_action_send_password": "Enviar contraseña guardada",
        "close_app": "Cerrar Termia", "close_app_confirm": "¿Quieres cerrar Termia?",
        "font_size": "Fuente y tamaño", "custom_prompt": "Personalizar prompt local", "prompt_template": "Plantilla PS1", "prompt_color": "Color del prompt", "prompt_presets": "Temas de prompt", "prompt_datetime": "Fecha y hora", "prompt_datetime_none": "Sin fecha/hora", "prompt_datetime_time": "Hora", "prompt_datetime_time_seconds": "Hora y segundos", "prompt_datetime_date": "Fecha", "prompt_datetime_both": "Fecha y hora", "prompt_settings_saved": "Configuración de prompt guardada", "terminal_settings_saved": "Preferencias de terminal guardadas", "security_settings_saved": "Preferencias de seguridad guardadas", "terminal_font_size_changed": "Tamaño de fuente del terminal: {size}", "foreground": "Foreground", "background": "Background", "palettes": "Paletas",
        "connection_storage_mode": "Almacenamiento de conexiones", "connection_storage_plain": "Texto plano", "connection_storage_obfuscated": "Ofuscado", "connection_storage_obfuscated_warning": "La ofuscación evita lecturas accidentales del fichero, pero no cifra ni protege frente a un atacante con acceso al código.", "configuration": "Configuración", "connections_file": "Importar/Exportar", "export_config": "Exportar configuración", "import_config": "Importar configuración",
        "summary": "{groups} grupos · {subgroups} subgrupos · {servers} servidores",
        "import_asbru": "Importar configuración de Ásbrú", "clear_config": "Eliminar toda la configuración", "configure_terminal": "Configurar terminal", "local_terminal": "Terminal local", "new_tab": "Nueva pestaña",
        "statistics": "Estadísticas", "statistics_title": "Estadísticas", "top_servers": "Servidores más usados", "no_statistics": "Sin estadísticas todavía", "sessions": "Sesiones", "duration": "Duración", "connections": "Conexiones",
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
            "- Permite configurar atajos de terminal, incluido copiar, pegar y enviar la contraseña guardada.\n"
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
        "terminal": "Terminal", "prompt": "Prompt", "keybindings": "Dreceres", "security": "Seguretat", "general": "General", "preferences": "Preferències", "filter_servers": "Filtrar servidors",
        "connect": "Connectar", "edit_server": "Editar servidor", "delete_server": "Eliminar servidor", "clone_connection": "Clonar connexió",
        "edit_group": "Editar grup", "delete_group": "Eliminar grup", "no_group": "Sense grup",
        "parent_group": "Grup pare", "no_parent_group": "Sense grup pare",
        "cancel": "Cancel·lar", "close": "Tancar", "save": "Desar", "name": "Nom", "host": "IP o host",
        "ssh_user": "Usuari SSH", "ssh_port": "Port SSH", "group": "Grup",
        "password": "Contrasenya", "public_key": "Clau SSH privada",
        "ssh_fingerprint_manual": "Host nou: respon al fingerprint en aquest terminal. Després introdueix la contrasenya manualment o amb Ctrl+P.",
        "password_warning": "Avís: la contrasenya es desarà a connections.json. Pots canviar entre text pla i ofuscat des de Seguretat.",
        "server_required_fields": "El nom, el host i l'usuari SSH són obligatoris.",
        "required_field": "* Camp obligatori",
        "reconnect_prompt": "Prem Enter per reconnectar.",
        "close_tab_on_ssh_exit": "Tancar la pestanya en sortir d'una sessió SSH amb exit",
        "open_local_terminal_on_startup": "Obrir un terminal local en iniciar Termia",
        "show_sidebar_on_startup": "Mostrar el llistat de servidors en iniciar Termia",
        "delete_group_confirm": "Eliminar grup",
        "delete_group_confirm_detail": "Vols eliminar {name}? També s'eliminaran tots els subgrups i servidors. Aquesta acció no es pot desfer.",
        "group_deleted": "Grup eliminat: {name}",
        "theme": "Tema", "language": "Idioma", "restart_language": "L'idioma s'aplicarà en reiniciar l'aplicació.",
        "close_tab": "Tancar pestanya", "disconnect": "Desconnectar", "connecting": "Connectant",
        "close_session_title": "Tancar sessió", "close_ssh_session_confirm": "Vols tancar aquesta sessió SSH? La connexió es desconnectarà.", "close_local_session_confirm": "Vols tancar aquest terminal local? El procés en execució es finalitzarà.",
        "close_tab_on_disconnect": "Tancar la pestanya en desconnectar una sessió",
        "show_session_status_bar": "Mostrar barra d'estat de la sessió", "hide_status_bar": "Amagar",
        "statistics_enabled": "Registrar estadístiques locals de connexions i durada",
        "confirm_disconnect": "Confirmar abans de desconnectar o tancar una sessió activa", "confirm_close_app": "Confirmar per tancar Termia",
        "sudo_password_shortcut": "Permetre enviar contrasenya amb drecera",
        "sudo_password_enter": "Enviar contrasenya i prémer Enter",
        "sudo_password_sent": "Contrasenya desada enviada al terminal",
        "sudo_password_unavailable": "Aquest terminal no té cap contrasenya desada",
        "keybindings_description": "Configura dreceres actives dins del terminal. Deixa una acció desactivada perquè la combinació arribi al shell remot.",
        "keybindings_restore_defaults": "Restaurar valors",
        "keybindings_settings_saved": "Dreceres desades",
        "keybinding_disabled": "Desactivat",
        "keybinding_action_copy": "Copiar selecció",
        "keybinding_action_paste": "Enganxar porta-retalls",
        "keybinding_action_previous_tab": "Pestanya anterior",
        "keybinding_action_next_tab": "Pestanya següent",
        "keybinding_action_font_increase": "Augmentar lletra",
        "keybinding_action_font_decrease": "Reduir lletra",
        "keybinding_action_send_password": "Enviar contrasenya desada",
        "close_app": "Tancar Termia", "close_app_confirm": "Vols tancar Termia?",
        "font_size": "Tipus de lletra i mida", "custom_prompt": "Personalitzar prompt local", "prompt_template": "Plantilla PS1", "prompt_color": "Color del prompt", "prompt_presets": "Temes de prompt", "prompt_datetime": "Data i hora", "prompt_datetime_none": "Sense data/hora", "prompt_datetime_time": "Hora", "prompt_datetime_time_seconds": "Hora i segons", "prompt_datetime_date": "Data", "prompt_datetime_both": "Data i hora", "prompt_settings_saved": "Configuració del prompt desada", "terminal_settings_saved": "Preferències del terminal desades", "security_settings_saved": "Preferències de seguretat desades", "terminal_font_size_changed": "Mida de la lletra del terminal: {size}", "foreground": "Primer pla", "background": "Fons", "palettes": "Paletes",
        "connection_storage_mode": "Emmagatzematge de connexions", "connection_storage_plain": "Text pla", "connection_storage_obfuscated": "Ofuscat", "connection_storage_obfuscated_warning": "L'ofuscació evita lectures accidentals del fitxer, però no xifra ni protegeix davant un atacant amb accés al codi.", "configuration": "Configuració", "connections_file": "Importar/Exportar", "export_config": "Exportar configuració", "import_config": "Importar configuració",
        "summary": "{groups} grups · {subgroups} subgrups · {servers} servidors",
        "import_asbru": "Importar configuració d'Ásbrú", "clear_config": "Eliminar tota la configuració", "configure_terminal": "Configurar terminal", "local_terminal": "Terminal local", "new_tab": "Pestanya nova",
        "statistics": "Estadístiques", "statistics_title": "Estadístiques", "top_servers": "Servidors més usats", "no_statistics": "Encara no hi ha estadístiques", "sessions": "Sessions", "duration": "Durada", "connections": "Connexions",
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
            "- Permet configurar dreceres de terminal, incloent copiar, enganxar i enviar la contrasenya desada.\n"
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
        "terminal": "Terminal", "prompt": "Prompt", "keybindings": "Keybindings", "security": "Security", "general": "General", "preferences": "Preferences", "filter_servers": "Filter servers",
        "connect": "Connect", "edit_server": "Edit server", "delete_server": "Delete server", "clone_connection": "Clone connection",
        "edit_group": "Edit group", "delete_group": "Delete group", "no_group": "No group",
        "parent_group": "Parent group", "no_parent_group": "No parent group",
        "cancel": "Cancel", "close": "Close", "save": "Save", "name": "Name", "host": "IP or host",
        "ssh_user": "SSH user", "ssh_port": "SSH port", "group": "Group",
        "password": "Password", "public_key": "Private SSH key",
        "ssh_fingerprint_manual": "New host: answer the fingerprint prompt in this terminal. Then enter the password manually or with Ctrl+P.",
        "password_warning": "Warning: the password will be stored in connections.json. You can switch between plain text and obfuscated storage from Security.",
        "server_required_fields": "Name, host, and SSH user are required.",
        "required_field": "* Required field",
        "reconnect_prompt": "Press Enter to reconnect.",
        "close_tab_on_ssh_exit": "Close the tab when leaving an SSH session with exit",
        "open_local_terminal_on_startup": "Open a local terminal when Termia starts",
        "show_sidebar_on_startup": "Show the server list when Termia starts",
        "delete_group_confirm": "Delete group",
        "delete_group_confirm_detail": "Delete {name}? All nested subgroups and servers will also be deleted. This action cannot be undone.",
        "group_deleted": "Group deleted: {name}",
        "theme": "Theme", "language": "Language", "restart_language": "The language will apply after restarting the application.",
        "close_tab": "Close tab", "disconnect": "Disconnect", "connecting": "Connecting",
        "close_session_title": "Close session", "close_ssh_session_confirm": "Do you want to close this SSH session? The connection will be disconnected.", "close_local_session_confirm": "Do you want to close this local terminal? The running process will be terminated.",
        "close_tab_on_disconnect": "Close the tab when disconnecting a session",
        "show_session_status_bar": "Show session status bar", "hide_status_bar": "Hide",
        "statistics_enabled": "Record local connection and duration statistics",
        "confirm_disconnect": "Confirm before disconnecting or closing an active session", "confirm_close_app": "Confirm before closing Termia",
        "sudo_password_shortcut": "Allow sending password with shortcut",
        "sudo_password_enter": "Send password and press Enter",
        "sudo_password_sent": "Saved password sent to the terminal",
        "sudo_password_unavailable": "This terminal does not have a saved password",
        "keybindings_description": "Configure shortcuts active inside the terminal. Leave an action disabled to let the combination reach the remote shell.",
        "keybindings_restore_defaults": "Restore defaults",
        "keybindings_settings_saved": "Keybindings saved",
        "keybinding_disabled": "Disabled",
        "keybinding_action_copy": "Copy selection",
        "keybinding_action_paste": "Paste clipboard",
        "keybinding_action_previous_tab": "Previous tab",
        "keybinding_action_next_tab": "Next tab",
        "keybinding_action_font_increase": "Increase font",
        "keybinding_action_font_decrease": "Decrease font",
        "keybinding_action_send_password": "Send saved password",
        "close_app": "Close Termia", "close_app_confirm": "Do you want to close Termia?",
        "font_size": "Font and size", "custom_prompt": "Customize local prompt", "prompt_template": "PS1 template", "prompt_color": "Prompt color", "prompt_presets": "Prompt themes", "prompt_datetime": "Date and time", "prompt_datetime_none": "No date/time", "prompt_datetime_time": "Time", "prompt_datetime_time_seconds": "Time with seconds", "prompt_datetime_date": "Date", "prompt_datetime_both": "Date and time", "prompt_settings_saved": "Prompt settings saved", "terminal_settings_saved": "Terminal preferences saved", "security_settings_saved": "Security preferences saved", "terminal_font_size_changed": "Terminal font size: {size}", "foreground": "Foreground", "background": "Background", "palettes": "Palettes",
        "connection_storage_mode": "Connection storage", "connection_storage_plain": "Plain text", "connection_storage_obfuscated": "Obfuscated", "connection_storage_obfuscated_warning": "Obfuscation prevents accidental file reads, but it does not encrypt data or protect against an attacker with access to the code.", "configuration": "Configuration", "connections_file": "Import/Export", "export_config": "Export configuration", "import_config": "Import configuration",
        "summary": "{groups} groups · {subgroups} subgroups · {servers} servers",
        "import_asbru": "Import Ásbrú configuration", "clear_config": "Delete all configuration", "configure_terminal": "Configure terminal", "local_terminal": "Local terminal", "new_tab": "New tab",
        "statistics": "Statistics", "statistics_title": "Statistics", "top_servers": "Most used servers", "no_statistics": "No statistics yet", "sessions": "Sessions", "duration": "Duration", "connections": "Connections",
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
            "- Configure terminal keybindings, including copy, paste and sending the saved password.\n"
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
