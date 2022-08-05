from collections import namedtuple
from typing import List, Dict, Set

REVIEW_INADEQUATE = 0
REVIEW_ADEQUATE = 1
REVIEW_PROFICIENT = 2
REVIEW_SKILLED = 3
REVIEW_EXCEPTIONAL = 4

REVIEW_SCORES = (REVIEW_INADEQUATE, REVIEW_ADEQUATE, REVIEW_PROFICIENT, REVIEW_SKILLED, REVIEW_EXCEPTIONAL)

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


TranslationAssignment = namedtuple("TranslationAssignment", "id name term")
TranslatedTerm = namedtuple("TranslatedTerm", "id term transterm transdescription")

class Review:
    def __init__(self,rev_id :str, rev_ass_id: str, r_id: str, t_id: str, term: str, transterm: str, transdescription: str):
        self.id = rev_id
        self.rev_ass_id = rev_ass_id
        self.r_id: str = r_id
        self.t_id: str = t_id
        self.term: str = term
        self.transterm: str = transterm
        self.transdescription: str = transdescription
        self.completed: bool = False
        self.review_score: int = -1
        self.review_comment: str = ""

    def set_review_comment(self, comment):
        self.review_comment = comment

    def set_review_score(self, score: int):
        if type(score) != int:
            score = int(score)
        if score not in REVIEW_SCORES:
            raise ValueError("Invalid review level")
        self.review_score = score
        self.completed = True

class ReviewAssignment:
    def __init__(self, rev_ass_id: str, r_id: str, t_id: str, term: str, transterm: str, transdescription: str):
        self.rev_ass_id = rev_ass_id
        self.r_id: str = r_id
        self.t_id: str = t_id
        self.term: str = term
        self.transterm: str = transterm
        self.transdescription: str = transdescription

    # def get_review(self) -> Review:
    #     return Review(self.rev_ass_id, self.r_id, self.t_id, self.term, self.transterm, self.transdescription)



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
        terms = "[ " + ", ". join([ a.term for a in self.reviews]) + " ]"
        return f"ReviewAssignments ({self.id} {self.name} {self.term} {terms})"

    def __repr__(self):
        return self.__str__()



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
