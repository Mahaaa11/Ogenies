-- L&C Emailing local MySQL schema (for phpMyAdmin / local dev)

CREATE TABLE IF NOT EXISTS prospects (
  id VARCHAR(32) PRIMARY KEY,
  first_name VARCHAR(128) NULL,
  last_name VARCHAR(128) NULL,
  email VARCHAR(320) NOT NULL,
  company VARCHAR(255) NULL,
  role VARCHAR(255) NULL,
  industry VARCHAR(255) NULL,
  provider VARCHAR(64) NULL DEFAULT 'SendGrid',
  status VARCHAR(32) NULL DEFAULT 'active',
  last_contacted_day INT NULL DEFAULT 999,
  UNIQUE KEY uq_prospects_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS email_events (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sg_event_id VARCHAR(128) NOT NULL,
  email VARCHAR(320) NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  ts BIGINT NOT NULL,
  payload_json JSON NOT NULL,
  prospect_id VARCHAR(32) NULL,
  campaign_step VARCHAR(64) NULL,
  day INT NULL DEFAULT 0,
  hour INT NULL DEFAULT 0,
  UNIQUE KEY uq_email_events_sg_event_id (sg_event_id),
  KEY idx_email_events_email_ts (email, ts),
  KEY idx_email_events_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

