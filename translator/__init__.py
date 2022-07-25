import datetime
import os
import pprint

from flask import Flask, jsonify, request, render_template, url_for
from tempfile import mkdtemp
from flask_caching import Cache

app = Flask(__name__)

preface = ""

config = {
    "DEBUG": True,
    "ENV": "development",
    "CACHE_TYPE": "simple",
    "CACHE_DEFAULT_TIMEOUT": 600,
    "SECRET_KEY": "replace-me",
    "SESSION_TYPE": "filesystem",
    "SESSION_FILE_DIR": mkdtemp(),
    "SESSION_COOKIE_NAME": "flask-session-id",
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SECURE": True,   # should be True in case of HTTPS usage (production)
    "SESSION_COOKIE_SAMESITE": None,  # should be 'None' in case of HTTPS usage (production)
    "DEBUG_TB_INTERCEPT_REDIRECTS": False
}

app.config.from_mapping(config)
cache = Cache(app)

@app.route('/init/', methods=['GET'])
def main_page():
    return render_template('main.html', preface=preface)
