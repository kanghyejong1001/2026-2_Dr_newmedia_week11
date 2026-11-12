CREATE TABLE user_table (
            id_num INTEGER PRIMARY KEY AUTOINCREMENT,
            userid TEXT NOT NULL UNIQUE COLLATE NOCASE,
            username TEXT NOT NULL, password TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE "survey_table" (
	"id_num"	INTEGER NOT NULL,
	"user_id"	TEXT,
	"q1"	INTEGER,
	"q2"	INTEGER,
	"q3"	INTEGER,
	"q4"	INTEGER,
	"q5"	INTEGER,
	"q6"	INTEGER,
	"q7"	INTEGER,
	"q8"	INTEGER,
	"q9"	INTEGER,
	"q10"	INTEGER,
	"created_at"	TEXT,
	PRIMARY KEY("id_num" AUTOINCREMENT)
);
