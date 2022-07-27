import datetime
import os
import random
import pprint
import json
import pymysql

from typing import Dict, List

from collections import namedtuple
from flask import Flask, jsonify, request, render_template, url_for, redirect, escape
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


STATUS_NOT_PREPARED = 0
STATUS_TERMS_PREPARED = 1
STATUS_TERMS_ASSIGNED = 2
STATUS_REVIEWS_ASSIGNED = 3
STATUS_VOTES_ASSIGNED = 4

CLAIM_EXT = 'https://purl.imsglobal.org/spec/lti/claim/ext'
CLAIM_CONTEXT = 'https://purl.imsglobal.org/spec/lti/claim/context'
CLAIM_CUSTOM = "https://purl.imsglobal.org/spec/lti/claim/custom"
CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
LEARNER = 'http://purl.imsglobal.org/vocab/lis/v2/membership#Learner'
INSTRUCTOR = 'http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor'
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

# Config = namedtuple('Config', ['course', 'phase', 'section', 'language'])
# User = namedtuple('User', ['id', 'email', 'username', 'course', 'full_name', 'role'])

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


@app.route('/create/', methods=['POST'])
def create_course():
    data = json.loads(request.form['datajson'])
    course_name = request.form['coursename']
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("INSERT INTO courses (iss, course_id, course_name) VALUES (%s, %s, %s)", (data['iss'], data['course'], course_name))
    conn.commit()
    conn.close()
    cursor.close()
    data['tas'] = []
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/delete/', methods=['POST'])
def delete_course():
    data = json.loads(request.form['datajson'])
    """ delete row from database with matching iss and course_id """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("DELETE FROM courses WHERE iss = %s AND course_id = %s", (data['iss'], data['course']))
    conn.commit()
    conn.close()
    cursor.close()
    return render_template('create_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/addsection/', methods=['POST'])
