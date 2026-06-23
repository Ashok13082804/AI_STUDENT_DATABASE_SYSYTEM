import sqlite3
import os
import pandas as pd
import numpy as np
import re
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from fpdf import FPDF
import ml_engine
import dsa_helpers

app = Flask(__name__)
app.secret_key = 'student_database_secret_key' # In production, use a strong random key
DATABASE = 'database.db'
UPLOAD_FOLDER = os.path.join(app.root_path, 'static/uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DEPARTMENTS = [
    'Artificial Intelligence and Machine Learning',
    'Computer Science and Engineering',
    'Cybersecurity',
    'Internet of Things',
    'Electrical Engineering',
    'Agricultural Engineering',
    'Biomedical Engineering',
    'Electronics and Communication Engineering',
    'Mechatronics',
    'Automobile Engineering',
    'Food Technology'
]

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # 1. Create users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student'
        )
    ''')
    
    # 2. Check/add role column to users
    cursor = conn.execute('PRAGMA table_info(users)')
    user_columns = [row['name'] for row in cursor.fetchall()]
    if 'role' not in user_columns:
        conn.execute('ALTER TABLE users ADD COLUMN role TEXT DEFAULT "student"')
        
    # 3. Create students table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            email TEXT NOT NULL,
            parent_name TEXT,
            parent_contact TEXT,
            address TEXT,
            additional_info TEXT,
            hobbies TEXT,
            parent_occupation TEXT,
            cgpa REAL DEFAULT 0.0,
            semester TEXT DEFAULT 'Semester 1',
            income REAL DEFAULT 0.0,
            category TEXT DEFAULT 'General',
            profile_photo TEXT,
            documents TEXT
        )
    ''')
    
    # Check/add new columns to students
    cursor = conn.execute('PRAGMA table_info(students)')
    student_columns = [row['name'] for row in cursor.fetchall()]
    new_student_cols = [
        ('parent_name', 'TEXT'),
        ('parent_contact', 'TEXT'),
        ('address', 'TEXT'),
        ('additional_info', 'TEXT'),
        ('hobbies', 'TEXT'),
        ('parent_occupation', 'TEXT'),
        ('cgpa', 'REAL DEFAULT 0.0'),
        ('semester', 'TEXT DEFAULT "Semester 1"'),
        ('income', 'REAL DEFAULT 0.0'),
        ('category', 'TEXT DEFAULT "General"'),
        ('profile_photo', 'TEXT'),
        ('documents', 'TEXT')
    ]
    for col_name, col_type in new_student_cols:
        if col_name not in student_columns:
            conn.execute(f'ALTER TABLE students ADD COLUMN {col_name} {col_type}')
            
    # 4. Create other tables
    conn.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            course_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            credits INTEGER NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS course_prerequisites (
            course_id TEXT NOT NULL,
            prerequisite_id TEXT NOT NULL,
            PRIMARY KEY (course_id, prerequisite_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_id TEXT NOT NULL,
            semester TEXT NOT NULL,
            internal_marks REAL,
            exam_marks REAL,
            grade TEXT,
            attendance_percentage REAL DEFAULT 100.0,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS library_books (
            book_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            available_copies INTEGER DEFAULT 1
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS book_loans (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            return_date TEXT,
            fine_amount REAL DEFAULT 0.0,
            FOREIGN KEY(book_id) REFERENCES library_books(book_id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS fees (
            student_id TEXT PRIMARY KEY,
            total_fee REAL NOT NULL,
            paid_fee REAL DEFAULT 0.0,
            pending_fee REAL DEFAULT 0.0,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS placements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            job_role TEXT NOT NULL,
            min_cgpa REAL NOT NULL,
            salary TEXT NOT NULL,
            interview_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            course_id TEXT NOT NULL,
            day TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            room TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(course_id) ON DELETE CASCADE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            date TEXT NOT NULL,
            target_role TEXT NOT NULL DEFAULT 'All'
        )
    ''')

    # Seed Default Users
    admin_user = conn.execute('SELECT * FROM users WHERE username = ?', ('admin',)).fetchone()
    if not admin_user:
        conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                     ('admin', generate_password_hash('admin123'), 'admin'))
    else:
        conn.execute('UPDATE users SET role = "admin" WHERE username = "admin"')
        
    faculty_user = conn.execute('SELECT * FROM users WHERE username = ?', ('faculty',)).fetchone()
    if not faculty_user:
        conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                     ('faculty', generate_password_hash('faculty123'), 'faculty'))
                     
    student_user = conn.execute('SELECT * FROM users WHERE username = ?', ('student',)).fetchone()
    if not student_user:
        conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                     ('student', generate_password_hash('student123'), 'student'))

    # Seed some initial courses, books, placements, notifications if empty
    if conn.execute('SELECT COUNT(*) FROM courses').fetchone()[0] == 0:
        initial_courses = [
            ('CS101', 'Introduction to Programming', 'Computer Science and Engineering', 4),
            ('CS102', 'Data Structures and Algorithms', 'Computer Science and Engineering', 4),
            ('AI201', 'Artificial Intelligence Foundations', 'Artificial Intelligence and Machine Learning', 4),
            ('AI202', 'Machine Learning Essentials', 'Artificial Intelligence and Machine Learning', 4),
            ('CY301', 'Introduction to Cybersecurity', 'Cybersecurity', 3),
        ]
        conn.executemany('INSERT INTO courses (course_id, name, department, credits) VALUES (?, ?, ?, ?)', initial_courses)
        
        # Prerequisites
        conn.execute('INSERT INTO course_prerequisites (course_id, prerequisite_id) VALUES (?, ?)', ('CS102', 'CS101'))
        conn.execute('INSERT INTO course_prerequisites (course_id, prerequisite_id) VALUES (?, ?)', ('AI202', 'CS101'))
        conn.execute('INSERT INTO course_prerequisites (course_id, prerequisite_id) VALUES (?, ?)', ('AI202', 'AI201'))

    if conn.execute('SELECT COUNT(*) FROM library_books').fetchone()[0] == 0:
        initial_books = [
            ('B01', 'Introduction to Algorithms', 'Thomas H. Cormen', 5),
            ('B02', 'Artificial Intelligence: A Modern Approach', 'Stuart Russell', 3),
            ('B03', 'Computer Networking', 'James Kurose', 4),
            ('B04', 'Database System Concepts', 'Abraham Silberschatz', 6)
        ]
        conn.executemany('INSERT INTO library_books (book_id, title, author, available_copies) VALUES (?, ?, ?, ?)', initial_books)

    if conn.execute('SELECT COUNT(*) FROM placements').fetchone()[0] == 0:
        initial_placements = [
            ('Google', 'Software Engineer Intern', 8.5, '120,000 USD / Year', '2026-10-15', 'Open'),
            ('Microsoft', 'Associate Consultant', 7.5, '85,000 USD / Year', '2026-11-01', 'Open'),
            ('Amazon', 'Support Engineer', 7.0, '75,000 USD / Year', '2026-09-20', 'Open')
        ]
        conn.executemany('INSERT INTO placements (company_name, job_role, min_cgpa, salary, interview_date, status) VALUES (?, ?, ?, ?, ?, ?)', initial_placements)

    if conn.execute('SELECT COUNT(*) FROM notifications').fetchone()[0] == 0:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        initial_notifications = [
            ('Semester Registration Open', 'Please register for courses before the end of the week.', now_str, 'All'),
            ('Fee Payment Reminder', 'Second installment of academic fees is due next Monday.', now_str, 'student'),
            ('Midterm Marks Upload', 'Faculty members are requested to complete internal mark uploads by Wednesday.', now_str, 'faculty')
        ]
        conn.executemany('INSERT INTO notifications (title, message, date, target_role) VALUES (?, ?, ?, ?)', initial_notifications)

    conn.commit()
    conn.close()
    print("Database initialized with expanded schema.")

# Initialize database
init_db()

def async_retrain_model():
    import threading
    threading.Thread(target=ml_engine.predictor.train_model).start()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role'] if 'role' in user.keys() else 'student'
            flash('Login Successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Username or Password', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    # 1. Gather Metrics
    total_students = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    total_courses = conn.execute('SELECT COUNT(*) FROM courses').fetchone()[0]
    defaulters_count = conn.execute('SELECT COUNT(DISTINCT student_id) FROM enrollments WHERE attendance_percentage < 75.0').fetchone()[0]
    active_loans = conn.execute('SELECT COUNT(*) FROM book_loans WHERE return_date IS NULL').fetchone()[0]
    
    metrics = {
        "total_students": total_students,
        "total_courses": total_courses,
        "defaulters_count": defaulters_count,
        "active_loans": active_loans
    }
    
    # 2. Chart Data: Department-wise
    dept_rows = conn.execute('SELECT department, COUNT(*) as cnt FROM students GROUP BY department').fetchall()
    dept_chart_data = {
        "labels": [row['department'] for row in dept_rows],
        "values": [row['cnt'] for row in dept_rows]
    }
    
    # 3. Chart Data: Scatter plot (Attendance vs Internals)
    scatter_rows = conn.execute('SELECT attendance_percentage, internal_marks FROM enrollments').fetchall()
    scatter_chart_data = [{"x": row['attendance_percentage'] or 0.0, "y": row['internal_marks'] or 0.0} for row in scatter_rows]
    
    # 4. Top-K Rankings (using Heap)
    students_rows = conn.execute('SELECT id, name, department, year, cgpa FROM students').fetchall()
    students_list = [dict(s) for s in students_rows]
    top_students = dsa_helpers.TopStudentsHeap.get_top_k(students_list, k=5)
    
    # 5. Local Notifications
    role = session.get('role', 'student')
    notifications_rows = conn.execute(
        'SELECT * FROM notifications WHERE target_role = ? OR target_role = "All" ORDER BY id DESC LIMIT 5',
        (role,)
    ).fetchall()
    notifications = [dict(n) for n in notifications_rows]
    
    # 6. ML Performance at-risk students
    at_risk_students = []
    enrollment_rows = conn.execute("""
        SELECT e.student_id, s.name, e.attendance_percentage, e.internal_marks, s.cgpa, c.name as course_name
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        JOIN courses c ON e.course_id = c.course_id
        WHERE e.attendance_percentage < 75.0 OR e.internal_marks < 15.0 OR s.cgpa < 6.5
    """).fetchall()
    
    for er in enrollment_rows:
        pred = ml_engine.predictor.predict(er['attendance_percentage'], er['internal_marks'], er['cgpa'])
        if pred['risk_level'] in ['High', 'Medium']:
            at_risk_students.append({
                "id": er['student_id'],
                "name": f"{er['name']} ({er['course_name']})",
                "attendance": er['attendance_percentage'],
                "internals": er['internal_marks'],
                "cgpa": er['cgpa'],
                "risk": pred['risk_level'],
                "recommendation": pred['recommendation']
            })
    
    conn.close()
    return render_template(
        'dashboard.html',
        metrics=metrics,
        dept_chart_data=dept_chart_data,
        scatter_chart_data=scatter_chart_data,
        top_students=top_students,
        notifications=notifications,
        at_risk_students=at_risk_students[:5]
    )

# --- AI Helpers & Validation ---
def validate_student_data(data):
    errors = []
    if any(char.isdigit() for char in data['name']):
        errors.append("Student name should not contain numbers.")
    if not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
        errors.append("Invalid email format.")
    return errors

def get_ai_analytics():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM students", conn)
    conn.close()
    
    if df.empty:
        return {
            'summary': "No data available yet.",
            'trend': "Awaiting student registration...",
            'recommendation': "Register students to see trends.",
            'popular_dept': "None",
            'counts': {}
        }
    
    popular_dept = df['department'].value_counts().idxmax()
    dept_counts = df['department'].value_counts().to_dict()
    
    return {
        'summary': f"Total {len(df)} students analyzed. {popular_dept} is the leading department.",
        'trend': f"Departmental distribution is healthy, with {popular_dept} having the highest enrollment.",
        'recommendation': "Consider scaling resources in highly populated departments.",
        'popular_dept': popular_dept,
        'counts': dept_counts
    }

def save_uploaded_file(file, prefix):
    if not file or file.filename == '':
        return None
    filename = secure_filename(f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename

@app.route('/add', methods=['GET', 'POST'])
def add_student():
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        department = request.form['department']
        year = request.form['year']
        email = request.form['email']
        
        semester = request.form.get('semester', 'Semester 1')
        cgpa = float(request.form.get('cgpa') or 0.0)
        category = request.form.get('category', 'General')
        income = float(request.form.get('income') or 0.0)
        parent_name = request.form.get('parent_name')
        parent_contact = request.form.get('parent_contact')
        parent_occupation = request.form.get('parent_occupation')
        address = request.form.get('address')
        additional_info = request.form.get('additional_info')
        hobbies = request.form.get('hobbies')
        
        # File Uploads
        photo_file = request.files.get('profile_photo')
        doc_file = request.files.get('documents')
        
        profile_photo = save_uploaded_file(photo_file, 'photo')
        documents = save_uploaded_file(doc_file, 'doc')
        
        student_data = {
            'student_id': student_id,
            'name': name,
            'department': department,
            'year': year,
            'email': email
        }
        
        errors = validate_student_data(student_data)
        
        conn = get_db_connection()
        exists = conn.execute('SELECT 1 FROM students WHERE id = ?', (student_id,)).fetchone()
        if exists:
            errors.append(f"Student ID {student_id} already exists.")
            
        if errors:
            for err in errors:
                flash(err, 'error')
            conn.close()
        else:
            try:
                conn.execute('''
                    INSERT INTO students (
                        id, name, department, year, email, 
                        parent_name, parent_contact, address, additional_info,
                        hobbies, parent_occupation, cgpa, semester, income, category,
                        profile_photo, documents
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, name, department, year, email, 
                      parent_name, parent_contact, address, additional_info,
                      hobbies, parent_occupation, cgpa, semester, income, category,
                      profile_photo, documents))
                
                # Create fee record
                conn.execute('INSERT OR IGNORE INTO fees (student_id, total_fee, paid_fee, pending_fee) VALUES (?, ?, ?, ?)',
                             (student_id, 4500.0, 0.0, 4500.0))
                             
                conn.commit()
                conn.close()
                flash('Student added successfully!', 'success')
                return redirect(url_for('view_students'))
            except sqlite3.IntegrityError:
                conn.close()
                flash('Fatal database error: ID collision.', 'error')
                
    return render_template('add_student.html', departments=DEPARTMENTS)

@app.route('/forgot_password')
def forgot_password():
    flash('Redirecting to Change Password for safety.', 'info')
    return redirect(url_for('change_password'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        username = request.form['username']
        new_password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user:
            hashed_password = generate_password_hash(new_password)
            conn.execute('UPDATE users SET password = ? WHERE username = ?', (hashed_password, username))
            conn.commit()
            conn.close()
            flash('Password updated successfully!', 'success')
            return redirect(url_for('login'))
        else:
            conn.close()
            flash('Username not found.', 'error')
            
    return render_template('change_password.html')

@app.route('/ai_insights')
def ai_insights():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('ai_insights.html', insights=get_ai_analytics())

@app.route('/bot', methods=['GET', 'POST'])
def search_bot():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chatbot.html')

@app.route('/report/<student_id>')
def generate_report(student_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    conn.close()
    
    if not student:
        flash('Student not found.', 'error')
        return redirect(url_for('view_students'))
        
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, "OFFICIAL STUDENT REPORT", 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font("Helvetica", '', 12)
    pdf.cell(50, 10, f"Name: {student['name']}", 0, 1)
    pdf.cell(50, 10, f"ID: {student['id']}", 0, 1)
    pdf.cell(50, 10, f"Department: {student['department']}", 0, 1)
    pdf.cell(50, 10, f"Academic Level: {student['semester'] or student['year']}", 0, 1)
    pdf.cell(50, 10, f"CGPA Score: {student['cgpa'] or '0.00'}", 0, 1)
    pdf.cell(50, 10, f"Email: {student['email']}", 0, 1)
    pdf.ln(5)
    pdf.cell(0, 10, "Parent Information:", 'B', 1)
    pdf.cell(50, 10, f"Guardian: {student['parent_name'] or 'N/A'}", 0, 1)
    pdf.cell(50, 10, f"Occupation: {student['parent_occupation'] or 'N/A'}", 0, 1)
    pdf.ln(10)
    
    pdf.set_font("Helvetica", 'I', 10)
    pdf.multi_cell(0, 10, f"AI Analysis Notes: {student['additional_info'] or 'No additional data recorded.'}")
    
    output = pdf.output(dest='S')
    return send_file(
        io.BytesIO(output),
        as_attachment=True,
        download_name=f"report_{student_id}.pdf",
        mimetype='application/pdf'
    )

@app.route('/view')
def view_students():
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
        
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    conn = get_db_connection()
    
    query = 'SELECT * FROM students'
    params = []
    
    if search_query:
        query += ' WHERE id LIKE ? OR name LIKE ? OR department LIKE ?'
        params = [f'%{search_query}%', f'%{search_query}%', f'%{search_query}%']
    
    if sort_by == 'id':
        query += ' ORDER BY id ASC'
    elif sort_by == 'department':
        query += ' ORDER BY department ASC'
    elif sort_by == 'year':
        query += ' ORDER BY year ASC'
    else:
        query += ' ORDER BY name ASC'
        
    all_students = conn.execute(query, params).fetchall()
    
    total = len(all_students)
    start = (page - 1) * per_page
    end = start + per_page
    students = all_students[start:end]
    
    total_pages = (total + per_page - 1) // per_page
    
    conn.close()
    return render_template('view_students.html', 
                           students=students, 
                           search=search_query, 
                           sort=sort_by, 
                           page=page, 
                           total_pages=total_pages)

@app.route('/student/<student_id>')
def student_profile(student_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    
    ml_prediction = None
    if student:
        perf = conn.execute("""
            SELECT AVG(attendance_percentage) as avg_att, AVG(internal_marks) as avg_int
            FROM enrollments
            WHERE student_id = ?
        """, (student_id,)).fetchone()
        
        attendance = perf['avg_att'] if perf['avg_att'] is not None else 100.0
        internals = perf['avg_int'] if perf['avg_int'] is not None else 30.0
        cgpa = student['cgpa'] or 0.0
        
        ml_prediction = ml_engine.predictor.predict(attendance, internals, cgpa)
        
    conn.close()
    if student:
        return render_template('student_profile.html', student=student, ml_prediction=ml_prediction)
    flash('Student not found.', 'error')
    return redirect(url_for('view_students'))

@app.route('/edit/<student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        year = request.form['year']
        email = request.form['email']
        
        semester = request.form.get('semester', 'Semester 1')
        cgpa = float(request.form.get('cgpa') or 0.0)
        category = request.form.get('category', 'General')
        income = float(request.form.get('income') or 0.0)
        parent_name = request.form.get('parent_name')
        parent_contact = request.form.get('parent_contact')
        parent_occupation = request.form.get('parent_occupation')
        address = request.form.get('address')
        additional_info = request.form.get('additional_info')
        hobbies = request.form.get('hobbies')
        
        photo_file = request.files.get('profile_photo')
        doc_file = request.files.get('documents')
        
        profile_photo = save_uploaded_file(photo_file, 'photo') or student['profile_photo']
        documents = save_uploaded_file(doc_file, 'doc') or student['documents']
        
        conn.execute('''
            UPDATE students SET 
            name = ?, department = ?, year = ?, email = ?, 
            parent_name = ?, parent_contact = ?, address = ?, additional_info = ?,
            hobbies = ?, parent_occupation = ?, cgpa = ?, semester = ?, income = ?, category = ?,
            profile_photo = ?, documents = ?
            WHERE id = ?
        ''', (name, department, year, email, 
              parent_name, parent_contact, address, additional_info,
              hobbies, parent_occupation, cgpa, semester, income, category,
              profile_photo, documents, student_id))
        conn.commit()
        conn.close()
        
        async_retrain_model()
        
        flash('Student record updated!', 'success')
        return redirect(url_for('view_students'))
        
    conn.close()
    return render_template('edit_student.html', student=student, departments=DEPARTMENTS)

@app.route('/delete/<student_id>')
def delete_student(student_id):
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    conn.execute('DELETE FROM students WHERE id = ?', (student_id,))
    conn.commit()
    conn.close()
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('view_students'))

# --- Courses, Prerequisites, Enrollments ---
@app.route('/courses')
def courses_view():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    courses_rows = conn.execute('SELECT * FROM courses').fetchall()
    courses = []
    for cr in courses_rows:
        prereqs = conn.execute('SELECT prerequisite_id FROM course_prerequisites WHERE course_id = ?', (cr['course_id'],)).fetchall()
        courses.append({
            "course_id": cr['course_id'],
            "name": cr['name'],
            "department": cr['department'],
            "credits": cr['credits'],
            "prereqs": [p['prerequisite_id'] for p in prereqs]
        })
        
    students_rows = conn.execute('SELECT id, name FROM students').fetchall()
    
    enrollment_rows = conn.execute("""
        SELECT e.id, e.student_id, s.name as student_name, e.course_id, c.name as course_name, e.semester, e.attendance_percentage, e.grade
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        JOIN courses c ON e.course_id = c.course_id
    """).fetchall()
    
    # Directed Graph (DSA) for course prerequisites
    graph = dsa_helpers.CourseGraph()
    for c in courses:
        graph.add_course(c['course_id'])
        for pr in c['prereqs']:
            graph.add_prerequisite(c['course_id'], pr)
            
    topo_order = graph.topological_sort()
    
    conn.close()
    return render_template('courses.html',
                           courses=courses,
                           students=students_rows,
                           enrollments=enrollment_rows,
                           departments=DEPARTMENTS,
                           topo_order=topo_order)

@app.route('/add_course', methods=['POST'])
def add_course():
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('courses_view'))
        
    course_id = request.form['course_id'].strip().upper()
    name = request.form['name'].strip()
    department = request.form['department']
    credits = int(request.form['credits'])
    
    try:
        conn = get_db_connection()
        conn.execute('INSERT INTO courses (course_id, name, department, credits) VALUES (?, ?, ?, ?)',
                     (course_id, name, department, credits))
        conn.commit()
        conn.close()
        flash(f'Course {course_id} added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('Course code already exists.', 'error')
        
    return redirect(url_for('courses_view'))

@app.route('/add_prerequisite', methods=['POST'])
def add_prerequisite():
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('courses_view'))
        
    course_id = request.form['course_id']
    prereq_id = request.form['prerequisite_id']
    
    if course_id == prereq_id:
        flash('A course cannot be a prerequisite of itself.', 'error')
        return redirect(url_for('courses_view'))
        
    conn = get_db_connection()
    courses = conn.execute('SELECT course_id FROM courses').fetchall()
    prereqs_all = conn.execute('SELECT course_id, prerequisite_id FROM course_prerequisites').fetchall()
    
    graph = dsa_helpers.CourseGraph()
    for c in courses:
        graph.add_course(c['course_id'])
    for pr in prereqs_all:
        graph.add_prerequisite(pr['course_id'], pr['prerequisite_id'])
        
    graph.add_prerequisite(course_id, prereq_id)
    
    if graph.has_cycle():
        conn.close()
        flash('Cannot add prerequisite: Circular dependency detected!', 'error')
    else:
        try:
            conn.execute('INSERT INTO course_prerequisites (course_id, prerequisite_id) VALUES (?, ?)',
                         (course_id, prereq_id))
            conn.commit()
            flash('Prerequisite link established.', 'success')
        except sqlite3.IntegrityError:
            flash('Prerequisite mapping already exists.', 'error')
        conn.close()
        
    return redirect(url_for('courses_view'))

@app.route('/enroll_student', methods=['POST'])
def enroll_student():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    student_id = request.form['student_id']
    course_id = request.form['course_id']
    semester = request.form['semester']
    
    conn = get_db_connection()
    
    # Graph check
    prereqs_needed = conn.execute('SELECT prerequisite_id FROM course_prerequisites WHERE course_id = ?', (course_id,)).fetchall()
    completed_rows = conn.execute("""
        SELECT course_id FROM enrollments 
        WHERE student_id = ? AND grade IS NOT NULL AND grade != 'F'
    """, (student_id,)).fetchall()
    completed_courses = [cr['course_id'] for cr in completed_rows]
    
    missing = []
    for pr in prereqs_needed:
        pid = pr['prerequisite_id']
        if pid not in completed_courses:
            missing.append(pid)
            
    if missing:
        conn.close()
        flash(f'Cannot enroll student: Missing prerequisites: {", ".join(missing)}', 'error')
        return redirect(url_for('courses_view'))
        
    enr = conn.execute('SELECT id FROM enrollments WHERE student_id = ? AND course_id = ?', (student_id, course_id)).fetchone()
    if enr:
        conn.close()
        flash('Student already enrolled in this course.', 'error')
        return redirect(url_for('courses_view'))
        
    conn.execute('''
        INSERT INTO enrollments (student_id, course_id, semester, attendance_percentage)
        VALUES (?, ?, ?, 100.0)
    ''', (student_id, course_id, semester))
    conn.commit()
    conn.close()
    
    flash('Student enrolled successfully!', 'success')
    return redirect(url_for('courses_view'))

@app.route('/drop_enrollment/<int:enrollment_id>')
def drop_enrollment(enrollment_id):
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('courses_view'))
        
    conn = get_db_connection()
    conn.execute('DELETE FROM enrollments WHERE id = ?', (enrollment_id,))
    conn.commit()
    conn.close()
    flash('Course enrollment dropped.', 'success')
    return redirect(url_for('courses_view'))

@app.route('/api/prereq_path/<course_id>')
def api_prereq_path(course_id):
    conn = get_db_connection()
    crs = conn.execute('SELECT course_id FROM courses WHERE course_id = ?', (course_id,)).fetchone()
    if not crs:
        conn.close()
        return jsonify({"error": f"Course code {course_id} not found."}), 404
        
    courses = conn.execute('SELECT course_id FROM courses').fetchall()
    prereqs_all = conn.execute('SELECT course_id, prerequisite_id FROM course_prerequisites').fetchall()
    
    graph = dsa_helpers.CourseGraph()
    for c in courses:
        graph.add_course(c['course_id'])
    for pr in prereqs_all:
        graph.add_prerequisite(pr['course_id'], pr['prerequisite_id'])
        
    path = graph.get_prerequisite_path(course_id)
    conn.close()
    return jsonify({"course_id": course_id, "path": path})

# --- Attendance Module ---
@app.route('/attendance')
def attendance_view():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    attendance_records = conn.execute("""
        SELECT e.id, e.student_id, s.name as student_name, e.course_id, c.name as course_name, e.attendance_percentage
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        JOIN courses c ON e.course_id = c.course_id
    """).fetchall()
    
    defaulters = conn.execute("""
        SELECT e.student_id, s.name as student_name, e.course_id, c.name as course_name, e.attendance_percentage, s.email
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        JOIN courses c ON e.course_id = c.course_id
        WHERE e.attendance_percentage < 75.0
    """).fetchall()
    
    conn.close()
    return render_template('attendance.html',
                           attendance_records=attendance_records,
                           defaulters=defaulters)

@app.route('/update_attendance', methods=['POST'])
def update_attendance():
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('attendance_view'))
        
    enrollment_id = int(request.form['enrollment_id'])
    attendance_percentage = float(request.form['attendance_percentage'])
    
    conn = get_db_connection()
    conn.execute('UPDATE enrollments SET attendance_percentage = ? WHERE id = ?',
                 (attendance_percentage, enrollment_id))
    conn.commit()
    conn.close()
    
    async_retrain_model()
    
    flash('Attendance updated successfully.', 'success')
    return redirect(url_for('attendance_view'))

# --- Marks, Grade Cards, PDF ---
@app.route('/marks')
def marks_view():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    grade_records = conn.execute("""
        SELECT e.id, e.student_id, s.name as student_name, e.course_id, c.name as course_name, e.internal_marks, e.exam_marks, e.grade
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        JOIN courses c ON e.course_id = c.course_id
    """).fetchall()
    
    course_rows = conn.execute('SELECT course_id, name as course_name, department FROM courses').fetchall()
    course_stats = []
    for cr in course_rows:
        stats = conn.execute("""
            SELECT AVG(internal_marks + exam_marks) as avg_score,
                   COUNT(*) as enrolled,
                   SUM(CASE WHEN (internal_marks + exam_marks) >= 40 THEN 1 ELSE 0 END) as passed
            FROM enrollments
            WHERE course_id = ? AND internal_marks IS NOT NULL
        """, (cr['course_id'],)).fetchone()
        
        if stats['enrolled'] > 0:
            pass_percentage = (stats['passed'] / stats['enrolled']) * 100.0
            avg_score = stats['avg_score'] or 0.0
        else:
            pass_percentage = 100.0
            avg_score = 0.0
            
        course_stats.append({
            "course_id": cr['course_id'],
            "course_name": cr['course_name'],
            "department": cr['department'],
            "total_students": stats['enrolled'],
            "avg_score": avg_score,
            "pass_percentage": pass_percentage
        })
        
    conn.close()
    return render_template('marks.html', grade_records=grade_records, course_stats=course_stats)

@app.route('/update_marks', methods=['POST'])
def update_marks():
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('marks_view'))
        
    enrollment_id = int(request.form['enrollment_id'])
    internal_marks = float(request.form['internal_marks'])
    exam_marks = float(request.form['exam_marks'])
    
    total = internal_marks + exam_marks
    if total >= 90: grade = 'O'
    elif total >= 80: grade = 'A+'
    elif total >= 70: grade = 'A'
    elif total >= 60: grade = 'B'
    elif total >= 50: grade = 'C'
    elif total >= 40: grade = 'D'
    else: grade = 'F'
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE enrollments 
        SET internal_marks = ?, exam_marks = ?, grade = ?
        WHERE id = ?
    ''', (internal_marks, exam_marks, grade, enrollment_id))
    
    enrollment_rec = conn.execute('SELECT student_id FROM enrollments WHERE id = ?', (enrollment_id,)).fetchone()
    if enrollment_rec:
        student_id = enrollment_rec['student_id']
        student_enrollments = conn.execute("""
            SELECT e.internal_marks, e.exam_marks, c.credits
            FROM enrollments e
            JOIN courses c ON e.course_id = c.course_id
            WHERE e.student_id = ? AND e.internal_marks IS NOT NULL
        """, (student_id,)).fetchall()
        
        total_points = 0.0
        total_credits = 0.0
        
        for se in student_enrollments:
            tot_score = (se['internal_marks'] or 0) + (se['exam_marks'] or 0)
            if tot_score >= 90: gp = 10.0
            elif tot_score >= 80: gp = 9.0
            elif tot_score >= 70: gp = 8.0
            elif tot_score >= 60: gp = 7.0
            elif tot_score >= 50: gp = 6.0
            elif tot_score >= 40: gp = 5.0
            else: gp = 0.0
            
            total_points += gp * se['credits']
            total_credits += se['credits']
            
        new_cgpa = (total_points / total_credits) if total_credits > 0 else 0.0
        conn.execute('UPDATE students SET cgpa = ? WHERE id = ?', (round(new_cgpa, 2), student_id))
        
    conn.commit()
    conn.close()
    
    async_retrain_model()
    
    flash('Marks and grade updated successfully.', 'success')
    return redirect(url_for('marks_view'))

@app.route('/download_report_card/<int:enrollment_id>')
def download_report_card(enrollment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    record = conn.execute("""
        SELECT e.student_id, s.name as student_name, s.department, s.semester, s.cgpa,
               e.course_id, c.name as course_name, c.credits, e.internal_marks, e.exam_marks, e.grade
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        JOIN courses c ON e.course_id = c.course_id
        WHERE e.id = ?
    """, (enrollment_id,)).fetchone()
    conn.close()
    
    if not record:
        flash('Record not found.', 'error')
        return redirect(url_for('marks_view'))
        
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 15, "OFFICIAL TRANSCRIPT & GRADE CARD", 0, 1, 'C', fill=True)
    pdf.ln(10)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "Student Credentials", 'B', 1)
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(100, 8, f"Student Name: {record['student_name']}", 0, 0)
    pdf.cell(0, 8, f"Registration ID: {record['student_id']}", 0, 1)
    pdf.cell(100, 8, f"Department: {record['department']}", 0, 0)
    pdf.cell(0, 8, f"Academic Level: {record['semester']}", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "Subject Grade Analysis", 'B', 1)
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(100, 8, f"Course Title: {record['course_name']} ({record['course_id']})", 0, 1)
    pdf.cell(50, 8, f"Internal Score: {record['internal_marks'] or 0}/30", 0, 0)
    pdf.cell(50, 8, f"End-Exam Score: {record['exam_marks'] or 0}/70", 0, 1)
    pdf.cell(50, 8, f"Total Marks: {(record['internal_marks'] or 0) + (record['exam_marks'] or 0)}/100", 0, 0)
    pdf.cell(50, 8, f"Letter Grade: {record['grade'] or 'F'}", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "Summary Analytics", 'B', 1)
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(100, 8, f"Cumulative CGPA: {record['cgpa'] or '0.0'}/10.0", 0, 1)
    pdf.ln(10)
    
    pdf.set_font("Helvetica", 'I', 9)
    pdf.cell(0, 8, "Generated by Local Student Database System. No Signature Required.", 0, 1, 'C')
    
    output = pdf.output(dest='S')
    return send_file(
        io.BytesIO(output),
        as_attachment=True,
        download_name=f"grade_card_{record['student_id']}_{record['course_id']}.pdf",
        mimetype='application/pdf'
    )

# --- Services (Fee, Library, Placement, Scholarship) ---
@app.route('/modules')
def modules_view():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    fee_records = conn.execute("""
        SELECT f.*, s.name as student_name
        FROM fees f
        JOIN students s ON f.student_id = s.id
    """).fetchall()
    
    books = conn.execute('SELECT * FROM library_books').fetchall()
    
    loans = conn.execute("""
        SELECT bl.*, s.name as student_name, b.title as book_title
        FROM book_loans bl
        JOIN students s ON bl.student_id = s.id
        JOIN library_books b ON bl.book_id = b.book_id
    """).fetchall()
    
    jobs = conn.execute('SELECT * FROM placements').fetchall()
    
    students_rows = conn.execute('SELECT id, name, department, year, cgpa, category, income FROM students').fetchall()
    students_list = [dict(s) for s in students_rows]
    
    conn.close()
    return render_template('modules.html',
                           fee_records=fee_records,
                           books=books,
                           loans=loans,
                           jobs=jobs,
                           students_list=students_list)

@app.route('/post_fee_payment', methods=['POST'])
def post_fee_payment():
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('modules_view'))
        
    student_id = request.form['student_id']
    amount = float(request.form['amount'])
    
    conn = get_db_connection()
    fee = conn.execute('SELECT * FROM fees WHERE student_id = ?', (student_id,)).fetchone()
    
    if fee:
        paid = fee['paid_fee'] + amount
        pending = max(0.0, fee['total_fee'] - paid)
        conn.execute('UPDATE fees SET paid_fee = ?, pending_fee = ? WHERE student_id = ?',
                     (paid, pending, student_id))
        conn.commit()
        flash('Payment processed successfully.', 'success')
    else:
        flash('Fee record not found.', 'error')
    conn.close()
    return redirect(url_for('modules_view'))

@app.route('/download_fee_receipt/<student_id>')
def download_fee_receipt(student_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    fee = conn.execute("""
        SELECT f.*, s.name as student_name, s.department
        FROM fees f
        JOIN students s ON f.student_id = s.id
        WHERE f.student_id = ?
    """, (student_id,)).fetchone()
    conn.close()
    
    if not fee:
        flash('Receipt not found.', 'error')
        return redirect(url_for('modules_view'))
        
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 15, "OFFICIAL TUITION FEE RECEIPT", 0, 1, 'C', fill=True)
    pdf.ln(10)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 8, f"Student Name: {fee['student_name']}", 0, 1)
    pdf.cell(0, 8, f"Student ID: {fee['student_id']}", 0, 1)
    pdf.cell(0, 8, f"Department: {fee['department']}", 0, 1)
    pdf.ln(5)
    pdf.cell(0, 8, "Fee Summary Details", 'B', 1)
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(80, 8, f"Total Scheduled Fee: ${fee['total_fee']}", 0, 1)
    pdf.cell(80, 8, f"Processed Paid Amount: ${fee['paid_fee']}", 0, 1)
    pdf.cell(80, 8, f"Remaining Outstanding Balance: ${fee['pending_fee']}", 0, 1)
    pdf.ln(10)
    
    pdf.set_font("Helvetica", 'I', 10)
    pdf.cell(0, 8, "Thank you for your payment.", 0, 1, 'C')
    
    output = pdf.output(dest='S')
    return send_file(
        io.BytesIO(output),
        as_attachment=True,
        download_name=f"fee_receipt_{student_id}.pdf",
        mimetype='application/pdf'
    )

@app.route('/post_lend_book', methods=['POST'])
def post_lend_book():
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('modules_view'))
        
    book_id = request.form['book_id']
    student_id = request.form['student_id']
    
    conn = get_db_connection()
    book = conn.execute('SELECT available_copies FROM library_books WHERE book_id = ?', (book_id,)).fetchone()
    
    if book and book['available_copies'] > 0:
        now_str = datetime.now().strftime("%Y-%m-%d")
        conn.execute('INSERT INTO book_loans (book_id, student_id, issue_date) VALUES (?, ?, ?)',
                     (book_id, student_id, now_str))
        conn.execute('UPDATE library_books SET available_copies = available_copies - 1 WHERE book_id = ?',
                     (book_id,))
        conn.commit()
        flash('Book successfully checked out.', 'success')
    else:
        flash('Book is out of stock.', 'error')
    conn.close()
    return redirect(url_for('modules_view'))

@app.route('/return_book/<int:loan_id>')
def return_book(loan_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    loan = conn.execute('SELECT * FROM book_loans WHERE loan_id = ?', (loan_id,)).fetchone()
    
    if loan and not loan['return_date']:
        now_str = datetime.now().strftime("%Y-%m-%d")
        
        issue_date = datetime.strptime(loan['issue_date'], "%Y-%m-%d")
        days_loaned = (datetime.now() - issue_date).days
        fine = 0.0
        if days_loaned > 14:
            fine = (days_loaned - 14) * 5.00
            
        conn.execute('UPDATE book_loans SET return_date = ?, fine_amount = ? WHERE loan_id = ?',
                     (now_str, fine, loan_id))
        conn.execute('UPDATE library_books SET available_copies = available_copies + 1 WHERE book_id = ?',
                     (loan['book_id'],))
        conn.commit()
        if fine > 0:
            flash(f'Book returned. Overdue fine calculated: ${fine:.2f}', 'info')
        else:
            flash('Book returned successfully.', 'success')
    else:
        flash('Invalid loan record.', 'error')
    conn.close()
    return redirect(url_for('modules_view'))

@app.route('/post_placement', methods=['POST'])
def post_placement():
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('modules_view'))
        
    company_name = request.form['company_name']
    job_role = request.form['job_role']
    min_cgpa = float(request.form['min_cgpa'])
    salary = request.form['salary']
    interview_date = request.form['interview_date']
    
    conn = get_db_connection()
    conn.execute('INSERT INTO placements (company_name, job_role, min_cgpa, salary, interview_date) VALUES (?, ?, ?, ?, ?)',
                 (company_name, job_role, min_cgpa, salary, interview_date))
    conn.commit()
    conn.close()
    
    flash('Placement drive scheduled successfully.', 'success')
    return redirect(url_for('modules_view'))

@app.route('/api/placement_eligible')
def api_placement_eligible():
    min_cgpa = float(request.args.get('min_cgpa', 0.0))
    conn = get_db_connection()
    rows = conn.execute('SELECT id, name, department, semester, cgpa FROM students WHERE cgpa >= ?', (min_cgpa,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/scholarship_check')
def api_scholarship_check():
    student_id = request.args.get('student_id')
    category = request.args.get('category', 'General')
    income = float(request.args.get('income', 0.0))
    
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM students WHERE id = ?', (student_id,)).fetchone()
    
    perf = conn.execute("""
        SELECT AVG(attendance_percentage) as avg_att
        FROM enrollments
        WHERE student_id = ?
    """, (student_id,)).fetchone()
    conn.close()
    
    if not student:
        return jsonify({"error": "Student not found"}), 404
        
    attendance = perf['avg_att'] if perf['avg_att'] is not None else 100.0
    cgpa = student['cgpa'] or 0.0
    
    thresholds = {
        "SC": 50000.0,
        "ST": 50000.0,
        "OBC": 30000.0,
        "General": 15000.0
    }
    limit = thresholds.get(category, 15000.0)
    
    eligible = True
    remarks = "Approved! Student meets academic criteria and household income limit."
    
    if cgpa < 7.5:
        eligible = False
        remarks = "Disapproved: CGPA must be at least 7.5."
    elif attendance < 75.0:
        eligible = False
        remarks = "Disapproved: Attendance must be at least 75%."
    elif income > limit:
        eligible = False
        remarks = f"Disapproved: Family income exceeds the ${limit} limit set for {category} category."
        
    return jsonify({
        "student_id": student_id,
        "cgpa": cgpa,
        "attendance": round(attendance, 1),
        "category": category,
        "income": income,
        "threshold": limit,
        "eligible": eligible,
        "remarks": remarks
    })

# --- DSA Lab Visualizer ---
@app.route('/dsa_visualizer')
def dsa_visualizer():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    students_rows = conn.execute('SELECT id, name, department, year, cgpa FROM students').fetchall()
    students_list = [dict(s) for s in students_rows]
    
    # Heap
    heap_array = sorted(students_list, key=lambda x: float(x.get('cgpa') or 0.0), reverse=True)
    
    # Graph
    graph_edges = conn.execute('SELECT * FROM course_prerequisites').fetchall()
    
    # Timetables Dynamic Programming Clash
    timetables_rows = conn.execute('SELECT * FROM timetables').fetchall()
    timetables_list = [dict(t) for t in timetables_rows]
    dp_scheduled, dp_conflicted = dsa_helpers.TimetableOptimizer.schedule_clash_free(timetables_list)
    
    courses_list = conn.execute('SELECT course_id, name FROM courses').fetchall()
    
    conn.close()
    return render_template('dsa_visualizer.html',
                           heap_array=heap_array,
                           graph_edges=graph_edges,
                           dp_scheduled=dp_scheduled,
                           dp_conflicted=dp_conflicted,
                           courses_list=courses_list)

@app.route('/post_timetable', methods=['POST'])
def post_timetable():
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('dsa_visualizer'))
        
    class_name = request.form['class_name']
    course_id = request.form['course_id']
    day = request.form['day']
    room = request.form['room']
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO timetables (class_name, course_id, day, start_time, end_time, room)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (class_name, course_id, day, start_time, end_time, room))
    conn.commit()
    conn.close()
    
    flash('Timetable slot added. Running DP collision checker...', 'success')
    return redirect(url_for('dsa_visualizer'))

@app.route('/api/bst_search/<student_id>')
def api_bst_search(student_id):
    conn = get_db_connection()
    students_rows = conn.execute('SELECT id, name, department, semester, cgpa FROM students').fetchall()
    conn.close()
    
    if not students_rows:
        return jsonify({"error": "No students in registry."}), 400
        
    bst = dsa_helpers.StudentBST()
    for s in students_rows:
        bst.insert(s['id'], dict(s))
        
    res, path = bst.search(student_id)
    bst_steps = len(path)
    
    id_list = [s['id'] for s in students_rows]
    linear_steps = id_list.index(student_id) + 1 if student_id in id_list else len(id_list)
    
    return jsonify({
        "student_id": student_id,
        "found": res is not None,
        "path": path,
        "bst_steps": bst_steps,
        "linear_steps": linear_steps
    })

# --- Offline AI Chatbot ---
@app.route('/api/chatbot_query')
def api_chatbot_query():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"response": "I didn't receive any query. How can I help you today?"})
        
    conn = get_db_connection()
    response = None
    query_lower = query.lower()
    
    DEPT_MAPPINGS = {
        "computer science": "Computer Science and Engineering",
        "cse": "Computer Science and Engineering",
        "artificial intelligence": "Artificial Intelligence and Machine Learning",
        "aiml": "Artificial Intelligence and Machine Learning",
        "ai": "Artificial Intelligence and Machine Learning",
        "cybersecurity": "Cybersecurity",
        "cyber": "Cybersecurity",
        "internet of things": "Internet of Things",
        "iot": "Internet of Things",
        "electrical": "Electrical Engineering",
        "eee": "Electrical Engineering",
        "agricultural": "Agricultural Engineering",
        "agri": "Agricultural Engineering",
        "biomedical": "Biomedical Engineering",
        "biomed": "Biomedical Engineering",
        "electronics": "Electronics and Communication Engineering",
        "ece": "Electronics and Communication Engineering",
        "mechatronics": "Mechatronics",
        "mech": "Mechatronics",
        "automobile": "Automobile Engineering",
        "auto": "Automobile Engineering",
        "food tech": "Food Technology",
        "food": "Food Technology"
    }
    
    # 1. Match Attendance Queries
    if "attendance" in query_lower:
        num_match = re.search(r"(\d+)", query_lower)
        if num_match:
            val = float(num_match.group(1))
            is_below = any(kw in query_lower for kw in ["below", "less", "under", "<", "defaulter"])
            
            if is_below:
                rows = conn.execute("""
                    SELECT DISTINCT e.student_id, s.name, e.attendance_percentage, c.name as course_name
                    FROM enrollments e
                    JOIN students s ON e.student_id = s.id
                    JOIN courses c ON e.course_id = c.course_id
                    WHERE e.attendance_percentage < ?
                """, (val,)).fetchall()
                if rows:
                    lines = [f"- {r['name']} (ID: {r['student_id']}) has {r['attendance_percentage']}% in {r['course_name']}" for r in rows]
                    response = f"Found {len(rows)} course enrollments with attendance below {val}%:\n" + "\n".join(lines)
                else:
                    response = f"No students have attendance below {val}%."
            else:
                rows = conn.execute("""
                    SELECT DISTINCT e.student_id, s.name, e.attendance_percentage, c.name as course_name
                    FROM enrollments e
                    JOIN students s ON e.student_id = s.id
                    JOIN courses c ON e.course_id = c.course_id
                    WHERE e.attendance_percentage >= ?
                """, (val,)).fetchall()
                if rows:
                    lines = [f"- {r['name']} (ID: {r['student_id']}) has {r['attendance_percentage']}% in {r['course_name']}" for r in rows]
                    response = f"Found {len(rows)} course enrollments with attendance >= {val}%:\n" + "\n".join(lines)
                else:
                    response = f"No students have attendance >= {val}%."
                    
    # 2. Match CGPA Queries
    elif "cgpa" in query_lower or "gpa" in query_lower:
        float_match = re.search(r"(\d+(?:\.\d+)?)", query_lower)
        if float_match:
            val = float(float_match.group(1))
            is_below = any(kw in query_lower for kw in ["below", "less", "under", "<"])
            
            if is_below:
                rows = conn.execute("SELECT id, name, cgpa FROM students WHERE cgpa < ?", (val,)).fetchall()
                if rows:
                    lines = [f"- {r['name']} (ID: {r['id']}) - CGPA: {r['cgpa']}" for r in rows]
                    response = f"Found {len(rows)} students with CGPA < {val}:\n" + "\n".join(lines)
                else:
                    response = f"No students found with CGPA < {val}."
            else:
                rows = conn.execute("SELECT id, name, cgpa FROM students WHERE cgpa >= ?", (val,)).fetchall()
                if rows:
                    lines = [f"- {r['name']} (ID: {r['id']}) - CGPA: {r['cgpa']}" for r in rows]
                    response = f"Found {len(rows)} students with CGPA >= {val}:\n" + "\n".join(lines)
                else:
                    response = f"No students found with CGPA >= {val}."
                        
    # 3. Match Department and Year Queries
    else:
        matched_dept = None
        for key, value in DEPT_MAPPINGS.items():
            if re.search(rf"\b{key}\b", query_lower):
                matched_dept = value
                break
                
        matched_year = None
        if any(kw in query_lower for kw in ["1st", "first", "1 year"]):
            matched_year = "1st Year"
        elif any(kw in query_lower for kw in ["2nd", "second", "2 year"]):
            matched_year = "2nd Year"
        elif any(kw in query_lower for kw in ["3rd", "third", "3 year"]):
            matched_year = "3rd Year"
        elif any(kw in query_lower for kw in ["4th", "fourth", "4 year"]):
            matched_year = "4th Year"
            
        is_count = any(kw in query_lower for kw in ["count", "how many"])
        
        if matched_dept and matched_year:
            if is_count:
                cnt = conn.execute("SELECT COUNT(*) FROM students WHERE department = ? AND year = ?", (matched_dept, matched_year)).fetchone()[0]
                response = f"There are {cnt} students in {matched_dept} ({matched_year})."
            else:
                rows = conn.execute("SELECT id, name FROM students WHERE department = ? AND year = ?", (matched_dept, matched_year)).fetchall()
                if rows:
                    lines = [f"- {r['name']} (ID: {r['id']})" for r in rows]
                    response = f"Found {len(rows)} students in {matched_dept} ({matched_year}):\n" + "\n".join(lines)
                else:
                    response = f"No students found in {matched_dept} ({matched_year})."
        elif matched_dept:
            if is_count:
                cnt = conn.execute("SELECT COUNT(*) FROM students WHERE department = ?", (matched_dept,)).fetchone()[0]
                response = f"There are {cnt} students in {matched_dept}."
            else:
                rows = conn.execute("SELECT id, name, year FROM students WHERE department = ?", (matched_dept,)).fetchall()
                if rows:
                    lines = [f"- {r['name']} (ID: {r['id']}) - {r['year']}" for r in rows]
                    response = f"Found {len(rows)} students in {matched_dept}:\n" + "\n".join(lines)
                else:
                    response = f"No students found in {matched_dept}."
        elif matched_year:
            if is_count:
                cnt = conn.execute("SELECT COUNT(*) FROM students WHERE year = ?", (matched_year,)).fetchone()[0]
                response = f"There are {cnt} students in {matched_year}."
            else:
                rows = conn.execute("SELECT id, name, department FROM students WHERE year = ?", (matched_year,)).fetchall()
                if rows:
                    lines = [f"- {r['name']} (ID: {r['id']}) - {r['department']}" for r in rows]
                    response = f"Found {len(rows)} students in {matched_year}:\n" + "\n".join(lines)
                else:
                    response = f"No students found in {matched_year}."
        elif is_count or "total" in query_lower:
            cnt = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            response = f"There are currently {cnt} students registered in the system."
            
    if response is None:
        response = (
            "I run entirely locally offline! Ask me questions like:\n"
            "- 'Show students with CGPA > 8.0'\n"
            "- 'List students with attendance below 75%'\n"
            "- 'How many students in CSE?'\n"
            "- 'Show students in AIML in 3rd year'"
        )
        
    conn.close()
    return jsonify({"response": response})

# --- Announcements Notice Board ---
@app.route('/post_notification', methods=['POST'])
def post_notification():
    if 'user_id' not in session or session.get('role') not in ['admin', 'faculty']:
        flash('Permission denied.', 'error')
        return redirect(url_for('dashboard'))
        
    title = request.form['title'].strip()
    message = request.form['message'].strip()
    role = session.get('role', 'faculty')
    target_role = 'student' if role == 'faculty' else 'All'
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    conn = get_db_connection()
    conn.execute('INSERT INTO notifications (title, message, date, target_role) VALUES (?, ?, ?, ?)',
                 (title, message, now_str, target_role))
    conn.commit()
    conn.close()
    
    flash('Announcement notice posted.', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
