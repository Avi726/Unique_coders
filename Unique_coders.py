import base64
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from gtts import gTTS
import pymysql
import speech_recognition as sr
import mysql.connector
from werkzeug.utils import secure_filename
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os
import wave
import pyttsx3

def generate_audio(question_text, tts_path):
    engine = pyttsx3.init()
    engine.save_to_file(question_text, tts_path)
    engine.runAndWait()

recognizer = sr.Recognizer()

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Abhi123",
    database="login"
)
cursor = db.cursor()

# Initialize the Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'wav', 'mp3', 'flac'}
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:Abhi123@localhost/login'
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)

# Admin table model
class Admin(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

# User table model
class User(db.Model):
    __tablename__ = 'form'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    
    scores = db.relationship('Score', backref='user', lazy=True)
    interview_answers = db.relationship('InterviewAnswer', backref='user', lazy=True)

# Score table model
class Score(db.Model):
    __tablename__ = 'scores'
    user_id = db.Column(db.Integer, db.ForeignKey('form.id'), primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<Score {self.username} - {self.score}>'

# MCQ Question table model
class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(100), nullable=False)  # Added topic field
    question = db.Column(db.String(255), nullable=False)
    a = db.Column(db.String(55), nullable=False)
    b = db.Column(db.String(55), nullable=False)
    c = db.Column(db.String(55), nullable=False)
    d = db.Column(db.String(55), nullable=False)
    ans = db.Column(db.String(1), nullable=False)

    def __repr__(self):
        return f'<Question {self.id}: {self.question}>'

# Interview Question table model
class InterviewQuestion(db.Model):
    __tablename__ = 'interview_questions'
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(100), nullable=False)  # Added topic field
    question_text = db.Column(db.String(255), nullable=False)
    
    interview_answers = db.relationship('InterviewAnswer', backref='interview_question', lazy=True)

# Interview Answer table model
class InterviewAnswer(db.Model):
    __tablename__ = 'interview_answers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('form.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('interview_questions.id'), nullable=False)
    answer = db.Column(db.Text, nullable=False)

# Helper function to check allowed file types
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Admin login route
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Query the admin table for the admin credentials
        admin = Admin.query.filter_by(username=username, password=password).first()

        if admin:
            session['admin_logged_in'] = True
            return redirect(url_for('home'))  # Redirect to home.html
        else:
            return render_template('admin.html', message="Invalid username or password.")

    return render_template('admin.html')

# Home page route after admin login
@app.route('/home')
def home():
    if 'admin_logged_in' in session:
        return render_template('home.html')
    else:
        return redirect(url_for('admin_login'))

# View candidate details route
@app.route('/candidate_details')
def candidate_details():
    if 'admin_logged_in' in session:
        candidates = User.query.all()
        return render_template('candidate_details.html', candidates=candidates)
    else:
        return redirect(url_for('admin_login'))

# View candidate scores route
@app.route('/candidate_scores')
def candidate_scores():
    if 'admin_logged_in' in session:
        scores = Score.query.all()
        return render_template('candidate_scores.html', scores=scores)
    else:
        return redirect(url_for('admin_login'))

# View interview marks route (assuming Interview model exists)
@app.route('/interview_marks')
def interview_marks():
    if 'admin_logged_in' in session:
        # Assuming you have a table to store interview marks
        interview_marks = InterviewAnswer.query.all()  # Modify as per actual structure
        return render_template('interview_marks.html', interview_marks=interview_marks)
    else:
        return redirect(url_for('admin_login'))

# Logout route
@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# Change password route
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        username = request.form['username']
        current_password = request.form['current_password']
        new_password = request.form['new_password']

        # Fetch user from the database
        user = User.query.filter_by(username=username, password=current_password).first()

        if user:
            # Update password
            user.password = new_password
            db.session.commit()
            return render_template('cng_pswd.html', message="Password successfully changed.")
        else:
            return render_template('cng_pswd.html', message="Invalid username or current password.")

    return render_template('cng_pswd.html')

# User login route
@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('main'))
        else:
            return render_template('index.html', message="Invalid username or password.")
        
    return render_template('index.html')

# Main user dashboard
@app.route('/main')
def main():
    message = request.args.get('message', None)
    return render_template('main.html', message=message)

# Register route
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        # Get the form data from the registration page
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Check if the username or email already exists in the database
        existing_user = User.query.filter_by(username=username).first()
        existing_email = User.query.filter_by(email=email).first()

        if existing_user:
            return "Username already exists. Please choose a different one."
        if existing_email:
            return "Email already exists. Please use a different email address."

        # Create a new user instance
        new_user = User(username=username, password=password, email=email)
        
        try:
            # Add the new user to the database
            cursor.execute("INSERT INTO form (username, password, email) VALUES (%s, %s, %s)", 
                           (username, password, email))
            db.commit()

            # After successful registration, redirect to the login page
            return redirect(url_for('index'))

        except Exception as e:
            return "An error occurred during registration: " + str(e)

    # Render the registration page (GET request)
    return render_template('register.html')

