# 🎮 CoDM Attachments Bot

Advanced Telegram Bot for managing and sharing Call of Duty: Mobile loadouts. Built with Python and PostgreSQL.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-316192.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ Key Features

- **Smart Search**: Fuzzy & Full-Text search for attachments.
- **Inline Mode**: Search and share loadouts directly in any chat.
- **Game Modes**: Support for both Battle Royale (BR) and Multiplayer (MP).
- **Admin Panel**: Comprehensive dashboard, user submission review, and broadcast system.
- **RBAC**: Role-Based Access Control for administrators.
- **Analytics**: Deep insights into search trends and user activity.
- **Automated Backups**: Scheduled database and configuration backups.

## 🚀 Quick Deployment (Linux)

To install on a Linux server (Ubuntu/Debian recommended):

```bash
git clone https://github.com/MasterALiReza/Call-Of-Duty-Attachments.git
cd Call-Of-Duty-Attachments
sudo bash deploy.sh
```

The `deploy.sh` script handles:
- System dependency installation (Python, PostgreSQL).
- Database & User creation.
- Virtual environment setup.
- Systemd service configuration.

## 🛠️ Management

After installation, use the management tool:
```bash
wx-attach
```

## 📖 Documentation
Detailed documentation for specific modules can be found in the `/docs` directory.

## 🤝 Contributing
Contributions are welcome! Please read the contribution guidelines before submitting a PR.

## 📜 License
This project is licensed under the MIT License - see the `LICENSE` file for details.

