"""Read-only Flask web UI (do not expose directly to the internet)."""
from flask import Flask, jsonify, render_template
from config import Config
from storage import initialize, recent

cfg = Config().validate()
app = Flask(__name__)
initialize(cfg.database_path)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/events")
def events():
    return jsonify(recent(cfg.database_path))


if __name__ == "__main__":
    app.run(host=cfg.dashboard_host, port=cfg.dashboard_port, debug=False)
