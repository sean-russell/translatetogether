from collections import namedtuple

TranslationAssignment = namedtuple("TranslationAssignment", "id name term")
TranslatedTerm = namedtuple("TranslatedTerm", "id term transterm transdescription")

STATUS_NOT_PREPARED = 0
STATUS_TERMS_PREPARED = 1
STATUS_TERMS_ASSIGNED = 2
STATUS_REVIEWS_ASSIGNED = 3 
STATUS_VOTES_ASSIGNED = 4

PHASE_TRANSLATE= "translate"
PHASE_REVIEW = "review"
PHASE_VOTE = "vote"

NUM_REVIEWS = 3

CLAIM_EXT = 'https://purl.imsglobal.org/spec/lti/claim/ext'
CLAIM_CONTEXT = 'https://purl.imsglobal.org/spec/lti/claim/context'
CLAIM_CUSTOM = "https://purl.imsglobal.org/spec/lti/claim/custom"
CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
LEARNER = 'http://purl.imsglobal.org/vocab/lis/v2/membership#Learner'
INSTRUCTOR = 'http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor'


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
