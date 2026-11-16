#!/usr/bin/env python3
"""Small GTK3 icon-theme browser for the MATE desktop."""

import configparser
import os
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk


SAMPLES = [
    "folder", "folder-documents", "folder-download", "folder-music",
    "folder-pictures", "folder-videos", "user-home", "user-trash",
    "document-new", "document-open", "document-save", "document-print",
    "edit-copy", "edit-paste", "edit-delete", "edit-find",
    "view-refresh", "view-fullscreen", "go-home", "go-next",
    "system-search", "system-file-manager", "system-software-install",
    "system-shutdown", "preferences-system", "preferences-desktop",
    "preferences-desktop-theme", "utilities-terminal", "accessories-calculator",
    "accessories-text-editor", "internet-web-browser", "internet-mail",
    "multimedia-volume-control", "media-playback-start", "media-playback-pause",
    "media-skip-forward", "audio-volume-high", "audio-volume-muted",
    "network-wireless", "network-wired", "network-server", "computer",
    "drive-harddisk", "drive-removable-media", "printer", "camera-photo",
    "audio-headphones", "input-keyboard", "input-mouse", "battery-full",
    "dialog-information", "dialog-warning", "dialog-error", "dialog-question",
    "emblem-favorite", "emblem-important", "weather-clear", "weather-overcast",
    "application-x-executable", "text-x-generic", "image-x-generic",
    "video-x-generic", "audio-x-generic", "application-pdf",
]
MINI = ["folder", "user-home", "utilities-terminal", "preferences-system"]
MAX_SEARCH_RESULTS = 160


def icon_roots():
    roots = [Path.home() / ".icons", Path.home() / ".local/share/icons"]
    xdg = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    roots += [Path(base) / "icons" for base in xdg.split(":") if base]
    roots += [Path("/usr/share/icons"), Path("/usr/local/share/icons")]
    unique = []
    for path in roots:
        if path not in unique and path.is_dir():
            unique.append(path)
    return unique


def find_themes(roots):
    found = {}
    for root in roots:
        for directory in root.iterdir():
            index = directory / "index.theme"
            if not index.is_file() or directory.name in ("hicolor", "default"):
                continue
            parser = configparser.ConfigParser(interpolation=None)
            try:
                parser.read(index, encoding="utf-8")
                if parser.getboolean("Icon Theme", "Hidden", fallback=False):
                    continue
                label = parser.get("Icon Theme", "Name", fallback=directory.name)
                found.setdefault(directory.name, label)
            except (OSError, configparser.Error):
                continue
    return sorted(found.items(), key=lambda x: (x[1].casefold(), x[0].casefold()))


def gtk_theme(name, roots):
    theme = Gtk.IconTheme.new()
    theme.set_search_path([str(path) for path in roots])
    theme.set_custom_theme(name)
    return theme


def icon_picture(theme, name, size):
    try:
        pixbuf = theme.load_icon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
        return Gtk.Image.new_from_pixbuf(pixbuf) if pixbuf else None
    except GLib.Error:
        return None


def label(text, xalign=0):
    widget = Gtk.Label(label=text, xalign=xalign)
    widget.set_line_wrap(True)
    return widget


