# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import sys
import tempfile


logger = logging.getLogger(__name__)
API_VERSION = 2


class PluginIncompatible(ValueError):
    pass


@dataclass
class Plugin:
    id: str
    directory: Path
    names: dict
    version: str = ""
    icon: str = "application-x-addon-symbolic"
    module: str = ""
    capabilities: tuple = ()
    default_enabled: bool = False
    requested_enabled: bool = False
    problem: str = ""
    instance: object = None
    loaded_module: object = None

    def name(self, language):
        return self.names.get(language, self.names.get("en", self.id))


class PluginRuntime:
    def __init__(self, root, profile, capabilities, *, blocked=False, changed=lambda: None):
        self.root = Path(root)
        self.profile = Path(profile)
        self.capabilities = dict(capabilities)
        self.blocked = blocked
        self.changed = changed
        self.plugins = {}
        for manifest in sorted(self.root.glob("*/plugin.json")):
            plugin = Plugin(manifest.parent.name, manifest.parent, {"en": manifest.parent.name})
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                identifier = data["id"]
                if not isinstance(identifier, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", identifier):
                    raise ValueError("Invalid plugin identifier")
                if identifier != manifest.parent.name:
                    raise ValueError("Plugin identifier must match its directory")
                names = data["name"]
                if not isinstance(names, dict) or not names.get("en") or not all(
                    isinstance(k, str) and isinstance(v, str) and v for k, v in names.items()
                ):
                    raise ValueError("Invalid plugin names")
                plugin.names = names
                plugin.version = data["version"]
                plugin.icon = data["icon"]
                plugin.module = data["module"]
                if not all(isinstance(v, str) and v for v in (plugin.version, plugin.icon, plugin.module)):
                    raise ValueError("Invalid metadata")
                if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", plugin.module):
                    raise ValueError("Invalid module name")
                requested = data["capabilities"]
                if not isinstance(requested, list) or not all(isinstance(k, str) for k in requested):
                    raise ValueError("Invalid capabilities")
                if any(k not in self.capabilities for k in requested):
                    raise PluginIncompatible("Unsupported capability")
                plugin.capabilities = tuple(requested)
                plugin.default_enabled = data.get("default_enabled", False)
                if type(plugin.default_enabled) is not bool:
                    raise ValueError("Invalid default state")
                if type(data["api_version"]) is not int or data["api_version"] != API_VERSION:
                    raise PluginIncompatible("Incompatible API")
                if not (plugin.directory / "src" / plugin.module / "__init__.py").is_file():
                    raise FileNotFoundError("Plugin code missing")
            except PluginIncompatible:
                plugin.problem = "addon_incompatible"
                logger.exception("Incompatible plugin %s", manifest.parent.name)
            except FileNotFoundError:
                plugin.problem = "addon_missing"
                logger.exception("Missing plugin %s", manifest.parent.name)
            except Exception:
                plugin.problem = "addon_metadata_failed"
                logger.exception("Cannot read plugin %s", manifest.parent.name)
            self.plugins[plugin.id] = plugin
            try:
                plugin.requested_enabled = self._enabled(plugin)
            except Exception:
                plugin.problem = "addon_state_failed"
                logger.exception("Cannot read plugin preference %s", plugin.id)
            if not plugin.problem and not blocked and plugin.requested_enabled:
                try:
                    plugin.instance = self._create(plugin)
                except PluginIncompatible:
                    plugin.problem = "addon_incompatible"
                    logger.exception("Incompatible plugin %s", plugin.id)
                except Exception:
                    plugin.problem = "addon_load_failed"
                    logger.exception("Cannot start plugin %s", plugin.id)
        # Retain saved choices even when a previously configured plugin is removed.
        for state in sorted(self.profile.glob("*-addon.disabled")):
            identifier = state.name.removesuffix("-addon.disabled")
            if identifier in self.plugins or not re.fullmatch(r"[a-z][a-z0-9_-]*", identifier):
                continue
            plugin = Plugin(identifier, self.root / identifier, {"en": identifier},
                            problem="addon_missing")
            self.plugins[identifier] = plugin
            try:
                plugin.requested_enabled = self._enabled(plugin)
            except Exception:
                plugin.problem = "addon_state_failed"
                logger.exception("Cannot read missing plugin preference %s", identifier)

    def _state_path(self, plugin):
        return self.profile / f"{plugin.id}-addon.disabled"

    def _enabled(self, plugin):
        path = self._state_path(plugin)
        if path.exists():
            # Existing empty markers mean disabled.
            value = path.read_text(encoding="utf-8").strip()
            if value not in {"", "enabled", "disabled"}:
                raise ValueError("Invalid saved plugin preference")
            return value == "enabled"
        return plugin.default_enabled

    def _save(self, plugin, enabled):
        self.profile.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=self.profile, delete=False) as stream:
                temporary = stream.name
                stream.write("enabled\n" if enabled else "disabled\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._state_path(plugin))
            temporary = None
        finally:
            if temporary is not None:
                os.unlink(temporary)

    def _create(self, plugin):
        if plugin.loaded_module is None:
            entry = plugin.directory / "src" / plugin.module / "__init__.py"
            namespace = "termia_plugin_" + plugin.id.replace("-", "_")
            if namespace in sys.modules:
                raise RuntimeError("Plugin module namespace collision")
            spec = importlib.util.spec_from_file_location(namespace, entry,
                                                        submodule_search_locations=[str(entry.parent)])
            if spec is None or spec.loader is None:
                raise RuntimeError("Cannot load plugin")
            module = importlib.util.module_from_spec(spec)
            sys.modules[namespace] = module
            try:
                spec.loader.exec_module(module)
                if getattr(module, "API_VERSION", None) != API_VERSION:
                    raise PluginIncompatible("Incompatible module API")
                if not callable(getattr(module, "create", None)):
                    raise RuntimeError("Missing factory")
            except Exception:
                for key in tuple(sys.modules):
                    if key == namespace or key.startswith(namespace + "."):
                        del sys.modules[key]
                raise
            plugin.loaded_module = module
        instance = plugin.loaded_module.create(**{
            key: self.capabilities[key] for key in plugin.capabilities
        })
        if not callable(getattr(instance, "show", None)) or not callable(getattr(instance, "close", None)):
            close = getattr(instance, "close", None)
            if callable(close):
                close()
            raise RuntimeError("Invalid plugin controller")
        return instance

    def options(self, language):
        return [
            (p.id, p.name(language), "addon_launch_disabled" if self.blocked else p.problem,
             p.requested_enabled,
             not self.blocked and (not p.problem or p.requested_enabled or p.instance is not None))
            for p in self.plugins.values()
        ]

    def set_enabled(self, identifier, enabled):
        plugin = self.plugins[identifier]
        if self.blocked or (enabled and plugin.problem):
            raise RuntimeError("Plugin unavailable")
        if enabled:
            if plugin.requested_enabled and plugin.instance is not None:
                return
            try:
                candidate = self._create(plugin)
            except PluginIncompatible:
                plugin.problem = "addon_incompatible"
                self.changed()
                raise
            except Exception:
                plugin.problem = "addon_load_failed"
                logger.exception("Cannot activate plugin %s", identifier)
                self.changed()
                raise
            try:
                self._save(plugin, True)
            except Exception:
                try:
                    candidate.close()
                except Exception:
                    plugin.instance = candidate
                    plugin.problem = "addon_cleanup_pending"
                    logger.exception("Cannot close unsaved plugin %s", identifier)
                    self.changed()
                raise
            plugin.instance = candidate
            plugin.requested_enabled = True
        else:
            # Keep the user's disabled choice even if cleanup fails.
            self._save(plugin, False)
            plugin.requested_enabled = False
            if plugin.instance is not None:
                try:
                    plugin.instance.close()
                except Exception:
                    plugin.problem = "addon_cleanup_pending"
                    logger.exception("Plugin cleanup requires restart: %s", identifier)
                    self.changed()
                    raise
                plugin.instance = None
        self.changed()

    def show(self, identifier, language):
        plugin = self.plugins[identifier]
        if plugin.instance is not None:
            try:
                plugin.instance.show(language)
            except Exception:
                plugin.problem = "addon_open_failed"
                logger.exception("Cannot open plugin %s", identifier)
                try:
                    plugin.instance.close()
                    plugin.instance = None
                except Exception:
                    plugin.problem = "addon_cleanup_pending"
                    logger.exception("Cannot close failed plugin %s", identifier)
                self.changed()

    def close(self, *_args):
        for plugin in self.plugins.values():
            if plugin.instance is not None:
                try:
                    plugin.instance.close()
                except Exception:
                    logger.exception("Cannot stop plugin %s", plugin.id)
                else:
                    plugin.instance = None
