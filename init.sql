CREATE USER IF NOT EXISTS 'transapp'@'%' IDENTIFIED BY '8HT6c8U74GcMQWnBj9GaZmaRahAu49';
Grant All Privileges ON *.* to 'transapp'@'%' Identified By '8HT6c8U74GcMQWnBj9GaZmaRahAu49'; 
FLUSH PRIVILEGES;

DROP DATABASE IF EXISTS translation;
CREATE DATABASE translation;
use translation;

CREATE TABLE IF NOT EXISTS `status` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `course_id` varchar(255) NOT NULL,
  `termgroup` INTEGER NOT NULL,
  `ready` BOOLEAN,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `terms` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `term` varchar(255) NOT NULL,
  `termgroup` INTEGER NOT NULL,
  `course_id` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

INSERT INTO `terms` (`id`, `term`, `termgroup`, `course_id`) VALUES
(1, 'term1', 1, 'COMP1001J'),
(2, 'term2', 1, 'COMP1001J'),
(3, 'term3', 1, 'COMP1001J'),
(4, 'term4', 1, 'COMP1001J'),
(5, 'term5', 1, 'COMP1001J'),
(6, 'term6', 1, 'COMP1001J'),
(7, 'term7', 1, 'COMP1001J'),
(8, 'term8', 1, 'COMP1001J');

INSERT INTO `status` (`id`, `course_id`, `termgroup`, `ready`) VALUES (1, 'COMP1001J', 1, true);

CREATE TABLE IF NOT EXISTS `actions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `vle_user_id` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `vle_username` varchar(255) NOT NULL,
  `course_id` varchar(255) NOT NULL,
  `actioncompleted` varchar(255) CHARACTER SET latin1 DEFAULT NULL,
  `time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;



CREATE TABLE IF NOT EXISTS `translations` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `vle_id` varchar(255) NOT NULL,
  `term` varchar(255) NOT NULL,
  `transterm` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `transdescription` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `course_id` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `reviews` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `reviewer_id` varchar(255) NOT NULL,
  `translator_id` varchar(255) NOT NULL,
  `transterm` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `transdescription` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `review_score` INTEGER NOT NULL,
  `review_comment` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `course_id` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS `votes` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `voter_id` varchar(255) NOT NULL,
  `translator_id` varchar(255) NOT NULL,
  `transterm` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `transdescription` varchar(255) CHARACTER SET utf8mb4 DEFAULT NULL,
  `vote_score` INTEGER NOT NULL,
  `course_id` varchar(255) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

