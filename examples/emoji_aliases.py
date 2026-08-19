"""Emoji aliases: pick your own or let the server roll one.

The SDK validates emoji aliases before sending, against the server's own
accepted catalogue (GET /emoji-set, fetched once per client and cached).

Run: python examples/emoji_aliases.py
"""

from spoo import AliasType, SpooClient


def main() -> None:
    with SpooClient() as client:
        # Auto-generate an emoji code
        url = client.shorten("https://example.com", alias_type=AliasType.EMOJI)
        print(f"generated : {url.short_url}")

        # Pick your own; the SDK checks it against the accepted set first
        check = client.links.check_alias("🚀🔥")
        if check.available:
            url = client.shorten("https://example.com", alias="🚀🔥")
            print(f"custom    : {url.short_url}")
        else:
            print(f"🚀🔥 unavailable: {check.reason}")

        # The catalogue itself, e.g. to build a picker
        emoji_set = client.links.emoji_set()
        rockets = [e for e in emoji_set.emoji if "rocket" in e.n]
        print(
            f"catalogue : {len(emoji_set.emoji)} emoji, "
            f"aliases up to {emoji_set.max_graphemes} long, {rockets[0].c} is in"
        )


if __name__ == "__main__":
    main()
