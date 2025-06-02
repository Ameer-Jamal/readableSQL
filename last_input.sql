-- DEMO FILE
SET @MaxUsers=100;SET @Greeting:='Hello, world!';
CREATE TABLE "users"(id INT PRIMARY KEY,name VARCHAR(50) NOT NULL,email VARCHAR(100) UNIQUE,metadata JSON,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,is_active BOOLEAN DEFAULT TRUE);
CREATE TABLE logs(log_id INT PRIMARY KEY AUTO_INCREMENT,user_id INT,action VARCHAR(20),detail TEXT,timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES "users"(id));
INSERT INTO "users"(id,name,email,metadata)VALUES(101,'John Doe','john@example.com','{"role":"admin","lastLogin":"2023-11-01T14:30:00"}'),(102,'Jane, Smith','jane@example.com',JSON_OBJECT('role','editor','preferences',JSON_OBJECT('darkMode',TRUE,'notifications',FALSE)));
INSERT INTO logs(user_id,action,detail)VALUES(101,'login',CONCAT('User ','John Doe',' logged in.')),(102,'signup','New user created.');
INSERT INTO logs(user_id,action,detail) SELECT id,'auto-login',CONCAT('Auto-logged in at ',CURRENT_TIMESTAMP) FROM "users" WHERE is_active=TRUE;
UPDATE "users" SET metadata='{"role":"editor","preferences":{"darkMode":true,"notifications":false}}' WHERE id=101;
UPDATE "users" SET metadata=JSON_SET(metadata,'$.lastLogin',DATE_FORMAT(NOW(),'%Y-%m-%dT%H:%i:%s')) WHERE id=102;
UPDATE "users"

-- JSON PRETTY-PRINT DEMO
SET metadata='{"settings":{"theme":"dark","layout":{"panels":["left","right"],"sizes":[20,80]},"features":{"beta":true,"notifications":["email","sms"],"security":{"twoFactor":false,"questions":["pet","city"]}}},"profile":{"displayName":"AmeerJ","tags":["developer","sql","pyqt5"],"preferences":{"fontSize":14,"showLineNumbers":true}}}'
WHERE id=102;

ALTER TABLE "users" ADD COLUMN phone VARCHAR(15);
ALTER TABLE logs ADD COLUMN ip_address VARCHAR(45);
ALTER TABLE logs DROP COLUMN detail;
DELETE FROM "users" WHERE is_active=FALSE AND created_at<'2023-01-01';
DELETE FROM logs WHERE timestamp<DATE_SUB(NOW(),INTERVAL 30 DAY);
DROP INDEX IF EXISTS idx_users_email ON "users";
DROP        TABLE IF EXISTS temp_data;
SELECT id,name,CASE WHEN is_active=TRUE THEN 'active' WHEN is_active=FALSE THEN 'inactive' ELSE 'unknown' END AS status,CASE WHEN JSON_EXTRACT(metadata,'$.role')='"admin"' THEN 'Administrator' WHEN JSON_EXTRACT(metadata,'$.role')='"editor"' THEN 'Editor' ELSE 'User' END AS role_name FROM "users" WHERE id IN (101,102);
SELECT CONCAT(name,' <',email,'>') AS "user_info",LENGTH(COALESCE(name,'')) AS name_length FROM "users" WHERE name LIKE 'J%';
-- Random comment here
