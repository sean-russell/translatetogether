from importlib import resources
import os
import random
import jwt
import re

from translator import dbstuff
from translator.constants import *
from typing import Dict, List, Set, Any

from collections import namedtuple
from flask import Flask, jsonify, request, render_template, url_for, redirect, escape
from datetime import date
from tempfile import mkdtemp
from flask_caching import Cache
from importlib.resources import is_resource

from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest, FlaskCacheDataStorage
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem
from pylti1p3.tool_config import ToolConfJsonFile
from pylti1p3.registration import Registration

from translator.deep_link import DeepLink


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

@app.template_filter()
def any_filter(dttm):
    l = list(dttm)
    return any(l)

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
    ta_emails = dbstuff.get_ta_emails_for_course(data['iss'], data['course'])
    if data['email'] in ta_emails:
        data['role'] = TEACHING_ASSISTANT


    if data['role'] == INSTRUCTOR:
        owner = dbstuff.get_course_owner(data['iss'], data['course'])
        if message_launch.is_deep_link_launch():
            section_list =  [ s['section'] for s in dbstuff.get_sections_for_course(data['iss'], data['course'])]
            deployment_id = message_launch._get_deployment_id()
            deep_linking_settings = message_launch._get_jwt_body().get('https://purl.imsglobal.org/spec/lti-dl/claim/deep_linking_settings')  
            deep_link_response = DeepLink(message_launch._registration, deployment_id, deep_linking_settings)
            resources = []
            for sec_num in section_list:
                for phase in (PHASE_TRANSLATE,PHASE_REVIEW,PHASE_VOTE):
                    for lang in ("Arabic", "Chinese"):
                        r = {}
                        resource = DeepLinkResource()
                        resource.set_url('https://cstools.ucd.ie'+preface+'/init/')
                        resource.set_custom_params({'section': str(sec_num), 'phase': phase, 'language': lang})
                        resource.set_title('Translate Together ({}) - {} task'.format(sec_num, phase))
                        r['JWT'] = deep_link_response.get_response_jwt([resource])
                        r['title'] = 'Translate Together ({}) - {} task'.format(sec_num, phase)
                        r['description'] = phase_descriptions[phase].format(lang)
                        resources.append(r)

            return render_template('deep_response.html', resources=resources, deep_link_return_url=deep_linking_settings['deep_link_return_url'])
        elif owner == data['id']:
            data['sections'] = dbstuff.get_sections_for_course(data['iss'], data['course'])
            data['tas'] = dbstuff.get_ta_details_for_course(data['iss'], data['course'])
            data['students'] = dbstuff.get_student_details_for_course(data['iss'], data['course'])
            return render_template('manage_course.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))
    #    else: # This is where the teaching assistants should be 
    elif data['role'] == TEACHING_ASSISTANT:
        status = dbstuff.get_status_of_section(data['iss'], data['course'], data['section_num'])
        if status in (STATUS_REVIEWS_ASSIGNED, convert_status(STATUS_REVIEWS_ASSIGNED)):
            reviews = dbstuff.get_assigned_and_completed_reviews_for_student_in_section(data['id'], data['iss'], data['course'], data['section_num'])
            rll: Dict[str,List[Review]] = {}
            for review in reviews:
                if review.term not in rll:
                    rll[review.term] = []
                rll[review.term].append(review)
            return render_template('ta_reviews.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"), reviews=rll)
        else:
            return render_template('no_action.html')
    elif data['role'] == LEARNER:
        start = date.fromisoformat(data['phase_start'])
        end = date.fromisoformat(data['phase_end'])
        today : date = date.today()
        if start > today:
            dbstuff.record_action(data, "Entered the translation tool before it is open")
            return render_template('before_start.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))
        elif end < today:
            dbstuff.record_action(data, "Entered the translation tool after the deadline")
            return render_template('after_end.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))
        
        if dbstuff.section_exists(data['iss'], data['course'], data['section_num']):
            data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], data['section_num'])
            print("data['section']", data['section'])
            print("current status is ", data['section']['status'])
            if data['section']['status'] in (STATUS_NOT_PREPARED, STATUS_TERMS_PREPARED):
                dbstuff.record_action(data, "encountered a configuration error")
                return render_template('config.html', preface=preface, data=jsonify(data))
            elif data['phase'] == PHASE_TRANSLATE:
                if data['section']['status'] in (STATUS_TERMS_ASSIGNED, convert_status(STATUS_TERMS_ASSIGNED)):
                    term = dbstuff.get_assigned_term(data)
                    if term == None:
                        assign_term(data)
                        term = dbstuff.get_assigned_term(data)
                    dbstuff.record_action(data, "opened the translation assignment")
                    return render_template('term.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"),term=term)
            elif data['phase'] == PHASE_REVIEW:
                print("phase is review")
                if data['section']['status'] in (STATUS_REVIEWS_ASSIGNED, convert_status(STATUS_REVIEWS_ASSIGNED)):
                    review_assignments = dbstuff.get_assigned_and_completed_reviews_for_student_in_section(data['id'], data['iss'], data['course'], data['section_num'])
                    if review_assignments == None:
                        raise Exception("No reviews assigned!!!")
                    dbstuff.record_action(data, "opened the review assignment")
                    return render_template('reviews.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"),reviews=review_assignments)
            elif data['phase'] == PHASE_VOTE:
                if data['section']['status'] in (STATUS_VOTES_ASSIGNED, convert_status(STATUS_VOTES_ASSIGNED)):
                    data['candidates']: Dict[str,List[Dict[str,str]]] = {}
                    get_candidates(data)
                    data['terms']: List[str] = list(data['candidates'].keys())
                    dbstuff.record_action(data, "opened the voting assignment")
                    return render_template('votes.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))
            
        else:
            dbstuff.record_action(data, "encountered a configuration error, probably because the section does not exist")
            return render_template('config.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

def get_candidates(data):
    data['candidates']: Dict[str,List[Dict[str,str]]] = {}
    candidates = dbstuff.get_votes_for_student(data['id'], data['iss'], data['course'])
    
    candidates = [ {
            "vote_assign_id": c.vote_assign_id,
            "v_id": c.v_id,
            "t_id": c.t_id,
            "term_id": c.term_id,
            "term": c.term,
            "trans_id": c.trans_id,
            "transterm": c.transterm,
            "transdescription": c.transdescription,
            "vote_score": c.vote_score,
            "completed": c.completed
        } for c in candidates ]
    
    for candidate in candidates:
        if candidate['term'] not in data['candidates']:
            data['candidates'][candidate['term']] = []
        data['candidates'][candidate['term']].append(candidate)

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
    if data['section']['status'] == STATUS_TERMS_ASSIGNED_STR:
        data['students'] = dbstuff.get_student_translation_assignments_for_section(data['iss'], data['course'], request.form['section'])
        data['num_translations'] = sum(list(dbstuff.get_num_translations_for_section_of_course(data['iss'], data['course'], request.form['section']).values()))
        data['num_translations_complete'] = dbstuff.count_unique_translations_by_student_for_section(data['iss'], data['course'], request.form['section'])
    elif data['section']['status'] == STATUS_REVIEWS_ASSIGNED_STR:
        data['students'] = dbstuff.get_student_translation_assignments_for_section(data['iss'], data['course'], request.form['section'])
        data['students'] = dbstuff.get_student_review_assignments_for_section(data['iss'], data['course'], request.form['section'], data['students'])
        data['assistants'] = dbstuff.get_assistant_review_assignments_for_section(data['iss'], data['course'], request.form['section'])
        data['num_translations'] = sum(list(dbstuff.get_num_translations_for_section_of_course(data['iss'], data['course'], request.form['section']).values()))
        data['num_translations_complete'] = dbstuff.count_unique_translations_by_student_for_section(data['iss'], data['course'], request.form['section'])
        data['num_reviews'] = sum(list(dbstuff.get_num_reviews_for_section_of_course(data['iss'], data['course'], request.form['section']).values()))
        data['num_reviews_complete'] = dbstuff.count_unique_reviews_by_student_for_section(data['iss'], data['course'], request.form['section'])
    return render_template('manage_section_alt.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

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
    assert data['role'] == INSTRUCTOR
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
    assert data['role'] == INSTRUCTOR
    section_num = request.form['section']
    iss = data['iss']
    course = data['course']
    term_assignments = dbstuff.get_trans_assignments_for_section_of_course(iss, course, section_num)
    student_reviews: Dict[str, ReviewAssignments] = {}
    ta_reviews: Dict[str, TAReviewAssignments] = {}
    for term in term_assignments:
        for t in term_assignments[term]:
            student_reviews[t.id] = ReviewAssignments(t.id, t.term_id, t.name, term)
    # print("student_reviews length", len(student_reviews))
    tas = dbstuff.get_ta_details_for_course(iss, course)
    for ta in tas:
        ta_reviews[ta['vle_user_id']] = TAReviewAssignments(ta['vle_user_id'])

    translations = dbstuff.get_term_translations_for_section(iss, course, section_num)
    term_lists: Dict[str,List[TranslatedTerm]] = {}
    term_lists_variable: Dict[str,List[TranslatedTerm]] = {}
    ta_term_lists_variable: List[Any] = []
    all_assigned: Dict[str,bool] = {}
    term_set: Set[str] = set()

    for sid in student_reviews:
        x = student_reviews[sid]
        if x.term not in term_lists:
            term_lists[x.term] = []
            term_lists_variable[x.term] = []
            all_assigned[x.term] = False
    # print("translations", translations)
    for t in translations:
        term_set.add(t.term)
        term_lists[t.term].append(t)
    # print("Distribution Terms", list(map(lambda x: (x[0], x[1], len(x[2])), ta_term_lists_variable )))
    for t in term_lists:
        term_lists_variable[t] = term_lists[t] * NUM_REVIEWS
        ta_term_lists_variable.append([0 , t, term_lists[t]])
        random.shuffle(term_lists_variable[t])
    # print("Distribution Terms", list(map(lambda x: (x[0], x[1], len(x[2])), ta_term_lists_variable )))
    
    num_lists = len(term_lists.keys()) * NUM_TA_REVIEWS
    num_tas = len(tas)
    # print("num_lists", num_lists, "num_tas", num_tas)
    if num_lists <= num_tas:
        # print("everyone gets 1")
        for tar in ta_reviews.values():
            # print("assigning a list to ta", tar.id)
            ta_term_lists_variable.sort(key=lambda x: (x[0], len(x[2])))
            # print("Distribution Terms", list(map(lambda x: (x[0], x[1], len(x[2])), ta_term_lists_variable )))
            tar.assign_reviews(ta_term_lists_variable[0][2])
            ta_term_lists_variable[0][0] += 1
    elif num_lists <= num_tas * 2:
        # print("doubling up")
        for tar in ta_reviews.values():
            # print("assigning 2 lists to ta", tar.id)
            ta_term_lists_variable.sort(key=lambda x: (x[0], len(x[2])))
            # print("Distribution Terms", list(map(lambda x: (x[0], x[1], len(x[2])), ta_term_lists_variable )))
            tar.assign_reviews(ta_term_lists_variable[0][2])
            ta_term_lists_variable[0][0] += 1
            ta_term_lists_variable.sort(key=lambda x: (x[0], len(x[2])))
            # print("Distribution Terms", list(map(lambda x: (x[0], x[1], len(x[2])), ta_term_lists_variable )))
            tar.assign_reviews(ta_term_lists_variable[0][2])
            ta_term_lists_variable[0][0] += 1
            # print("Distribution Terms", list(map(lambda x: (x[0], x[1], len(x[2])), ta_term_lists_variable )))

    # print("Distribution TAs", list(map(lambda x: len(x.reviews), ta_reviews.values())))
    # print("Distribution Terms", list(map(lambda x: (x[0], x[1], len(x[2])), ta_term_lists_variable )))
    
    for id, ta in ta_reviews.items():
        for r in ta.reviews:
            dbstuff.add_review_assignment(id, r.id, r.term, r.term_id, r.trans_id, r.transterm, r.transdescription, data['iss'], data['course'], section_num)
    # dbstuff.set_status_of_section(data['iss'], data['course'], section_num, STATUS_REVIEWS_ASSIGNED)

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
            dbstuff.add_review_assignment(id, r.id, r.term, r.term_id, r.trans_id, r.transterm, r.transdescription, data['iss'], data['course'], section_num)
    dbstuff.set_status_of_section(data['iss'], data['course'], section_num, STATUS_REVIEWS_ASSIGNED)
    data['section'] = dbstuff.get_section_for_course(data['iss'], data['course'], section_num)
    return render_template('manage_section.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))

@app.route('/section/voting/', methods=['POST'])
def start_voting():
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    assert data['role'] == INSTRUCTOR
    section_num = request.form['section']
    iss = data['iss']
    course = data['course']
    vote_candidates = dbstuff.get_candidates_for_section(iss, course, section_num)
    term_assignments = dbstuff.get_trans_assignments_for_section_of_course(iss, course, section_num)
    print("vote candidates", vote_candidates)
    print("term assignments", term_assignments)
    
    for term, ass_list in term_assignments.items():
        for ass in ass_list:
            trans_ids = []
            for vc in vote_candidates:
                if vc.term != term and vc.trans_id not in trans_ids:
                    trans_ids.append(vc.trans_id)
                    dbstuff.assign_vote_to_student(ass.id, vc, iss, course, section_num)
    dbstuff.set_status_of_section(data['iss'], data['course'], section_num, STATUS_VOTES_ASSIGNED)
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
    students = dbstuff.get_student_details_for_course(iss, course)
    student_ids = [ student['vle_user_id'] for student in students ]
    # print("terms list", terms)
    # print("student ids", student_ids)
    random_terms: List[Dict[str,str]] = []
    while len(random_terms) < len(student_ids):
        random_terms.extend(terms_with_ids)
    # print("random terms", len(random_terms), random_terms)
    random.shuffle(random_terms)
    random.shuffle(student_ids)
    for student in student_ids:
        term = random_terms.pop(0)
        dbstuff.assign_term_to_student(iss, course, section_num, term['term'], student, term['id'])

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
        term = term_counts[0]
        dbstuff.assign_term_to_student(data['iss'], data['course'], data['section_num'], term['term'], data['id'], term['id'])

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
    phase_start = custom.get('phase_start')
    phase_end = custom.get('phase_end')
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
        'phase_start'   : phase_start,
        'phase_end'     : phase_end,
        'today'         : date.today().isoformat(),
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
    term_id = request.form['term_id']
    trans_ass_id = request.form['trans_ass_id']
    termtrans = request.form['termtrans']
    translation = request.form['translation']
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    dbstuff.add_term_translation(data['id'], trans_ass_id, term_id, term, termtrans, translation, data['iss'], data['course'], data['section_num'])
    term = dbstuff.get_assigned_term(data)
    dbstuff.record_action(data, "added a new translation")
    return render_template('term.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"),term=term)

@app.route('/translation/review/', methods=['POST'])
def show_review():
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    rev_ass_id = request.form['rev_ass_id']
    review = dbstuff.get_latest_review_by_review_assignment_id(rev_ass_id)
    ta_emails = dbstuff.get_ta_emails_for_course(data['iss'], data['course'])
    if data['email'] in ta_emails:
        data['role'] = TEACHING_ASSISTANT
    if data['role'] == INSTRUCTOR or data['role'] == TEACHING_ASSISTANT:
        return render_template('ta_review.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"),review=review)
    dbstuff.record_action(data, "displayed a translation to review")
    return render_template('review.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"), review=review)

@app.route('/review/add/', methods=['POST'])
def add_new_review():
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    rev_ass_id = request.form['rev_ass_id']
    review = dbstuff.get_latest_review_by_review_assignment_id(rev_ass_id)
    review.set_review_score(request.form['review_score'])
    review.set_review_comment(request.form['review_comment'])
    dbstuff.add_review(review, data['iss'], data['course'], data['section_num'])
    review_assignments = dbstuff.get_assigned_and_completed_reviews_for_student_in_section(data['id'], data['iss'], data['course'], data['section_num'])
    if review_assignments == None:
        raise Exception("No reviews assigned!!!")
    dbstuff.record_action(data, "submitted a review of a translation")
    return render_template('reviews.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"),reviews=review_assignments)
    # return render_template('review.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"), review=review)

@app.route('/review/taadd/', methods=['POST'])
def add_new_ta_review():
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    rev_ass_id = request.form['rev_ass_id']
    candidate = request.form.get('candidate')  != None
    review = dbstuff.get_latest_review_by_review_assignment_id(rev_ass_id)
    review.set_review_score(request.form['review_score'])
    review.set_review_comment(request.form['review_comment'])
    review.set_candidate(candidate)
    dbstuff.add_review(review, data['iss'], data['course'], data['section_num'])
    reviews = dbstuff.get_assigned_and_completed_reviews_for_student_in_section(data['id'], data['iss'], data['course'], data['section_num'])
    rll: Dict[str,List[Review]] = {}
    for review in reviews:
        if review.term not in rll:
            rll[review.term] = []
        rll[review.term].append(review)
    dbstuff.record_action(data, "submitted a review of a translation as a TA")
    return render_template('ta_reviews.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"), reviews=rll)
    # return render_template('ta_review.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"), review=review)


@app.route('/translation/vote/', methods=['POST'])
def show_vote():
    term = request.form['term']
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    votes = data['candidates'][term]


    return render_template('vote.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"), votes=votes, term=term)

@app.route('/translation/addvote/', methods=['POST'])
def add_votes():
    term = request.form['term']
    print('term',term)
    data = jwt.decode(request.form['datajson'], _public_key, algorithms=["RS256"])
    votes: List[Vote] = []
    print("data['candidates'][term]",data['candidates'][term], type(data['candidates'][term]), len(data['candidates'][term]))
    for v in data['candidates'][term]:
        print(v)
        vt = Vote(v['vote_assign_id'], v['v_id'], v['t_id'], v['term_id'], v['term'], v['trans_id'], v['transterm'], v['transdescription'])
        vt.set_vote_score(v['vote_score'])
        print(vt)
        votes.append(vt)
    scores = {}
    for i in range(len(votes)):
        vs = request.form.get("vote-{}".format(i))
        print("getting","vote-{}".format(i), vs)
        scores[i] = vs
    for vote in votes:
        for score in scores:
            print("score",score,"vote.vote_assign_id", vote.vote_assign_id, "scores[score]", scores[score])
            if "vote-"+str(vote.vote_assign_id) == scores[score]:
                print("setting score of" , vote.vote_assign_id, "to", score)
                vote.set_vote_score(score)
                dbstuff.update_vote(vote, data['iss'], data['course'], data['section_num'])
        # vs = request.form.get("vote-{}".format(vote.vote_assign_id))
        # print("getting","vote-{}".format(vote.vote_assign_id), vs)
        # if vs != None:
        #     vote.set_vote_score(vs)
        #     
        print("data['candidates'][term]",data['candidates'][term], type(data['candidates'][term]), len(data['candidates'][term]))
        get_candidates(data)
        print("data['candidates'][term]",data['candidates'][term], type(data['candidates'][term]), len(data['candidates'][term]))
    
    return render_template('votes.html', preface=preface, data=data, datajson=jwt.encode(data, _private_key, algorithm="RS256"))



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
