# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gettext
import locale
import os
from functools import lru_cache
from pathlib import Path

DOMAIN = "termia"
LOCALE_DIR = Path(__file__).resolve().parent / "locale"
LANGUAGES = {"es": "Español", "ca": "Català", "en": "English"}


def detect_system_language() -> str:
    language = (locale.getlocale()[0] or os.environ.get("LANG") or "").lower()
    if language.startswith("ca"):
        return "ca"
    if language.startswith("es"):
        return "es"
    return "en"


def normalize_language(language: str | None) -> str:
    if language in LANGUAGES:
        return language
    return detect_system_language()


@lru_cache(maxsize=None)
def get_translation(language: str | None) -> gettext.NullTranslations:
    language = normalize_language(language)
    if language == "en":
        return gettext.NullTranslations()
    return gettext.translation(DOMAIN, localedir=LOCALE_DIR, languages=[language], fallback=True)


def translate_key(key: str, language: str | None) -> str:
    message = MESSAGES.get(key, key)
    return get_translation(language).gettext(message)


MESSAGES = {'servers': 'Show or hide server list',
 'new_group': 'New group',
 'new_server': 'New server',
 'new_local_terminal': 'New local terminal',
 'terminal': 'Terminal',
 'prompt': 'Prompt',
 'keybindings': 'Keybindings',
 'security': 'Security',
 'general': 'General',
 'preferences': 'Preferences',
 'filter_servers': 'Filter servers',
 'connect': 'Connect',
 'start_group': 'Start group',
 'edit_server': 'Edit server',
 'edit_local_terminal': 'Edit local terminal',
 'delete_server': 'Delete server',
 'delete_local_terminal': 'Delete local terminal',
 'clone_connection': 'Clone connection',
 'favorite_server': 'Favorite',
 'add_favorite': 'Add to favorites',
 'remove_favorite': 'Remove from favorites',
 'recent': 'Recent',
 'favorites': 'Favorites',
 'edit_group': 'Edit group',
 'delete_group': 'Delete group',
 'no_group': 'No group',
 'parent_group': 'Parent group',
 'no_parent_group': 'No parent group',
 'cancel': 'Cancel',
 'continue': 'Continue',
 'unlock': 'Unlock',
 'close': 'Close',
 'save': 'Save',
 'name': 'Name',
 'host': 'IP or host',
 'ssh_user': 'SSH user',
 'ssh_port': 'SSH port',
 'group': 'Group',
 'password': 'Password',
 'public_key': 'Private SSH key',
 'ssh_fingerprint_manual': 'New host: answer the fingerprint prompt in this terminal. Then enter '
                           'the password manually or with Ctrl+P.',
 'password_warning': 'Warning: the password will be stored in connections.json. You can switch '
                     'between plain text and obfuscated storage from Security.',
 'server_required_fields': 'Name, host, and SSH user are required.',
 'required_field': '* Required field',
 'reconnect_prompt': 'Press Enter to reconnect.',
 'close_tab_on_ssh_exit': 'Close the tab when leaving an SSH session with exit',
 'open_local_terminal_on_startup': 'Open a local terminal when Termia starts',
 'show_sidebar_on_startup': 'Show the server list when Termia starts',
 'delete_group_confirm': 'Delete group',
 'delete_group_confirm_detail': 'Delete {name}? All nested subgroups and servers will also be '
                                'deleted. This action cannot be undone.',
 'group_deleted': 'Group deleted: {name}',
 'theme': 'Theme',
 'theme_system': 'System',
 'theme_light': 'Light',
 'theme_dark': 'Dark',
 'language': 'Language',
 'restart_language': 'The language will apply after restarting the application.',
 'language_settings_saved': 'Language saved',
 'select_server': 'Select a server',
 'empty_detail_hint': 'Create groups and servers from the header bar.',
 'group_detail_info': '{count} server(s) in this group. Use Edit group or Delete group to manage it.',
 'server_detail_info': 'SSH: {user}@{host}\nPort: {port}\nGroup: {group}',
 'split': 'Split',
 'split_up': 'Split up',
 'split_down': 'Split down',
 'split_right': 'Split right',
 'split_left': 'Split left',
 'split_layout_none': 'No splits',
 'split_layout_columns': '2 columns',
 'split_layout_rows': '2 rows',
 'split_layout_left_rows': 'Left column split',
 'split_layout_right_rows': 'Right column split',
 'split_layout_top_columns': 'Top row split',
 'split_layout_bottom_columns': 'Bottom row split',
 'split_layout_grid': '2x2 grid',
 'tab': 'Tab',
 'close_tab': 'Close tab',
 'disconnect': 'Disconnect',
 'connecting': 'Connecting',
 'close_session_title': 'Close session',
 'close_ssh_session_confirm': 'Do you want to close this SSH session? The connection will be '
                              'disconnected.',
 'close_local_session_confirm': 'Do you want to close this local terminal? The running process '
                                'will be terminated.',
 'close_tab_on_disconnect': 'Close the tab when disconnecting a session',
 'show_session_status_bar': 'Show session status bar',
 'hide_status_bar': 'Hide',
 'statistics_enabled': 'Record local connection and duration statistics',
 'read_only_badge': 'Read-only',
 'read_only_mode_enabled': 'This Termia instance is running in read-only mode because another '
                           'instance already owns the write lock.',
 'read_only_mode_tooltip': 'Disabled while another Termia instance holds the write lock.',
 'confirm_disconnect': 'Confirm before disconnecting or closing an active session',
 'confirm_close_app': 'Confirm before closing Termia',
 'sudo_password_shortcut': 'Allow sending password with shortcut',
 'sudo_password_enter': 'Send password and press Enter',
 'sudo_password_sent': 'Saved password sent to the terminal',
 'sudo_password_unavailable': 'This terminal does not have a saved password',
 'send_files_to_server': 'Send files to server',
 'send_files_to_server_title': 'Uploading to {name}',
 'send_files_to_server_started': 'Transfer started to {name}',
 'send_files_to_server_running': 'Uploading to {name} in {destination}',
 'send_files_to_server_prepare_remote': 'Preparing remote directory...',
 'send_files_to_server_copying': 'Copying files...',
 'send_files_to_server_finished': 'Files sent to {name}',
 'send_files_to_server_failed_generic': 'Could not complete the transfer.',
 'send_files_to_server_failed_detail': 'Could not complete the transfer: {error}',
 'send_files_to_server_cancelled': 'Transfer cancelled.',
 'send_files_to_server_start_failed': 'Could not start file transfer: {error}',
 'send_files_to_server_missing': 'scp or ssh was not found in PATH.',
 'send_files_to_server_fingerprint': 'Confirm the host fingerprint in the terminal if prompted, '
                                     'then enter the password if needed.',
 'keybindings_description': 'Click a shortcut and press the combination you want. Use Clear to '
                            'leave it disabled so the combination reaches the remote shell.',
 'keybinding_capture_prompt': 'Press the combination',
 'keybinding_clear': 'Clear',
 'keybindings_restore_defaults': 'Restore defaults',
 'keybindings_settings_saved': 'Keybindings saved',
 'keybindings_conflict': 'Shortcut {shortcut} is already assigned to another action',
 'keybinding_disabled': 'Disabled',
 'keybinding_action_copy': 'Copy selection',
 'keybinding_action_paste': 'Paste clipboard',
 'keybinding_action_previous_tab': 'Previous tab',
 'keybinding_action_next_tab': 'Next tab',
 'keybinding_action_font_increase': 'Increase font',
 'keybinding_action_font_decrease': 'Decrease font',
 'keybinding_action_send_password': 'Send saved password',
 'close_app': 'Close Termia',
 'close_app_confirm': 'Do you want to close Termia?',
 'font_size': 'Font and size',
 'custom_prompt': 'Customize local prompt',
 'prompt_template': 'PS1 template',
 'prompt_color': 'Prompt color',
 'prompt_presets': 'Prompt themes',
 'prompt_datetime': 'Date and time',
 'prompt_datetime_none': 'No date/time',
 'prompt_datetime_time': 'Time',
 'prompt_datetime_time_seconds': 'Time with seconds',
 'prompt_datetime_date': 'Date',
 'prompt_datetime_both': 'Date and time',
 'prompt_settings_saved': 'Prompt settings saved',
 'terminal_settings_saved': 'Terminal preferences saved',
 'security_settings_saved': 'Security preferences saved',
 'local_terminal_cloned': 'Local terminal cloned',
 'terminal_font_size_changed': 'Terminal font size: {size}',
 'foreground': 'Foreground',
 'background': 'Background',
 'split_separator_color': 'Split separator color',
 'split_separator_thickness': 'Split separator thickness',
 'palettes': 'Palettes',
 'connection_storage_mode': 'Connection storage',
 'connection_storage_plain': 'Plain text',
 'connection_storage_obfuscated': 'Obfuscated',
 'connection_storage_encrypted': 'Encrypted',
 'connection_storage_obfuscated_warning': 'Obfuscation prevents accidental file reads, but it does '
                                          'not encrypt data or protect against an attacker with '
                                          'access to the code.',
 'enable_connection_encryption_title': 'Enable connection file encryption',
 'enable_connection_encryption_detail': 'Termia will encrypt the file that stores your servers, '
                                        'users, private key paths, and saved passwords.\n\n'
                                        'From now on, Termia will ask for the master password every '
                                        'time it starts.\n\n'
                                        'If you forget the master password, Termia cannot recover '
                                        'these data. You will need to restore them from a backup or '
                                        'configure them again manually.\n\n'
                                        'After reading this information, do you want to continue '
                                        'enabling encryption?',
 'master_password_title': 'Set master password',
 'master_password_detail': 'Choose the master password that will unlock your Termia connections.',
 'master_password': 'Master password',
 'confirm_master_password': 'Confirm master password',
 'enable_encryption': 'Enable encryption',
 'master_password_too_short': 'Use at least 8 characters.',
 'master_password_mismatch': 'The master passwords do not match.',
 'unlock_connections_title': 'Unlock connections',
 'unlock_connections_detail': 'Enter the master password to unlock your Termia connections.',
 'unlock_connections_failed': 'Could not unlock connections with this master password.',
 'connections_locked': 'Connections are locked until the master password is entered.',
 'connections_locked_tooltip': 'Unlock encrypted connections before changing configuration.',
 'connections_unlocked': 'Connections unlocked',
 'configuration': 'Configuration',
 'data_locations': 'Data locations',
 'data_locations_title': 'Data Locations',
 'data_locations_detail': 'Termia uses these local paths for configuration, connection data, '
                          'history, statistics, and the write lock.',
 'config_directory': 'Config directory',
 'connections_file_path': 'Connections file',
 'settings_file_path': 'Settings file',
 'instance_lock_file_path': 'Instance lock',
 'state_directory': 'State directory',
 'statistics_file_path': 'Statistics file',
 'connection_history_file_path': 'Connection history file',
 'path_exists': 'Exists',
 'path_missing': 'Not created yet',
 'connections_file': 'Import/Export',
 'export_config': 'Export configuration',
 'import_config': 'Import configuration',
 'summary': '{groups} groups · {subgroups} subgroups · {servers} servers',
 'import_asbru': 'Import Ásbrú configuration',
 'clear_config': 'Delete all configuration',
 'local_terminals': 'Local terminals',
 'connection_history': 'Connection history',
 'connection_history_title': 'Connection History',
 'no_connection_history': 'No connection history yet',
 'no_matching_history': 'No matching history entries',
 'clear_history': 'Clear history',
 'clear_history_confirm': 'Delete all connection history? This action cannot be undone.',
 'history_cleared': 'Connection history cleared',
 'search_history': 'Search history',
 'hide_local_terminals': 'Hide local terminals',
 'show_local_terminals': 'Show local terminals',
 'history_kind_ssh': 'SSH',
 'history_kind_local': 'Local terminal',
 'history_result_closed': 'Closed',
 'history_result_disconnected': 'Disconnected',
 'history_result_failed': 'Failed',
 'history_result_running': 'In progress',
 'working_directory': 'Working directory',
 'shell': 'Shell',
 'arguments': 'Arguments',
 'run_command_on_start': 'Run command on start',
 'title_shown_in_tab': 'Title shown in tab',
 'local_terminal_required_fields': 'Name and shell are required.',
 'local_terminal_invalid_arguments': 'Could not parse arguments: {error}',
 'local_terminal_settings_saved': 'Local terminal saved',
 'local_terminal_detail_info': 'Working directory: {working_directory}\nShell: {shell}\nArguments: {arguments}\nRun command on start: {command_on_start}\nTab title: {tab_title}',
 'configure_terminal': 'Configure terminal',
 'local_terminal': 'Local terminal',
 'new_tab': 'New tab',
 'statistics': 'Statistics',
 'statistics_title': 'Statistics',
 'top_servers': 'Most used servers',
 'no_statistics': 'No statistics yet',
 'sessions': 'Sessions',
 'duration': 'Duration',
 'connections': 'Connections',
 'global': 'Global',
 'current_run': 'Current run',
 'shortest_duration': 'Shortest duration',
 'longest_duration': 'Longest duration',
 'average_duration': 'Average duration',
 'copy': 'Copy',
 'paste': 'Paste',
 'session_statistics': 'Session statistics',
 'server_connections': 'Global connections to this server',
 'config_file_recovered': 'Recovered corrupt configuration. Backup created: {path}',
 'local_terminal_start_failed': 'Could not start local terminal: {error}',
 'local_terminal_retry_prompt': 'Press Enter to open a new local terminal.',
 'local_terminal_closed': 'Local terminal closed: {title}',
 'ssh_missing': 'The ssh client was not found in PATH.',
 'ssh_missing_status': 'No ssh',
 'sshpass_missing': 'sshpass was not found. Install sshpass or leave the password empty.',
 'sshpass_missing_status': 'No sshpass',
 'ssh_start_failed': 'Could not start ssh: {error}',
 'ssh_start_failed_toast': 'Could not start ssh for {name}',
 'ssh_connecting_command': 'Connecting: {command}',
 'session_opened': 'Session opened: {title}',
 'server_reconnect_missing': 'Could not find the server to reconnect',
 'disconnect_session_title': 'Disconnect session',
 'disconnect_session_detail': 'Do you want to disconnect {title}?',
 'disconnect_session_confirm': 'Disconnect',
 'sigterm_failed': 'Could not send SIGTERM to the ssh process.',
 'session_disconnected_terminal': 'Session disconnected.',
 'session_disconnected_status': 'Disconnected: {title}',
 'session_disconnected_toast': 'Session disconnected: {title}',
 'session_closed_status': 'Closed: {title}',
 'session_closed_toast': 'Session closed: {title}',
 'tab_closed_title': '{title} (closed)',
 'tab_disconnected_title': '{title} (disconnected)',
 'tab_error_title': '{title} (error)',
 'connection_failed_toast': 'Connection failed: {title}',
 'export_config_success': 'Configuration exported',
 'import_config_failed': 'Could not import JSON: {error}',
 'import_config_success': 'Configuration imported',
 'import_asbru_failed': 'Could not import Ásbrú YAML: {error}',
 'import_asbru_invalid': 'The Ásbrú YAML does not have a compatible format',
 'import_asbru_success': 'Ásbrú: imported {groups} groups and {servers} servers',
 'clear_confirm': 'Delete all groups and servers? This action cannot be undone.',
 'rename_tab': 'Rename tab',
 'duplicate_tab': 'Duplicate tab',
 'detach_tab': 'Move to new window',
 'expand_all': 'Expand all groups',
 'collapse_all': 'Collapse all groups',
 'help': 'Help',
 'about': 'About',
 'report_issue': 'Report an issue',
 'main_menu': 'Main menu',
 'help_title': 'Termia Help',
 'help_content': 'Termia is an SSH connection manager with embedded terminals.\n'
                 '\n'
                 'Main features:\n'
                 '- Organize servers into groups and subgroups.\n'
                 '- Create, edit, delete, clone and filter SSH connections.\n'
                 '- Mark servers as favorites for quick access from a dedicated section.\n'
                 '- Open connections and local terminals from the sidebar in embedded, compact '
                 'and detachable tabs.\n'
                 '- View a statistics dashboard with global metrics, durations and most used '
                 'servers, plus per-session statistics.\n'
                 '- The session status bar shows status, PID, duration and disconnect controls; it '
                 'can be enabled from General, hidden per session and restored from the context '
                 'menu.\n'
                 '- Configure terminal keybindings, including copy, paste and sending the saved '
                 'password.\n'
                 '- Configure general options, the VTE terminal, split separators and the PS1 '
                 'prompt separately.\n'
                 '- The local prompt supports color, presets, time, date and live preview without '
                 'modifying remote sessions.\n'
                 '- View a local connection history with timestamps, outcomes and durations.\n'
                 '- Import and export configurations, including basic imports from Ásbrú.\n'
                 '\n'
                 'Quick start:\n'
                 'Use the sidebar icons to create groups, servers or local terminal profiles. '
                 'Double-click a server or local terminal profile to connect. Right-click '
                 'servers, tabs or terminals to access contextual actions such as duplicate, '
                 'split panes, disconnect, copy, paste, show the status bar or view statistics.',
 'about_content': 'SSH connection manager with embedded terminals'}
