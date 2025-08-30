CREATE TABLE [question_packs] (
    [id] NVARCHAR(64) PRIMARY KEY,
    [name] NVARCHAR(64) NOT NULL,
    [public] INTEGER NOT NULL,
    [created_by] NVARCHAR(32) NOT NULL,
    [created_at] INTEGER NOT NULL,
    [changed_at] INTEGER NOT NULL
);

CREATE TABLE [question_categories] (
    [id] NVARCHAR(64) PRIMARY KEY,
    [pack_id] NVARCHAR(64) NOT NULL,
    [name] NVARCHAR(64) NOT NULL,
    [order] INTEGER NOT NULL
);

CREATE TABLE [question_tiers] (
    [id] NVARCHAR(64) PRIMARY KEY,
    [category_id] NVARCHAR(64) NOT NULL,
    [value] INTEGER NOT NULL
);

CREATE TABLE [questions] (
    [id] NVARCHAR(64) PRIMARY KEY,
    [tier_id] NVARCHAR(64) NOT NULL,
    [round] INTEGER NOT NULL,
    [question] NVARCHAR(128) NOT NULL,
    [answer] NVARCHAR(128) NOT NULL,
    [extra] JSON NULL
);

CREATE TABLE [games] (
    [id] NVARCHAR(64) PRIMARY KEY,
    [pack_id] NVARCHAR(64) NOT NULL,
    [title] NVARCHAR(64) NOT NULL,
    [regular_rounds] INTEGER NOT NULL,
    [created_by] NVARCHAR(32) NOT NULL,
    [started_at] INTEGER NOT NULL,
    [ended_at] INTEGER NULL,
    [max_contestants] INTEGER NOT NULL,
    [round] INTEGER DEFAULT(0),
    [question] INTEGER DEFAULT(0),
    [category] NVARCHAR(128) NULL,
    [tier] INTEGER NULL,
    [use_powerups] INTEGER DEFAULT(1),
    [state] NVARCHAR(32) DEFAULT('lobby')
);

CREATE TABLE [contestants] (
    [id] NVARCHAR(64) PRIMARY KEY,
    [game_id] NVARCHAR(64) NOT NULL,
    [name] NVARCHAR(32) NOT NULL,
    [avatar] NVARCHAR(128) NULL,
    [bg_image] NVARCHAR(128) NULL,
    [color] NVARCHAR(32) NOT NULL,
    [score] INTEGER DEFAULT(0),
    [buzzes] INTEGER DEFAULT(0),
    [hits] INTEGER DEFAULT(0),
    [misses] INTEGER DEFAULT(0),
    [finale_wager] INTEGER NULL,
    [finale_answer] NVARCHAR(128) NULL
);

CREATE TABLE [game_questions] (
    [pack_id] NVARCHAR(64) NOT NULL,
    [game_id] NVARCHAR(64) NOT NULL,
    [category] NVARCHAR(128) NOT NULL,
    [tier] INTEGER NOT NULL,
    [round] INTEGER NOT NULL,
    [used] INTEGER DEFAULT(0),
    PRIMARY KEY (pack_id, category, tier, round)
);

CREATE TABLE [power_ups] (
    [id] NVARCHAR(64) PRIMARY KEY,
    [contestant_id] NVARCHAR(64) NOT NULL,
    [name] NVARCHAR(64) NOT NULL,
    [enabled] INTEGER DEFAULT(0),
    [used] INTEGER DEFAULT(0)
);