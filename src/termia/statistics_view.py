# SPDX-FileCopyrightText: 2026 Jordi Pons
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .statistics_utils import average_session_duration, format_duration, top_server_statistics


class StatisticsViewMixin:
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
        average_duration = average_session_duration(stats)
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
            self.build_stat_card(self.t("sessions"), str(stats.completed_sessions), self.t("global")),
            1, 0, 1, 1
        )
        cards.attach(
            self.build_stat_card(self.t("average_duration"), format_duration(average_duration), self.t("duration")),
            2, 0, 1, 1
        )
        cards.attach(
            self.build_stat_card(
                self.t("longest_duration"),
                format_duration(stats.duration_max if stats.completed_sessions else None),
                f"{self.t('shortest_duration')}: {format_duration(stats.duration_min)}",
            ),
            0, 1, 1, 1
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

        ranked = top_server_statistics(stats, self.store.data.servers)
        max_count = max((item.count for item in ranked), default=1)
        for item in ranked:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            row_box.add_css_class("stat-row")
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            name_label = Gtk.Label(label=f"{item.index}. {item.name}")
            name_label.set_xalign(0)
            name_label.set_hexpand(True)
            count_label = Gtk.Label(label=str(item.count))
            count_label.set_xalign(1)
            count_label.add_css_class("heading")
            header.append(name_label)
            header.append(count_label)
            row_box.append(header)
            if item.subtitle:
                subtitle_label = Gtk.Label(label=item.subtitle)
                subtitle_label.set_xalign(0)
                subtitle_label.add_css_class("dim-label")
                row_box.append(subtitle_label)
            progress = Gtk.LevelBar.new_for_interval(0, max_count)
            progress.set_value(item.count)
            progress.set_hexpand(True)
            row_box.append(progress)
            row.set_child(row_box)
            list_box.append(row)
        return list_box

    def refresh_statistics_menu(self) -> None:
        return
