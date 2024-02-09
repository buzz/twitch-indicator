from urllib.error import URLError

from gi.repository import GLib

from twitch_indicator.errors import NotAuthorizedException


class StreamFetcher:

    def refresh_streams(self):
        """Refresh live streams list. Also push notifications when needed."""
        settings = self.settings

        GLib.idle_add(self.indicator.disable_check_now)

        # Get Twitch user ID
        if self.user_id is None:
            try:
                self.user_id = self.api.get_user_id()
            except NotAuthorizedException:
                GLib.idle_add(self.not_authorized)
                return
            except URLError as err:
                self.refresh_failed("Cannot retrieve user ID from Twitch", err)
                return

        # Fetch followed channels
        try:
            self.followed_channels = self.api.fetch_followed_channels(self.user_id)
        except NotAuthorizedException:
            GLib.idle_add(self.not_authorized)
            return
        except URLError as err:
            self.refresh_failed("Cannot retrieve channel list from Twitch", err)
            return

        # Are there channels that the user follows?
        if self.followed_channels:
            GLib.idle_add(self.settings.enable_channel_chooser)

            # Fetch live streams
            try:
                new_live_streams = self.api.fetch_live_streams(
                    [ch["id"] for ch in self.followed_channels]
                )
            except NotAuthorizedException:
                GLib.idle_add(self.not_authorized)
                return
            except URLError as err:
                self.refresh_failed("Cannot retrieve live streams from Twitch", err)
                return

            # Are there *live* streams?
            if new_live_streams:

                # Update menu with live streams
                GLib.idle_add(self.indicator.add_streams_menu, new_live_streams)

                # Check which streams were not live before, create separate list for
                # notifications and update main livestreams list.
                # We check live streams by URL, because sometimes Twitch API does not
                # show stream status, which makes notifications appear even if stream
                # has been live before.
                notify_list = list(new_live_streams)
                for old_stream in self.live_streams:
                    for new_stream in new_live_streams:
                        if old_stream["url"] == new_stream["url"]:
                            notify_list[:] = [
                                d
                                for d in notify_list
                                if d.get("url") != new_stream["url"]
                            ]
                            break

                self.live_streams = new_live_streams

                # Only show notifications for enabled streams
                notify_list = [
                    stream
                    for stream in notify_list
                    if stream["id"] not in self.channel_chooser.enabled_channel_ids
                    or self.channel_chooser.enabled_channel_ids[stream["id"]]
                ]

                # Push notifications of new streams
                if settings.get_boolean("enable-notifications"):
                    GLib.idle_add(self.notifications.show_streams, notify_list)

        # Schedule next periodic fetch
        GLib.idle_add(self.start_timer)

        # Re-enable "Check now" button
        GLib.idle_add(self.indicator.enable_check_now)

    def refresh_failed(self, msg, err):
        """Handle network error while fetching data."""
        interval = self.settings.get_int("refresh-interval")
        GLib.idle_add(
            self.indicator.abort_refresh,
            err,
            msg,
            f"Retrying in {interval} minutes...",
        )
        GLib.idle_add(self.start_timer)
