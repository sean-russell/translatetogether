import os
import random
import jwt
import re

from translator import dbstuff
from translator.constants import *
from typing import Dict, List, Set

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
_public_key = open("translator/config/jwtRS256.key.pub", 'rb').read()
email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

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
    data = None
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = None
    if 'datajson' in request.form:
        data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
        launch_id = data['launch_id']
        message_launch = FlaskMessageLaunch.from_cache(launch_id, flask_request, tool_conf, launch_data_storage=launch_data_storage)
    else:
        message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    
    message_launch_data = message_launch.get_launch_data()  
    launch_id = message_launch.get_launch_id()
    data = build_launch_dict(message_launch_data, launch_id)
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
            elif data['phase'] == PHASE_REVIEW:
                print("phase is review")
                if data['section']['status'] in (STATUS_REVIEWS_ASSIGNED, convert_status(STATUS_REVIEWS_ASSIGNED)):
                    review_assignments = dbstuff.get_assigned_reviews_for_student_in_section(data['id'], data['iss'], data['course'], data['section_num'])
                    if review_assignments == None:
                        raise Exception("No reviews assigned!!!")
                    reviews = [ r.get_review() for r in review_assignments]
                    return render_template('reviews.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"),reviews=reviews)
            
        else:
            return render_template('config.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

######################################################################################################################################################################
# Functions for managing the sections in a course ####################################################################################################################
######################################################################################################################################################################

@app.route('/section/add/', methods=['POST'])
def add_section():
    """ add a section to the database and refresh the page """
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
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

@app.route('/section/setterms/', methods=['POST'])
def set_num_terms():
    """ set the number of terms wanted in a section """
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    desired_terms = request.form['num_terms']
    print("desired_terms", desired_terms)
    data['section'] = dbstuff.set_desired_terms_for_section_in_course(data['iss'], data['course'], request.form['section'], desired_terms)
    return render_template('manage_section.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

@app.route('/section/finalise/', methods=['POST'])
def finalise_section():
    """ finalise the list of terms that are used in a section"""
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    num_terms = request.form['form_num_terms']
    desired_num_terms = request.form['form_desired_terms']
    if num_terms != desired_num_terms:
        return render_template('manage_section.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))
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
    iss = data['iss']
    course = data['course']
    term_assignments = dbstuff.get_trans_assignments_for_section_of_course(iss, course, section_num)
    student_reviews: Dict[str, ReviewAssignments] = {}
    for term in term_assignments:
        for t in term_assignments[term]:
            student_reviews[t.id] = ReviewAssignments(t.id, t.name, term)
    print("student_reviews length", len(student_reviews))
    tas = dbstuff.get_ta_details_for_course(iss, course)

    translations = dbstuff.get_term_translations_for_section(iss, course, section_num)
    term_lists: Dict[str,List[TranslatedTerm]] = {}
    term_lists_variable: Dict[str,List[TranslatedTerm]] = {}
    all_assigned: Dict[str,bool] = {}
    term_set: Set[str] = set()

    for sid in student_reviews:
        x = student_reviews[sid]
        if x.term not in term_lists:
            term_lists[x.term] = []
            term_lists_variable[x.term] = []
            all_assigned[x.term] = False
        
    for t in translations:
        term_set.add(t.term)
        term_lists[t.term].append(t)
    for t in term_lists:
        term_lists_variable[t] = term_lists[t] * NUM_REVIEWS
        random.shuffle(term_lists_variable[t])

    """ now assign reviews to each student """
    for s, d in student_reviews.items():
        for t in term_lists_variable:
            if len(term_lists_variable[t]) == 0:
                term_lists_variable[t].extend(term_lists[t]) #reup when empty
                all_assigned[t] = True
            if d.term != t:
                temp_term = term_lists_variable[t].pop()
                d.add_review(temp_term)
    
    if not all(all_assigned.values()):
        remaining_terms = [ a for l in term_lists_variable if not all_assigned[l] for a in term_lists_variable[l] ]
        student_ids = list(student_reviews.keys())
        i = 0
        while i < len(student_reviews):
            if len(remaining_terms) != 0:
                student = student_reviews[student_ids[i]]
                temp = remaining_terms.pop()
                if not student.add_extra_review(temp):
                    remaining_terms.append(temp)
            i = i + 1
        if not all(map(lambda x: len(x.reviews) == NUM_REVIEWS+1, student_reviews.values())):
            terms_variable = [ a for v in term_lists.values() for a in v ] 
            i = 0
            while i < len(student_reviews):
                student = student_reviews[student_ids[i]]
                if len(terms_variable) == 0:
                    terms_variable = [ a for v in term_lists.values() for a in v ]
                if len(student.reviews) < NUM_REVIEWS + 1:
                    temp = terms_variable.pop()
                    student.add_extra_review(temp)
                if len(student.reviews) == NUM_REVIEWS + 1:
                    i = i + 1
 
    for id, s in student_reviews.items():
        for r in s.reviews:
            dbstuff.add_review_assignment(id, r.id, r.term, r.transterm, r.transdescription, data['iss'], data['course'], section_num)
    dbstuff.set_status_of_section(data['iss'], data['course'], section_num, STATUS_REVIEWS_ASSIGNED)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], section_num)
    return render_template('manage_section.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

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
    if ',' in term:
        terms = [ t.strip() for t in term.split(',') ]
    else:
        terms = [term.strip()]
    for t in terms:
        if t:
            dbstuff.add_term_to_section_of_course(iss, course, section, t)
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
    ta_emails = [ a.strip() for a in request.form['tas'].split(',') if a.strip() != '' and re.fullmatch(email_regex, a.strip()) ] 
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

def build_launch_dict(mld, launch_id)-> Dict:
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

@app.route('/translation/review/', methods=['POST'])
def show_review():
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    rev_ass_id = request.form['rev_ass_id']
    review = dbstuff.get_review_by_id(rev_ass_id)
    print("rev_ass_id", rev_ass_id, "review", review)
    return render_template('review.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"), review=review)

@app.route('/review/add/', methods=['POST'])
def add_new_review():
    print("add_new_review", request.form)
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    rev_ass_id = request.form['rev_ass_id']
    review = dbstuff.get_review_by_id(rev_ass_id)
    review.set_review_score(request.form['review_score'])
    review.set_review_comment(request.form['review_comment'])
    dbstuff.update_review(review)
    return render_template('review.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"), review=review)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
