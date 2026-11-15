# Third-party components

Termia does not vendor third-party source code or binaries. It dynamically uses
system packages and invokes system commands installed by the user.

| Component | Purpose | License | Project |
| --- | --- | --- | --- |
| Python | Runtime | PSF License | https://www.python.org/ |
| PyGObject | Python GObject bindings | LGPL-2.1-or-later | https://pygobject.gnome.org/ |
| GTK 4 | User interface toolkit | LGPL-2.1-or-later | https://www.gtk.org/ |
| GtkSourceView 5 | Notes text editor | LGPL-2.1-or-later | [Official API and license](https://gnome.pages.gitlab.gnome.org/gtksourceview/gtksourceview5/) |
| VTE | Embedded terminal widget | LGPL-3.0-or-later | https://gitlab.gnome.org/GNOME/vte |
| PyYAML | YAML parser for Asbru imports | MIT | https://pyyaml.org/ |
| Paramiko | Native SFTP transport | LGPL-2.1 | https://www.paramiko.org/ |
| cryptography | Connection and Notes encryption | Apache-2.0 OR BSD-3-Clause | [Upstream license](https://github.com/pyca/cryptography/blob/main/LICENSE) |
| OpenSSH client | SSH connections | BSD-style license | https://www.openssh.org/ |
| sshpass | Optional password-based SSH helper | GPL-2.0 | https://sourceforge.net/projects/sshpass/ |

These components are installed separately by the operating system package
manager and are not redistributed in this repository. Review the package terms
again if future releases bundle binaries, create installers that redistribute
packages, or copy third-party source code into the repository.
