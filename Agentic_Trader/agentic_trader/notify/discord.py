"""Discord REST posting. Without a token/channel, messages go to state/discord_outbox.log (dry run)."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import requests

from ..config import STATE_DIR, Settings

API = "https://discord.com/api/v10/channels/{cid}/messages"


class DiscordNotifier:
    def __init__(self, s: Settings, echo: bool = True):
        self.token = s.discord_token
        self.channels = {"realtime": s.discord_realtime_channel, "updates": s.discord_updates_channel}
        self.echo = echo
        self.sent: list[tuple[str, str]] = []  # (channel_key, text) - handy for tests

    @property
    def live(self) -> bool:
        return bool(self.token)

    def post(self, channel: str, text: str, image_path: str | None = None) -> bool:
        self.sent.append((channel, text))
        cid = self.channels.get(channel, "")
        if not (self.token and cid):
            self._outbox(channel, text)
            return False
        for chunk in (text[i:i + 1900] for i in range(0, len(text), 1900)):
            for attempt in range(3):
                r = requests.post(API.format(cid=cid), timeout=15, json={"content": chunk},
                                  headers={"Authorization": f"Bot {self.token}"})
                if r.status_code == 429:
                    time.sleep(float(r.json().get("retry_after", 1)))
                    continue
                if r.status_code >= 300:
                    print(f"[discord] {r.status_code}: {r.text[:200]}")
                    self._outbox(channel, chunk)
                    return False
                break
        if image_path:
            return self._post_image(cid, image_path, channel)
        return True

    def _post_image(self, cid: str, image_path: str, channel: str) -> bool:
        try:
            with open(image_path, "rb") as fh:
                r = requests.post(API.format(cid=cid), timeout=30, headers={"Authorization": f"Bot {self.token}"},
                                  files={"files[0]": (Path(image_path).name, fh, "image/png")})
            if r.status_code < 300:
                return True
            print(f"[discord] chart upload {r.status_code}: {r.text[:200]}")
        except Exception as exc:
            print("[discord] chart upload failed:", repr(exc))
        self._outbox(channel, f"(chart not sent: {image_path})")
        return False

    def _outbox(self, channel: str, text: str) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_DIR / "discord_outbox.log", "a") as f:
            f.write(f"--- {datetime.now().isoformat(timespec='seconds')} #{channel} (not sent)\n{text}\n")
        if self.echo:
            print(f"\n[discord dry-run #{channel}]\n{text}")
