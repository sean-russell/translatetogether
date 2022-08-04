from collections import namedtuple
from typing import List, Dict, Set

TranslationAssignment = namedtuple("TranslationAssignment", "id name term")
ReviewAssignment = namedtuple("ReviewAssignment", "id name term transterm transdescription")
TranslatedTerm = namedtuple("TranslatedTerm", "id term transterm transdescription")

class ReviewAssignments:
    def __init__(self, id, name, term):
        self.id: str = id
        self.name: str = name
        self.term: str = term
        self.reviews: List[TranslatedTerm] = []

    def add_review(self, trans: TranslatedTerm) -> bool:
        if trans.term != self.term and trans.term not in ( r.term for r in self.reviews ):
            self.reviews.append(trans)
            return True
        return False

    def add_extra_review(self, trans: TranslatedTerm) -> bool:
        """ Adds a term to be reviewed. This version of the method allows addition of reviews 
        when the same term has been previously added """
        if trans.term != self.term and trans not in self.reviews:
            self.reviews.append(trans)
            return True
        return False

    def get_num_assigned(self) -> int:
        return len(self.reviews)

    def get_as_review_assignments(self) -> List[ReviewAssignment]:
        return [ ReviewAssignment(self.id, self.name, r.term, r.transterm, r.transdescription) for r in self.reviews ]

    def __str__(self):
        return f"ReviewAssignments ({self.id} {self.name} {self.term} {len(self.reviews)})"

    def __repr__(self):
        return self.__str__()

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