def add_section():
    data = json.loads(request.form['datajson'])
    section = request.form['sec_number']
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("INSERT INTO sections (iss, course, section_number) VALUES (%s, %s, %s)", (data['iss'], data['course'], section))
    conn.commit()
    conn.close()
    cursor.close()
    data['sections'] = get_sections_for_course(data['iss'], data['course'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/managesection/', methods=['POST'])
def manage_section():
    data = json.loads(request.form['datajson'])
    data['section'] = get_section_for_course(data['iss'], data['course'], request.form['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/finalisesection/', methods=['POST'])
def finalise_section():
    data = json.loads(request.form['datajson'])
    set_status_of_section(data['iss'], data['course'], data['section']['section'], STATUS_TERMS_PREPARED)
    data['section'] = get_section_for_course(data['iss'], data['course'], request.form['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/assignterms/', methods=['POST'])
def asign_terms():
    data = json.loads(request.form['datajson'])
    # distribute_terms(data)
    # set_status_of_section(data['iss'], data['course'], data['section']['section'], STATUS_TERMS_PREPARED)
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/addtas/', methods=['POST'])
def add_tas():
    data = json.loads(request.form['datajson'])
    ta_emails = request.form['tas'].split(',') 
    add_tas_to_course(data['iss'], data['course'], ta_emails)
    data['tas'] = get_ta_details_for_course(data['iss'], data['course'])
    # distribute_terms(data)
    # set_status_of_section(data['iss'], data['course'], data['section']['section'], STATUS_TERMS_PREPARED)
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])



@app.route('/deletesection/', methods=['POST'])
def delete_section():
    data = json.loads(request.form['datajson'])
    data['section'] = request.form['section']
    data['terms'] = get_terms_for_section_of_course(data['iss'], data['course'], data['section']['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/addterm/', methods=['POST'])
def add_term():
    data = json.loads(request.form['datajson'])
    term = request.form['term']
    add_term_to_section_of_course(data['iss'], data['course'], data['section']['section'], term)
    data['section'] = get_section_for_course(data['iss'], data['course'], data['section']['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/deleteterm/', methods=['POST'])
def delete_term():
    data = json.loads(request.form['datajson'])
    term_id = request.form['term_id']
    success = delete_term_from_database(term_id)
    data['section'] = get_section_for_course(data['iss'], data['course'], data['section']['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'], success=success)


@app.route('/init/', methods=['POST'])
def main_page():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    message_launch_data = message_launch.get_launch_data()    
    data = build_launch_dict(message_launch_data)
    
    if data['role'] == INSTRUCTOR:
        if course_exists(data['iss'], data['course']):
            if message_launch.is_deep_link_launch():
                print("deep_link_launch")
            else:
                pass
                # record_action(data, "Initiated the translation tool")
            data['sections'] = get_sections_for_course(data['iss'], data['course'])
            return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])
        else:
            return render_template('create_course.html',  preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

    elif data['role'] == LEARNER:
        status = get_status(config)
        print("current status is ", status)
        if status == STATUS_NOT_PREPARED:
            return render_template('config.html', preface=preface, data=jsonify(data))
        elif status == STATUS_TERMS_PREPARED:
            distribute_terms(config, message_launch)
            term = get_assigned_term(data)
            id_token = request.form['id_token']
            return render_template('term.html', preface=preface, data=jsonify(data),term=term, id_token=id_token, language = config['language'])




    if message_launch.is_resource_launch():
        pprint.pprint("is_resource_launch")
    


    return render_template('term.html', preface=preface, term="hello")

@app.route('/translate/', methods=['POST'])
def process_translation():
    user=json.loads(request.form['user'])
    config=json.loads(request.form['config'])
    term=request.form['term']
    termtrans=request.form['termtrans']
    translation=request.form['translation']

    print(request.form)
    record_action(user, "submitted translation")
    translate_term(user, config, term, termtrans, translation)
    return render_template('config.html', preface=preface, user=user ,config = config)
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

def record_action(data, actioncompleted: str ):
    print("recording action", actioncompleted, "for user", data)
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO actions (vle_user_id, email, vle_username, iss, course, role, action_completed) VALUES (%s, %s, %s, %s, %s, %s, %s)", (
        data['id'], data['email'], data['username'], data['iss'], data['course'], data['role'], actioncompleted))
    conn.commit()
    conn.close()
    return

def get_status(config) -> str:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT status FROM status WHERE course_id = %s AND section = %s", (config['course'], config['section']))
    rows = cursor.fetchall()
    status = -1
    if len(rows) == 1:
        status = rows[0]['status']
    conn.close()
    cursor.close()
    return status

def distribute_terms(config, message_launch: FlaskMessageLaunch):
    members = []
    if message_launch.has_nrps():
        nrps = message_launch.get_nrps()
        members = nrps.get_members()
    print(members)
    teaching_assistants= ['ta@example.com']
    students = [ m for m in members if 'Learner' in m.get('roles') ]
    print("students at the start", students)
    students = [ s for s in students if s.get('email') not in teaching_assistants ]
    print("students after removing teaching assistants", students)
    conn = mysql.connect()
    """ load the assignments from the database for this course and section """ 
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM assignments WHERE course_id = %s AND section = %s", (config['course'], config['section']))
    assignments = cursor.fetchall()
    cursor.close()
    print("assignments", assignments)
    """ load the terms from the database"""
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM terms where course_id = %s and section = %s", (config['course'], config['section']))
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
    term_list = random.choices(rows, k = num_students)
    for student in students:
        term = term_list[0]
        term_list.remove(term)
        assign_term(student, term, config)

    """ set the status in the database to indicate that the terms have been distributed """
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE status SET status = %s WHERE course_id = %s AND section = %s", (STATUS_TERMS_ASSIGNED, config['course'], config['section']))

def assign_term(student, term, config):
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO assignments (vle_id, term_id, term, section, course_id) VALUES (%s, %s, %s, %s, %s)", (student.get('user_id'), term.get('id'), term.get('term'), config['section'], config['course']))
    conn.commit()
    conn.close()
    return

def translate_term(user, config, term, transterm, translation):
    """ add the translation to the database """
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO translations (vle_id, term, transterm, transdescription, section, course_id) VALUES (%s, %s, %s, %s, %s, %s)", 
        (user['id'], term, transterm, translation, config['section'], config['course']))
    conn.commit()
    conn.close()
    return

def get_assigned_term(student, config):
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT term_id, term FROM assignments WHERE vle_id = %s AND course_id = %s AND section = %s", (student['id'], config['course'], config['section']))
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0]['term']
    conn.close()
    cursor.close()

    return None

