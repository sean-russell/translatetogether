import datetime
import os
import random
import pprint
import json
import pymysql
import dbstuff

from typing import Dict, List

from collections import namedtuple
from flask import Flask, jsonify, request, render_template, url_for, redirect, escape



from tempfile import mkdtemp
from flask_caching import Cache
from importlib.resources import is_resource

from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest, FlaskCacheDataStorage
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem
from pylti1p3.tool_config import ToolConfJsonFile
from pylti1p3.registration import Registration


from constants import *

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

# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = 'transapp'
app.config['MYSQL_DATABASE_PASSWORD'] = '8HT6c8U74GcMQWnBj9GaZmaRahAu49'
app.config['MYSQL_DATABASE_DB'] = 'translation'
app.config['MYSQL_DATABASE_HOST'] = 'database'

dbstuff.prep(app)
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

app.config.from_mapping(config)
cache = Cache(app)

def get_lti_config_path():
    return os.path.join(app.root_path, 'config', 'tool.json')

def get_launch_data_storage():
    return FlaskCacheDataStorage(cache)

@app.route('/login/', methods=['GET', 'POST'])
def login():
    """ Initiation of the LTI 1.3 login process. """
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    launch_data_storage = get_launch_data_storage()
    flask_request = FlaskRequest()
    target_link_uri = flask_request.get_param('target_link_uri')
    if not target_link_uri:
        raise Exception('Missing "target_link_uri" param')
    oidc_login = FlaskOIDCLogin(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    return oidc_login.enable_check_cookies().redirect(target_link_uri)

@app.route('/addsection/', methods=['POST'])
def add_section():
    """ add a section to the database """
    data = json.loads(request.form['datajson'])
    dbstuff.create_section(data, request.form['sec_number'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/managesection/', methods=['POST'])
def manage_section():
    data = json.loads(request.form['datajson'])
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], request.form['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/finalisesection/', methods=['POST'])
def finalise_section():
    data = json.loads(request.form['datajson'])
    dbstuff.set_status_of_section(data['iss'], data['course'], data['section']['section'], STATUS_TERMS_PREPARED)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], request.form['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/assignterms/', methods=['POST'])
def asign_terms():
    data = json.loads(request.form['datajson'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/addtas/', methods=['POST'])
def add_tas():
    data = json.loads(request.form['datajson'])
    ta_emails = request.form['tas'].split(',') 
    dbstuff.add_tas_to_course(data['iss'], data['course'], ta_emails)
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/updatestudents/', methods=['POST'])
def update_students():
    data = json.loads(request.form['datajson'])
    launch_id = request.form['launch_id']
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch.from_cache(launch_id, flask_request, tool_conf, launch_data_storage=launch_data_storage)
    
    if message_launch.has_nrps():
        nrps = message_launch.get_nrps()
        members = nrps.get_members()
        for member in members:
            role = 'none'
            roles = member['roles']
            if LEARNER in roles or 'Learner' in roles:
                role = LEARNER
            elif INSTRUCTOR in roles or 'Instructor' in roles:
                role = INSTRUCTOR
            dbstuff.add_participant_to_course(member['user_id'], member['email'],member["name"],  role, data['iss'], data['course'])
        print(members)
    else:
        print('No NRPS')
    
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
    print("current students: " + str(data['students']))
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])


@app.route('/removeta/', methods=['POST'])
def remove_ta():
    data = json.loads(request.form['datajson'])
    ta_id = request.form['ta_id']
    dbstuff.remove_ta_from_course(ta_id)
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/deletesection/', methods=['POST'])
def delete_section():
    data = json.loads(request.form['datajson'])
    data['section'] = request.form['section']
    data['terms'] = dbstuff.get_terms_for_section_of_course(data['iss'], data['course'], data['section_num'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/addterm/', methods=['POST'])
def add_term():
    data = json.loads(request.form['datajson'])
    term = request.form['term']
    dbstuff.add_term_to_section_of_course(data['iss'], data['course'], data['section_num'], term)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], data['section_num'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/deleteterm/', methods=['POST'])
def delete_term():
    data = json.loads(request.form['datajson'])
    term_id = request.form['term_id']
    success = dbstuff.delete_term_from_database(term_id)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], data['section_num'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'], success=success)


@app.route('/init/', methods=['POST'])
def main_page():
    id_token = request.form['id_token']
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    message_launch_data = message_launch.get_launch_data()  
    launch_id = message_launch.get_launch_id()
    data = build_launch_dict(message_launch_data)
    dbstuff.create_course(data)
    dbstuff.add_participant_to_course(data['id'], data['email'], data['full_name'], data['role'], data['iss'], data['course'])
    dbstuff.record_action(data, "Initiated the translation tool")
    if data['role'] == INSTRUCTOR:
        if message_launch.is_deep_link_launch():
            print("deep_link_launch")
        else:
            data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
            data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
            data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
            return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=id_token, launch_id=launch_id)

    elif data['role'] == LEARNER:
        data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], data['section_num'])
        print("current status is ", data['section']['status'])
        if data['section']['status'] in (STATUS_NOT_PREPARED, STATUS_TERMS_PREPARED):
            return render_template('config.html', preface=preface, data=jsonify(data))
        elif data['phase'] == PHASE_TRANSLATE:
            if data['section']['status'] == STATUS_TERMS_ASSIGNED:
                
                term = dbstuff.get_assigned_term(data)
                if term == None:
                    assign_term(data)
                    term = get_assigned_term(data)
                
                
                return render_template('term.html', preface=preface, data=data, datajson=json.dumps(data), id_token=id_token, term=term)




    if message_launch.is_resource_launch():
        pprint.pprint("is_resource_launch")
    


    return render_template('term.html', preface=preface, data=data, datajson=json.dumps(data), id_token=id_token, term="hello")

