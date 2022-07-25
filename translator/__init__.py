import datetime
import os
import pprint

from flask import Flask, jsonify, request, render_template, url_for

app = Flask(__name__)

preface = ""


@app.route('/init/', methods=['GET'])
def main_page():
    return render_template('main.html', preface=preface)
