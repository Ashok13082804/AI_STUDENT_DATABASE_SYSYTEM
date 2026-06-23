import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
import sqlite3
import os

DATABASE = 'database.db'

class StudentPerformancePredictor:
    def __init__(self):
        self.model = DecisionTreeClassifier(max_depth=3, random_state=42)
        self.is_trained = False
        self.train_model()

    def train_model(self):
        """Train the model using data from the database, or mock data if there is not enough data."""
        attendance = []
        internal_marks = []
        cgpa = []
        passed = []

        # Try to pull from database enrollments and student details
        if os.path.exists(DATABASE):
            try:
                conn = sqlite3.connect(DATABASE)
                query = """
                    SELECT e.attendance_percentage, e.internal_marks, s.cgpa, e.exam_marks
                    FROM enrollments e
                    JOIN students s ON e.student_id = s.id
                """
                df = pd.read_sql_query(query, conn)
                conn.close()
                
                if len(df) >= 10:
                    X = df[['attendance_percentage', 'internal_marks', 'cgpa']].fillna(0).values
                    # Pass if exam marks >= 40 and internal marks >= 15
                    y = (df['exam_marks'].fillna(0) >= 40).astype(int).values
                    self.model.fit(X, y)
                    self.is_trained = True
                    return
            except Exception as e:
                print(f"Error reading from DB for ML model: {e}")

        # Fallback to Mock Training Data
        np.random.seed(42)
        # Generate 100 sample records
        # Columns: attendance (50-100), internal_marks (0-30), prev_cgpa (4-10)
        mock_attendance = np.random.uniform(60, 100, 100)
        mock_internals = np.random.uniform(10, 30, 100)
        mock_cgpa = np.random.uniform(5.0, 10.0, 100)
        
        # Rule: pass (1) if attendance >= 75 and internals >= 15 and cgpa >= 6.0
        # Otherwise, 20% chance of passing, 80% passing if metrics are good
        mock_passed = []
        for i in range(100):
            score = 0
            if mock_attendance[i] >= 75: score += 1
            if mock_internals[i] >= 15: score += 1
            if mock_cgpa[i] >= 6.0: score += 1
            
            prob = 0.1 if score <= 1 else (0.4 if score == 2 else 0.9)
            mock_passed.append(1 if np.random.random() < prob else 0)
            
        X = np.column_stack((mock_attendance, mock_internals, mock_cgpa))
        y = np.array(mock_passed)
        
        self.model.fit(X, y)
        self.is_trained = True

    def predict(self, attendance, internal_marks, cgpa):
        """Predict pass (True) or fail (False) and risk assessment."""
        if not self.is_trained:
            self.train_model()
            
        try:
            features = np.array([[float(attendance), float(internal_marks), float(cgpa)]])
            pred = self.model.predict(features)[0]
            prob = self.model.predict_proba(features)[0][1] # Probability of passing
            
            # Risk Level: High, Medium, Low
            if prob < 0.4 or float(attendance) < 75.0:
                risk = "High"
                recommendation = "Provide intensive mentoring. Require mandatory attendance counseling."
            elif prob < 0.75:
                risk = "Medium"
                recommendation = "Suggest remedial classes and practice assignments."
            else:
                risk = "Low"
                recommendation = "Student is performing well. Maintain current status."
                
            return {
                "pass_prediction": "Pass" if pred == 1 else "Fail",
                "pass_probability": round(prob * 100, 1),
                "risk_level": risk,
                "recommendation": recommendation
            }
        except Exception as e:
            return {
                "pass_prediction": "N/A",
                "pass_probability": 0.0,
                "risk_level": "Unknown",
                "recommendation": f"Error during prediction: {str(e)}"
            }

# Singleton instance
predictor = StudentPerformancePredictor()
