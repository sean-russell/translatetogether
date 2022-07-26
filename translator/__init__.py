import datetime
import os
import random
import pprint
import pymysql
from collections import namedtuple
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
preface = "/trans"

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

Config = namedtuple('Config', ['course', 'phase', 'section', 'language'])

app.config.from_mapping(config)
cache = Cache(app)

def get_lti_config_path():
    return os.path.join(app.root_path, 'config', 'tool.json')


def get_launch_data_storage():
    return FlaskCacheDataStorage(cache)


@app.route('/login/', methods=['GET', 'POST'])
def login():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    launch_data_storage = get_launch_data_storage()
    flask_request = FlaskRequest()
    target_link_uri = flask_request.get_param('target_link_uri')
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
    user_vle_id = message_launch_data.get('sub')
    user_email = message_launch_data.get('email')
    vle_username = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/ext').get('user_username')
    context = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/context')
    course_code = context.get('label')
    record_action(user_vle_id, user_email, vle_username, course_code, "Initiated the translation tool")
    
    custom = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/custom')
    language = custom.get('language')
    phase = custom.get('phase')
    section = custom.get('section')
    config = Config(course_code, phase, section, language)
    print(config, message_launch)
    



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

def record_action(vle_user_id, email, vle_username, course_id, actioncompleted ):
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO actions (vle_user_id, email, vle_username, course_id, actioncompleted) VALUES (%s, %s, %s, %s, %s)", (vle_user_id, email, vle_username, course_id, actioncompleted))
    conn.commit()
    conn.close()
    return

def distribute_terms(config: Config, message_launch: FlaskMessageLaunch):
    members = []
    if message_launch.has_nrps():
        nrps = message_launch.get_nrps()
        members = nrps.get_members()
    teaching_assistants= ['ta@example.com']
    students = [ m for m in members if 'Learner' in m.get('role') ]
    print("students at the start", students)
    students = [ s for s in students if s.get('email') not in teaching_assistants ]
    print("students after removing teaching assistants", students)
    conn = mysql.connect()
    """ load the assignments from the database for this course and section """ 
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM assignments WHERE course_code = %s AND section = %s", (config.course, config.section))
    assignments = cursor.fetchall()
    cursor.close()
    conn.close()
    print("assignments", assignments)
    """ load the terms from the database"""
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM terms where course_code = %s and section = %s", (config.course, config.section))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    print("terms", rows)
    """ remove students from the list if they have already been assigned a term for this section of the course"""
    assigned_ids = [ a.get('vle_id') for a in assignments ]
    students = [ s for s in students if s.get('user_id') not in assigned_ids ]
    print("students after assigned are removed", students)
    """ distribute the terms to the students """
    num_students = len(students)
    term_list = random.sample(rows, k = num_students)
    for student in students:
        term = term_list[0]
        term_list.remove(term)
        assign_term(student, term, config)

def assign_term(student, term, config: Config):
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO assignments (vle_id, term_id, term, termgroup, course_id) VALUES (%s, %s, %s, %s, %s)", (student.get('user_id'), term.get('id'), term.get('term'), config.section, config.course))
    conn.commit()
    conn.close()
    return

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
