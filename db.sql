-- phpMyAdmin SQL Dump
SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";

--
-- Database: `opensips`
--

-- --------------------------------------------------------

--
-- Table structure for table `phx_reg_mon`
--

CREATE TABLE IF NOT EXISTS `phx_reg_mon` (
  `id` bigint(20) NOT NULL auto_increment,
  `sip` varchar(128) collate utf8_unicode_ci NOT NULL,
  `ip_addr` varchar(24) collate utf8_unicode_ci NOT NULL COMMENT 'registered clients IP address',
  `port` int(11) NOT NULL COMMENT 'registered clients port',
  `expires` int(11) NOT NULL COMMENT 'registration expiration time',
  `cseq` int(11) NOT NULL COMMENT 'SIP packet counter',
  `reg_idx` int(11) NOT NULL,
  `sock_state` varchar(24) collate utf8_unicode_ci default NULL,
  `ka_timer` varchar(64) collate utf8_unicode_ci default NULL,
  `created_at` timestamp NOT NULL default CURRENT_TIMESTAMP,
  `num_registrations` int(11) NOT NULL COMMENT 'number of active registrations',
  PRIMARY KEY  (`id`),
  KEY `sip` (`sip`)
) ENGINE=MyISAM  DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci COMMENT='sip registration monitor' AUTO_INCREMENT=55 ;


