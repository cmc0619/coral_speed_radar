"""Exercise the built images and shared database without a camera or TPU.

Run after `docker compose build`. This is a packaging check, not a hardware test.
"""
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "coral-radar-smoke-" + uuid.uuid4().hex[:8]
COMPOSE = ["docker", "compose", "--env-file", ".env.example", "-p", PROJECT]
ENV = dict(os.environ, DASHBOARD_HOST="127.0.0.1", DASHBOARD_PORT="0")


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, env=ENV, check=True, text=True,
                          capture_output=True, **kwargs).stdout.strip()


def dashboard_url():
    port = run(COMPOSE + ["port", "dashboard", "8080"]).rsplit(":", 1)[1]
    return "http://127.0.0.1:" + port


def main():
    try:
        run(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "90", "dashboard"])
        dashboard = run(COMPOSE + ["ps", "-q", "dashboard"])
        url = dashboard_url()
        with urllib.request.urlopen(url + "/", timeout=5) as response:
            assert b"Coral Speed Radar" in response.read()
        with urllib.request.urlopen(url + "/api/events", timeout=5) as response:
            assert json.load(response) == []

        # Run the detector image's real storage code against the dashboard's volume.
        writer = """from storage import initialize, save_event
initialize('/data/radar.db')
save_event('/data/radar.db', {
    'track_id': 42, 'plate': 'TEST123', 'plate_votes': 2,
    'vehicle_type': 'car', 'speed_mph': 25.0, 'elapsed_seconds': 0.4,
    'direction': 'right'}, 'offline')
"""
        run(["docker", "run", "--rm", "-i", "--platform", "linux/arm64",
             "--volumes-from", dashboard, "coral-speed-radar-detector:local",
             "python", "-"], input=writer)
        run(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "90",
                       "--force-recreate", "dashboard"])
        with urllib.request.urlopen(dashboard_url() + "/api/events", timeout=5) as response:
            rows = json.load(response)
        assert len(rows) == 1 and rows[0]["plate"] == "TEST123"
        assert rows[0]["speed_mph"] == 25.0 and rows[0]["post_status"] == "offline"
        print("PASS: dashboard HTTP, detector storage, and persistence after recreation")
    except subprocess.CalledProcessError as exc:
        print(exc.stdout, exc.stderr)
        raise
    finally:
        print(run(COMPOSE + ["logs", "--tail", "30", "dashboard"]))
        subprocess.run(COMPOSE + ["down", "--volumes"], cwd=ROOT, env=ENV, check=True)


if __name__ == "__main__":
    main()
