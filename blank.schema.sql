-- MySQL dump 10.16  Distrib 10.1.21-MariaDB, for Linux (x86_64)
--
-- Host: db.domain.tld    Database: myDB
-- ------------------------------------------------------
-- Server version	10.1.21-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `myTBL`
--

DROP TABLE IF EXISTS `myTBL`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `myTBL` (
  `episode` varchar(8) NOT NULL,
  `file_prefix` varchar(255) NOT NULL,
  `sha_mp3` char(64) NOT NULL,
  `sha_ogg` char(64) NOT NULL,
  `bytesize_mp3` int(16) NOT NULL,
  `bytesize_ogg` int(16) NOT NULL,
  `length` int(8) NOT NULL,
  `editor` varchar(64) NOT NULL,
  `intro_title` varchar(128) NOT NULL,
  `intro_artist` varchar(128) NOT NULL,
  `intro_link` varchar(256) NOT NULL,
  `intro_copyright` varchar(45) NOT NULL,
  `intro_copyrightlink` varchar(256) NOT NULL,
  `outro_title` varchar(128) NOT NULL,
  `outro_artist` varchar(128) NOT NULL,
  `outro_link` varchar(256) NOT NULL,
  `outro_copyright` varchar(45) NOT NULL,
  `outro_copyrightlink` varchar(256) NOT NULL,
  `recorded` datetime NOT NULL,
  `released` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `changed` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`episode`),
  UNIQUE KEY `episode_UNIQUE` (`episode`),
  UNIQUE KEY `file_prefix_UNIQUE` (`file_prefix`),
  UNIQUE KEY `sha_mp3_UNIQUE` (`sha_mp3`),
  UNIQUE KEY `sha_ogg_UNIQUE` (`sha_ogg`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2017-03-23 18:19:43