# @app.route('/translate/', methods=['POST'])
# def process_translation():
#     user=json.loads(request.form['user'])
#     config=json.loads(request.form['config'])
#     term=request.form['term']
#     termtrans=request.form['termtrans']
#     translation=request.form['translation']

#     print(request.form)
#     dbstuff.record_action(user, "submitted translation")
#     translate_term(user, config, term, termtrans, translation)
#     return render_template('config.html', preface=preface, user=user ,config = config)
#     pass


@app.route('/jwks/', methods=['GET'])
def get_jwks():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    return jsonify(tool_conf.get_jwks())

# def distribute_terms(config, message_launch: FlaskMessageLaunch):
#     members = []
#     if message_launch.has_nrps():
#         nrps = message_launch.get_nrps()
#         members = nrps.get_members()
#     print(members)
#     teaching_assistants= ['ta@example.com']
#     students = [ m for m in members if 'Learner' in m.get('roles') ]
#     print("students at the start", students)
#     students = [ s for s in students if s.get('email') not in teaching_assistants ]
#     print("students after removing teaching assistants", students)
#     conn = mysql.connect()
#     """ load the assignments from the database for this course and section """ 
#     cursor = conn.cursor(pymysql.cursors.DictCursor)
#     cursor.execute("SELECT * FROM assignments WHERE course_id = %s AND section = %s", (config['course'], config['section']))
#     assignments = cursor.fetchall()
#     cursor.close()
#     print("assignments", assignments)
#     """ load the terms from the database"""
#     cursor = conn.cursor(pymysql.cursors.DictCursor)
#     cursor.execute("SELECT * FROM terms where course_id = %s and section = %s", (config['course'], config['section']))
#     rows = cursor.fetchall()
#     cursor.close()
#     conn.close()
#     print("terms", rows)
#     """ remove students from the list if they have already been assigned a term for this section of the course"""
#     assigned_ids = [ a.get('vle_id') for a in assignments ]
#     students = [ s for s in students if s.get('user_id') not in assigned_ids ]
#     print("students after assigned are removed", students)
#     """ distribute the terms to the students """
#     num_students = len(students)
#     term_list = random.choices(rows, k = num_students)
#     for student in students:
#         term = term_list[0]
#         term_list.remove(term)
#         assign_term(student, term, config)

#     """ set the status in the database to indicate that the terms have been distributed """
#     conn = mysql.connect()
#     cursor = conn.cursor()
#     cursor.execute("UPDATE status SET status = %s WHERE course_id = %s AND section = %s", (STATUS_TERMS_ASSIGNED, config['course'], config['section_num']))

def choose_term(data: Dict) -> Dict:
    terms: List[str] = dbstuff.get_terms_for_section_of_course(data['iss'], data['course'], data['section_num'])
    members = []
    if message_launch.has_nrps():
        nrps = message_launch.get_nrps()
        members = nrps.get_members()
    print(members)
    teaching_assistants= ['


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
        'id'            : user_vle_id, 
        'email'         : user_email,
        'username'      : vle_username, 
        'full_name'     : user_name, 
        'role'          : role,
        'iss'           : iss,
        'course'        : course_code,
        'phase'         : phase,
        'section_num'   : section,
        'language'      : language
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
