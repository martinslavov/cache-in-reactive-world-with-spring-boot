CREATE TABLE IF NOT EXISTS "user_t" (
    id SERIAL PRIMARY KEY,
    username VARCHAR (50) UNIQUE NOT NULL,
    password VARCHAR (50) NOT NULL,
    email VARCHAR (255) UNIQUE NOT NULL,
    created_on TIMESTAMP NOT NULL,
    last_login TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "subscription" (
    id SERIAL PRIMARY KEY,
    type VARCHAR ( 50 ) UNIQUE NOT NULL,
    active INT NOT NULL,
    user_id INT NOT NULL
);

-- INSERT INTO "user_t"(
--     username, password, email, created_on)
-- VALUES ('martin', 'password', 'slavoff.martin@gmail.com', now());
-- INSERT INTO public."user_t"(
--     username, password, email, created_on)
-- VALUES ('test1', 'password', 'test1.test1@gmail.com', now());
-- INSERT INTO public."user_t"(
--     username, password, email, created_on)
-- VALUES ('test2', 'password', 'test2.test2@gmail.com', now());