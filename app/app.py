"""
Deliberately VULNERABLE demo app for a CI/CD security lab.
DO NOT deploy this anywhere. Each issue is marked so you can find,
explain and fix it as part of the exercise.
"""
import os
import sqlite3
import subprocess

import requests
import yaml
from flask import Flask, request

app = Flask(__name__)

# VULN 1: hardcoded secret (should come from env / a secret manager)
API_TOKEN = "ghp_1a2B3c4D5e6F7g8H9i0J1k2L3m4N5o6P7q8R"  # fake token for the lab


def get_db():
    conn = sqlite3.connect("demo.db")
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER, name TEXT)")
    return conn


@app.route("/user")
def get_user():
    # VULN 2: SQL injection (string-built query)
    name = request.args.get("name", "")
    query = "SELECT * FROM users WHERE name = '" + name + "'"
    rows = get_db().execute(query).fetchall()
    return {"rows": rows}


@app.route("/ping")
def ping():
    # VULN 3: command injection (shell=True with user input)
    host = request.args.get("host", "127.0.0.1")
    output = subprocess.check_output("ping -c 1 " + host, shell=True)
    return output


@app.route("/config", methods=["POST"])
def load_config():
    # VULN 4: unsafe YAML deserialisation (yaml.load without SafeLoader)
    data = yaml.load(request.data, Loader=yaml.Loader)
    return {"loaded": str(data)}


@app.route("/fetch")
def fetch():
    # VULN 5: TLS verification disabled + SSRF (user-controlled URL)
    url = request.args.get("url")
    r = requests.get(url, verify=False, timeout=5)
    return r.text


if __name__ == "__main__":
    # VULN 6: debug mode on and bound to all interfaces
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
