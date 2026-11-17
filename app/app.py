"""
Deliberately VULNERABLE demo app for a CI/CD security lab.
DO NOT deploy this anywhere. Each issue is marked so you can find,
explain and fix it as part of the exercise.
"""
import ipaddress
import os
import secrets
import sqlite3
import subprocess
from urllib.parse import urlparse

import requests
import yaml
from flask import Flask, abort, request
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
csrf = CSRFProtect(app)

# VULN 1: hardcoded secret (should come from env / a secret manager)
# fix 1: no hardcoded secret
API_TOKEN = os.environ.get("API_TOKEN")

# fix 2: only allowed hosts
ALLOWED_FETCH_HOSTS = {"api.github.com", "pypi.org"}


def get_db():
    conn = sqlite3.connect("demo.db")
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER, name TEXT)")
    return conn


@app.route("/user", methods=["GET"])
def get_user():
    # VULN 2: SQL injection (string-built query)
    # fix 3: fix the SQL injection using parameterised query
    name = request.args.get("name", "")
    query = "SELECT * FROM users WHERE name = ?"
    rows = get_db().execute(query, (name,)).fetchall()
    return {"rows": rows}


@app.route("/ping", methods=["GET"])
def ping():
    # VULN 3: command injection (shell=True with user input)
    # fix 4: fix the command injection
    host = request.args.get("host", "127.0.0.1")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        abort(400, "host must be valid IP address")
    output = subprocess.run(  # nosec B603 - fixed command, validated IP, no shell
        ["/bin/ping", "-c", "1", str(ip)],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return {"output": output.stdout}


@app.route("/config", methods=["POST"])
@csrf.exempt
def load_config():
    # VULN 4: unsafe YAML deserialisation (yaml.load without SafeLoader)
    # fix 5: use safe loader
    try:
        data = yaml.safe_load(request.data)
    except yaml.YAMLError:
        abort(400, "invalid YAML")
    return {"loaded": str(data)}


@app.route("/fetch", methods=["GET"])
def fetch():
    # VULN 5: TLS verification disabled + SSRF (user-controlled URL)
    url = request.args.get("url")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_FETCH_HOSTS:
        abort(400, "URL not allowed")
    r = requests.get(url, timeout=5)
    return r.text


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    # VULN 6: debug mode on and bound to all interfaces
    app.run(host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", 5000)), debug=False)
