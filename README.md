# Student Database System with AI Insights 🎓📊

A modern web application built with **Flask**, **SQLite**, and **Pandas** that serves as a student database management system. It features interactive AI-driven insights, search bot utilities, and automated PDF report generation.

---

## 🚀 Features

- **Secure Authentication**: Built-in user login, session management, and secure password hashing.
- **Student Profiles**: Full CRUD (Create, Read, Update, Delete) capability for student details, including parent details, hobbies, and additional context.
- **Search & Sort**: Advanced search by ID, name, or department with sorting and paginated views.
- **AI Insights & Analytics**: Real-time analytical graphs/metrics showing enrollment patterns and department breakdowns powered by `pandas`.
- **Intelligent Query Bot**: Ask questions like *"how many students"* or *"show students in CSE"* to retrieve real-time statistics.
- **PDF Report Generation**: Export official student report cards and details to PDF with one click.

---

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **Database**: SQLite3 (automatically initialized)
- **Data Analysis**: Pandas, NumPy
- **PDF Generation**: FPDF2
- **Frontend**: HTML5, Vanilla CSS3 (responsive design), JavaScript

---

## 🔑 Default Login Credentials

Upon running the application for the first time, a default administrator account is automatically created in the database:

* **Username**: `admin`
* **Password**: `admin123`

---

## 🖥️ Setup & Installation Instructions

Choose the appropriate setup instructions for your operating system.

### 🍎 macOS & Linux Setup

1. **Open Terminal** and navigate to the project directory:
   ```bash
   cd student_database_system
   ```

2. **Create a Python Virtual Environment**:
   ```bash
   python3 -m venv .venv
   ```

3. **Activate the Virtual Environment**:
   ```bash
   source .venv/bin/activate
   ```

4. **Upgrade pip & Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Run the Application**:
   ```bash
   python app.py
   ```
   *The server will start running on `http://127.0.0.1:5000/`.*

---

### 🪟 Windows Setup

1. **Open Command Prompt (cmd) or PowerShell** and navigate to the project directory:
   ```cmd
   cd student_database_system
   ```

2. **Create a Python Virtual Environment**:
   ```cmd
   python -m venv .venv
   ```

3. **Activate the Virtual Environment**:
   * **Command Prompt (cmd)**:
     ```cmd
     .venv\Scripts\activate.bat
     ```
   * **PowerShell**:
     ```powershell
     .venv\Scripts\Activate.ps1
     ```

4. **Upgrade pip & Install Dependencies**:
   ```cmd
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Run the Application**:
   ```cmd
   python app.py
   ```
   *The server will start running on `http://127.0.0.1:5000/`.*

---

## 📂 Project Structure

```text
student_database_system/
├── app.py                  # Main Flask application entry point
├── database.db             # SQLite database file (created automatically)
├── requirements.txt        # Project dependencies
├── README.md               # Setup and usage guide
├── static/                 # Static CSS, JS, and image assets
└── templates/              # HTML layout templates
```

---

## 📝 Note on Database Updates
The database updates automatically on start to run migrations for new columns (e.g., parent contact details, hobbies, and additional notes).
