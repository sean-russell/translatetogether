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

phase_descriptions={ 
    PHASE_TRANSLATE: "This phase of the assessment, students will be asked to translate a single term into {}.",
    PHASE_REVIEW: "This phase of the assessment, students will be asked to review the translation of a number of terms translated into {} by their classmates.",
    PHASE_VOTE: "This phase of the assessment, students will be asked to vote on a number of terms translated into {} to determine which is considered best."
}

NUM_REVIEWS = 3
NUM_TA_REVIEWS = 2

CLAIM_EXT = 'https://purl.imsglobal.org/spec/lti/claim/ext'
CLAIM_CONTEXT = 'https://purl.imsglobal.org/spec/lti/claim/context'
CLAIM_CUSTOM = "https://purl.imsglobal.org/spec/lti/claim/custom"
CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
LEARNER = 'http://purl.imsglobal.org/vocab/lis/v2/membership#Learner'
INSTRUCTOR = 'http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor'


TranslationAssignment = namedtuple("TranslationAssignment", "id name term_id term")
TranslatedTerm = namedtuple("TranslatedTerm", "id term_id term trans_id transterm transdescription")

class Review:
    def __init__(   self, rev_ass_id: str, r_id: str, t_id: str, term_id:str, 
                    term: str, trans_id: str, transterm: str, transdescription: str):
        self.rev_ass_id = rev_ass_id
        self.r_id: str = r_id
        self.t_id: str = t_id
        self.term_id: str = term_id
        self.term: str = term
        self.trans_id: str = trans_id
        self.transterm: str = transterm
        self.transdescription: str = transdescription
        self.completed: bool = False
        self.review_score: int = -1
        self.review_comment: str = ""
        self.review_candidate: bool = False

    def set_review_comment(self, comment):
        self.review_comment = comment

    def set_review_score(self, score: int):
        if type(score) != int:
            score = int(score)
        if score not in REVIEW_SCORES:
            raise ValueError("Invalid review level")
        self.review_score = score
        self.completed = True
    
    def set_candidate(self, candidate: bool):
        self.review_candidate = candidate

    def __str__(self):
        return f"{self.transterm} {self.review_score} {self.review_candidate} {self.review_comment}"

    def __repr__(self):
        return self.__str__()


class TAReviewAssignments:
    def __init__(self, id):
        self.id: str = id
        self.reviews: List[TranslatedTerm] = []

    def assign_reviews(self, trans: List[TranslatedTerm]):
        self.reviews.extend(trans)

    def get_num_assigned(self) -> int:
        return len(self.reviews)

class ReviewAssignments:
    def __init__(self, id: str, name: str, term_id: str, term: str):
        self.id: str = id
        self.name: str = name
        self.term_id: str = term_id
        self.term: str = term
        self.reviews: List[TranslatedTerm] = []

    def add_review(self, trans: TranslatedTerm) -> bool:
        if trans.term_id != self.term_id and trans.term_id not in ( r.term_id for r in self.reviews ):
            self.reviews.append(trans)
            return True
        return False

    def add_extra_review(self, trans: TranslatedTerm) -> bool:
        """ Adds a term to be reviewed. This version of the method allows addition of reviews 
        when the same term has been previously added """
        if trans.term_id != self.term_id and trans not in self.reviews:
            self.reviews.append(trans)
            return True
        return False

    def get_num_assigned(self) -> int:
        return len(self.reviews)

class Vote:
    def __init__(self, vai: str, v_id, t_id, term_id, term, transterm, transdescription):
        self.vote_assign_id: str = vai
        self.v_id: str = v_id
        self.t_id: str = t_id
        self.term_id: str = term_id
        self.term: str = term
        self.transterm: str = transterm
        self.transdescription: str = transdescription
        self.vote_score: int = -1
        self.completed: bool = False

    def set_vote_score(self, score: int):
        if type(score) != int:
            score = int(score)
        self.vote_score = score
        self.completed = True
    def toJSON(self):
        return {
            "vote_assign_id": self.vote_assign_id,
            "v_id": self.v_id,
            "t_id": self.t_id,
            "term": self.term,
            "transterm": self.transterm,
            "transdescription": self.transdescription,
            "vote_score": self.vote_score,
            "completed": self.completed
        }
    def __str__(self):
        return f"{self.vote_assign_id} {self.t_id} {self.transterm} {self.vote_score}"


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
    return "Unknown"
