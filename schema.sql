-- Drop tables if they exist to ensure a clean slate
DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS session;
DROP TABLE IF EXISTS word;
DROP TABLE IF EXISTS quiz;

-- User table to store login credentials
CREATE TABLE user (
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE NOT NULL,
password TEXT NOT NULL
);

-- Session table to track each learning session
CREATE TABLE session (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER NOT NULL,
mode TEXT NOT NULL, -- beginner, intermediate, proficient
score_percent INTEGER NOT NULL,
date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (user_id) REFERENCES user (id)
);

-- Word table to store the words for each session
CREATE TABLE word (
id INTEGER PRIMARY KEY AUTOINCREMENT,
session_id INTEGER NOT NULL,
letter TEXT NOT NULL,
word_text TEXT NOT NULL,
meaning TEXT NOT NULL,
example TEXT,
FOREIGN KEY (session_id) REFERENCES session (id)
);

-- Quiz table to store the quiz details for each session
CREATE TABLE quiz (
id INTEGER PRIMARY KEY AUTOINCREMENT,
session_id INTEGER NOT NULL,
quiz_data TEXT NOT NULL, -- Storing the quiz structure as a JSON string
FOREIGN KEY (session_id) REFERENCES session (id)
);