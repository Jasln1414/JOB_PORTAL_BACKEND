# 💼 JOB_PORTAL_BACKEND

Welcome to the **backend of SARAM – a modern Job Portal** built with Django and Django REST Framework.

This project powers a complete job platform that connects **employers** and **candidates** with real-time communication, secure payments, and smart interview scheduling.

---

## 🚀 Features

### 👥 Authentication
- Employer & Candidate Signup/Login with token-based authentication

### 📝 Job Management
- Employers can post jobs (based on subscription)
- Candidates can browse & apply to job listings

### 💬 Real-Time Chat
- Built with **Django Channels** & WebSockets
- Instant messaging between employers and candidates

### 📅 Interview Scheduling
- Employers can schedule interviews
- Candidates receive **email notifications** and **real-time alerts**
- Automated updates on interview status using background tasks

### 💳 Subscription System
- Employers purchase plans via **Razorpay**
- Job post limits based on the active plan
- Background checks for plan expiry using **Celery**

---

## ⚙️ Tech Stack

- **Backend:** Django, Django REST Framework
- **Database:** PostgreSQL
- **Real-time:** Django Channels + Redis
- **Payments:** Razorpay Integration
- **Background Tasks:** Celery + Redis
- **Auth:** JWT Token Authentication

---

## 📂 Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/Jasln1414/JOB_PORTAL_BACKEND.git
   cd JOB_PORTAL_BACKEND
