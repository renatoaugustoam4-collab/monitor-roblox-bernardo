"""Check Roblox's public presence endpoint and alert on offline-to-online transitions.

This only reads presence visible through the official endpoint. It does not
circumvent Roblox privacy settings, log into accounts, or read Roblox cookies.
"""
import datetime as dt
import json
import os
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
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    headers.update(extra_headers or {})
    return call("https://ntfy.sh/" + topic, message.encode("utf-8"), headers)


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


def main():
    data = json.dumps({"userIds": [USER_ID]}).encode("utf-8")
    payload = call(
        "https://presence.roblox.com/v1/presence/users",
        data,
        {"Content-Type": "application/json", "User-Agent": "RobloxPresenceMonitor/1.0"},
    )
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
        publish(
            TOPIC,
            f"Conta monitorada detectada online em {brazil_time} (Brasília). "
            f"Tipo de presença: {presence}.",
            {"Title": "Roblox: conta online", "Priority": "high"},
        )
        print("Online notification sent")

    now = dt.datetime.now(dt.timezone.utc).timestamp()
    if status != previous or now - last_time >= 6 * 3600:
        publish(
            STATE_TOPIC,
            status,
            {"Title": "Roblox monitor state", "Priority": "min"},
        )
        print("State recorded")


if __name__ == "__main__":
    main()
