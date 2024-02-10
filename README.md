# Twitch Indicator

*This program is not affiliated, authorized, endorsed by, or in any way
officially connected to Twitch.*

![screenshot 1](https://raw.githubusercontent.com/buzz/twitch-indicator/main/img/screenshot-1.webp)
![screenshot 2](https://raw.githubusercontent.com/buzz/twitch-indicator/main/img/screenshot-2.webp)

Twitch Indicator for Linux. Tracks your followed channels and notifies when they go live.

## Installation

### Arch Linux

Available in AUR: [twitch-indicator](https://aur.archlinux.org/packages/twitch-indicator/)

### Install manually

```
cd twitch-indicator
sudo ./setup.sh
twitch-indicator &
```

## Push vs. Poll

### Push Notification Limit

You can subscribe to a maximum of **10 real-time push notifications**
concurrently, as enforced by the Twitch API.

### Additional Streams

You are unrestricted in enabling additional streams beyond the push notification
limit. These streams will operate in **polling mode**, ensuring notifications
are received according to the configured refresh interval.

## Credits

Forked from [twitch-indicator](https://github.com/rolandasb/twitch-indicator) by
[Rolandas Barysas](https://github.com/rolandasb).

## License

Licensed under [GNU General Public License
v2.0](https://github.com/buzz/twitch-indicator/blob/master/LICENSE.txt).

Previously licensed under [zlib
License](https://github.com/buzz/twitch-indicator/blob/5ffcbe9bc776396a690fa2f839d7e753313a701b/LICENSE).
