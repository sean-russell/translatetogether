# pytrans

# Database Tables
1. courses(<ins>iss, course_id</ins>)
2. sections(<ins>*iss*,*course*, section_number</ins>, status)
3. terms(<ins>id</ins>, term, *iss*, *section*, *course* )

4. participants(<ins>vle_user_id, *iss*, *course*</ins>, email, fullname, role)
5. assistants(<ins>id</ins>, email, *iss*, *course*)

6. actions(<ins>id</ins>, *vle_user_id*, email, vle_username, *iss*, *course*, role, action_completed, action_time)

7. trans_assignments(<ins>id</ins>, *vle_user_id*, term, *iss*, *course*, *section* )
8. translations(<ins>id</ins>, *vle_user_id*, *trans_ass_id*, term, transterm, transdescription, *iss*, *course*, *section*)

9. review_assignments(<ins>id</ins>, *reviewer_id*, *translator_id*, term, transterm, transdescription, *iss*, *course*, *section* )
10. reviews(<ins>id</ins>, *rev_ass_id*, *reviewer_id*, *translator_id*, term, transterm, transdescription, review_score, review_comment, *iss*, *course*, *section* )

11. vote_assignments(<ins>id</ins>, *voter_id*, *translator_id*, term, transterm, transdescription, *iss*, *course*, *section* )
12. votes(<ins>id</ins>, *vote_ass_id*, *voter_id*, *translator_id*, term, transterm, transdescription, vote_score, *iss*, *course*, *section*)


# Tasks

## Section Management

- [X] Add section config for number of terms and number of reviews
- [X] Add check before finalise that number of terms is correct
- [X] Add check on term input that it is not an empty string
- [] Add start and end dates for phases
- [] Include check box for making vote phase optional
- [] Fix the broken review assignment algorithm
- [X] Add ability to input multiple terms ar the same time
- [] Add vote assignment algorithm
## Course Management

- [X] Add valid email address check for ta entry
- [] Add 


# Student Side

- [] View list of assigned translations
- [] Select individual translation for completion
- [] Review translation
- [] Show completed translations in list
- [] View list of terms to be voted on
- [] Select individual term for voting on the translation
- [] Input votes for the individual terms


# Teaching Assistant Side

- [] View list of assigned translations
- [] Select individual translation for completion
- [] Review translation
- [] Show completed translations in list