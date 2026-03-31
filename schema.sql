-- Banking Management System - MySQL Schema
-- Run: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS banking_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE banking_db;

CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    full_name     VARCHAR(120) NOT NULL,
    email         VARCHAR(180) NOT NULL UNIQUE,
    phone         VARCHAR(20),
    password_hash VARCHAR(256) NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NOT NULL,
    account_type ENUM('checking', 'savings') NOT NULL,
    account_no   VARCHAR(20) NOT NULL UNIQUE,
    balance      DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transactions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    account_id      INT NOT NULL,
    type            ENUM('deposit','withdrawal','transfer_in','transfer_out') NOT NULL,
    amount          DECIMAL(15,2) NOT NULL,
    balance_after   DECIMAL(15,2) NOT NULL,
    description     VARCHAR(255),
    related_account INT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);
