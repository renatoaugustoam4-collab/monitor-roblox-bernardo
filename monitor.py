"""Check Roblox's public presence endpoint and alert on offline-to-online transitions.

This only reads presence visible through the official endpoint. It does not
circumvent Roblox privacy settings, log into accounts, or read Roblox cookies.
"""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request

USER_ID = int(os.environ["ROBLOX_USER_ID"])
TOPIC = os.environ["NTFY_TOPIC"]
STATE_TOPIC = os.environ["NTFY_STATE_TOPIC"]


def call(url, data=None, headers=None):
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers or {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8")


def publish(topic, message, extra_headers=None):
    """Retry temporary ntfy failures without crashing the cron job."""
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    headers.update(extra_headers or {})
    for attempt in range(3):
        try:
            call("https://ntfy.sh/" + topic, message.encode("utf-8"), headers)
            return True
        except urllib.error.HTTPError as error:
            print(f"ntfy HTTP {error.code}; attempt {attempt + 1}/3")
            if error.code not in (429, 500, 502, 503, 504):
                return False
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            print(f"ntfy connection failed; attempt {attempt + 1}/3: {error}")
        if attempt < 2:
            time.sleep(2 * (attempt + 1))
    print("ntfy unavailable: notification was not confirmed; monitoring will retry later")
    return False


def read_previous_state():
    try:
        data = call("https://ntfy.sh/" + STATE_TOPIC + "/json?poll=1&since=12h")
        events = [json.loads(line) for line in data.splitlines() if line.strip()]
        statuses = [
            event for event in events
            if event.get("event") == "message"
            and event.get("message") in ("online", "offline")
        ]
        if statuses:
            last = max(statuses, key=lambda event: event.get("time", 0))
            return last["message"], last.get("time", 0)
    except (urllib.error.URLError, ValueError, KeyError) as error:
        print("State read unavailable:", error)
    return None, 0


def fetch_roblox_presence(data):
    """Retry temporary failures only. Never convert an API error to offline."""
    transient_codes = {429, 500, 502, 503, 504}
    for attempt in range(3):
        try:
            return call(
                "https://presence.roblox.com/v1/presence/users",
                data,
                {"Content-Type": "application/json",
                 "User-Agent": "RobloxPresenceMonitor/1.0"},
            )
        except urllib.error.HTTPError as error:
            if error.code not in transient_codes:
                raise
            print(f"Roblox API temporarily unavailable: HTTP {error.code} "
                  f"(attempt {attempt + 1}/3)")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            print(f"Roblox presence network error (attempt {attempt + 1}/3): "
                  f"{error}")
        if attempt < 2:
            time.sleep((attempt + 1) * 2)
    print("Roblox presence unavailable after retries; "
          "skipping this check without changing the recorded status.")
    return None


def main():
    data = json.dumps({"userIds": [USER_ID]}).encode("utf-8")
    payload = fetch_roblox_presence(data)
    if payload is None:
        return
    response = json.loads(payload)
    matches = [
        item for item in response.get("userPresences", [])
        if item.get("userId") == USER_ID
    ]
    if len(matches) != 1:
        raise RuntimeError("Roblox did not return a verified presence for the user ID")

    presence = matches[0].get("userPresenceType")
    if presence not in (0, 1, 2, 3):
        raise RuntimeError("Roblox returned an unknown presence type")

    status = "online" if presence in (1, 2, 3) else "offline"
    previous, last_time = read_previous_state()
    print("Current visible status:", status, "previous:", previous)

    # A first observation is the baseline; it is not proof of a new login.
    if status == "online" and previous == "offline":
        brazil_time = dt.datetime.now(
            dt.timezone(dt.timedelta(hours=-3))
        ).strftime("%d/%m/%Y %H:%M")
        delivered = publish(
            TOPIC,
            f"Conta monitorada detectada online em {brazil_time} (Brasília). "
            f"Tipo de presença: {presence}.",
            {"Title": "Roblox: conta online", "Priority": "high"},
        )
        if not delivered:
            print("Online alert delivery not confirmed; preserving prior status for next check")
            return
        print("Online notification sent")

    now = dt.datetime.now(dt.timezone.utc).timestamp()
    if status != previous or now - last_time >= 6 * 3600:
        if publish(
            STATE_TOPIC,
            status,
            {"Title": "Roblox monitor state", "Priority": "min"},
        ):
            print("State recorded")
        else:
            print("State could not be saved; continuing on the next scheduled check")


if __name__ == "__main__":
    main()
