import sqlite3
import os
import pandas as pd
import numpy as np
import re
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'student_database_secret_key' # In production, use a strong random key
DATABASE = 'database.db'

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
    # Create users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Create students table with expanded fields
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
            additional_info TEXT
        )
    ''')
    
    # Simple migration: check if new columns exist and add them if not
    cursor = conn.execute('PRAGMA table_info(students)')
    columns = [row['name'] for row in cursor.fetchall()]
    new_columns = [
        ('parent_name', 'TEXT'),
        ('parent_contact', 'TEXT'),
        ('address', 'TEXT'),
        ('additional_info', 'TEXT'),
        ('hobbies', 'TEXT'),
        ('parent_occupation', 'TEXT')
    ]
    for col_name, col_type in new_columns:
        if col_name not in columns:
            conn.execute(f'ALTER TABLE students ADD COLUMN {col_name} {col_type}')
    
    # Create a default admin user (admin / admin123)
    user = conn.execute('SELECT * FROM users WHERE username = ?', ('admin',)).fetchone()
    if not user:
        hashed_password = generate_password_hash('admin123')
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', ('admin', hashed_password))
    
    conn.commit()
    conn.close()
    print("Database initialized.")

# Initialize database
init_db()

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
    return render_template('dashboard.html')

# --- AI Helpers & Validation ---
def validate_student_data(data):
    errors = []
    # Name validation: should not contain numbers
    if any(char.isdigit() for char in data['name']):
        errors.append("Student name should not contain numbers.")
    # Email validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
        errors.append("Invalid email format.")
    # ID Duplicate check
    conn = get_db_connection()
    exists = conn.execute('SELECT 1 FROM students WHERE id = ?', (data['student_id'],)).fetchone()
    conn.close()
    if exists:
        errors.append(f"Student ID {data['student_id']} already exists.")
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

@app.route('/add', methods=['GET', 'POST'])
def add_student():
    if 'user_id' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        student_data = {
            'student_id': request.form['student_id'],
            'name': request.form['name'],
            'department': request.form['department'],
            'year': request.form['year'],
            'email': request.form['email']
        }
        
        errors = validate_student_data(student_data)
        if errors:
            for err in errors:
                flash(err, 'error')
        else:
            student_id = student_data['student_id']
            name = student_data['name']
            department = student_data['department']
            year = student_data['year']
            email = student_data['email']
            parent_name = request.form.get('parent_name')
            parent_contact = request.form.get('parent_contact')
            address = request.form.get('address')
            additional_info = request.form.get('additional_info')
            hobbies = request.form.get('hobbies')
            parent_occupation = request.form.get('parent_occupation')
            
            try:
                conn = get_db_connection()
                conn.execute('''
                    INSERT INTO students (
                        id, name, department, year, email, 
                        parent_name, parent_contact, address, additional_info,
                        hobbies, parent_occupation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, name, department, year, email, 
                      parent_name, parent_contact, address, additional_info,
                      hobbies, parent_occupation))
                conn.commit()
                conn.close()
                flash('Student added successfully!', 'success')
                return redirect(url_for('view_students'))
            except sqlite3.IntegrityError:
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
    
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    
    # Mock AI Analysis logic
    total_students = len(students)
    dept_stats = {}
    for student in students:
        dept = student['department']
        dept_stats[dept] = dept_stats.get(dept, 0) + 1
    
    top_dept = max(dept_stats, key=dept_stats.get) if dept_stats else "N/A"
    
    insights = {
        "summary": f"Our AI model analyzed {total_students} student records.",
        "trend": f"The most popular department is {top_dept}.",
        "recommendation": "Consider adding more resources to the IoT and AI sectors based on current enrollment trends.",
        "efficiency": "Student data entry efficiency is currently at 98.4%."
    }
    
    return render_template('ai_insights.html', insights=get_ai_analytics())

@app.route('/bot', methods=['GET', 'POST'])
def search_bot():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    response = None
    query = request.args.get('query', '').lower()
    
    if query:
        conn = get_db_connection()
        if "show all students" in query:
            students = conn.execute("SELECT * FROM students").fetchall()
            response = f"Found {len(students)} students in the system."
        elif "count" in query or "how many" in query:
            count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            response = f"There are currently {count} students registered."
        elif any(dept.lower() in query for dept in DEPARTMENTS):
            matched_dept = next(dept for dept in DEPARTMENTS if dept.lower() in query)
            students = conn.execute("SELECT * FROM students WHERE department = ?", (matched_dept,)).fetchall()
            response = f"There are {len(students)} students in {matched_dept}."
        else:
            response = "I can help you count students or find them by department. Try 'How many students?' or 'Show students in AIML'."
        conn.close()
        
    return render_template('chatbot.html', response=response, query=query)

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
        
    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, "OFFICIAL STUDENT REPORT", 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font("Helvetica", '', 12)
    pdf.cell(50, 10, f"Name: {student['name']}", 0, 1)
    pdf.cell(50, 10, f"ID: {student['id']}", 0, 1)
    pdf.cell(50, 10, f"Department: {student['department']}", 0, 1)
    pdf.cell(50, 10, f"Year: {student['year']}", 0, 1)
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
    
    # Base query
    query = 'SELECT * FROM students'
    params = []
    
    if search_query:
        query += ' WHERE id LIKE ? OR name LIKE ? OR department LIKE ?'
        params = [f'%{search_query}%', f'%{search_query}%', f'%{search_query}%']
    
    # Sorting
    if sort_by == 'id':
        query += ' ORDER BY id ASC'
    elif sort_by == 'department':
        query += ' ORDER BY department ASC'
    elif sort_by == 'year':
        query += ' ORDER BY year ASC'
    else:
        query += ' ORDER BY name ASC'
        
    all_students = conn.execute(query, params).fetchall()
    
    # Pagination logic
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
    conn.close()
    
    if student:
        return render_template('student_profile.html', student=student)
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
        parent_name = request.form.get('parent_name')
        parent_contact = request.form.get('parent_contact')
        address = request.form.get('address')
        additional_info = request.form.get('additional_info')
        
        hobbies = request.form.get('hobbies')
        parent_occupation = request.form.get('parent_occupation')
        
        conn.execute('''
            UPDATE students SET 
            name = ?, department = ?, year = ?, email = ?, 
            parent_name = ?, parent_contact = ?, address = ?, additional_info = ?,
            hobbies = ?, parent_occupation = ?
            WHERE id = ?
        ''', (name, department, year, email, 
              parent_name, parent_contact, address, additional_info,
              hobbies, parent_occupation, student_id))
        conn.commit()
        conn.close()
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

if __name__ == '__main__':
    app.run(debug=True)
