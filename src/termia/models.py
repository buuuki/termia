# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import dataclass, field

from .i18n import detect_system_language

DEFAULT_LS_COLORS = 'rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=40;31;01:mi=00:su=37;41:sg=30;43:ca=00:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arc=01;31:*.arj=01;31:*.taz=01;31:*.lha=01;31:*.lz4=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.tzo=01;31:*.t7z=01;31:*.zip=01;31:*.z=01;31:*.dz=01;31:*.gz=01;31:*.lrz=01;31:*.lz=01;31:*.lzo=01;31:*.xz=01;31:*.zst=01;31:*.tzst=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.war=01;31:*.ear=01;31:*.sar=01;31:*.rar=01;31:*.alz=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.cab=01;31:*.wim=01;31:*.swm=01;31:*.dwm=01;31:*.esd=01;31:*.avif=01;35:*.jpg=01;35:*.jpeg=01;35:*.mjpg=01;35:*.mjpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.webm=01;35:*.webp=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.ogv=01;35:*.ogx=01;35:*.aac=00;36:*.au=00;36:*.flac=00;36:*.m4a=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.oga=00;36:*.opus=00;36:*.spx=00;36:*.xspf=00;36:*~=00;90:*#=00;90:*.bak=00;90:*.crdownload=00;90:*.dpkg-dist=00;90:*.dpkg-new=00;90:*.dpkg-old=00;90:*.dpkg-tmp=00;90:*.old=00;90:*.orig=00;90:*.part=00;90:*.rej=00;90:*.rpmnew=00;90:*.rpmorig=00;90:*.rpmsave=00;90:*.swp=00;90:*.tmp=00;90:*.ucf-dist=00;90:*.ucf-new=00;90:*.ucf-old=00;90:'
DEFAULT_ANSI_PALETTE = ['#2e3436', '#b45d58', '#6f8f5f', '#aa8750', '#5f7f9f', '#8a6f8f', '#5f9292', '#c9c9c9', '#646b70', '#cf6f68', '#8fbf77', '#d2b45f', '#82a8c9', '#aa8aaa', '#83c4c4', '#eeeeec']



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
    show_sidebar_on_startup: bool = True
    show_session_status_bar: bool = True
    confirm_disconnect: bool = True
    confirm_close_app: bool = False
    sudo_password_shortcut: bool = False
    sudo_password_enter: bool = False
    connection_storage_mode: str = "plain"


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


@dataclass
class StoreData:
    groups: list[Group] = field(default_factory=list)
    servers: list[Server] = field(default_factory=list)
    terminal: TerminalSettings = field(default_factory=TerminalSettings)
    app: AppSettings = field(default_factory=AppSettings)
    statistics: StatisticsSettings = field(default_factory=StatisticsSettings)

