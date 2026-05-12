import os
from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import requests

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/stats")
def get_stats():
    days = request.args.get("days", 7, type=int)
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = f"{SUPABASE_URL}/rest/v1/analytics"
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    params = {"select": "*", "date": f"gte.{start_date}", "order": "date.asc"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            return jsonify({"error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
