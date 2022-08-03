CREATE USER IF NOT EXISTS 'transapp'@'%' IDENTIFIED BY '8HT6c8U74GcMQWnBj9GaZmaRahAu49';
Grant All Privileges ON *.* to 'transapp'@'%' Identified By '8HT6c8U74GcMQWnBj9GaZmaRahAu49'; 
FLUSH PRIVILEGES;

CREATE DATABASE IF NOT EXISTS translation;
use translation;

CREATE TABLE IF NOT EXISTS `courses` (
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `owner_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  PRIMARY KEY (`iss`,`course_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `sections` (
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `section_number` INTEGER NOT NULL,
  `status` INTEGER NOT NULL DEFAULT 0,
  `num_terms` INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (`iss`,`course`, `section_number`),
  CONSTRAINT fk_mrt_ot FOREIGN KEY (`iss`,`course`) REFERENCES `courses`(`iss`,`course_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `terms` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `term` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `section` INTEGER NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT fk_mrt_ot2 FOREIGN KEY (`iss`,`course`, `section`) REFERENCES `sections`(`iss`,`course`, `section_number`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `participants` (
  `vle_user_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `email` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `fullname` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `role` varchar(255) CHARACTER SET utf8mb4 NOT NULL,	/* learner, instructor, admin*/
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  PRIMARY KEY (`vle_user_id`, `iss`, `course`),
  CONSTRAINT fk_mrt_ot3 FOREIGN KEY (`iss`,`course`) REFERENCES `courses`(`iss`,`course_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `assistants` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `email` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE(`email`, `iss`, `course`),
  CONSTRAINT fk_mrt_ot4 FOREIGN KEY (`iss`,`course`) REFERENCES `courses`(`iss`,`course_id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `actions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `vle_user_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `email` varchar(255) NOT NULL,
  `vle_username` varchar(255) NOT NULL,
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `role` varchar(255) NOT NULL,
  `action_completed` varchar(255) CHARACTER SET latin1 DEFAULT NULL,
  `action_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT fk_mrt_ot5 FOREIGN KEY (`iss`,`course`) REFERENCES `courses`(`iss`,`course_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (`vle_user_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `trans_assignments` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `vle_user_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `term` varchar(255) NOT NULL,
  `status` INTEGER NOT NULL DEFAULT 0,
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `section` INTEGER NOT NULL,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`vle_user_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_mrt_ot6 FOREIGN KEY (`iss`,`course`, `section`) REFERENCES `sections`(`iss`,`course`, `section_number`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `translations` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `trans_ass_id` bigint(20) NOT NULL,
  `vle_user_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `term` varchar(255) NOT NULL, /*duplication of term in terms table*/
  `transterm` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `transdescription` varchar(2048) CHARACTER SET utf8mb4 DEFAULT NULL,
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `section` INTEGER NOT NULL,
  `submit_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`trans_ass_id`) REFERENCES `trans_assignments`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (`vle_user_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_mrt_ot7 FOREIGN KEY (`iss`,`course`, `section`) REFERENCES `sections`(`iss`,`course`, `section_number`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;


CREATE TABLE IF NOT EXISTS `review_assignments` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reviewer_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `translator_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `term` varchar(255) NOT NULL, /*duplication of term in terms table*/
  `transterm` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,/*duplication of transterm in translations table*/
  `transdescription` varchar(2048) CHARACTER SET utf8mb4 DEFAULT NULL, /*duplication of transdescription in translations table*/
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `section` INTEGER NOT NULL,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`reviewer_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (`translator_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_mrt_ot8 FOREIGN KEY (`iss`,`course`, `section`) REFERENCES `sections`(`iss`,`course`, `section_number`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;


CREATE TABLE IF NOT EXISTS `reviews` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `rev_ass_id` bigint(20) NOT NULL,
  `reviewer_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `translator_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `term` varchar(255) NOT NULL, /*duplication of term in terms table*/
  `transterm` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL, /*duplication of transterm in translations table*/
  `transdescription` varchar(2048) CHARACTER SET utf8mb4 DEFAULT NULL, /*duplication of transdescription in translations table*/
  `review_score` INTEGER NOT NULL,
  `review_comment` varchar(2048) CHARACTER SET utf8mb4 DEFAULT NULL,
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `section` INTEGER NOT NULL,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`reviewer_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (`translator_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (`rev_ass_id`) REFERENCES `review_assignments`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_mrt_ot9 FOREIGN KEY (`iss`,`course`, `section`) REFERENCES `sections`(`iss`,`course`, `section_number`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `vote_assignments` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `voter_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `translator_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `term` varchar(255) NOT NULL, /*duplication of term in terms table*/
  `transterm` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,/*duplication of transterm in translations table*/
  `transdescription` varchar(2048) CHARACTER SET utf8mb4 DEFAULT NULL, /*duplication of transdescription in translations table*/
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `section` INTEGER NOT NULL,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`voter_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (`translator_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_mrt_ot10 FOREIGN KEY (`iss`,`course`, `section`) REFERENCES `sections`(`iss`,`course`, `section_number`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;


CREATE TABLE IF NOT EXISTS `votes` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `vote_ass_id` bigint(20) NOT NULL,
  `voter_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `translator_id` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `term` varchar(255) NOT NULL, /*duplication of term in terms table*/
  `transterm` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL, /*duplication of transterm in translations table*/
  `transdescription` varchar(2048) CHARACTER SET utf8mb4 DEFAULT NULL, /*duplication of transdescription in translations table*/
  `vote_score` INTEGER NOT NULL,
  `iss` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `course` varchar(255) CHARACTER SET utf8mb4 NOT NULL,
  `section` INTEGER NOT NULL,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`voter_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (`translator_id`) REFERENCES `participants`(`vle_user_id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (`vote_ass_id`) REFERENCES `vote_assignments`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_mrt_ot11 FOREIGN KEY (`iss`,`course`, `section`) REFERENCES `sections`(`iss`,`course`, `section_number`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;


