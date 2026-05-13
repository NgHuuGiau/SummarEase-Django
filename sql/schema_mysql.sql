CREATE DATABASE IF NOT EXISTS summarease_django_rebuild CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE summarease_django_rebuild;

CREATE TABLE auth_user (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    password VARCHAR(128) NOT NULL,
    last_login DATETIME NULL,
    is_superuser TINYINT(1) NOT NULL DEFAULT 0,
    username VARCHAR(150) NOT NULL UNIQUE,
    first_name VARCHAR(150) NOT NULL DEFAULT '',
    last_name VARCHAR(150) NOT NULL DEFAULT '',
    email VARCHAR(254) NOT NULL DEFAULT '',
    is_staff TINYINT(1) NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    date_joined DATETIME NOT NULL
);

CREATE TABLE summaries_userprofile (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE
);

CREATE TABLE summaries_usersetting (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    default_summary_ratio DOUBLE NOT NULL DEFAULT 0.2,
    language_preference VARCHAR(20) NOT NULL DEFAULT 'auto',
    CONSTRAINT fk_setting_user FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE
);

CREATE TABLE summaries_document (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    source_name VARCHAR(255) NOT NULL DEFAULT '',
    uploaded_file VARCHAR(255) NOT NULL DEFAULT '',
    content LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_document_user FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE
);

CREATE TABLE summaries_tag (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE summaries_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    document_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    method VARCHAR(20) NOT NULL DEFAULT 'textrank',
    language VARCHAR(20) NOT NULL DEFAULT 'english',
    ratio DOUBLE NOT NULL DEFAULT 0.2,
    summary_text LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_summary_document FOREIGN KEY (document_id) REFERENCES summaries_document(id) ON DELETE CASCADE,
    CONSTRAINT fk_summary_user FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE
);

CREATE TABLE summaries_summary_tags (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    summary_id BIGINT NOT NULL,
    tag_id BIGINT NOT NULL,
    UNIQUE KEY uq_summary_tag (summary_id, tag_id),
    CONSTRAINT fk_summarytags_summary FOREIGN KEY (summary_id) REFERENCES summaries_summary(id) ON DELETE CASCADE,
    CONSTRAINT fk_summarytags_tag FOREIGN KEY (tag_id) REFERENCES summaries_tag(id) ON DELETE CASCADE
);

CREATE TABLE summaries_summarysentence (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    summary_id BIGINT NOT NULL,
    sentence_text TEXT NOT NULL,
    sentence_index INT NOT NULL DEFAULT 0,
    is_highlighted TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT fk_sentence_summary FOREIGN KEY (summary_id) REFERENCES summaries_summary(id) ON DELETE CASCADE
);

CREATE TABLE summaries_evaluation (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    summary_id BIGINT NOT NULL,
    evaluator_type VARCHAR(10) NOT NULL DEFAULT 'human',
    clarity_score SMALLINT NULL,
    coverage_score SMALLINT NULL,
    fluency_score SMALLINT NULL,
    comments TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_evaluation_summary FOREIGN KEY (summary_id) REFERENCES summaries_summary(id) ON DELETE CASCADE
);