# Route for checking eligibility for interview
@app.route('/check_interview_eligibility')
def check_interview_eligibility():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user_id = session['user_id']

    # Check if user has a score entry
    score_entry = Score.query.filter_by(user_id=user_id).first()

    if not score_entry:
        # If no score entry found for the user
        message = "You are not eligible for interview. Please complete the MCQ test."
        return render_template('main.html', message=message)

    # If the user's score is less than 5
    if score_entry.score < 5:
        message = "You are not eligible for interview. Your score is too low."
        return render_template('main.html', message=message)
    
    # If eligible, redirect to the interview page
    return redirect(url_for('interview'))

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Abhi123",
    database="login"
)
cursor = db.cursor()

# MySQL connection setup
def create_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Abhi123",
        database="login"
    )

# Route for MCQ Question Paper
@app.route('/mcq-question-paper', methods=['GET', 'POST'])
def mcq_question_paper():
    if 'user_id' not in session or 'username' not in session:
        return redirect(url_for('index'))
    
    # Get the user_id and username from the session
    user_id = session.get('user_id')
    username = session.get('username')

    # Create a new database connection
    db = create_connection()
    cursor = db.cursor(dictionary=True)

    # Check if the user has already taken the test
    cursor.execute("SELECT * FROM scores WHERE user_id = %s", (user_id,))
    existing_score = cursor.fetchone()

    if existing_score:
        # If the user has already taken the test, render a message
        return render_template('result.html', message="You can only give the test once. Your marks are already saved and cannot be changed.", score=existing_score.score, total_questions="N/A")

    if request.method == 'POST':
        score = 0
        total_questions = 0

        # Fetch all MCQ questions
        questions = Question.query.all()
        for q in questions:
            user_answer = request.form.get(f'q{q.id}')
            if user_answer == q.ans:
                score += 1
            total_questions += 1

        # Store the score in the database
        cursor.execute("INSERT INTO scores (user_id, username, score) VALUES (%s, %s, %s)", (user_id, username, score))
        db.commit()

        return render_template('result.html', score=score, total_questions=total_questions)
    
    # Fetch 10 random questions from the database
    cursor.execute("SELECT * FROM questions ORDER BY RAND() LIMIT 10")
    questions = cursor.fetchall()

    # Close cursor and connection
    cursor.close()
    db.close()
    return render_template('mcq.html', questions=questions)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Abhi123",
    database="login"
)
cursor = db.cursor()

# Get all questions from the MySQL table
def get_questions_from_db():
    cursor.execute("SELECT id, question_text FROM interview_questions")
    questions = cursor.fetchall()
    cursor.close()
    return questions

def fetch_interview_questions():
    cursor = db.cursor()
    cursor.execute("SELECT * FROM interview_questions")
    questions = cursor.fetchall()
    cursor.close()
    return questions

@app.route('/interview', methods=['GET', 'POST'])
def interview():
    if 'user_id' not in session or 'username' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']

    # Check if the user has already submitted the interview
    if session.get('interview_submitted'):
        return redirect(url_for('thank_you'))

    if request.method == 'POST':
        # Process the interview answers and save them to the database
        questions = fetch_interview_questions()  # Replace with your function to fetch questions

        for question in questions:
            answer = request.form.get(f'answer_{question.id}')
            if answer:
                # Save the answer to the interview_answers table
                cursor.execute(
                    "INSERT INTO interview_answers (user_id, question_id, answer) VALUES (%s, %s, %s)",
                    (user_id, question.id, answer)
                )

        # Commit the changes to the database
        db.commit()

        # After processing, set the flag in the session
        session['interview_submitted'] = True

        return redirect(url_for('thank_you'))

    # Render the interview questions
    questions = fetch_interview_questions()  # Replace with your function to fetch questions
    return render_template('interview.html', questions=questions)

import os
from gtts import gTTS

@app.route('/get_question', methods=['GET'])
def get_question():
    question_id = request.args.get('id', default=1, type=int)

    # Fetch the question from the interview_questions table
    cursor = db.cursor()
    cursor.execute("SELECT question_text FROM interview_questions WHERE id = %s", (question_id,))
    question = cursor.fetchone()

    if question:
        question_text = question[0]

        # Generate the audio for the question using gTTS
        tts = gTTS(text=question_text, lang='en')
        audio_dir = "static/audio/"
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)

        tts_path = os.path.join(audio_dir, f"question_{question_id}.mp3")
        tts.save(tts_path)

        return jsonify({'question': question_text, 'tts_path': tts_path}), 200
    else:
        return jsonify({'error': 'Question not found'}), 404

import speech_recognition as sr

# Function to handle database connection
def get_db_connection():
    connection = pymysql.connect(
        host='localhost',
        user='root',
        password='Abhi123',
        database='login'
    )
    return connection

