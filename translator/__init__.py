import datetime
import os
import random
import pprint
import json
import pymysql
from translator import dbstuff
from translator.constants import *
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

@app.route('/jwks/', methods=['GET'])
def get_jwks():
    """ This is a route that is used to get the JWKS for the LTI 1.3 Tool. """
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    return jsonify(tool_conf.get_jwks())

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
            print(data) #TODO: remove this
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
                    term = dbstuff.get_assigned_term(data)
                
                
                return render_template('term.html', preface=preface, data=data, datajson=json.dumps(data), id_token=id_token, term=term)

######################################################################################################################################################################
# Functions for managing the sections in a course ####################################################################################################################
######################################################################################################################################################################

@app.route('/section/add/', methods=['POST'])
def add_section():
    """ add a section to the database and refresh the page """
    data = json.loads(request.form['datajson'])
    dbstuff.create_section(data, request.form['sec_number'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/section/delete/', methods=['POST'])
def delete_section():
    """ delete a section from the database and refresh the page """
    data = json.loads(request.form['datajson'])
    iss = request.form['iss']
    course = request.form['course']
    section_num = request.form['section']
    dbstuff.delete_section(iss, course, section_num)
    
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/section/manage/', methods=['POST'])
def manage_section():
    """ change to the page for managing a section """
    data = json.loads(request.form['datajson'])
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], request.form['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/section/finalise/', methods=['POST'])
def finalise_section():
    """ finalise the list of terms that are used in a section"""
    data = json.loads(request.form['datajson'])
    dbstuff.set_status_of_section(data['iss'], data['course'], data['section']['section'], STATUS_TERMS_PREPARED)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], request.form['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/section/assign/', methods=['POST'])
def asign_terms():
    """ assign terms to all registered students within a section TODO finish this"""
    data = json.loads(request.form['datajson'])
    section_num = request.form['section']
    assign_terms(data['iss'], data['course'], section_num)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], section_num)
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

######################################################################################################################################################################
# Functions for administering the terms within in a section ##########################################################################################################
######################################################################################################################################################################

@app.route('/term/add/', methods=['POST'])
def add_term():
    """ add a term to the database and refresh the page """
    data = json.loads(request.form['datajson'])
    iss = request.form['iss']
    course = request.form['course']
    section = request.form['section']
    term = request.form['term']
    id_token=request.form['id_token']
    dbstuff.add_term_to_section_of_course(iss, course, section, term)
    data['section'] = dbstuff.get_section_for_course(iss, course, section)
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=id_token)

@app.route('/term/delete/', methods=['POST'])
def delete_term():
    """ delete a term from the database and refresh the page """
    data = json.loads(request.form['datajson'])
    term_id = request.form['term_id']
    success = dbstuff.delete_term_from_database(term_id)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], data['section_num'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'], success=success)

def assign_terms(iss, course, section_num) -> None:
    """ assign a term to every student in a course for the current section """
    terms_with_ids = dbstuff.get_terms_for_section_of_course(iss,course,section_num)
    terms = [ term['term'] for term in terms_with_ids ]
    students = dbstuff.get_student_details_for_course(iss, course)
    student_ids = [ student['vle_user_id'] for student in students ]
    print("terms list", terms)
    print("student ids", student_ids)
    random_terms = random.choices(terms, k = len(student_ids))
    random.shuffle(student_ids)
    for student in student_ids:
        term = random_terms.pop()
        dbstuff.assign_term_to_student(iss, course, section_num, term, student)

def assign_term(data: Dict) -> None:
    """ This is for when a student was not in the list when terms were being assigned
    so we need to assign them a term. It finds the term that has the lowsest number of students
    assigned to it and assigns that one to the student. """

    terms: List[str] = dbstuff.get_terms_for_section_of_course(data['iss'], data['course'], data['section_num'])
    term_counts = dbstuff.count_term_assignments_for_section(data['iss'], data['course'], data['section_num'])	
    if len(terms) > len(term_counts):
        raise Exception("Here we have a problem. There are more terms than term counts. This should be impossible!")
    elif len(term_counts) == 0:
        raise Exception("There were no values returned, this should be impossible!")
    else:
        term = term_counts[0]['term']
        dbstuff.assign_term_to_student(data['iss'], data['course'], data['section_num'], term, data['id'])

######################################################################################################################################################################
# Functions for administering the teaching assistants in a course ####################################################################################################
######################################################################################################################################################################

@app.route('/tas/add/', methods=['POST'])
def add_teaching_assistants():
    data = json.loads(request.form['datajson'])
    ta_emails = request.form['tas'].split(',') 
    dbstuff.add_tas_to_course(data['iss'], data['course'], ta_emails)
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

@app.route('/tas/remove/', methods=['POST'])
def remove_teaching_assistant():
    data = json.loads(request.form['datajson'])
    ta_id = request.form['ta_id']
    dbstuff.remove_ta_from_course(ta_id)
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

######################################################################################################################################################################
# Functions for administering the students in a course ###############################################################################################################
######################################################################################################################################################################

@app.route('/students/update/', methods=['POST'])
def update_students():
    """ Get the Names and Roles Provisioning Service. 
        Read the list of students from the service. 
        Remove any students that are listed as teaching assistants in the course.
        Add remaining list as participants in the database."""
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
        raise Exception('No NRPS found in message launch')
    
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
    print("current students: " + str(data['students']))
    return render_template('manage_course.html', preface=preface, data=data, datajson=json.dumps(data), id_token=request.form['id_token'])

######################################################################################################################################################################
# Functions for building the core data carried through the program ###################################################################################################
######################################################################################################################################################################

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

######################################################################################################################################################################
# Functions for processing the submitted translations ###################################################################################################
######################################################################################################################################################################

@app.route('/translation/add/', methods=['POST'])
def add_new_translation():
    pass


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
