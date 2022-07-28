import pymysql

from flaskext.mysql import MySQL
from typing import Dict, List

mysql = MySQL()

from typing import Dict, List, Any
from constants import *

def prep(app):
    mysql.init_app(app)

def create_course(data: Dict) -> None:
    """ Create a course in the database """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("INSERT IGNORE INTO courses (iss, course_id) VALUES (%s, %s)", (data['iss'], data['course']))
    conn.commit()
    conn.close()
    cursor.close()
    data['sections'] = []
    data['tas'] = []
    data['students'] = []

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

def get_section_for_course(iss: str, course: str, section_number: str) -> Dict[str, Any]:
    """ Get a specific section for a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM sections WHERE iss = %s AND course = %s AND section_number = %s", (iss, course, section_number))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    if len(rows) == 1:
        return { 
            'section' : rows[0]['section_number'], 
            'status' : convert_status(rows[0]['status']), 
            'terms': get_terms_for_section_of_course(iss, course, rows[0]['section_number']) 
        }
    else:
        return {}

def set_status_of_section(iss: str, course: str, section: str, status: str) -> None:
    """ Set the status of a section of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("UPDATE sections SET status = %s WHERE iss = %s AND course = %s AND section_number = %s", (status, iss, course, section))
    conn.commit()
    conn.close()
    cursor.close()

def get_status_of_section(data: Dict) -> int:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT status FROM status WHERE course_id = %s AND section = %s", (data['course'], data['section']))
    rows = cursor.fetchall()
    status = -1
    if len(rows) == 1:
        status = rows[0]['status']
    conn.close()
    cursor.close()
    return status

def convert_status(status : int) -> str:
    """ Convert the status from the database to a more readable format """
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

def record_action(data: Dict, actioncompleted: str ):
    """ Record an action in the database """
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO actions (vle_user_id, email, vle_username, iss, course, role, action_completed) VALUES (%s, %s, %s, %s, %s, %s, %s)", (
        data['id'], data['email'], data['username'], data['iss'], data['course'], data['role'], actioncompleted))
    conn.commit()
    conn.close()
    return

def get_terms_for_section_of_course(iss: str, course: str, section: str) -> List:
    """ Get all terms for a section of a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT id, term FROM terms WHERE iss = %s AND course = %s AND section = %s", (iss, course, section))
    rows = cursor.fetchall()
    conn.close()
    cursor.close()
    return [ r for r in rows ]

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

def add_tas_to_course(iss: str, course: str, tas : List) -> None:
    """ Add TAs to a course """
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    for ta in tas:
        cursor.execute("INSERT INTO assistants (iss, course, email) VALUES (%s, %s, %s)", (iss, course, ta))
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
    cursor.execute("INSERT IGNORE INTO participants (vle_user_id, email, fullname, iss, course, role) VALUES (%s, %s, %s, %s, %s, %s)", (
        user_id, email, name, iss, course, role))
    conn.commit()
    conn.close()

def assign_term_to_student(iss: str, course: str, section: str, term: str, vle_user_id: str) -> None:
    """ Assign a term to a student """
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute("INSERT IGNORE INTO trans_assignments (term, iss, section, course, vle_user_id) VALUES (%s, %s, %s, %s, %s)", (
        term, iss, section, course, vle_user_id))
    conn.commit()
    conn.close()

#########################################
# def course_exists(iss: str, course: str) -> bool:
#     """ Check if a course exists in the database """
#     conn = mysql.connect()
#     cursor = conn.cursor(pymysql.cursors.DictCursor)
#     cursor.execute("SELECT * FROM courses WHERE iss = %s AND course_id = %s", (iss, course))
#     rows = cursor.fetchall()
#     conn.close()
#     cursor.close()
#     return len(rows) == 1
# def assign_term(data):
#     """ get list of terms that have been assigned for this iss, course and section
#     order the list by the number of times they have been assigned descending"""
#     conn = mysql.connect()
#     cursor = conn.cursor(pymysql.cursors.DictCursor)
#     cursor.execute("SELECT term, count(vle_user_id) as c FROM trans_assignments WHERE iss = %s AND course = %s AND section = %s GROUP BY term ORDER BY c DESC", (data['iss'], data['course'], data['section_num']))
#     rows = cursor.fetchall()
#     print(rows)
#     if len(rows) > 0:
#         term = rows[0]['term']
#     else:
#         term = assign_random_term(data)
#     """ assign the term to the user """
#     conn = mysql.connect()
#     cursor = conn.cursor()
#     cursor.execute("INSERT INTO trans_assignments (vle_user_id, term, iss, course, section) VALUES (%s, %s, %s, %s, %s)", (data['id'], term, data['iss'], data['course'], data['section_num'])  )
#     conn.commit()
#     conn.close()
#     return

# def assign_random_term(data):
#     conn = mysql.connect()
#     cursor = conn.cursor(pymysql.cursors.DictCursor)
#     cursor.execute("SELECT term FROM terms WHERE iss = %s AND course = %s AND section = %s", (data['course'], data['section_num']))
#     rows = cursor.fetchall()
#     cursor.close()
#     conn.close()
#     term = random.choice([r['term'] for r in rows])
#     return term

# def translate_term(user, config, term, transterm, translation):
#     """ add the translation to the database """
#     conn = mysql.connect()
#     cursor = conn.cursor()
#     cursor.execute("INSERT INTO translations (vle_id, term, transterm, transdescription, section, course_id) VALUES (%s, %s, %s, %s, %s, %s)", 
#         (user['id'], term, transterm, translation, config['section_num'], config['course']))
#     conn.commit()
#     conn.close()
#     return

def get_assigned_term(data: Dict) -> str:
    conn = mysql.connect()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT term_id, term FROM assignments WHERE iss = %s AND vle_user_id = %s AND course = %s AND section = %s", 
        (data['iss'], data['id'], data['course'], data['section_num']))
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0]['term']
    conn.close()
    cursor.close()

    return None