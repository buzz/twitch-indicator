# Twitch Indicator

*This program is not affiliated, authorized, endorsed by, or in any way
officially connected to Twitch.*

![screenshot 1](https://raw.githubusercontent.com/buzz/twitch-indicator/main/img/screenshot-1.webp)
![screenshot 2](https://raw.githubusercontent.com/buzz/twitch-indicator/main/img/screenshot-2.webp)

Twitch Indicator for Linux. Tracks your followed channels and notifies when they go live.

## Installation

### Arch Linux

Available in AUR: [twitch-indicator](https://aur.archlinux.org/packages/twitch-indicator/)

### Install using pipx

[pipx](https://pipx.pypa.io/stable/installation/) handles virtual
environment creation and package installation for you automatically.

```
# install package
$ pipx ensurepath
$ pipx install git+https://github.com/buzz/twitch-indicator

# install files
$ mkdir -p \
  $HOME/.local/share/applications \
  $HOME/.local/share/glib-2.0/schemas
$ wget -q \
  -O $HOME/.local/share/icons/twitch-indicator.svg \
  https://raw.githubusercontent.com/buzz/twitch-indicator/main/twitch_indicator/data/twitch-indicator.svg
$ wget -q \
  -O $HOME/.local/share/glib-2.0/schemas/apps.twitch-indicator.gschema.xml \
  https://raw.githubusercontent.com/buzz/twitch-indicator/main/data/apps.twitch-indicator.gschema.xml
$ wget -q \
  -O $HOME/.local/share/applications/twitch-indicator.desktop \
  https://raw.githubusercontent.com/buzz/twitch-indicator/main/data/twitch-indicator.desktop

# compile settings schema
$ glib-compile-schemas $HOME/.local/share/glib-2.0/schemas
```

## Credits

Forked from [twitch-indicator](https://github.com/rolandasb/twitch-indicator) by
[Rolandas Barysas](https://github.com/rolandasb).

## License

Licensed under [GNU General Public License
v3.0](https://github.com/buzz/twitch-indicator/blob/master/LICENSE.txt).

Previously licensed under [zlib
License](https://github.com/buzz/twitch-indicator/blob/5ffcbe9bc776396a690fa2f839d7e753313a701b/LICENSE).
