import pymysql

from flaskext.mysql import MySQL
from typing import Dict, List, Tuple

mysql: MySQL = MySQL()

from typing import Dict, List, Any
from translator.constants import *

def prep(app):
    mysql.init_app(app)

def create_course(data: Dict) -> None:
    """ Create a course in the database """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("INSERT IGNORE INTO courses (iss, course_id, owner_id) VALUES (%s, %s, %s)", (data['iss'], data['course'], data['id']))
    conn.commit()
    conn.close()
    cursor.close()
    data['sections'] = []
    data['tas'] = []
    data['students'] = []

def get_course_owner(iss: str, course: str) -> str:
    """ Get the owner of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT owner_id FROM courses WHERE iss = %s AND course_id = %s", (iss, course))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return rows[0]['owner_id']

def create_section(data: Dict, sec: str) -> None:
    """ Create a section in the database """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("INSERT INTO sections (iss, course, section_number) VALUES (%s, %s, %s)", (data['iss'], data['course'], sec))
    conn.commit()
    conn.close()
    cursor.close()
    data['sections'] = get_sections_for_course(data['iss'], data['course'])
    data['tas'] = get_ta_details_for_course(data['iss'], data['course'])
    data['students'] = get_student_details_for_course(data['iss'], data['course'])

def section_exists(iss: str, course: str, section: str) -> bool:
    """ Check if a section exists """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM sections WHERE iss = %s AND course = %s AND section_number = %s", (iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return len(rows) > 0

def delete_section(iss: str, course: str, section: str) -> None:
    """ delete the votes for this iss, course, and section"""
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM votes WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()
    """ delete the vote assignments for this iss, course, and section"""
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vote_assignments WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()
    """ delete the reviews for this iss, course, and section"""
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()
    """ delete the review assignments for this iss, course, and section"""
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM review_assignments WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()
    """ delete the translations for this iss, course, and section"""
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM translations WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()
    """ delete the translation assignments for this iss, course, and section"""
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trans_assignments WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()
    """ delete the terms for this iss, course, and section"""
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM terms WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()
    """ delete the section from a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("DELETE FROM sections WHERE iss = %s AND course = %s AND section_number = %s", (iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()

def get_sections_for_course(iss: str, course: str) -> List:
    """ Get all sections for a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM sections WHERE iss = %s AND course = %s", (iss, course))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return [ 
        { 
            'section' : r['section_number'], 
            'status' : convert_status(r['status']), 
            'terms': get_terms_for_section_of_course(iss, course, r['section_number']) 
        } 
        for r in rows 
    ]

def set_desired_terms_for_section_in_course(iss: str, course: str, section: str, desired_terms: int) -> Dict[str,Any]:
    """ Set the desired terms for a section in a course """
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE sections SET num_terms = %s WHERE iss = %s AND course = %s AND section_number = %s", (desired_terms, iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()
    return get_section_for_course(iss, course, section)

def get_section_for_course(iss: str, course: str, section_number: str) -> Dict[str, Any]:
    """ Get a specific section for a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM sections WHERE iss = %s AND course = %s AND section_number = %s", (iss, course, section_number))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    section_description = {}
    if len(rows) == 1:
        section_description['section'] = rows[0]['section_number']
        section_description['status'] = convert_status(rows[0]['status'])
        section_description['terms'] = get_terms_for_section_of_course(iss, course, rows[0]['section_number'])
        section_description['desired_terms'] = rows[0]['num_terms']
        temp = get_trans_assignments_for_section_of_course(iss, course, section_number)
        for term in temp:
            lt = temp[term]
            temp[term] = [ a.name for a in lt ]
        section_description['trans_assignments'] = temp
        section_description['trans_numbers'] = get_num_translations_for_section_of_course(iss, course, section_number)
        section_description['review_numbers'] = get_num_reviews_for_section_of_course(iss, course, section_number)
        section_description['vote_numbers'] = get_num_votes_for_section_of_course(iss, course, section_number)
        return section_description
    else:
        return {}

def set_status_of_section(iss: str, course: str, section: str, status: int) -> None:
    """ Set the status of a section of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("UPDATE sections SET status = %s WHERE iss = %s AND course = %s AND section_number = %s", (status, iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()

def get_status_of_section(iss, course, section) -> int:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT status FROM sections WHERE iss = %s AND course = %s AND section_number = %s", (iss, course, section))
    rows = cursor.fetchall()
    status = -1
    if len(rows) == 1:
        status = rows[0]['status']
    conn.close()
    cursor.close()
    return status

def record_action(data: Dict, actioncompleted: str ):
    """ Record an action in the database """
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO actions (vle_user_id, email, vle_username, iss, course, role, action_completed) VALUES (%s, %s, %s, %s, %s, %s, %s)", (
        data['id'], data['email'], data['username'], data['iss'], data['course'], data['role'], actioncompleted))
    conn.commit()
    conn.close()
    return

def get_terms_for_section_of_course(iss: str, course: str, section: str) -> List[Dict[str,str]]:
    """ Get all terms for a section of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT id, term FROM terms WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return [ r for r in rows ]

def get_trans_assignments_for_section_of_course(iss: str, course: str, section: str) -> Dict[str,List[TranslationAssignment]]:
    """ Get all term assignments for a section of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM trans_assignments WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    ass_dict = {}
    for r in rows:
        if r['term'] not in ass_dict:
            ass_dict[r['term']] = [ TranslationAssignment(r['vle_user_id'], get_name_for_vle_user_id(r['vle_user_id']), r['term_id'], r['term'])]
        else:
            ass_dict[r['term']].append( TranslationAssignment(r['vle_user_id'], get_name_for_vle_user_id(r['vle_user_id']), r['term_id'], r['term']) )
    return ass_dict

def get_trans_assignment_for_student_in_section(u_id:str, iss: str, course: str, section: str) -> TranslationAssignment:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM trans_assignments WHERE vle_user_id = %s AND iss = %s AND course = %s AND section = %s", (u_id, iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    if len(rows) == 1:
        return TranslationAssignment(rows[0]['vle_user_id'], get_name_for_vle_user_id(rows[0]['vle_user_id']), rows[0]['term_id'], rows[0]['term'])
    return None

def get_num_translations_for_section_of_course(iss: str, course: str, section: str) -> Dict[str,int]:
    """ Get the number of translations for each term for a section of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT term, COUNT(*) AS num_translations from translations where iss = %s AND course = %s AND section = %s GROUP BY term", (iss, course, section))
    rows = cursor.fetchall()
    trans_num_dict = {}
    for r in rows:
        trans_num_dict[r['term']] = r['num_translations']
    conn.close()
    cursor.close()
    return trans_num_dict

def get_num_reviews_for_section_of_course(iss: str, course: str, section: str) -> Dict[str,int]:
    """ Get the number of reviews for each term for a section of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT term, COUNT(*) AS num_reviews from reviews where iss = %s AND course = %s AND section = %s GROUP BY term", (iss, course, section))
    rows = cursor.fetchall()
    rev_num_dict = {}
    for r in rows:
        rev_num_dict[r['term']] = r['num_reviews']
    conn.close()
    cursor.close()
    return rev_num_dict

def get_num_votes_for_section_of_course(iss: str, course: str, section: str) -> Dict[str,int]:
    """ Get the number of votes for each term for a section of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT term, COUNT(*) AS num_votes from votes where iss = %s AND course = %s AND section = %s GROUP BY term", (iss, course, section))
    rows = cursor.fetchall()
    votes_num_dict = {}
    for r in rows:
        votes_num_dict[r['term']] = r['num_votes']
    conn.close()
    cursor.close()
    return votes_num_dict


def get_student_translation_assignments_for_section(iss: str, course: str, section: str) -> tuple:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT vle_user_id, fullname FROM participants WHERE iss = %s AND course = %s", (iss, course))
    rows = cursor.fetchall()

    students = [ [r['vle_user_id'], r['fullname']] for r in rows ]
    i = 0
    for vle_user_id, fullname in students:
        cursor.execute("SELECT id, term from trans_assignments WHERE iss = %s AND course = %s AND section = %s and vle_user_id = %s", (iss, course, section, vle_user_id))
        result = cursor.fetchone()
        if result != None:
            term, trans_ass_id = result['term'], result['id']
            students[i] = students[i] + [term, trans_ass_id]
            cursor.execute("SELECT id from translations WHERE iss = %s AND course = %s AND section = %s and trans_ass_id = %s", (iss, course, section, trans_ass_id))
            result = cursor.fetchone()
            if result != None:
                students[i].append(True)
            else:
                students[i].append(False)
        i = i + 1
    students = [ s for s in students if len(s) > 2] 
    conn.close()
    cursor.close()
    return students

def get_student_review_assignments_for_section(iss: str, course: str, section: str, students: List[List[str]]) -> tuple:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT vle_user_id, fullname FROM participants WHERE iss = %s AND course = %s", (iss, course))
    i = 0
    for vle_user_id, fullname, term, trans_ass_id, comp in students:
        cursor.execute("SELECT id, term from review_assignments WHERE iss = %s AND course = %s AND section = %s and reviewer_id = %s", (iss, course, section, vle_user_id))
        rows = cursor.fetchall()
        if rows != None:
            rev_assignments = []
            for r in rows:
                rev_ass_id, rev_term = r['id'], r['term']
                rev_assignments.append([rev_ass_id,rev_term])
            j = 0
            for rev_ass_id, rev_term in rev_assignments:
                cursor.execute("SELECT id from reviews WHERE iss = %s AND course = %s AND section = %s and rev_ass_id = %s", (iss, course, section, rev_ass_id))
                result = cursor.fetchone()
                if result != None:
                    rev_assignments[j].append(True)
                else:
                    rev_assignments[j].append(False)
                j = j + 1
            students[i].append(rev_assignments)
        i = i + 1
    students = [ s for s in students if len(s) > 5] 
    conn.close()
    cursor.close()
    return students

def get_assistant_review_assignments_for_section(iss: str, course: str, section: str) -> tuple:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT vle_user_id, fullname FROM assistants NATURAL LEFT OUTER JOIN participants WHERE iss = %s AND course = %s", (iss, course))
    rows = cursor.fetchall()
    
    assistants = [ [a['vle_user_id'], a['fullname']] for a in rows]
    i = 0
    for vle_user_id, fullname in assistants:
        cursor.execute("SELECT id, term, translator_id from review_assignments WHERE iss = %s AND course = %s AND section = %s and reviewer_id = %s", (iss, course, section, vle_user_id))
        rows = cursor.fetchall()
        if rows != None:
            rev_assignments = []
            for r in rows:
                rev_ass_id, rev_term, translator_id = r['id'], r['term'], r['translator_id']
                rev_assignments.append([rev_ass_id, rev_term, translator_id])
            j = 0
            for rev_ass_id, rev_term, translator_id in rev_assignments:
                cursor.execute("SELECT fullname from participants WHERE vle_user_id = %s", (translator_id))
                name_results = cursor.fetchone()
                if name_results != None:
                    rev_assignments[j].append(name_results['fullname'])
                else:
                    rev_assignments[j].append("unable to access name for " + str(translator_id))
                cursor.execute("SELECT id from reviews WHERE iss = %s AND course = %s AND section = %s and rev_ass_id = %s", (iss, course, section, rev_ass_id))
                result = cursor.fetchone()
                if result != None:
                    rev_assignments[j].append(True)
                else:
                    rev_assignments[j].append(False)
                j = j + 1
            assistants[i].append(rev_assignments)
        i = i + 1
    assistants = [ s for s in assistants if len(s) > 2] 
    conn.close()
    cursor.close()
    return assistants


def get_candidates_for_section(iss: str, course: str, section: str):
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT translator_id,term, fullname FROM reviews WHERE iss = %s AND course = %s AND section = %s AND candidate = 1", (iss, course, section))
    rows = cursor.fetchall()
    print(rows)


def get_name_for_vle_user_id(vle_user_id: str) -> str:
    """ Get the name of a VLE user """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT distinct fullname FROM participants WHERE vle_user_id = %s", (vle_user_id))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    if len(rows) == 1:
        return rows[0]['fullname']
    else:
        return ""

def add_term_to_section_of_course(iss: str, course: str, section: str, term: str) -> None:
    """ Add a term to a section of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("INSERT INTO terms (term, iss, section, course) VALUES (%s, %s, %s, %s)", (term, iss, section, course))
    conn.commit()
    conn.close()
    cursor.close()

def delete_term_from_database(term_id : int) -> bool:
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

def assign_term_to_student(iss: str, course: str, section: str, term: str, vle_user_id: str, term_id: str) -> None:
    """ Assign a term to a student """
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO trans_assignments (vle_user_id, term_id, term, iss, section, course) VALUES (%s, %s, %s, %s, %s, %s)", (
        vle_user_id, term_id, term, iss, section, course))
    conn.commit()
    conn.close()

def count_term_assignments_for_section(iss: str, course: str, section: str) -> List:
    """ Get all term assignments for a section """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT t.term, count(a.vle_user_id) as num FROM terms t LEFT OUTER JOIN trans_assignments a ON t.iss = a.iss AND t.course = a.course AND t.section = a.section AND t.term = a.term where a.iss = %s AND a.course = %s AND a.section = %s GROUP BY t.term ORDER BY num DESC", (iss, course, section))
    terms = cursor.fetchall()
    conn.close()
    cursor.close()
    return terms

def count_unique_translations_by_student_for_section(iss: str, course: str, section: str) -> List:
    """ Get all term assignments for a section """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT count(DISTINCT vle_user_id) AS num_translations from translations where iss = %s AND course = %s AND section = %s", (iss, course, section))
    count = cursor.fetchone()
    conn.close()
    cursor.close()
    return count['num_translations']

def count_unique_reviews_by_student_for_section(iss: str, course: str, section: str) -> List:
    """ Get all term assignments for a section """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT count(DISTINCT rev_ass_id) AS num_reviews from reviews where iss = %s AND course = %s AND section = %s", (iss, course, section))
    count = cursor.fetchone()
    conn.close()
    cursor.close()
    return count['num_reviews']

def add_tas_to_course(iss: str, course: str, tas : List) -> None:
    """ Add TAs to a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    for ta in tas:
        cursor.execute("INSERT INTO assistants (iss, course, email) VALUES (%s, %s, %s)", (iss, course, ta))
        cursor.execute("UPDATE participants SET role = %s WHERE iss = %s AND course = %s AND email = %s", (INSTRUCTOR, iss, course, ta))
    conn.commit()
    conn.close()
    cursor.close()

def update_tas_in_course(iss: str, course: str, tas : List) -> None:
    """ Add TAs to a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    for ta in tas:
        cursor.execute("INSERT IGNORE INTO assistants (iss, course, email) VALUES (%s, %s, %s)", (iss, course, ta))
        cursor.execute("UPDATE participants SET role = %s WHERE iss = %s AND course = %s AND email = %s", (INSTRUCTOR, iss, course, ta))
    conn.commit()
    conn.close()
    cursor.close()

def remove_ta_from_course(ta_id: int) -> None:
    """ Remove a TA from a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("DELETE FROM assistants WHERE id = %s", (ta_id,))
    conn.commit()
    conn.close()
    cursor.close()
    return

def get_ta_emails_for_course(iss: str, course: str) -> List:
    """ Get the emails of all TAs for a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT email FROM assistants WHERE iss = %s AND course = %s", (iss, course))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    emails = []
    for row in rows:
        emails.append(row['email'])
    return emails

def get_student_details_for_course(iss: str, course: str) -> List:
    """ Get all students for a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM participants WHERE iss = %s AND course = %s AND role = %s", (iss, course, LEARNER))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    for row in rows:
        """ get timestamp for the last action based on the id"""
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT action_time FROM actions WHERE vle_user_id = %s ORDER BY action_time DESC LIMIT 1", (row['vle_user_id']))
        actions = cursor.fetchall()
        conn.close()
        cursor.close()
        if len(actions) == 1:
            row['last_action'] = str(actions[0]['action_time'])
        else:
            row['last_action'] = "Never"
    return [ r for r in rows ]

def get_teaching_assistant_emails_for_course(iss: str, course: str) -> List[str]:
    """ Get all teaching assistants for a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT email FROM assistants WHERE iss = %s AND course = %s", (iss, course))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return [ r['email'] for r in rows ]

def get_ta_details_for_course(iss: str, course: str) -> List:
    """ Get all TAs for a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM assistants NATURAL LEFT OUTER JOIN participants WHERE iss = %s AND course = %s", (iss, course))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    for row in rows:
        """ get timestamp for the last action based on the email"""
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT action_time FROM actions WHERE email = %s ORDER BY action_time DESC LIMIT 1", (row['email']))
        actions = cursor.fetchall()
        conn.close()
        cursor.close()
        if len(actions) == 1:
            row['last_action'] = str(actions[0]['action_time'])
        else:
            row['last_action'] = "Never"
    return [ r for r in rows ]

def add_participant_to_course(user_id: str, email: str, name: str, role: str, iss: str, course: str) -> None:
    """ Add a participant to a course """
    conn = mysql.connect()
    cursor = conn.cursor()
    n = cursor.execute("INSERT IGNORE INTO participants (vle_user_id, email, fullname, iss, course, role) VALUES (%s, %s, %s, %s, %s, %s)", (user_id, email, name, iss, course, role))
    n = cursor.execute("UPDATE participants SET email = %s, fullname = %s, role = %s WHERE iss = %s AND course = %s AND vle_user_id = %s", (email, name, role, iss, course, user_id))
    conn.commit()
    conn.close()

def add_term_translation(vle_user_id, trans_ass_id, term_id, term, transterm, translation, iss, course, section_num) -> None:
    """ Add a term translation """
    conn = mysql.connect()
    cursor = conn.cursor()
    stat = "INSERT IGNORE INTO translations (vle_user_id, trans_ass_id, term_id, term, transterm, transdescription, iss, course, section) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    stat1 = "INSERT IGNORE INTO translations (vle_user_id, trans_ass_id, term_id, term, transterm, transdescription, iss, course, section) VALUES ({}, {}, {}, {}, {}, {}, {}, {}, {})"
    cursor.execute(stat, (vle_user_id, trans_ass_id, term_id, term, transterm, translation, iss, course, section_num))
    print(stat1.format(vle_user_id, trans_ass_id, term_id, term, transterm, translation, iss, course, section_num))
    conn.commit()   
    cursor.execute("UPDATE trans_assignments SET status = %s WHERE id= %s", (1, trans_ass_id))
    conn.commit()
    conn.close()

def get_term_translations_for_section(iss: str, course: str, section: int) -> List[TranslatedTerm]:
    """ load the most recent translation for each student. TODO This will only work if students are assigned 1 term!"""
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    query = "SELECT id, vle_user_id, term_id, term, transterm, transdescription FROM translations WHERE id IN (SELECT MAX(id) FROM translations GROUP BY iss, course, section, vle_user_id HAVING iss = %s AND course = %s AND section = %s)"
    cursor.execute(query, (iss, course, str(section)))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    #"id term transterm transdescription"
    return [ TranslatedTerm(r['vle_user_id'], r['term_id'], r['term'], r['id'], r['transterm'], r['transdescription']) for r in rows ]

def add_review_assignment(reviewer_id: str, translator_id: str, term: str, term_id: str, trans_id: str, transterm: str, transdescription: str, iss: str, course: str, section_num: str) -> None:
    #<ins>id</ins>, *reviewer_id*, *translator_id*, term, transterm, transdescription, *iss*, *course*, *section* 
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO review_assignments (reviewer_id, translator_id, term_id, term, trans_id, transterm, transdescription, iss, course, section) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
    (reviewer_id, translator_id, term_id, term, trans_id, transterm, transdescription, iss, course, section_num))
    conn.commit()
    conn.close()

def get_assigned_reviews_for_student_in_section(id:str, iss:str, course:str, section:int) -> List[Review]:
    """ Get all assigned reviews for a student """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM review_assignments WHERE reviewer_id = %s AND iss = %s AND course = %s AND section = %s", (id, iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return [ Review(r['id'], r['reviewer_id'], r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription']) for r in rows ]

def get_latest_review_by_review_assignment_id(rev_id) -> Review:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    #SELECT * FROM reviews WHERE id IN(SELECT MAX(id) FROM reviews WHERE rev_ass_id = %s)
    cursor.execute("SELECT * FROM reviews WHERE id IN (SELECT MAX(id) FROM reviews WHERE rev_ass_id = %s)", (rev_id))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    review = None
    if len(rows) == 1:
        r = rows[0]
        review = Review(r['rev_ass_id'], r['reviewer_id'], r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription'])
        review.set_review_comment(r['review_comment'])
        review.set_review_score(r['review_score'])
        review.set_candidate(r['candidate'] in (1, '1'))
    else:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM review_assignments WHERE id = %s", (rev_id))
        rows = cursor.fetchall()
        conn.close()
        cursor.close()
        if len(rows) == 1:
            r = rows[0]
            review = Review(r['id'], r['reviewer_id'], r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription'])
    
    return review

def get_candidates_for_section(iss:str, course:str, section:int) -> List[Review]:
    """ Get all candidates for a section """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM reviews WHERE id IN (SELECT a from (SELECT rev_ass_id, MAX(id) as a from reviews GROUP BY iss, course, section, rev_ass_id HAVING iss = %s AND course = %s AND section = %s) tab )", (iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    reviews = []
    for r in rows:
        review = Review(r['rev_ass_id'], r['reviewer_id'], r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription'])
        review.set_review_comment(r['review_comment'])
        review.set_review_score(r['review_score'])
        review.set_candidate(r['candidate'] in (1, '1'))
        if review.review_candidate:
            reviews.append(review)
    return reviews

def get_latest_vote_by_vote_assignment_id(rev_id) -> Review:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM votes WHERE id IN (SELECT MAX(id) FROM votes WHERE vote_ass_id = %s)", (rev_id))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    review = None
    if len(rows) == 1:
        r = rows[0]
        review = Review(r['rev_ass_id'], r['reviewer_id'], r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription'])
        review.set_review_comment(r['review_comment'])
        review.set_review_score(r['review_score'])
        review.set_candidate(r['candidate'] in (1, '1'))
    else:
        conn = mysql.connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM review_assignments WHERE id = %s", (rev_id))
        rows = cursor.fetchall()
        conn.close()
        cursor.close()
        if len(rows) == 1:
            r = rows[0]
            review = Review(r['id'], r['reviewer_id'], r['translator_id'], r['term_id'], 
                            r['term'], r['trans_id'], r['transterm'], r['transdescription'])
    
    return review

def get_votes_for_student_in_section(id:str, iss:str, course:str, section:int) -> List[Vote]:
    votes: Dict[str,Vote] = {}
    """ Get all vote assignments for a student """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM vote_assignments WHERE voter_id = %s AND iss = %s AND course = %s AND section = %s", (id, iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    for r in rows:
        vote = Vote(r['id'], r['voter_id'],r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription'])
        votes[r['id']] = vote

    """ Get all votes for a student in a section """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM votes WHERE id in (SELECT max(id) from votes GROUP BY iss, section, course, vote_ass_id HAVING voter_id = %s AND iss = %s AND course = %s AND section = %s)", (id, iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    
    for r in rows:
        vote = Vote(r['vote_ass_id'], r['voter_id'],r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription'])
        vote.set_vote_score(r['vote_score'])
        votes[r['vote_ass_id']] = vote
    return list(votes.values())

def get_votes_for_student(id:str, iss:str, course:str) -> List[Vote]:
    votes: Dict[str,Vote] = {}
    """ Get all vote assignments for a student """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM vote_assignments WHERE voter_id = %s AND iss = %s AND course = %s", (id, iss, course))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    for r in rows:
        vote = Vote(r['id'], r['voter_id'],r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription'])
        votes[r['id']] = vote

    """ Get all votes for a student """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM votes WHERE id in (SELECT max(id) from votes GROUP BY iss, section, course, vote_ass_id HAVING voter_id = %s AND iss = %s AND course = %s)", (id, iss, course))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    
    for r in rows:
        vote = Vote(r['vote_ass_id'], r['voter_id'],r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription'])
        vote.set_vote_score(r['vote_score'])
        votes[r['vote_ass_id']] = vote
    return list(votes.values())

def assign_vote_to_student(vle_user_id: str, vc: Review, iss: str, course: str, section_num: str):
    conn = mysql.connect()
    cursor = conn.cursor()
    print("INSERT IGNORE INTO vote_assignments (voter_id, translator_id, term_id, term, trans_id, transterm, transdescription, iss, course, section) VALUES ('{}', '{}', {}, '{}', {}, '{}', '{}', '{}', '{}', '{}')".format(vle_user_id, vc.t_id, vc.term_id, vc.term, vc.trans_id, vc.transterm, vc.transdescription, iss, course, section_num))
    cursor.execute("INSERT IGNORE INTO vote_assignments (voter_id, translator_id, term_id, term, trans_id, transterm, transdescription, iss, course, section) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
    (vle_user_id, vc.t_id, vc.term_id, vc.term, vc.trans_id, vc.transterm, vc.transdescription, iss, course, section_num))
    conn.commit()
    conn.close()

def get_assigned_votes_for_student_in_section(id:str, iss:str, course:str, section:int) -> List[Vote]:
    """ Get all assigned votes for a student """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM vote_assignments WHERE voter_id = %s AND iss = %s AND course = %s AND section = %s", (id, iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return [ Vote(r['id'], r['voter_id'], r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription']) for r in rows ]

def get_latest_vote_by_vote_assignment_id(v_id) -> Vote:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    #SELECT * FROM votes WHERE id IN(SELECT MAX(id) FROM votes WHERE v_ass_id = %s)
    cursor.execute("SELECT * FROM votes WHERE id IN (SELECT MAX(id) FROM votes WHERE v_ass_id = %s)", (v_id))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    vote = None
    if len(rows) == 1:
        r = rows[0]
        vote = Vote(r['v_ass_id'], r['voter_id'], r['translator_id'], r['term_id'], r['term'], r['trans_id'], r['transterm'], r['transdescription'])
        vote.set_vote_score(r['vote_score'])
    return vote
    
def update_vote(vote: Vote, iss: str, course: str, section: int):
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO votes (vote_ass_id, voter_id, translator_id, term_id, term, trans_id, transterm, transdescription, vote_score, iss, course, section) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
    (vote.vote_assign_id, vote.v_id, vote.t_id, vote.term_id, vote.term, vote.trans_id, vote.transterm, vote.transdescription, vote.vote_score, iss, course, section))
    conn.commit()
    conn.close()

def get_assigned_and_completed_votes_for_student_in_section(id:str, iss:str, course:str, section:int) -> List[Vote]:
    votes: List[Vote] = []
    assigned_votes = get_assigned_votes_for_student_in_section(id, iss, course, section)
    for av in assigned_votes:
        vote = get_latest_vote_by_vote_assignment_id(av.vote_assign_id)
        if vote is not None:
            votes.append(vote)
        else:
            votes.append(av)
    return votes

def add_review(review: Review, iss: str, course: str, section: str):
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO reviews (rev_ass_id, reviewer_id, translator_id, term_id, term, trans_id, transterm, transdescription, review_comment, review_score, candidate, iss, course, section ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
    (review.rev_ass_id, review.r_id, review.t_id, review.term_id, review.term, review.trans_id, review.transterm, review.transdescription, review.review_comment, review.review_score, review.review_candidate, iss, course, section))
    conn.commit()
    conn.close()

def get_assigned_and_completed_reviews_for_student_in_section(id:str, iss:str, course:str, section:int) -> List[Review]:
    reviews: List[Review] = []
    assigned_reviews = get_assigned_reviews_for_student_in_section(id, iss, course, section)
    for ar in assigned_reviews:
        review = get_latest_review_by_review_assignment_id(ar.rev_ass_id)
        if review is not None:
            reviews.append(review)
        else:
            reviews.append(ar)
    return reviews

def get_assigned_term(data: Dict) -> Dict[str,str]:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT id, term_id, term, status FROM trans_assignments WHERE iss = %s AND vle_user_id = %s AND course = %s AND section = %s LIMIT 1", 
        (data['iss'], data['id'], data['course'], data['section_num']))
    ass_rows = cursor.fetchall()
    if len(ass_rows) == 1:
        """ get the most recent translation """
        cursor.execute("SELECT transterm, transdescription FROM translations WHERE vle_user_id = %s AND term = %s AND iss = %s AND course = %s AND section = %s ORDER BY submit_time DESC LIMIT 1",
            (data['id'], ass_rows[0]['term'], data['iss'], data['course'], data['section_num']))
        trans_rows = cursor.fetchall()
        t_dict = {
            'id': ass_rows[0]['id'],
            'term_id': ass_rows[0]['term_id'],
            'term': ass_rows[0]['term'],
            'status': ass_rows[0]['status'],
            'transterm' : "",
            'transdescription' : ""
        }
        if len(trans_rows) == 1:
            t_dict['transterm'] = trans_rows[0]['transterm']
            t_dict['transdescription'] = trans_rows[0]['transdescription']
        return t_dict
    conn.close()
    cursor.close()

    return None
