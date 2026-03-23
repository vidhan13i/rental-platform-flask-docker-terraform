-- Creates a separate database for each microservice
-- This runs automatically when the postgres container first starts

CREATE DATABASE users_db;
CREATE DATABASE listings_db;
CREATE DATABASE bookings_db;
CREATE DATABASE payments_db;
CREATE DATABASE reviews_db;

GRANT ALL PRIVILEGES ON DATABASE users_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE listings_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE bookings_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE payments_db TO postgres;
GRANT ALL PRIVILEGES ON DATABASE reviews_db TO postgres;
