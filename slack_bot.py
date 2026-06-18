from flask import Flask, request, jsonify
import os
import subprocess
import threading
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

@app.route("/slack/command", methods=["POST"])
def slack_command():
    # Verify Slack Signing Secret here for production security
    text = request.form.get("text", "").strip()
    
    if text.startswith("audit"):
        # Run in background thread to avoid Slack timeout (3s)
        threading.Thread(target=lambda: subprocess.run(["python", "seo_guardian.py"])).start()
        return jsonify({
            "response_type": "in_channel",
            "text": "🔍 *Audit Started:* Running full SEO scan for all sites. Report will be emailed to info@atozadvert.com."
        })
    
    elif text == "uptime":
        threading.Thread(target=lambda: subprocess.run(["python", "uptime_monitor.py"])).start()
        return jsonify({
            "text": "🟢 *Uptime Check:* Refreshing status for all monitored domains..."
        })

    elif text == "help":
        return jsonify({
            "text": "🛡️ *SEO Guardian Commands:*\n`/seo audit` - Run full SEO scan\n`/seo uptime` - Check site status\n`/seo help` - Show this list"
        })

    return jsonify({
        "text": "❓ Unknown command. Try `/seo help`"
    })

if __name__ == "__main__":
    # Use port 5001 to avoid conflict with Streamlit if running locally
    port = int(os.environ.get("SLACK_BOT_PORT", 5001))
    app.run(host="0.0.0.0", port=port)