# Function to process audio recording
@app.route('/process_audio', methods=['POST'])
def process_audio():
    audio_data = request.form.get('audio_data')
    question_id = request.form.get('question_id')

    if audio_data:
        # Decode the Base64 encoded audio data
        audio_bytes = base64.b64decode(audio_data)
        
        # Save the audio file on the server (could also store in the database)
        audio_file_path = os.path.join('static', 'recordings', 'user_audio.wav')
        with open(audio_file_path, 'wb') as audio_file:
            audio_file.write(audio_bytes)

        # You can store the file path in the database if needed
        connection = get_db_connection()
        with connection.cursor() as cursor:
            user_id = 1  # Replace with actual user ID
            sql = "INSERT INTO interview_answers (user_id, question_id, answer) VALUES (%s, %s, %s)"
            cursor.execute(sql, (user_id, request.form['question_id'], audio_file_path))
            connection.commit()
        connection.close()

        return redirect(url_for('interview'))
    else:
        return "No audio data received", 400

@app.route('/speak_question/<int:question_id>')
def speak_question(question_id):
    cursor.execute("SELECT question_text FROM interview_questions WHERE id = %s", (question_id,))
    question = cursor.fetchone()
    if question:
        tts = gTTS(text=question[0], lang='en')
        audio_file = f"static/question_{question_id}.mp3"
        tts.save(audio_file)
        return audio_file
    return "Question not found", 404

def get_current_question():
    # Logic to get the current question
    return {"id": 1, "question_text": "What is your greatest strength?"}
    
# Helper function to determine related topics based on user's answer
def get_related_topics(answer_text):
    # Simple keyword-based topic extraction
    # In a real scenario, use NLP techniques or a pre-trained model
    topics = set()
    keywords = {
        'python': 'Programming',
        'java': 'Programming',
        'database': 'Databases',
        'sql': 'Databases',
        'machine learning': 'AI',
        'deep learning': 'AI',
        'networking': 'Networking',
        'security': 'Cybersecurity',
        # Add more keywords and corresponding topics as needed
    }
    for word, topic in keywords.items():
        if word.lower() in answer_text.lower():
            topics.add(topic)
    return topics

# Route to save interview answers
@app.route('/save_interview_answer', methods=['POST'])
def save_interview_answer():
    data = request.get_json()
    user_id = session.get('user_id')
    interviewer = data.get('interviewer')
    question_index = data.get('question_index')
    answer = data.get('answer')

    if not all([user_id, interviewer, question_index, answer]):
        return jsonify({'message': 'Missing data'}), 400

    # Save the answer to the database
    question_id = InterviewQuestion.query.filter_by(id=question_index).first().id
    new_answer = InterviewAnswer(user_id=user_id, question_id=question_id, answer=answer)
    db.session.add(new_answer)
    db.session.commit()

    # Get all questions from the database
    all_questions = InterviewQuestion.query.all()

    # Determine related questions using ML algorithm
    next_questions = calculate_similarity(answer, all_questions)

    # Serialize the questions for frontend
    questions_data = [{"id": q.id, "question_text": q.question_text} for q in next_questions]

    return jsonify({'message': 'Answer saved successfully!', 'next_questions': questions_data})

def calculate_similarity(user_answer, questions):
    """Calculate cosine similarity between user's answer and available questions."""
    documents = [user_answer] + [q.question_text for q in questions]
    tfidf = TfidfVectorizer().fit_transform(documents)
    cosine_similarities = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()

    # Sort questions based on cosine similarity
    ranked_questions = sorted(zip(questions, cosine_similarities), key=lambda x: x[1], reverse=True)
    return [q[0] for q in ranked_questions[:4]]  # Return top 4 related questions

import os

# Directory to save audio files
SAVE_DIRECTORY = 'static\audio_files'

@app.route('/save_audio', methods=['POST'])
def save_audio():
    if 'audio' not in request.files:
        return 'No audio file uploaded', 400

    audio_file = request.files['audio']
    
    # Ensure the directory exists
    if not os.path.exists(SAVE_DIRECTORY):
        os.makedirs(SAVE_DIRECTORY)

    # Generate the full file path
    file_path = os.path.join(SAVE_DIRECTORY, 'recording.wav')
    
    # Save the audio file
    audio_file.save(file_path)

    # Convert audio to text (your existing code here)
    return 'Audio saved and processed', 200

@app.route('/start_question/<int:question_id>', methods=['GET'])
def start_question(question_id):
    cursor.execute("SELECT question_text FROM interview_questions WHERE id = %s", (question_id,))
    question = cursor.fetchone()
    if question:
        question_text = question[0]
        tts = gTTS(text=question_text, lang='en')
        audio_path = f'static/audio/question_{question_id}.mp3'
        tts.save(audio_path)
        return jsonify({'audio_path': audio_path, 'question_text': question_text})
    return jsonify({'error': 'Question not found'}), 404

@app.route('/save_answer', methods=['POST'])
def save_answer():
    user_id = request.form['user_id']  # Assuming user_id is passed in the form
    question_id = request.form['question_id']
    answer_text = request.form['answer_text']
    
    # Save the answer to the database (create the interview_answers table if it doesn't exist)
    cursor.execute("INSERT INTO interview_answers (user_id, question_id, answer) VALUES (%s, %s, %s)",
                   (user_id, question_id, answer_text))
    db.commit()
    
    return "Answer saved!", 200

@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')

# Start the Flask app
if __name__ == '__main__':
    app.run(debug=True)
