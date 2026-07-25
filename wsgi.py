from flask import Flask
import os

flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health():
    return "🤖 Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port)