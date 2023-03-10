INSERT INTO "user_t"(
	username, password, email, created_on)
VALUES ('martin', 'password', 'slavoff.martin@gmail.com', now());
INSERT INTO public."user_t"(
	username, password, email, created_on)
VALUES ('test1', 'password', 'test1.test1@gmail.com', now());
INSERT INTO public."user_t"(
    username, password, email, created_on)
VALUES ('test2', 'password', 'test2.test2@gmail.com', now());