def build_launch_dict(mld)-> Dict:
    iss = mld.get('iss')
    user_vle_id = mld.get('sub')
    user_email = mld.get('email')
    user_name = mld.get('name')
    vle_username = mld.get(CLAIM_EXT).get('user_username')
    context = mld.get(CLAIM_CONTEXT)
    course_code = context.get('label')
    custom = mld.get(CLAIM_CUSTOM)
    phase = custom.get('phase')
    language = custom.get('language')
    section = custom.get('section')
    roles = mld.get(CLAIM_ROLES)
    role = 'none'
    if LEARNER in roles:
        role = LEARNER
    elif INSTRUCTOR in roles:
        role = INSTRUCTOR
    return {
        'id'        : user_vle_id, 
        'email'     : user_email,
        'username'  : vle_username, 
        'full_name' : user_name, 
        'role'      : role,
        'iss'       : iss,
        'course'    : course_code,
        'phase'     : phase,
        'section'   : section,
        'language'  : language
    }

def course_exists(iss, course) -> bool:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM courses WHERE iss = %s AND course_id = %s", (iss, course))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return len(rows) == 1

def get_sections_for_course(iss, course) -> List:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM sections WHERE iss = %s AND course = %s", (iss, course))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return [ { 'section' : r['section_number'], 'status' : convert_status(r['status']), 'terms': get_terms_for_section_of_course(iss, course, r['section_number']) } for r in rows ]

def get_section_for_course(iss, course, section_number) -> List:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM sections WHERE iss = %s AND course = %s AND section_number = %s", (iss, course, section_number))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    if len(rows) == 1:
        return { 'section' : rows[0]['section_number'], 'status' : convert_status(rows[0]['status']), 'terms': get_terms_for_section_of_course(iss, course, rows[0]['section_number']) }
    else:
        return None

def get_terms_for_section_of_course(iss, course, section) -> List:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT id, term FROM terms WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return [ r for r in rows ]

def add_term_to_section_of_course(iss, course, section, term) -> List:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("INSERT INTO terms (term, iss, section, course) VALUES (%s, %s, %s, %s)", (term, iss, section, course))
    conn.commit()
    conn.close()
    cursor.close()
    return

def delete_term_from_database(term_id) -> List:
    """ load term from the database """
    term = None
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM terms WHERE id = %s", (term_id,))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    if len(rows) == 1:
        term = rows[0]
    """ get status for section of course """
    if term is not None:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM sections WHERE iss = %s AND course = %s AND section_number = %s", (term['iss'], term['course'], term['section']))
        rows = cursor.fetchall()
        conn.close()
        cursor.close()
        if len(rows) == 1:
            status = rows[0]['status']
            if status == STATUS_NOT_PREPARED: # con only delete the term if the section is not prepared
                """ delete term from database """
                conn = mysql.connect()
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                cursor.execute("DELETE FROM terms WHERE id = %s", (term_id,))
                conn.commit()
                conn.close()
                cursor.close()
                return True
            else:
                print("status was not right so i did not delete the term")
    print("term was not found so it couldn't be deleted")
    return False

def set_status_of_section(iss, course, section, status):
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("UPDATE sections SET status = %s WHERE iss = %s AND course = %s AND section_number = %s", (status, iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()
    return

def convert_status(status):
    if status == STATUS_NOT_PREPARED:
        return "Not prepared"
    elif status == STATUS_TERMS_PREPARED:
        return "Terms added to section"
    elif status == STATUS_TERMS_ASSIGNED:
        return "Terms assigned to students"
    elif status == STATUS_REVIEWS_ASSIGNED:
        return "Reviews assigned to students"
    elif status == STATUS_VOTES_ASSIGNED:
        return "Votes assigned to students"

def add_tas_to_course(iss, course, tas):
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    for ta in tas:
        cursor.execute("INSERT INTO assistants (iss, course, email) VALUES (%s, %s, %s)", (iss, course, ta))
    conn.commit()
    conn.close()
    cursor.close()
    return

def get_ta_details_for_course(iss, course):
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM assistants NATURAL LEFT OUTER JOIN participants WHERE iss = %s AND course = %s", (iss, course))
    rows = cursor.fetchall()
    print(rows)
    conn.close()
    cursor.close()
    return [ r for r in rows ]

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