class Gallery(Gtk.Window):
    def __init__(self):
        super().__init__(title="MATE Icon Gallery")
        self.set_default_size(1060, 710)
        self.set_border_width(12)
        self.roots = icon_roots()
        self.themes = find_themes(self.roots)
        self.cached = {}
        self.selected = None
        self.cards = {}
        self.badges = {}
        self.update_source = None

        source = Gio.SettingsSchemaSource.get_default()
        schema = source.lookup("org.mate.interface", True) if source else None
        self.settings = Gio.Settings.new("org.mate.interface") if schema else None
        self.active_name = self.settings.get_string("icon-theme") if self.settings else ""

        css = Gtk.CssProvider()
        css.load_from_data(b"""
            .theme-tile { border: 1px solid alpha(@theme_fg_color, 0.15);
                          border-radius: 9px; padding: 10px; }
            .icon-tile { padding: 9px 4px; border-radius: 8px; }
            .big-title { font-size: 19px; font-weight: bold; }
            .subtle { opacity: .7; }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        split = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        split.set_position(390)
        split.set_wide_handle(True)
        self.add(split)

        # Left: installed icon themes, each with several real icon previews.
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left.set_margin_end(12)
        split.pack1(left, resize=False, shrink=False)
        left.add(label("Installed icon themes"))
        self.theme_search = Gtk.SearchEntry()
        self.theme_search.set_placeholder_text("Search themes...")
        self.theme_search.connect("search-changed", self.filter_themes)
        left.pack_start(self.theme_search, False, False, 0)

        theme_scroller = Gtk.ScrolledWindow()
        theme_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left.pack_start(theme_scroller, True, True, 0)
        self.theme_grid = Gtk.FlowBox()
        self.theme_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.theme_grid.set_min_children_per_line(2)
        self.theme_grid.set_max_children_per_line(2)
        self.theme_grid.set_row_spacing(9)
        self.theme_grid.set_column_spacing(9)
        self.theme_grid.set_valign(Gtk.Align.START)
        self.theme_grid.connect("selected-children-changed", self.choose_theme)
        theme_scroller.add(self.theme_grid)

        # Right: preview individual icons, without applying the theme.
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.set_margin_start(12)
        split.pack2(right, resize=True, shrink=False)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        right.pack_start(header, False, False, 0)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        header.pack_start(titles, True, True, 0)
        self.theme_title = label("Select a theme")
        self.theme_title.get_style_context().add_class("big-title")
        titles.add(self.theme_title)
        self.theme_subtitle = label("Choose a theme to preview its icons")
        self.theme_subtitle.get_style_context().add_class("subtle")
        titles.add(self.theme_subtitle)
        self.apply_button = Gtk.Button(label="Apply theme")
        self.apply_button.connect("clicked", self.apply_theme)
        self.apply_button.set_sensitive(False)
        header.pack_end(self.apply_button, False, False, 0)

        tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        right.pack_start(tools, False, False, 0)
        self.icon_search = Gtk.SearchEntry()
        self.icon_search.set_placeholder_text("Search icons by name...")
        self.icon_search.connect("search-changed", self.schedule_icons)
        tools.pack_start(self.icon_search, True, True, 0)
        tools.pack_start(label("Size"), False, False, 0)
        self.size_select = Gtk.ComboBoxText()
        for value in (32, 48, 64, 96):
            self.size_select.append_text(str(value))
        self.size_select.set_active(1)
        self.size_select.connect("changed", lambda *_: self.show_icons())
        tools.pack_start(self.size_select, False, False, 0)

        icon_scroller = Gtk.ScrolledWindow()
        icon_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        right.pack_start(icon_scroller, True, True, 0)
        self.icon_grid = Gtk.FlowBox()
        self.icon_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.icon_grid.set_min_children_per_line(3)
        self.icon_grid.set_max_children_per_line(9)
        self.icon_grid.set_row_spacing(12)
        self.icon_grid.set_column_spacing(8)
        self.icon_grid.set_valign(Gtk.Align.START)
        self.icon_grid.connect("child-activated", self.copy_icon_name)
        icon_scroller.add(self.icon_grid)

        self.status = label("Click an icon to copy its name")
        self.status.get_style_context().add_class("subtle")
        right.pack_end(self.status, False, False, 0)

        for name, display_name in self.themes:
            theme = self.get_theme(name)
            tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
            tile.get_style_context().add_class("theme-tile")
            pictures = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            pictures.set_halign(Gtk.Align.CENTER)
            for icon_name in MINI:
                image = icon_picture(theme, icon_name, 35)
                if image:
                    pictures.pack_start(image, False, False, 0)
            tile.add(pictures)
            title = label(display_name, xalign=0.5)
            title.set_max_width_chars(19)
            title.set_ellipsize(3)  # Pango.EllipsizeMode.END
            tile.pack_start(title, False, False, 0)
            tag = label("Currently active", xalign=0.5)
            tag.get_style_context().add_class("subtle")
            tag.set_no_show_all(True)
            tag.set_visible(name == self.active_name)
            tile.add(tag)
            self.badges[name] = tag
            child = Gtk.FlowBoxChild()
            child.theme_name = name
            child.add(tile)
            self.theme_grid.add(child)
            self.cards[name] = child

        if not self.themes:
            left.pack_start(label("No icon themes found in standard icon directories."), False, False, 0)
        self.show_all()
        first = self.active_name if self.active_name in self.cards else (self.themes[0][0] if self.themes else None)
        if first:
            self.theme_grid.select_child(self.cards[first])

    def get_theme(self, name):
        if name not in self.cached:
            self.cached[name] = gtk_theme(name, self.roots)
        return self.cached[name]

    def filter_themes(self, *_):
        term = self.theme_search.get_text().casefold().strip()
        for name, display in self.themes:
            self.cards[name].set_visible(term in name.casefold() or term in display.casefold())

    def choose_theme(self, grid):
        items = grid.get_selected_children()
        if not items:
            return
        self.selected = items[0].theme_name
        display = dict(self.themes).get(self.selected, self.selected)
        self.theme_title.set_text(display)
        self.theme_subtitle.set_text(
            self.selected + ("  ·  Currently active" if self.selected == self.active_name else "")
        )
        self.apply_button.set_sensitive(bool(self.settings) and self.selected != self.active_name)
        self.show_icons()

    def schedule_icons(self, *_):
        if self.update_source is not None:
            GLib.source_remove(self.update_source)
        self.update_source = GLib.timeout_add(180, self.refresh_after_search)

    def refresh_after_search(self):
        self.update_source = None
        self.show_icons()
        return False

    def show_icons(self):
        for child in self.icon_grid.get_children():
            self.icon_grid.remove(child)
        if not self.selected:
            return
        theme = self.get_theme(self.selected)
        term = self.icon_search.get_text().casefold().strip()
        if term:
            names = sorted(
                name for name in theme.list_icons(None)
                if term in name.casefold()
            )[:MAX_SEARCH_RESULTS]
        else:
            names = SAMPLES
        size = int(self.size_select.get_active_text() or "48")
        shown = 0
        for name in names:
            image = icon_picture(theme, name, size)
            if not image:
                continue
            tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
            tile.get_style_context().add_class("icon-tile")
            image.set_halign(Gtk.Align.CENTER)
            tile.pack_start(image, False, False, 0)
            short_name = Gtk.Label(label=name)
            short_name.set_max_width_chars(16)
            short_name.set_ellipsize(3)
            short_name.set_tooltip_text(name)
            tile.pack_start(short_name, False, False, 0)
            child = Gtk.FlowBoxChild()
            child.icon_name = name
            child.add(tile)
            self.icon_grid.add(child)
            shown += 1
        self.icon_grid.show_all()
        self.status.set_text(
            f"{shown} icons displayed. Click an icon to copy its name."
            + (" Narrow your search to see more." if term and len(names) == MAX_SEARCH_RESULTS else "")
        )

    def copy_icon_name(self, grid, child):
        name = child.icon_name
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(name, -1)
        clipboard.store()
        self.status.set_text(f"Copied: {name}")

    def apply_theme(self, *_):
        if not (self.settings and self.selected):
            return
        if self.settings.set_string("icon-theme", self.selected):
            self.active_name = self.selected
            for name, badge in self.badges.items():
                badge.set_visible(name == self.active_name)
            self.theme_subtitle.set_text(self.selected + "  ·  Currently active")
            self.apply_button.set_sensitive(False)
            self.status.set_text(f"Applied {self.selected} to MATE")
        else:
            self.status.set_text("Unable to change MATE's icon theme")


if __name__ == "__main__":
    window = Gallery()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()