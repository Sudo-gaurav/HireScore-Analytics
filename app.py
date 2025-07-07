from flask import Flask, render_template, request
from dotenv import load_dotenv
import pdfplumber
import google.generativeai as genai
import os 
import re

# Load .env file
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Extract text from a PDF file
def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf: 
        for page in pdf.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"
    return text

# Use Gemini to analyze resume
def analyze_resume_with_gemini(resume_text, job_description):
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = f"""
You are an AI resume reviewer.

Here is a job description:

{job_description}

And here is a candidate's resume:

{resume_text}

🔍 Analyze how well the resume matches the job description.

✅ Provide a clear match percentage on a separate line, in the exact format:

Match percentage: XX%

📌 List missing or weak areas
📈 Suggest improvements to make the resume more aligned with the job
🎯 Highlight the strongest matching points
⚠️ Identify any red flags or concerns
"""
    response = model.generate_content(prompt)
    return response.text

# Generate comparison analysis for multiple resumes
def generate_comparison_analysis(results, job_description):
    if len(results) <= 1:
        return None
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Prepare resume summaries for comparison
    resume_summaries = []
    for i, result in enumerate(results, 1):
        resume_summaries.append(f"Resume {i} ({result['filename']}): Match Score {result['match_score']}%")
    
    prompt = f"""
You are comparing multiple resumes for this job description:

{job_description}

Resume match scores:
{chr(10).join(resume_summaries)}

🏆 RANKING ANALYSIS:
1. Rank these resumes from best to worst match
2. Explain WHY each resume ranks where it does
3. Identify the TOP 3 strengths of the best resume
4. Identify the TOP 3 weaknesses of the worst resume
5. Give specific recommendations for the hiring manager

Provide a clear, actionable comparison that helps with hiring decisions.
"""
    
    response = model.generate_content(prompt)
    return response.text

# Extract match score from Gemini response
def extract_match_score(text):
    match = re.search(r"match percentage[:\s]*([0-9]{1,3})%", text, re.IGNORECASE)
    if match:
        score = int(match.group(1))
        return max(0, min(score, 100))
    return None

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Analyze route (multiple resume support)
@app.route('/analyze', methods=['POST'])
def analyze():
    resumes = request.files.getlist('resume')  
    job_desc = request.form['job_desc']

    results = []

    for resume in resumes:
        if resume.filename:  # Check if file was actually uploaded
            filename = resume.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume.save(file_path)

            resume_text = extract_text_from_pdf(file_path)
            ai_feedback = analyze_resume_with_gemini(resume_text, job_desc)
            match_score = extract_match_score(ai_feedback)

            results.append({
                'filename': filename,
                'resume_text': resume_text,
                'ai_feedback': ai_feedback,
                'match_score': match_score or 0
            })

    # Sort results by match score (highest first)
    results.sort(key=lambda x: x['match_score'], reverse=True)
    
    # Generate comparison analysis if multiple resumes
    comparison_analysis = generate_comparison_analysis(results, job_desc)

    return render_template('result.html', 
                         job_desc=job_desc, 
                         results=results,
                         comparison_analysis=comparison_analysis,
                         total_resumes=len(results))

if __name__ == '__main__':
    app.run(debug=True)