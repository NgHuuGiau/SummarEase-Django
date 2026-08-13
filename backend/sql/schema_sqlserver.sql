-- SQL Server
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'SummarEase_Django')
    CREATE DATABASE [SummarEase_Django];
GO
USE [SummarEase_Django];
GO

IF OBJECT_ID(N'[dbo].[summaries_summarysentence]', N'U') IS NOT NULL DROP TABLE [summaries_summarysentence];
GO
IF OBJECT_ID(N'[dbo].[summaries_summary_tags]', N'U') IS NOT NULL DROP TABLE [summaries_summary_tags];
GO
IF OBJECT_ID(N'[dbo].[summaries_summary]', N'U') IS NOT NULL DROP TABLE [summaries_summary];
GO
IF OBJECT_ID(N'[dbo].[summaries_tag]', N'U') IS NOT NULL DROP TABLE [summaries_tag];
GO
IF OBJECT_ID(N'[dbo].[summaries_document]', N'U') IS NOT NULL DROP TABLE [summaries_document];
GO
IF OBJECT_ID(N'[dbo].[summaries_usersetting]', N'U') IS NOT NULL DROP TABLE [summaries_usersetting];
GO
IF OBJECT_ID(N'[dbo].[summaries_userprofile]', N'U') IS NOT NULL DROP TABLE [summaries_userprofile];
GO
IF OBJECT_ID(N'[dbo].[auth_user]', N'U') IS NOT NULL DROP TABLE [auth_user];
GO

CREATE TABLE [auth_user] (
    [id] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [password] NVARCHAR(128) NOT NULL,
    [last_login] DATETIME2 NULL,
    [is_superuser] BIT NOT NULL DEFAULT 0,
    [username] NVARCHAR(150) NOT NULL UNIQUE,
    [first_name] NVARCHAR(150) NOT NULL DEFAULT '',
    [last_name] NVARCHAR(150) NOT NULL DEFAULT '',
    [email] NVARCHAR(254) NOT NULL DEFAULT '',
    [is_staff] BIT NOT NULL DEFAULT 0,
    [is_active] BIT NOT NULL DEFAULT 1,
    [date_joined] DATETIME2 NOT NULL
);
GO

CREATE TABLE [summaries_userprofile] (
    [id] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [user_id] BIGINT NOT NULL UNIQUE,
    [role] NVARCHAR(20) NOT NULL DEFAULT 'user',
    CONSTRAINT [fk_profile_user] FOREIGN KEY ([user_id]) REFERENCES [auth_user]([id]) ON DELETE CASCADE
);
GO

CREATE TABLE [summaries_usersetting] (
    [id] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [user_id] BIGINT NOT NULL UNIQUE,
    [default_summary_ratio] FLOAT NOT NULL DEFAULT 0.2,
    [language_preference] NVARCHAR(20) NOT NULL DEFAULT 'auto',
    [gemini_api_key] NVARCHAR(255) NOT NULL DEFAULT '',
    CONSTRAINT [fk_setting_user] FOREIGN KEY ([user_id]) REFERENCES [auth_user]([id]) ON DELETE CASCADE
);
GO

CREATE TABLE [summaries_document] (
    [id] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [user_id] BIGINT NOT NULL,
    [source_type] NVARCHAR(20) NOT NULL,
    [title] NVARCHAR(255) NOT NULL,
    [source_name] NVARCHAR(255) NOT NULL DEFAULT '',
    [uploaded_file] NVARCHAR(500) NOT NULL DEFAULT '',
    [content] NVARCHAR(MAX) NOT NULL,
    [created_at] DATETIME2 NOT NULL,
    CONSTRAINT [fk_document_user] FOREIGN KEY ([user_id]) REFERENCES [auth_user]([id]) ON DELETE CASCADE
);
GO

CREATE TABLE [summaries_tag] (
    [id] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [name] NVARCHAR(100) NOT NULL UNIQUE
);
GO

CREATE TABLE [summaries_summary] (
    [id] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [document_id] BIGINT NOT NULL,
    [user_id] BIGINT NOT NULL,
    [title] NVARCHAR(255) NOT NULL,
    [method] NVARCHAR(20) NOT NULL DEFAULT 'textrank',
    [language] NVARCHAR(20) NOT NULL DEFAULT 'english',
    [ratio] FLOAT NOT NULL DEFAULT 0.2,
    [summary_text] NVARCHAR(MAX) NOT NULL,
    [created_at] DATETIME2 NOT NULL,
    CONSTRAINT [fk_summary_document] FOREIGN KEY ([document_id]) REFERENCES [summaries_document]([id]) ON DELETE CASCADE,
    CONSTRAINT [fk_summary_user] FOREIGN KEY ([user_id]) REFERENCES [auth_user]([id]) ON DELETE CASCADE
);
GO

CREATE TABLE [summaries_summary_tags] (
    [id] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [summary_id] BIGINT NOT NULL,
    [tag_id] BIGINT NOT NULL,
    CONSTRAINT [uq_summary_tag] UNIQUE ([summary_id], [tag_id]),
    CONSTRAINT [fk_summarytags_summary] FOREIGN KEY ([summary_id]) REFERENCES [summaries_summary]([id]) ON DELETE CASCADE,
    CONSTRAINT [fk_summarytags_tag] FOREIGN KEY ([tag_id]) REFERENCES [summaries_tag]([id]) ON DELETE CASCADE
);
GO

CREATE TABLE [summaries_summarysentence] (
    [id] BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [summary_id] BIGINT NOT NULL,
    [sentence_text] NVARCHAR(MAX) NOT NULL,
    [sentence_index] INT NOT NULL DEFAULT 0,
    CONSTRAINT [fk_sentence_summary] FOREIGN KEY ([summary_id]) REFERENCES [summaries_summary]([id]) ON DELETE CASCADE
);
GO

-- Indexes
CREATE NONCLUSTERED INDEX [idx_document_user] ON [summaries_document]([user_id]);
GO
CREATE NONCLUSTERED INDEX [idx_document_source_type] ON [summaries_document]([source_type]);
GO
CREATE NONCLUSTERED INDEX [idx_summary_user] ON [summaries_summary]([user_id]);
GO
CREATE NONCLUSTERED INDEX [idx_summary_document] ON [summaries_summary]([document_id]);
GO
CREATE NONCLUSTERED INDEX [idx_sentence_summary] ON [summaries_summarysentence]([summary_id]);
GO
