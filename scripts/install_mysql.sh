#!/usr/bin/env bash
set -euo pipefail

cat <<'INSTRUCTIONS'
HubClock local MySQL setup
==========================
Install and secure MySQL on macOS (Homebrew) or Ubuntu (APT). Run the commands that match your VM.

macOS (Homebrew)
----------------
# Install server
brew install mysql
# Launch immediately and on login
brew services start mysql
# Set the root password (replace 'safeRootPass')
mysqladmin -u root password 'safeRootPass'

Ubuntu / Debian
---------------
sudo apt update
sudo apt install -y mysql-server
sudo systemctl enable --now mysql
sudo mysql_secure_installation

Create application database
---------------------------
mysql -u root -p <<'SQL'
CREATE DATABASE hubclock CHARACTER SET utf8mb4;
CREATE USER 'hubclock'@'localhost' IDENTIFIED BY 'hubclock';
GRANT ALL PRIVILEGES ON hubclock.* TO 'hubclock'@'localhost';
FLUSH PRIVILEGES;
SQL

Update backend/.env with the credentials you picked. Keep production secrets outside source control.
INSTRUCTIONS
