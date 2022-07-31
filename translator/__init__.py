import os
import random
import jwt

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


print(os.getcwd())
_private_key = open("translator/config/jwtRS256.key", 'rb').read()
_private_keya = open("translator/config/jwtRS256a.key", 'rb').read()
_public_key = open("translator/config/jwtRS256.key.pub", 'rb').read()
_public_keya = open("translator/config/jwtRS256a.key.pub", 'rb').read()

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
    """ This is the main page of the application. """
    id_token = None
    state = None
    data = None
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = None
    if 'datajson' in request.form:
        data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
        state = data['state']
        id_token = data['id_token']
        launch_id = data['launch_id']
        message_launch = FlaskMessageLaunch.from_cache(launch_id, flask_request, tool_conf, launch_data_storage=launch_data_storage)
    else:
        message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)
        state = request.form['state']
        id_token = request.form['id_token']
    
    message_launch_data = message_launch.get_launch_data()  
    launch_id = message_launch.get_launch_id()
    data = build_launch_dict(message_launch_data, id_token, state, launch_id)
    dbstuff.create_course(data)
    dbstuff.add_participant_to_course(data['id'], data['email'], data['full_name'], data['role'], data['iss'], data['course'])
    dbstuff.record_action(data, "Initiated the translation tool")
    if data['role'] == INSTRUCTOR:
        owner = dbstuff.get_course_owner(data['iss'], data['course'])
        if message_launch.is_deep_link_launch():
            print("deep_link_launch")
        elif owner == data['id']:
            data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
            data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
            data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
            return render_template('manage_course.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))
        else:
            data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
            data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
            data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
            return render_template('view_course.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

    elif data['role'] == LEARNER:
        if dbstuff.section_exists(data['iss'], data['course'], data['section_num']):
            data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], data['section_num'])
            print("data['section']", data['section'])
            print("current status is ", data['section']['status'])
            if data['section']['status'] in (STATUS_NOT_PREPARED, STATUS_TERMS_PREPARED):
                return render_template('config.html', preface=preface, data=jsonify(data))
            elif data['phase'] == PHASE_TRANSLATE:
                if data['section']['status'] in (STATUS_TERMS_ASSIGNED, convert_status(STATUS_TERMS_ASSIGNED)):
                    term = dbstuff.get_assigned_term(data)
                    if term == None:
                        assign_term(data)
                        term = dbstuff.get_assigned_term(data)
                    return render_template('term.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"),term=term)
        else:
            return render_template('config.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

######################################################################################################################################################################
# Functions for managing the sections in a course ####################################################################################################################
######################################################################################################################################################################

@app.route('/section/add/', methods=['POST'])
def add_section():
    """ add a section to the database and refresh the page """
    data = jwt.decode(request.form['datajson'], _public_keya, algorithms=["RS256"])
    dbstuff.create_section(data, request.form['sec_number'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

@app.route('/section/delete/', methods=['POST'])
def delete_section():
    """ delete a section from the database and refresh the page """
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    iss = data['iss']
    course = data['course']
    section_num = request.form['section']
    dbstuff.delete_section(iss, course, section_num)
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

@app.route('/section/manage/', methods=['POST'])
def manage_section():
    """ change to the page for managing a section """
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], request.form['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

@app.route('/section/finalise/', methods=['POST'])
def finalise_section():
    """ finalise the list of terms that are used in a section"""
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    dbstuff.set_status_of_section(data['iss'], data['course'], request.form['section'], STATUS_TERMS_PREPARED)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], request.form['section'])
    return render_template('manage_section.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

@app.route('/section/assign/', methods=['POST'])
def asign_terms():
    """ assign terms to all registered students within a section TODO finish this"""
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    section_num = request.form['section']
    assign_terms(data['iss'], data['course'], section_num)
    dbstuff.set_status_of_section(data['iss'], data['course'], section_num, STATUS_TERMS_ASSIGNED)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], section_num)
    return render_template('manage_section.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

@app.route('/section/review/', methods=['POST'])
def start_review():
    """ assign reviews to all registered students within a section """

    """ first find the list of translations completed for this section (only most recent by each student) """
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    section_num = request.form['section']
    print(section_num)
    iss = data['iss']
    course = data['course']
    student_reviews =  { s['vle_user_id'] : {'name' : s['fullname'], 'reviews' : [], 'term': None } for s in dbstuff.get_student_details_for_course(iss, course) }
    print("student_reviews", student_reviews)
    term_assignments = dbstuff.get_trans_assignments_for_section_of_course(iss, course, section_num)
    student_assignments = {}
    for term in term_assignments:
        for t in term_assignments[term]:
            student_assignments[t[0]] = { 'completed' : False, 'term' : term, 'transterm' : '', 'transdescription' : '' } 
            student_reviews[t[0]]['term'] = term
    print("student_assignments length", len(student_assignments))
    tas = dbstuff.get_ta_details_for_course(iss, course)

    translations = dbstuff.get_term_translations_for_section(iss, course, section_num)
    term_lists = {}
    term_set = set()
    for t in translations:
        term_set.add(t['term'])
        if t['vle_user_id'] in student_assignments:
            student_reviews[t['vle_user_id']]['term'] = student_assignments[t['vle_user_id']]['term']
        if t['vle_user_id'] not in student_assignments:
            raise Exception("Error: translation for student not assigned to a term")
        else:
            x = student_assignments[t['vle_user_id']]
            x['completed'] = True
            x['transterm'] = t['transterm']
            x['transdescription'] = t['transdescription']
    for sid in student_assignments:
        x = student_assignments[sid]
        if x['term'] not in term_lists:
            term_lists[x['term']] = []
        term_lists[x['term']].append(x)

    for t in term_lists:
        term_lists[t] = term_lists[t] * (NUM_REVIEWS+1)
        random.shuffle(term_lists[t])
        print(t, "term list len", len(term_lists[t]))


    """ now assign reviews to each student """
    # random.shuffle(students)
    for s, d in student_reviews.items():
        print("student", s, d)
        for t in term_lists:
            print(t, "term list len", len(term_lists[t]), end=" ")
            if d['term'] != t:
                temp_term = term_lists[t].pop()
                if temp_term['completed'] == True:
                    d['reviews'].append(temp_term)
                print("-1", "term list len", len(term_lists[t]))
            else:
                print("term list len", len(term_lists[t]))
        print("student", s, len(d['reviews']))
            

    print("first pass completed")
    for s in student_reviews:
        print(s, student_reviews[s]['term'], student_reviews[s]['reviews'])

    for t in term_lists:
        term_lists[t] = term_lists[t] * (NUM_REVIEWS * 2)
        random.shuffle(term_lists[t])
    for s, d in student_reviews.items():
        if len(d['reviews']) < NUM_REVIEWS:
            s_terms = set([x['term'] for x in d['reviews']]) | set(d['term'])
            missing_terms = term_set - s_terms
            for t in missing_terms:
                temp_term = term_lists[t].pop(0)
                while temp_term['completed'] == False:
                    temp_term = term_lists[t].pop(0)
                    if len(term_lists[t]) == 0:
                        raise Exception("Error: ran out of terms for student")
                d['reviews'].append(temp_term)

    print("second pass completed")
    for s in student_reviews:
        print(s, student_reviews[s]['term'], student_reviews[s]['reviews'])

######################################################################################################################################################################
# Functions for administering the terms within in a section ##########################################################################################################
######################################################################################################################################################################

@app.route('/term/add/', methods=['POST'])
def add_term():
    """ add a term to the database and refresh the page """
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    iss = data['iss']
    course = data['course']
    section = request.form['section']
    term = request.form['term']
    dbstuff.add_term_to_section_of_course(iss, course, section, term)
    data['section'] = dbstuff.get_section_for_course(iss, course, section)
    return render_template('manage_section.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

@app.route('/term/delete/', methods=['POST'])
def delete_term():
    """ delete a term from the database and refresh the page """
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    iss = data['iss']
    course = data['course']
    section = request.form['section']
    term_id = request.form['term_id']
    dbstuff.delete_term_from_database(term_id)
    data['section'] = dbstuff.get_section_for_course(iss, course, section)
    return render_template('manage_section.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

def assign_terms(iss, course, section_num) -> None:
    """ assign a term to every student in a course for the current section """
    terms_with_ids = dbstuff.get_terms_for_section_of_course(iss,course,section_num)
    terms = [ term['term'] for term in terms_with_ids ]
    students = dbstuff.get_student_details_for_course(iss, course)
    student_ids = [ student['vle_user_id'] for student in students ]
    # print("terms list", terms)
    # print("student ids", student_ids)
    random_terms = []
    while len(random_terms) < len(student_ids):
        random_terms.extend(terms)
    # print("random terms", len(random_terms), random_terms)
    random.shuffle(random_terms)
    random.shuffle(student_ids)
    for student in student_ids:
        term = random_terms.pop(0)
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
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    ta_emails = [ a.strip() for a in request.form['tas'].split(',') if a.strip() != '' ] 
    dbstuff.add_tas_to_course(data['iss'], data['course'], ta_emails)
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

@app.route('/tas/remove/', methods=['POST'])
def remove_teaching_assistant():
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    ta_id = request.form['ta_id']
    dbstuff.remove_ta_from_course(ta_id)
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
    return render_template('manage_course.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

######################################################################################################################################################################
# Functions for administering the students in a course ###############################################################################################################
######################################################################################################################################################################

@app.route('/students/update/', methods=['POST'])
def update_students():
    """ Get the Names and Roles Provisioning Service. 
        Read the list of students from the service. 
        Remove any students that are listed as teaching assistants in the course.
        Add remaining list as participants in the database."""
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    launch_id = data['launch_id']
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch.from_cache(launch_id, flask_request, tool_conf, launch_data_storage=launch_data_storage)
    
    if message_launch.has_nrps():
        teaching_assistant_emails = dbstuff.get_teaching_assistant_emails_for_course(data['iss'], data['course'])
        nrps = message_launch.get_nrps()
        members = nrps.get_members()
        print("members list from the service", members)
        print("teaching assistant emails", teaching_assistant_emails)
        for member in members:
            role = 'none'
            roles = member['roles']
            if LEARNER in roles or 'Learner' in roles:
                role = LEARNER
            elif INSTRUCTOR in roles or 'Instructor' in roles:
                role = INSTRUCTOR
            if member['email'] in teaching_assistant_emails:
                dbstuff.add_participant_to_course(member['user_id'], member['email'], member["name"], INSTRUCTOR, data['iss'], data['course'])
            else:
                dbstuff.add_participant_to_course(member['user_id'], member['email'], member["name"], role, data['iss'], data['course'])
            
        print(members)
    else:
        raise Exception('No NRPS found in message launch')
    
    data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
    data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
    print("current students: " + str(data['students']))
    return render_template('manage_course.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

######################################################################################################################################################################
# Functions for building the core data carried through the program ###################################################################################################
######################################################################################################################################################################

def build_launch_dict(mld, id_token, state, launch_id)-> Dict:
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
        'language'      : language,
        'id_token'      : id_token,
        'state'         : state,
        'launch_id'     : launch_id
    }

######################################################################################################################################################################
# Functions for processing the submitted translations ################################################################################################################
######################################################################################################################################################################

@app.route('/translation/add/', methods=['POST'])
def add_new_translation():
    term = request.form['term']
    trans_ass_id = request.form['trans_ass_id']
    termtrans = request.form['termtrans']
    translation = request.form['translation']
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    dbstuff.add_term_translation(data['id'], trans_ass_id, term, termtrans, translation, data['iss'], data['course'], data['section_num'])
    term = dbstuff.get_assigned_term(data)
    return render_template('term.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"),term=term)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
