# MATE Icon Gallery

A small Python GTK3 application to browse installed icon themes on the MATE desktop.

## Features

- Preview installed icon themes with sample icons
- Search themes and icon names
- Adjust icon preview size
- Click an icon to copy its name
- Apply an icon theme to MATE

## Fedora installation

Install GTK3 and Python GObject bindings:

```bash
sudo dnf install python3-gobject gtk3
```

Download the script and run:

```bash
python3 mate_icon_gallery.py
```

Or clone the repository:

```bash
git clone https://github.com/solo2101/mate-icon-gallery.git
cd mate-icon-gallery
python3 mate_icon_gallery.py
```

## Requirements

- Python 3
- PyGObject (GObject introspection bindings)
- GTK 3
- MATE desktop for applying themes

The gallery reads installed themes from standard user and system icon directories. Applying a theme updates the MATE `org.mate.interface icon-theme` setting.

No ThemeChanger dependency.

## Status

Python syntax verified. GUI tested by users on Fedora MATE.
