import datetime
import os
import pprint
import pymysql

from flask import Flask, jsonify, request, render_template, url_for, redirect
from flaskext.mysql import MySQL
from tempfile import mkdtemp
from flask_caching import Cache
from importlib.resources import is_resource

from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest, FlaskCacheDataStorage
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem
from pylti1p3.tool_config import ToolConfJsonFile
from pylti1p3.registration import Registration

class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)
mysql = MySQL()

# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = 'transapp'
app.config['MYSQL_DATABASE_PASSWORD'] = '8HT6c8U74GcMQWnBj9GaZmaRahAu49'
app.config['MYSQL_DATABASE_DB'] = 'translation'
app.config['MYSQL_DATABASE_HOST'] = 'database'
mysql.init_app(app)
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

def get_lti_config_path():
    return os.path.join(app.root_path, 'config', 'tool.json')


def get_launch_data_storage():
    return FlaskCacheDataStorage(cache)


@app.route('/login/', methods=['GET', 'POST'])
def login():
    print("request",request)
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    print("tool_conf", tool_conf)
    launch_data_storage = get_launch_data_storage()
    print("launch_data_storage", launch_data_storage)
    
    flask_request = FlaskRequest()

    target_link_uri = flask_request.get_param('target_link_uri')
    print("target_link_uri", target_link_uri)
    if not target_link_uri:
        raise Exception('Missing "target_link_uri" param')

    oidc_login = FlaskOIDCLogin(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    return oidc_login.enable_check_cookies().redirect(target_link_uri)


@app.route('/init/', methods=['POST'])
def main_page():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    message_launch_data = message_launch.get_launch_data()
    print("message_launch_data", message_launch_data)
    user_vle_id = message_launch_data.get('sub')
    print("User ID (Moodle)", user_vle_id)
    user_email = message_launch_data.get('email')
    print("User email", user_email)
    context = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/context')
    print("Context Value:",type(context), context)
    course_code = context.get('label')
    print("Course code:", course_code)
    vle_username = context.get('https://purl.imsglobal.org/spec/lti/claim/ext').get('user_username')
    print("VLE username:", vle_username)
    custom = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/custom')
    print("Custom:", custom)
    language = custom.get('language')
    print("Language:", language)
    phase = custom.get('phase')
    print("Phase:", phase)
    section = custom.get('section')
    print("Section:", section)
    # pprint.pprint(message_launch_data)
    email = message_launch_data.get('email')
    if "https://purl.imsglobal.org/spec/lti/claim/ext" in message_launch_data:
        pprint.pprint(message_launch_data["https://purl.imsglobal.org/spec/lti/claim/ext"])
        ext = message_launch_data["https://purl.imsglobal.org/spec/lti/claim/ext"]
        if "user_username" in ext:
            username = ext["user_username"]
            print("username", username)
        else:
            pprint.pprint("no username in ext")
    else:
        pprint.pprint("no ext in message_launch_data")
    if message_launch.is_resource_launch():
        pprint.pprint("is_resource_launch")
    if message_launch.is_deep_link_launch():
        pprint.pprint("deep_link_launch")
    if message_launch.has_ags():
        ags = message_launch.get_ags()
        items_lst = ags.get_lineitems()
        pprint.pprint(items_lst)
        gr = Grade()
        gr.set_score_given(100)
        gr.set_score_maximum(100)
        gr.set_timestamp(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+0000'))
        gr.set_activity_progress('Completed')
        gr.set_grading_progress('FullyGraded')
        gr.set_user_id(username)
        # ags.put_grade(gr)
        pprint.pprint("has_ags")
    if message_launch.has_nrps():
        nrps = message_launch.get_nrps()
        members = nrps.get_members()
        pprint.pprint(members)
        pprint.pprint("has_nrps")

    # custom_data = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/custom', {})
    # pprint.pprint(custom_data)


    return render_template('term.html', preface=preface, term="hello")

@app.route('/translate/', methods=['POST'])
def process_translation():
    pprint.pprint(request.form)
    return redirect(preface+url_for('main_page'))
    pass

@app.route('/test/', methods=['GET'])
def test_method():
    conn = mysql.connect()

    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM status")

    rows = cursor.fetchall()
    print("rows", jsonify(rows))

    cursor.execute("SELECT * FROM terms")

    rows = cursor.fetchall()
    print("rows", jsonify(rows))
    resp = jsonify(rows)
    resp.status_code = 200

    return resp
    
    
    return redirect(preface+url_for('main_page'))
    pass

@app.route('/jwks/', methods=['GET'])
def get_jwks():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    return jsonify(tool_conf.get_jwks())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
