from dotenv import load_dotenv
import os

load_dotenv()

from flask import Flask, render_template, jsonify, request, session
import os, json, csv, base64, time, logging, requests, subprocess, shutil
from pathlib import Path
import html
from datetime import datetime
import re
from collections import Counter
import statistics
import urllib.parse


# -------------------- CONFIG --------------------
app = Flask(__name__)
app.secret_key = 'interviewai_secret_key_2024'
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("interviewai")

# Add custom Jinja2 filters
@app.template_filter('escapejs')
def escapejs_filter(s):
    """Escape string for JavaScript"""
    if s is None:
        return ''
    return html.escape(str(s)).replace("'", "\\'").replace('"', '\\"')

ROOT = Path(__file__).parent
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
DATASETS_DIR = ROOT / "datasets"
QUESTIONS_CSV = DATASETS_DIR / "questions.csv"
COUNSELLOR_CSV = DATASETS_DIR / "counsellor_qa.csv"

# Job roles for practice page
job_roles = [
    'Software Engineer', 'Data Scientist', 'DevOps Engineer', 'Product Manager',
    'UI/UX Designer', 'QA Engineer', 'AI/ML Researcher', 'Technical Support',
    'Cybersecurity Analyst', 'Cloud Architect', 'Business Analyst', 'System Administrator',
    'Mobile App Developer', 'Game Developer', 'Embedded Engineer', 'Mechanical Engineer',
    'Civil Engineer', 'Electrical Engineer', 'HR Specialist', 'Marketing Manager',
    'Finance Analyst', 'Content Writer', 'Customer Support Executive', 'Sales Executive'
]

# -------------------- PERFORMANCE ANALYTICS --------------------
class PerformanceAnalyzer:
    def __init__(self):
        self.filler_words = ['um', 'uh', 'ah', 'like', 'you know', 'actually', 'basically', 'literally']
        self.positive_words = ['achieved', 'success', 'improved', 'optimized', 'developed', 'led', 'managed', 'created']
        self.negative_words = ['failed', 'problem', 'issue', 'challenge', 'difficult', 'struggled']
    
    def analyze_speech_clarity(self, transcript):
        """Analyze speech clarity and filler words"""
        words = transcript.lower().split()
        total_words = len(words)
        
        if total_words == 0:
            return {'clarity_score': 0, 'filler_count': 0, 'filler_percentage': 0}
        
        filler_count = sum(1 for word in words if word in self.filler_words)
        filler_percentage = (filler_count / total_words) * 100
        
        # Calculate clarity score (0-100)
        clarity_score = max(0, 100 - (filler_percentage * 2))
        
        return {
            'clarity_score': round(clarity_score, 1),
            'filler_count': filler_count,
            'filler_percentage': round(filler_percentage, 1),
            'total_words': total_words
        }
    
    def analyze_pace(self, transcript, duration_seconds):
        """Analyze speaking pace"""
        words = transcript.split()
        word_count = len(words)
        
        if duration_seconds == 0:
            return {'pace_wpm': 0, 'pace_score': 0}
        
        words_per_minute = (word_count / duration_seconds) * 60
        
        # Ideal pace: 130-170 WPM
        if 130 <= words_per_minute <= 170:
            pace_score = 100
        elif words_per_minute < 100:
            pace_score = max(0, (words_per_minute / 100) * 100)
        else:
            pace_score = max(0, 100 - ((words_per_minute - 170) / 2))
        
        return {
            'pace_wpm': round(words_per_minute, 1),
            'pace_score': round(pace_score, 1),
            'ideal_range': '130-170 WPM'
        }
    
    def analyze_content_quality(self, transcript, question):
        """Analyze content relevance and quality"""
        words = transcript.lower().split()
        positive_count = sum(1 for word in words if word in self.positive_words)
        negative_count = sum(1 for word in words if word in self.negative_words)
        
        # Calculate relevance score based on question keywords
        question_keywords = set(question.lower().split())
        answer_keywords = set(words)
        matching_keywords = question_keywords.intersection(answer_keywords)
        relevance_score = min(100, (len(matching_keywords) / max(1, len(question_keywords))) * 100)
        
        # Structure analysis (check for STAR method indicators)
        star_indicators = ['situation', 'task', 'action', 'result', 'achieved', 'outcome']
        star_score = sum(1 for indicator in star_indicators if indicator in words) / len(star_indicators) * 100
        
        return {
            'relevance_score': round(relevance_score, 1),
            'positive_words': positive_count,
            'negative_words': negative_count,
            'star_score': round(star_score, 1),
            'matching_keywords': list(matching_keywords)
        }
    
    def calculate_overall_score(self, analysis_results):
        """Calculate overall performance score"""
        weights = {
            'clarity': 0.3,
            'pace': 0.25,
            'relevance': 0.3,
            'star_structure': 0.15
        }
        
        overall_score = (
            analysis_results['clarity']['clarity_score'] * weights['clarity'] +
            analysis_results['pace']['pace_score'] * weights['pace'] +
            analysis_results['content']['relevance_score'] * weights['relevance'] +
            analysis_results['content']['star_score'] * weights['star_structure']
        )
        
        return round(overall_score, 1)

# Initialize performance analyzer
performance_analyzer = PerformanceAnalyzer()

# -------------------- INTERVIEW CUSTOMIZATION --------------------
interview_difficulty_levels = {
    'beginner': {
        'name': 'Beginner',
        'description': 'Basic questions focusing on fundamentals',
        'time_limit': 120,
        'question_types': ['behavioral', 'basic_technical']
    },
    'intermediate': {
        'name': 'Intermediate',
        'description': 'Moderate questions with scenario-based challenges',
        'time_limit': 90,
        'question_types': ['behavioral', 'technical', 'situational']
    },
    'advanced': {
        'name': 'Advanced',
        'description': 'Complex questions with real-world problem solving',
        'time_limit': 60,
        'question_types': ['technical', 'case_study', 'leadership']
    },
    'expert': {
        'name': 'Expert',
        'description': 'Executive-level questions with strategic thinking',
        'time_limit': 45,
        'question_types': ['strategic', 'leadership', 'business_case']
    }
}

interview_focus_areas = {
    'technical': 'Technical skills and problem-solving',
    'behavioral': 'Behavioral and situational questions',
    'leadership': 'Leadership and management skills',
    'culture_fit': 'Company culture alignment',
    'mixed': 'Balanced mix of all areas'
}

# -------------------- GAMIFICATION & PROGRESSION --------------------
class GamificationSystem:
    def __init__(self):
        self.levels = {
            1: {'name': 'Rookie', 'points_required': 0, 'badge': '🎯'},
            2: {'name': 'Trainee', 'points_required': 100, 'badge': '🌟'},
            3: {'name': 'Specialist', 'points_required': 300, 'badge': '🚀'},
            4: {'name': 'Expert', 'points_required': 600, 'badge': '🏆'},
            5: {'name': 'Master', 'points_required': 1000, 'badge': '👑'}
        }
        
        self.achievements = {
            'first_interview': {'name': 'First Steps', 'description': 'Complete your first interview', 'points': 50},
            'perfect_score': {'name': 'Perfectionist', 'description': 'Achieve 100% score in an interview', 'points': 100},
            'speed_demon': {'name': 'Speed Demon', 'description': 'Complete interview in half the time', 'points': 75},
            'consistency': {'name': 'Consistent', 'description': 'Complete 5 interviews', 'points': 150},
            'versatile': {'name': 'Versatile', 'description': 'Try 3 different job roles', 'points': 100},
            'clarity_master': {'name': 'Clear Speaker', 'description': 'Achieve 95%+ clarity score', 'points': 80}
        }
    
    def calculate_points(self, performance_score, duration_seconds, questions_answered):
        """Calculate points earned from interview performance"""
        base_points = performance_score * 0.5  # 0.5 points per percentage
        time_bonus = max(0, 50 - (duration_seconds / 60))  # Bonus for faster completion
        completion_bonus = questions_answered * 10  # 10 points per question
        
        return int(base_points + time_bonus + completion_bonus)
    
    def check_level_up(self, current_points, new_points):
        """Check if user leveled up"""
        current_level = self.get_current_level(current_points)
        new_level = self.get_current_level(current_points + new_points)
        
        if new_level > current_level:
            return self.levels[new_level]
        return None
    
    def get_current_level(self, points):
        """Get current level based on points"""
        for level, data in sorted(self.levels.items(), reverse=True):
            if points >= data['points_required']:
                return level
        return 1
    
    def check_achievements(self, user_stats, new_interview_data):
        """Check for new achievements unlocked"""
        unlocked = []
        
        # Check first interview
        if user_stats['total_interviews'] == 1 and 'first_interview' not in user_stats['achievements']:
            unlocked.append(self.achievements['first_interview'])
        
        # Check perfect score
        if new_interview_data['performance_score'] >= 100 and 'perfect_score' not in user_stats['achievements']:
            unlocked.append(self.achievements['perfect_score'])
        
        # Check speed demon (completed in half the time)
        if (new_interview_data['duration'] < new_interview_data['time_limit'] / 2 and 
            'speed_demon' not in user_stats['achievements']):
            unlocked.append(self.achievements['speed_demon'])
        
        return unlocked

# Initialize gamification system
gamification_system = GamificationSystem()

# -------------------- LEARNING RESOURCES --------------------
learning_resources = {
    'answer_frameworks': {
        'STAR': {
            'name': 'STAR Method',
            'description': 'Situation, Task, Action, Result - Perfect for behavioral questions',
            'template': """Situation: Describe the context and situation
Task: Explain your responsibility or goal
Action: Detail the specific actions you took
Result: Share the outcomes and what you learned""",
            'examples': [
                "Tell me about a time you faced a challenge",
                "Describe a project you're proud of",
                "Share an example of leadership"
            ]
        },
        'SOAR': {
            'name': 'SOAR Method',
            'description': 'Situation, Obstacle, Action, Result - Focus on overcoming obstacles',
            'template': """Situation: Set the scene
Obstacle: Describe the specific challenge
Action: Explain how you addressed it
Result: Share the positive outcome""",
            'examples': [
                "How do you handle difficult situations?",
                "Tell me about a time you failed",
                "Describe a conflict resolution"
            ]
        },
        'CARE': {
            'name': 'CARE Method',
            'description': 'Context, Action, Result, Evaluation - Great for technical questions',
            'template': """Context: Technical background and requirements
Action: Your approach and implementation
Result: Technical outcomes and metrics
Evaluation: Lessons learned and improvements""",
            'examples': [
                "Explain a technical project",
                "Describe your coding process",
                "How do you solve complex problems?"
            ]
        }
    },
    'industry_terminology': {
        'Software Engineer': [
            'Agile methodology', 'CI/CD pipeline', 'Microservices architecture', 'Test-driven development',
            'Code review', 'Version control', 'API design', 'System scalability', 'Performance optimization'
        ],
        'Data Scientist': [
            'Machine learning', 'Data preprocessing', 'Feature engineering', 'Model validation',
            'A/B testing', 'Statistical significance', 'Data visualization', 'Predictive modeling'
        ],
        'Product Manager': [
            'Product roadmap', 'User stories', 'MVP (Minimum Viable Product)', 'KPI metrics',
            'Stakeholder management', 'Market research', 'Competitive analysis', 'User experience'
        ]
    },
    'common_followups': [
        "Can you tell me more about that?",
        "What would you do differently next time?",
        "How did you measure success?",
        "What was your specific contribution?",
        "How did you handle team dynamics?",
        "What challenges did you face?"
    ]
}

# -------------------- KEY LOADER --------------------
def _load_keys():
    hf = os.environ.get('HUGGINGFACE_API_KEY')
    gem = os.environ.get('GEMINI_API_KEY')
    deepseek_key = os.environ.get('DEEPSEEK_API_KEY')
    groq_key = os.environ.get('GROQ_API_KEY')
    
    keys_file = ROOT / "keys.json"
    if keys_file.exists():
        try:
            data = json.loads(keys_file.read_text(encoding='utf-8'))
            hf = hf or data.get('huggingface_api_key')
            gem = gem or data.get('gemini_api_key')
            deepseek_key = deepseek_key or data.get('deepseek_api_key')
            groq_key = groq_key or data.get('groq_api_key')
        except Exception as e:
            log.warning("Failed to read keys.json: %s", e)
    
    return {
        'huggingface': hf, 
        'gemini': gem,
        'deepseek': deepseek_key,
        'groq': groq_key
    }

# -------------------- LOAD QUESTIONS --------------------
def load_questions():
    qs = []
    if QUESTIONS_CSV.exists():
        try:
            with open(QUESTIONS_CSV, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Handle different column names
                    career = row.get('career') or row.get('role') or row.get('job_role') or 'General'
                    question = row.get('question') or row.get('interview_question') or ''
                    if question.strip():  # Only add if question is not empty
                        qs.append({
                            'career': career.strip(),
                            'question': question.strip()
                        })
            log.info(f"✅ Loaded {len(qs)} questions from CSV")
        except Exception as e:
            log.error(f"❌ Error reading questions CSV: {e}")
            # Fallback to sample questions
            qs = [
                {'career': 'Software Engineer', 'question': 'Tell me about yourself and your background.'},
                {'career': 'Software Engineer', 'question': 'What programming languages are you most comfortable with?'},
                {'career': 'Software Engineer', 'question': 'Describe a challenging project you worked on.'},
                {'career': 'Data Scientist', 'question': 'Explain the bias-variance tradeoff.'},
                {'career': 'Data Scientist', 'question': 'How do you handle missing data in a dataset?'},
                {'career': 'Product Manager', 'question': 'How do you prioritize features in a product?'}
            ]
    else:
        log.warning("❌ Questions CSV not found, using sample questions")
        qs = [
            {'career': 'Software Engineer', 'question': 'Tell me about yourself and your background.'},
            {'career': 'Software Engineer', 'question': 'What programming languages are you most comfortable with?'},
            {'career': 'Data Scientist', 'question': 'Explain the bias-variance tradeoff.'},
            {'career': 'Product Manager', 'question': 'How do you prioritize features in a product?'}
        ]
    return qs

# -------------------- IMPROVED COUNSELLOR DATASET FUNCTIONS --------------------
def load_counsellor_qa():
    """Load counsellor questions and answers from CSV with better matching"""
    qa_pairs = []
    if COUNSELLOR_CSV.exists():
        try:
            with open(COUNSELLOR_CSV, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    question = row.get('question', '').strip()
                    answer = row.get('answer', '').strip()
                    if question and answer:
                        qa_pairs.append({
                            'question': question,
                            'answer': answer
                        })
            log.info(f"✅ Loaded {len(qa_pairs)} counsellor Q&A pairs from CSV")
        except Exception as e:
            log.error(f"❌ Error reading counsellor CSV: {e}")
            qa_pairs = get_fallback_qa_pairs()
    else:
        log.warning("❌ Counsellor CSV not found, using fallback Q&A")
        qa_pairs = get_fallback_qa_pairs()
    
    return qa_pairs

def get_fallback_qa_pairs():
    """Comprehensive fallback Q&A pairs with improved matching"""
    return [
        {'question': 'what should i study', 'answer': 'Consider your interests, strengths, and career goals. Popular fields include Computer Science, Business, Healthcare, and Engineering. Think about what subjects you enjoy and what career opportunities interest you.'},
        {'question': 'career guidance', 'answer': 'I can help you explore career options based on your skills and interests. Tell me about your strengths, what you enjoy doing, and what kind of work environment you prefer.'},
        {'question': 'i feel stressed', 'answer': 'Student stress is common. Try breaking tasks into smaller steps, practice time management, make sure to take breaks, exercise regularly, and talk to someone you trust. Remember to prioritize self-care.'},
        {'question': 'which programming language should i learn', 'answer': 'For beginners: Python is great for its simplicity. For web development: JavaScript. For mobile apps: Swift (iOS) or Kotlin (Android). For systems programming: C++ or Rust. Choose based on your goals!'},
        {'question': 'how to improve grades', 'answer': 'Develop consistent study habits, attend all classes, seek help when needed, form study groups, practice active learning techniques, and make sure to get enough sleep and exercise.'},
        {'question': 'how to improve my study habits', 'answer': 'Create a study schedule, find a quiet space, take regular breaks, use active learning techniques like summarizing and teaching others, stay organized, and eliminate distractions. Try the Pomodoro technique: 25 minutes focused study, 5-minute break.'},
        {'question': 'improve study habits', 'answer': 'Create a study schedule, find a quiet space, take regular breaks, use active learning techniques like summarizing and teaching others, stay organized, and eliminate distractions. Try the Pomodoro technique: 25 minutes focused study, 5-minute break.'},
        {'question': 'better study habits', 'answer': 'Create a study schedule, find a quiet space, take regular breaks, use active learning techniques like summarizing and teaching others, stay organized, and eliminate distractions. Try the Pomodoro technique: 25 minutes focused study, 5-minute break.'},
        {'question': 'study habits', 'answer': 'Create a study schedule, find a quiet space, take regular breaks, use active learning techniques like summarizing and teaching others, stay organized, and eliminate distractions. Try the Pomodoro technique: 25 minutes focused study, 5-minute break.'},
        {'question': 'i\'m feeling stressed about exams', 'answer': 'Exam stress is normal. Try breaking your study material into manageable chunks, practice relaxation techniques like deep breathing, get enough sleep, eat well, and remember to take regular breaks. You can do this!'},
        {'question': 'what career should i choose', 'answer': 'Consider your interests, skills, and values. Think about what activities you enjoy, what you\'re good at, and what kind of work environment you prefer. Research different careers and talk to people in those fields.'},
        {'question': 'how to manage time better', 'answer': 'Use a planner or digital calendar, prioritize tasks using the Eisenhower Matrix, break large tasks into smaller steps, eliminate distractions, set specific time blocks, and learn to say no to non-essential activities.'},
        {'question': 'i need motivation', 'answer': 'Set clear, achievable goals. Break them into small steps and celebrate your progress. Find your "why" - remember why this is important to you. Create a routine, find an accountability partner, and track your progress.'},
        {'question': 'should i go to college', 'answer': 'College provides education and networking opportunities, but also consider trade schools, online courses, or bootcamps based on your career goals. Think about your learning style and financial situation.'},
        {'question': 'how to choose a major', 'answer': 'Consider your interests, career goals, job market demand, and earning potential. Talk to academic advisors, professionals in the field, and current students. Remember many people change careers multiple times.'},
        {'question': 'i feel overwhelmed', 'answer': 'It\'s okay to feel overwhelmed. Break things down into smaller tasks, prioritize what\'s most important, ask for help when needed, and remember to take care of your basic needs like sleep and nutrition.'},
        {'question': 'how to prepare for interviews', 'answer': 'Research the company, practice common questions, prepare examples of your achievements, dress appropriately, arrive early, and remember to ask thoughtful questions about the role and company.'},
        {'question': 'what skills are in demand', 'answer': 'Currently in demand: digital literacy, data analysis, programming, AI/ML skills, digital marketing, project management, communication skills, and adaptability. Focus on both technical and soft skills.'},
        {'question': 'how to write a good resume', 'answer': 'Use a clean format, highlight achievements with metrics, tailor it to each job, include relevant keywords, keep it concise (1-2 pages), and proofread carefully for errors.'},
        {'question': 'career change advice', 'answer': 'Research your target industry, identify transferable skills, consider additional education if needed, network with people in the field, gain relevant experience through projects or volunteering, and update your resume accordingly.'}
    ]

def find_counsellor_answer(user_question, qa_pairs):
    """Find the best matching answer from counsellor dataset with improved matching"""
    if not user_question or not user_question.strip():
        return get_general_advice()
    
    question_lower = user_question.lower().strip()
    
    # Debug logging
    log.info(f"🔍 Searching for answer to: '{question_lower}'")
    
    # Exact match
    for qa in qa_pairs:
        if qa['question'].lower() == question_lower:
            log.info(f"✅ Exact match found: {qa['question']}")
            return qa['answer']
    
    # Check if any dataset question is contained in user question
    for qa in qa_pairs:
        if qa['question'].lower() in question_lower:
            log.info(f"✅ Partial match found: {qa['question']} in {question_lower}")
            return qa['answer']
    
    # Check if user question contains any dataset question keywords
    for qa in qa_pairs:
        dataset_question_words = set(qa['question'].lower().split())
        user_question_words = set(question_lower.split())
        common_words = dataset_question_words.intersection(user_question_words)
        
        # If there's significant overlap, use this answer
        if len(common_words) >= 2:  # At least 2 common words
            log.info(f"✅ Keyword match found: {common_words}")
            return qa['answer']
    
    # Enhanced keyword matching with priority
    keyword_mapping = {
        'study habit': 'Create a study schedule, find a quiet space, take regular breaks, use active learning techniques like summarizing and teaching others, stay organized, and eliminate distractions. Try the Pomodoro technique: 25 minutes focused study, 5-minute break.',
        'improve study': 'Create a study schedule, find a quiet space, take regular breaks, use active learning techniques like summarizing and teaching others, stay organized, and eliminate distractions. Try the Pomodoro technique: 25 minutes focused study, 5-minute break.',
        'better study': 'Create a study schedule, find a quiet space, take regular breaks, use active learning techniques like summarizing and teaching others, stay organized, and eliminate distractions. Try the Pomodoro technique: 25 minutes focused study, 5-minute break.',
        'study technique': 'Create a study schedule, find a quiet space, take regular breaks, use active learning techniques like summarizing and teaching others, stay organized, and eliminate distractions. Try the Pomodoro technique: 25 minutes focused study, 5-minute break.',
        'study': 'Consider your interests and career goals. Popular fields include STEM, Business, Healthcare, and Creative Arts. What subjects do you enjoy most?',
        'career': 'I can help you explore career options. Tell me about your skills, interests, and what you enjoy doing. What kind of work environment do you prefer?',
        'stress': 'Student stress is common. Try time management techniques, take regular breaks, exercise, talk to someone you trust, and remember to prioritize self-care.',
        'programming': 'For beginners: Python is excellent. Web development: JavaScript. Mobile apps: Swift/Kotlin. Data science: Python/R. Choose based on your goals!',
        'grades': 'Improve grades with consistent study habits, class attendance, seeking help when needed, and active learning techniques. Don\'t forget sleep and exercise!',
        'future': 'Think about what you enjoy, your strengths, and career opportunities. Many students explore multiple paths before finding their perfect fit.',
        'job': 'Consider internships, networking, building a portfolio, and developing both technical and soft skills. Research companies that align with your values.',
        'motivation': 'Set clear goals, break tasks into manageable steps, reward your progress, and remember why you started. Find what inspires you!',
        'college': 'College provides education and networking, but also consider trade schools, online courses, or bootcamps based on your goals and learning style.',
        'time management': 'Use planners, prioritize tasks, break them into smaller steps, eliminate distractions, and schedule regular breaks. Pomodoro technique can help!',
        'exam': 'Prepare with a study plan, practice past papers, get enough sleep, eat well, and use relaxation techniques to manage stress. You\'ve got this!',
        'stressed': 'Take deep breaths, break tasks into smaller steps, talk to someone, exercise, and remember to take breaks. You\'re not alone in feeling this way.',
        'career choice': 'Consider your passions, skills, values, and job market demand. Research different fields and talk to professionals in those areas.',
        'major': 'Choose a major based on your interests, career goals, and the job market. Many successful people work in fields different from their major!',
        'overwhelmed': 'Break tasks into smaller steps, prioritize what\'s important, ask for help, and remember progress over perfection. You can handle this!',
        'resume': 'Focus on achievements with metrics, use action verbs, tailor to each job, and include relevant keywords. Keep it clean and professional.',
        'interview': 'Research the company, practice common questions, prepare specific examples, and remember to ask thoughtful questions about the role.',
        'skill': 'Focus on both technical skills (programming, data analysis) and soft skills (communication, teamwork). Continuous learning is key!'
    }
    
    # Check for multi-word keywords first (more specific)
    for keyword, answer in keyword_mapping.items():
        if ' ' in keyword and keyword in question_lower:
            log.info(f"✅ Multi-word keyword match: {keyword}")
            return answer
    
    # Then check single word keywords
    words = question_lower.split()
    for word in words:
        if word in keyword_mapping:
            log.info(f"✅ Single word keyword match: {word}")
            return keyword_mapping[word]
    
    log.info("❌ No specific match found, using general advice")
    return get_general_advice()

def get_general_advice():
    """Provide general advice when no specific match is found"""
    general_responses = [
        "I understand you're looking for guidance. Could you tell me a bit more about your specific situation or question?",
        "That's an important question. Let me help you think through this - what are your main interests or concerns right now?",
        "I'd be happy to help with that. Could you provide a bit more context about what you're looking for?",
        "Many students face similar questions. Let's work through this together - what have you considered so far?",
        "I want to make sure I give you the best advice. Could you share more details about your situation?",
        "That's a great question! To help you better, could you tell me more about what specifically you'd like to know?",
        "I'm here to help with academic and career guidance. What aspect are you most curious or concerned about?"
    ]
    import random
    return random.choice(general_responses)

# -------------------- IMPROVED COUNSELLOR CHAT SYSTEM --------------------
class CounsellorChat:
    def __init__(self):
        self.conversation_history = {}
        self.system_prompt = """You are CareerGuide, a warm, empathetic, and knowledgeable AI student counsellor. You provide:

1. **Career Guidance**: Help students choose career paths, majors, and fields of study
2. **Academic Support**: Advice on study techniques, time management, and academic challenges
3. **Personal Support**: Help with stress, motivation, and personal development
4. **Practical Advice**: Actionable steps and resources for student success

Your tone should be:
- Warm and empathetic like a trusted mentor
- Practical and actionable with specific advice
- Encouraging and supportive
- Professional but friendly

Always provide specific, practical suggestions and ask follow-up questions to better understand the student's situation."""

    def get_conversation_history(self, user_id):
        """Get or create conversation history for a user"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = [
                {"role": "system", "content": self.system_prompt},
                {"role": "assistant", "content": "Hello! I'm CareerGuide, your AI student counsellor. I'm here to help you with career guidance, academic support, study advice, or any challenges you're facing. What would you like to talk about today?"}
            ]
        return self.conversation_history[user_id]

    def add_message(self, user_id, role, content):
        """Add a message to conversation history"""
        history = self.get_conversation_history(user_id)
        history.append({"role": role, "content": content})
        # Keep only last 20 messages to prevent context overflow
        if len(history) > 20:
            history = [history[0]] + history[-19:]  # Keep system prompt + last 19 messages
            self.conversation_history[user_id] = history

    def generate_chat_response(self, user_id, user_message):
        """Generate AI response using available APIs with robust fallback"""
        # Always load fresh dataset for fallback
        qa_pairs = load_counsellor_qa()
        
        # First, try dataset matching (fast and reliable)
        #dataset_answer = find_counsellor_answer(user_message, qa_pairs)
        #if dataset_answer and len(dataset_answer.strip()) > 10:
            #log.info("✅ Using dataset answer for quick response")
            #self.add_message(user_id, "assistant", dataset_answer)
            #return dataset_answer, 'dataset'
        
        # If no good dataset match, try APIs
        keys = _load_keys()
        
        # Add user message to history for API context
        self.add_message(user_id, "user", user_message)
        history = self.get_conversation_history(user_id)
        
        # Try different APIs in order with timeout protection
        response = None
        source = None
        
        # 1. Try DeepSeek first
        if keys['deepseek']:
            response, source = self._try_deepseek(history, keys['deepseek'])
            if response and len(response.strip()) > 15:  # Ensure meaningful response
                self.add_message(user_id, "assistant", response)
                return response, source
        
        # 2. Try Gemini
        if keys['gemini'] and not response:
            print("Trying gemini")
            response, source = self._try_gemini(history, keys['gemini'])
            if response and len(response.strip()) > 15:
                self.add_message(user_id, "assistant", response)
                return response, source
        
        # 3. Try Groq
        if keys['groq'] and not response:
            response, source = self._try_groq(history, keys['groq'])
            if response and len(response.strip()) > 15:
                self.add_message(user_id, "assistant", response)
                return response, source
        
        # 4. Try Hugging Face
        if keys['huggingface'] and not response:
            response, source = self._try_huggingface(user_message, keys['huggingface'])
            if response and len(response.strip()) > 15:
                self.add_message(user_id, "assistant", response)
                return response, source
        
        # Final fallback - use dataset with context
        log.info("🤖 All APIs failed, using enhanced dataset fallback")
        final_fallback = self._get_contextual_fallback(user_message, qa_pairs, history)
        self.add_message(user_id, "assistant", final_fallback)
        return final_fallback, 'dataset'

    def _get_contextual_fallback(self, user_message, qa_pairs, history):
        """Get a contextual fallback response based on conversation history"""
        # Try dataset matching again with conversation context
        dataset_answer = find_counsellor_answer(user_message, qa_pairs)
        if dataset_answer and len(dataset_answer.strip()) > 10:
            return dataset_answer
        
        # If still no good match, analyze conversation context
        recent_messages = [msg for msg in history[-4:] if msg['role'] != 'system']
        if len(recent_messages) >= 2:
            # Check if this is a follow-up question
            last_assistant_msg = None
            for msg in reversed(recent_messages):
                if msg['role'] == 'assistant':
                    last_assistant_msg = msg['content']
                    break
            
            if last_assistant_msg:
                # Generic follow-up response
                follow_ups = [
                    "Could you tell me more about that?",
                    "What specifically would you like to know about this?",
                    "I'd be happy to explore this further with you. What aspect are you most curious about?",
                    "Let me help you think this through. What are your main considerations?",
                    "That's an important point. Could you share more about your situation?"
                ]
                import random
                return random.choice(follow_ups)
        
        return get_general_advice()

    def _try_deepseek(self, history, api_key):
        """Try DeepSeek API with error handling"""
        try:
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": history,
                "max_tokens": 800,
                "temperature": 0.7,
                "stream": False
            }
            
            log.info("🤖 Trying DeepSeek API for counsellor...")
            r = requests.post(url, json=payload, headers=headers, timeout=15)  # Shorter timeout
            
            if r.status_code == 200:
                data = r.json()
                answer = data['choices'][0]['message']['content'].strip()
                log.info("✅ DeepSeek counsellor response successful")
                return answer, 'deepseek'
            else:
                log.warning(f"❌ DeepSeek API failed: {r.status_code}")
                return None, None
                
        except Exception as e:
            log.error(f"❌ DeepSeek API error: {e}")
            return None, None

    def _try_gemini(self, history, api_key):
        """
        Try Gemini via google-generativeai SDK (preferred).
        Returns (answer_text, 'gemini') on success, otherwise (None, None).
        """
        try:
            # try to import the official SDK
            try:
                import google.generativeai as genai
            except Exception as imp_e:
                log.error("google-generativeai SDK not installed or import failed: %s", imp_e)
                log.info("Install with: pip install -U google-generativeai")
                return None, None

            # configure the SDK with the key passed in
            genai.configure(api_key=api_key)

            log.info("🤖 Trying Gemini via google-generativeai SDK for counsellor...")

            # List available models for this API key and find a usable Gemini model
            try:
                available = [m.name for m in genai.list_models()]
            except Exception as e:
                log.warning("Could not list models (falling back to trying common names): %s", e)
                available = []

            # preferred model names to try in order
            preferred = [
                "models/gemini-2.5-flash"
            ]

            # choose the first preferred model present in available (if available list succeeded),
            # otherwise try preferred list in order and let SDK error if not accessible.
            model_name = None
            for m in preferred:
                if available and m in available:
                    model_name = m
                    break
            if not model_name:
                # fallback: attempt the first preferred name (SDK will raise a clear error if not allowed)
                model_name = preferred[0]

            log.info("Using Gemini model: %s", model_name)

            # Convert conversation history into a single prompt string (simple, robust)
            # We keep system messages out (like your original code)
            convo_lines = []
            for msg in history:
                if msg.get("role") == "system":
                    continue
                role = msg.get("role", "user")
                # Mark roles explicitly; Gemini handles natural conversation.
                if role == "user":
                    convo_lines.append("User: " + msg.get("content", ""))
                else:
                    convo_lines.append("Assistant: " + msg.get("content", ""))
            prompt_text = "\n".join(convo_lines).strip()
            if not prompt_text:
                log.warning("Empty prompt after formatting conversation history.")
                return None, None

            # Create model object and generate content
            model = genai.GenerativeModel(model_name)

            # generate_content signature can accept a simple string or dict depending on SDK version.
            # We use keyword args likely supported: temperature, max_output_tokens, top_p, top_k
            try:
                resp = model.generate_content(
                    prompt_text
                )
            except TypeError:
                # older/newer SDK variation — try alternate call style (positional)
                resp = model.generate_content(prompt_text, 0.7, 800)

            # Extract generated text safely
            answer = None
            # SDK response objects vary by version; try common attributes
            if resp is None:
                answer = None
            elif hasattr(resp, "text") and resp.text:
                answer = resp.text
            elif isinstance(resp, dict):
                # some JSON-like responses have 'candidates' -> 'content' -> 'parts'
                # or 'output' -> 'content' keys. Try to be tolerant.
                if "candidates" in resp and resp["candidates"]:
                    cand = resp["candidates"][0]
                    # candidate may have content->parts->text
                    if isinstance(cand, dict):
                        cont = cand.get("content") or cand.get("message") or {}
                        if isinstance(cont, dict) and "parts" in cont and cont["parts"]:
                            answer = cont["parts"][0].get("text")
                elif "output" in resp and isinstance(resp["output"], list) and resp["output"]:
                    # newer-ish PaLM style responses
                    pieces = []
                    for item in resp["output"]:
                        if isinstance(item, dict) and "content" in item:
                            pieces.append(item["content"])
                    answer = "\n".join(pieces).strip() if pieces else None
                else:
                    # fallback to stringifying
                    answer = str(resp)
            else:
                # fallback: str()
                answer = str(resp)

            if answer:
                answer = answer.strip()
                log.info("✅ Gemini counsellor response successful (model=%s)", model_name)
                return answer, "gemini"
            else:
                log.warning("Gemini returned no usable text (model=%s). Raw response: %s", model_name, resp)
                return None, None

        except Exception as e:
            log.error("❌ Gemini API error: %s", e, exc_info=True)
            return None, None

    def _try_groq(self, history, api_key):
        """Try Groq API with error handling"""
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": "llama2-70b-4096",
                "messages": history,
                "max_tokens": 800,
                "temperature": 0.7,
                "top_p": 0.8
            }
            
            log.info("🤖 Trying Groq API for counsellor...")
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if r.status_code == 200:
                data = r.json()
                answer = data['choices'][0]['message']['content'].strip()
                log.info("✅ Groq counsellor response successful")
                return answer, 'groq'
            else:
                log.warning(f"❌ Groq API failed: {r.status_code}")
                return None, None
                
        except Exception as e:
            log.error(f"❌ Groq API error: {e}")
            return None, None

    def _try_huggingface(self, user_message, api_key):
        """Try Hugging Face API with error handling"""
        try:
            # Create a prompt from conversation context
            prompt = f"""As a student counsellor, provide helpful advice for this student question:

Student: {user_message}

Counsellor:"""
            
            url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-large"
            headers = {"Authorization": f"Bearer {api_key}"}
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 400,
                    "temperature": 0.8,
                    "do_sample": True,
                    "top_p": 0.9,
                    "repetition_penalty": 1.1,
                    "return_full_text": False
                },
                "options": {
                    "wait_for_model": True
                }
            }
            
            log.info("🤖 Trying Hugging Face API for counsellor...")
            r = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    if 'generated_text' in data[0]:
                        answer = data[0]['generated_text'].strip()
                        # Clean the response
                        if prompt in answer:
                            answer = answer.replace(prompt, "").strip()
                        log.info("✅ Hugging Face counsellor response successful")
                        return answer, 'huggingface'
            return None, None
            
        except Exception as e:
            log.error(f"❌ Hugging Face API error: {e}")
            return None, None

    def clear_history(self, user_id):
        """Clear conversation history for a user"""
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]

# Initialize the improved counsellor chat system
counsellor_chat = CounsellorChat()

# -------------------- ROUTES --------------------
@app.route('/')
def index():
    return render_template('index.html', job_roles=job_roles)

@app.route('/practice')
def practice():
    return render_template('practice.html', job_roles=job_roles)

@app.route('/interview/<role>')
def interview(role):
    # Initialize session for interview tracking
    session['interview_started'] = datetime.now().isoformat()
    session['current_role'] = role
    session['questions_answered'] = 0
    
    return render_template('interview.html', role=role, job_roles=job_roles)

@app.route('/counsellor')
def counsellor():
    return render_template('counsellor.html', job_roles=job_roles)

@app.route('/questions')
def questions():
    return jsonify(load_questions())

@app.route('/questions/<role>')
def questions_by_role(role):
    all_questions = load_questions()
    role_questions = [q for q in all_questions if q['career'].lower() == role.lower()]
    
    # If no specific questions found, return general questions or all questions
    if not role_questions:
        role_questions = [q for q in all_questions if q['career'].lower() == 'general']
        if not role_questions:
            role_questions = all_questions  # Use all questions as fallback
    
    log.info(f"📊 Returning {len(role_questions)} questions for role: {role}")
    return jsonify(role_questions)

# -------------------- NEW ADVANCED FEATURES ROUTES --------------------

@app.route('/analyze_performance', methods=['POST'])
def analyze_performance():
    """Analyze interview performance with detailed metrics"""
    data = request.get_json() or {}
    transcript = data.get('transcript', '')
    question = data.get('question', '')
    duration_seconds = data.get('duration_seconds', 60)
    
    if not transcript:
        return jsonify({'ok': False, 'error': 'No transcript provided'})
    
    try:
        # Analyze different aspects
        clarity_analysis = performance_analyzer.analyze_speech_clarity(transcript)
        pace_analysis = performance_analyzer.analyze_pace(transcript, duration_seconds)
        content_analysis = performance_analyzer.analyze_content_quality(transcript, question)
        
        analysis_results = {
            'clarity': clarity_analysis,
            'pace': pace_analysis,
            'content': content_analysis
        }
        
        # Calculate overall score
        overall_score = performance_analyzer.calculate_overall_score(analysis_results)
        
        # Generate improvement suggestions
        suggestions = generate_improvement_suggestions(analysis_results, overall_score)
        
        return jsonify({
            'ok': True,
            'overall_score': overall_score,
            'analysis': analysis_results,
            'suggestions': suggestions,
            'grade': get_performance_grade(overall_score)
        })
        
    except Exception as e:
        log.error(f"❌ Performance analysis error: {e}")
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/get_learning_resources', methods=['POST'])
def get_learning_resources():
    """Get learning resources based on role and performance"""
    data = request.get_json() or {}
    role = data.get('role', 'General')
    weak_areas = data.get('weak_areas', [])
    
    try:
        resources = {
            'frameworks': learning_resources['answer_frameworks'],
            'terminology': learning_resources['industry_terminology'].get(role, []),
            'followup_questions': learning_resources['common_followups'],
            'personalized_recommendations': get_personalized_recommendations(weak_areas, role)
        }
        
        return jsonify({'ok': True, 'resources': resources})
        
    except Exception as e:
        log.error(f"❌ Learning resources error: {e}")
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/update_user_progress', methods=['POST'])
def update_user_progress():
    """Update user progress and check for achievements"""
    data = request.get_json() or {}
    performance_score = data.get('performance_score', 0)
    duration_seconds = data.get('duration_seconds', 0)
    questions_answered = data.get('questions_answered', 0)
    role = data.get('role', 'General')
    
    try:
        # Calculate points earned
        points_earned = gamification_system.calculate_points(
            performance_score, duration_seconds, questions_answered
        )
        
        # Get user stats from session
        user_stats = session.get('user_stats', {
            'total_points': 0,
            'level': 1,
            'total_interviews': 0,
            'achievements': [],
            'roles_tried': set()
        })
        
        # Update stats
        user_stats['total_points'] += points_earned
        user_stats['total_interviews'] += 1
        if 'roles_tried' not in user_stats:
            user_stats['roles_tried'] = set()
        user_stats['roles_tried'].add(role)
        
        # Check for level up
        level_up = gamification_system.check_level_up(
            user_stats['total_points'] - points_earned, points_earned
        )
        
        # Check for achievements
        interview_data = {
            'performance_score': performance_score,
            'duration': duration_seconds,
            'time_limit': 600,  # Default 10 minutes
            'questions_answered': questions_answered
        }
        new_achievements = gamification_system.check_achievements(user_stats, interview_data)
        
        # Add new achievements to user stats
        for achievement in new_achievements:
            if achievement['name'] not in user_stats['achievements']:
                user_stats['achievements'].append(achievement['name'])
        
        # Update session
        session['user_stats'] = user_stats
        
        return jsonify({
            'ok': True,
            'points_earned': points_earned,
            'total_points': user_stats['total_points'],
            'current_level': gamification_system.get_current_level(user_stats['total_points']),
            'level_up': level_up,
            'new_achievements': new_achievements,
            'level_info': gamification_system.levels
        })
        
    except Exception as e:
        log.error(f"❌ Progress update error: {e}")
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/get_interview_config', methods=['GET'])
def get_interview_config():
    """Get interview configuration options"""
    return jsonify({
        'ok': True,
        'difficulty_levels': interview_difficulty_levels,
        'focus_areas': interview_focus_areas,
        'time_limits': [30, 45, 60, 90, 120]
    })

@app.route('/generate_followup_questions', methods=['POST'])
def generate_followup_questions():
    """Generate follow-up questions based on user's answer"""
    data = request.get_json() or {}
    question = data.get('question', '')
    answer = data.get('answer', '')
    role = data.get('role', 'General')
    
    keys = _load_keys()
    gem, hf = keys.get("gemini"), keys.get("huggingface")
    
    prompt = f"""Based on this interview interaction, generate 3 relevant follow-up questions:

Original Question: {question}
Candidate's Answer: {answer}
Role: {role}

Generate 3 thoughtful follow-up questions that:
1. Probe deeper into the candidate's experience
2. Challenge their thinking
3. Explore related scenarios

Follow-up Questions:"""
    
    # Try Gemini first
    if gem:
        ok, followups = generate_with_gemini(prompt, gem)
        if ok and followups:
            questions = [q.strip() for q in followups.split('\n') if q.strip() and '?' in q]
            return jsonify({'ok': True, 'followup_questions': questions[:3]})
    
    # Fallback to predefined questions
    fallback_questions = [
        "Can you tell me more about that experience?",
        "What would you do differently if you faced that situation again?",
        "How did you measure the success of that approach?"
    ]
    
    return jsonify({'ok': True, 'followup_questions': fallback_questions})

@app.route('/generate_interview_report', methods=['POST'])
def generate_interview_report():
    """Generate comprehensive interview performance report"""
    data = request.get_json() or {}
    performance_data = data.get('performance_data', {})
    interview_details = data.get('interview_details', {})
    
    try:
        report = {
            'summary': generate_report_summary(performance_data),
            'strengths': identify_strengths(performance_data),
            'improvement_areas': identify_improvement_areas(performance_data),
            'action_plan': generate_action_plan(performance_data),
            'comparison_data': get_comparison_data(performance_data),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({'ok': True, 'report': report})
        
    except Exception as e:
        log.error(f"❌ Report generation error: {e}")
        return jsonify({'ok': False, 'error': str(e)})

# -------------------- COUNSELLOR CHAT ROUTES --------------------
@app.route('/counsellor_chat', methods=['POST'])
def counsellor_chat_api():
    """Handle counsellor chat messages with guaranteed responses"""
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    user_id = data.get('user_id', 'default_user')
    
    if not question:
        return jsonify({'ok': False, 'error': 'No question provided'})
    
    try:
        # This will always return a response due to the robust fallback system
        answer, source = counsellor_chat.generate_chat_response(user_id, question)
        
        return jsonify({
            'ok': True,
            'answer': answer,
            'source': source,
            'question': question
        })
        
    except Exception as e:
        log.error(f"❌ Counsellor chat error: {e}")
        # Even if everything fails, provide a fallback response
        fallback = "I'm here to help you with academic and career guidance. Could you tell me more about what you're looking for?"
        return jsonify({
            'ok': True,
            'answer': fallback,
            'source': 'dataset',
            'question': question
        })

@app.route('/counsellor_clear', methods=['POST'])
def counsellor_clear():
    """Clear conversation history"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'default_user')
    
    try:
        counsellor_chat.clear_history(user_id)
        return jsonify({'ok': True, 'message': 'Conversation history cleared'})
    except Exception as e:
        log.error(f"❌ Clear history error: {e}")
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/counsellor_history', methods=['POST'])
def counsellor_history():
    """Get conversation history"""
    data = request.get_json() or {}
    user_id = data.get('user_id', 'default_user')
    
    try:
        history = counsellor_chat.get_conversation_history(user_id)
        # Filter out system message for frontend
        filtered_history = [msg for msg in history if msg['role'] != 'system']
        return jsonify({'ok': True, 'history': filtered_history})
    except Exception as e:
        log.error(f"❌ Get history error: {e}")
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/debug')
def debug():
    """Debug route to check server status"""
    import os
    current_dir = os.getcwd()
    template_dir = os.path.join(current_dir, 'templates')
    template_files = os.listdir(template_dir) if os.path.exists(template_dir) else []
    
    return f"""
    <h1>Debug Information</h1>
    <p>Current directory: {current_dir}</p>
    <p>Templates directory: {template_dir}</p>
    <p>Templates exists: {os.path.exists(template_dir)}</p>
    <p>Template files: {', '.join(template_files)}</p>
    <p>Interview template exists: {os.path.exists(os.path.join(template_dir, 'interview.html'))}</p>
    <p>Counsellor template exists: {os.path.exists(os.path.join(template_dir, 'counsellor.html'))}</p>
    <hr>
    <h3>Test Links:</h3>
    <ul>
        <li><a href="/">Home</a></li>
        <li><a href="/practice">Practice</a></li>
        <li><a href="/interview/Software%20Engineer">Interview - Software Engineer</a></li>
        <li><a href="/counsellor">Counsellor</a></li>
    </ul>
    """

@app.route('/test_interview')
def test_interview():
    """Test route for interview template"""
    try:
        return render_template('interview.html', role='Test Role')
    except Exception as e:
        return f"Template error: {str(e)}"

# -------------------- HELPER FUNCTIONS FOR NEW FEATURES --------------------

def generate_improvement_suggestions(analysis_results, overall_score):
    """Generate personalized improvement suggestions"""
    suggestions = []
    
    clarity = analysis_results['clarity']
    pace = analysis_results['pace']
    content = analysis_results['content']
    
    # Clarity suggestions
    if clarity['filler_percentage'] > 5:
        suggestions.append({
            'area': 'Speech Clarity',
            'suggestion': f"Reduce filler words (currently {clarity['filler_percentage']}%). Practice pausing instead of using 'um', 'ah'.",
            'priority': 'high' if clarity['filler_percentage'] > 10 else 'medium'
        })
    
    # Pace suggestions
    if pace['pace_wpm'] < 130:
        suggestions.append({
            'area': 'Speaking Pace',
            'suggestion': f"Try speaking slightly faster. Current pace: {pace['pace_wpm']} WPM (ideal: 130-170 WPM)",
            'priority': 'medium'
        })
    elif pace['pace_wpm'] > 170:
        suggestions.append({
            'area': 'Speaking Pace',
            'suggestion': f"Slow down slightly for better clarity. Current pace: {pace['pace_wpm']} WPM (ideal: 130-170 WPM)",
            'priority': 'medium'
        })
    
    # Content suggestions
    if content['relevance_score'] < 70:
        suggestions.append({
            'area': 'Answer Relevance',
            'suggestion': "Focus on directly addressing the question. Use more keywords from the question in your answer.",
            'priority': 'high'
        })
    
    if content['star_score'] < 60:
        suggestions.append({
            'area': 'Answer Structure',
            'suggestion': "Use the STAR method (Situation, Task, Action, Result) to structure your answers more effectively.",
            'priority': 'medium'
        })
    
    # Overall encouragement
    if overall_score >= 80:
        suggestions.append({
            'area': 'Overall Performance',
            'suggestion': "Excellent performance! Continue practicing to maintain your high standards.",
            'priority': 'low'
        })
    
    return suggestions

def get_performance_grade(score):
    """Convert score to letter grade"""
    if score >= 90: return 'A+'
    elif score >= 85: return 'A'
    elif score >= 80: return 'A-'
    elif score >= 75: return 'B+'
    elif score >= 70: return 'B'
    elif score >= 65: return 'B-'
    elif score >= 60: return 'C+'
    else: return 'C'

def get_personalized_recommendations(weak_areas, role):
    """Get personalized learning recommendations"""
    recommendations = []
    
    if 'clarity' in weak_areas:
        recommendations.append("Practice speaking with intentional pauses instead of filler words")
    
    if 'pace' in weak_areas:
        recommendations.append("Use a metronome app to practice speaking at 150 WPM")
    
    if 'relevance' in weak_areas:
        recommendations.append("Study common interview questions for your target role")
    
    if 'structure' in weak_areas:
        recommendations.append("Practice answering questions using the STAR method framework")
    
    # Role-specific recommendations
    if role in ['Software Engineer', 'Data Scientist']:
        recommendations.append("Prepare 2-3 technical project examples with specific metrics")
    elif role in ['Product Manager', 'Business Analyst']:
        recommendations.append("Practice explaining complex concepts to non-technical audiences")
    
    return recommendations

def generate_report_summary(performance_data):
    """Generate summary for performance report"""
    overall_score = performance_data.get('overall_score', 0)
    grade = get_performance_grade(overall_score)
    
    return {
        'overall_score': overall_score,
        'grade': grade,
        'summary': f"Your performance scored {overall_score}/100 ({grade}). " +
                  f"This places you in the {get_performance_tier(overall_score)} tier.",
        'key_metrics': {
            'Clarity Score': performance_data.get('clarity', {}).get('clarity_score', 0),
            'Pace Score': performance_data.get('pace', {}).get('pace_score', 0),
            'Relevance Score': performance_data.get('content', {}).get('relevance_score', 0)
        }
    }

def identify_strengths(performance_data):
    """Identify user strengths from performance data"""
    strengths = []
    
    if performance_data.get('clarity', {}).get('clarity_score', 0) >= 85:
        strengths.append("Clear and articulate communication")
    
    if performance_data.get('pace', {}).get('pace_score', 0) >= 85:
        strengths.append("Excellent speaking pace and rhythm")
    
    if performance_data.get('content', {}).get('relevance_score', 0) >= 80:
        strengths.append("Strong relevance to questions asked")
    
    if performance_data.get('content', {}).get('star_score', 0) >= 75:
        strengths.append("Good use of structured answering frameworks")
    
    return strengths if strengths else ["Consistent performance across areas"]

def identify_improvement_areas(performance_data):
    """Identify areas for improvement"""
    areas = []
    
    if performance_data.get('clarity', {}).get('filler_percentage', 0) > 8:
        areas.append("Reduce filler words in speech")
    
    if performance_data.get('pace', {}).get('pace_score', 0) < 70:
        areas.append("Improve speaking pace consistency")
    
    if performance_data.get('content', {}).get('relevance_score', 0) < 70:
        areas.append("Increase answer relevance to questions")
    
    return areas

def generate_action_plan(performance_data):
    """Generate actionable improvement plan"""
    return {
        'short_term': [
            "Practice 2-3 common interview questions daily",
            "Record yourself and analyze filler word usage",
            "Time your responses to maintain ideal pace"
        ],
        'long_term': [
            "Develop a portfolio of 5-7 strong example stories",
            "Learn and practice the STAR method thoroughly",
            "Participate in mock interviews weekly"
        ],
        'resources': [
            "Interview frameworks guide",
            "Industry-specific terminology list",
            "Practice question bank"
        ]
    }

def get_performance_tier(score):
    """Get performance tier description"""
    if score >= 90: return "Exceptional"
    elif score >= 80: return "Strong"
    elif score >= 70: return "Competitive"
    elif score >= 60: return "Developing"
    else: return "Needs Improvement"

def get_comparison_data(performance_data):
    """Get comparison data"""
    return {
        'industry_average': 72,
        'top_performers_average': 88,
        'your_score': performance_data.get('overall_score', 0),
        'percentile': min(95, max(10, (performance_data.get('overall_score', 0) / 100) * 90 + 10))
    }

# -------------------- EXISTING AUDIO PROCESSING FUNCTIONS --------------------

def convert_to_wav(input_path: Path, out_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.warning("❌ ffmpeg not found, audio conversion skipped")
        return False
    try:
        subprocess.check_output([ffmpeg, "-y", "-i", str(input_path), "-ac", "1", "-ar", "16000", str(out_path)],
                                stderr=subprocess.STDOUT, timeout=60)
        return out_path.exists()
    except Exception as e:
        log.error(f"❌ Audio conversion failed: {e}")
        return False

def transcribe_with_hf(audio_bytes: bytes, hf_key: str):
    if not hf_key:
        return False, ''
    try:
        url = "https://api-inference.huggingface.co/models/openai/whisper-large-v2"
        headers = {"Authorization": f"Bearer {hf_key}"}
        log.info("🎤 Transcribing with Hugging Face Whisper...")
        r = requests.post(url, headers=headers, data=audio_bytes, timeout=120)
        if r.status_code == 200:
            try:
                j = r.json()
                txt = j.get("text") or j.get("transcription") or ''
                if not txt and isinstance(j, dict):
                    txt = ' '.join(map(str, j.values()))
                log.info(f"✅ Transcription successful: {txt[:100]}...")
                return True, txt
            except Exception as e:
                log.error(f"❌ HF transcription parse error: {e}")
                return True, r.text
        log.error(f"❌ HF transcription failed: {r.status_code}")
        return False, ''
    except Exception as e:
        log.error(f"❌ HF transcription error: {e}")
        return False, ''

def transcribe_with_gemini(wav_path: Path, gem_key: str):
    if not gem_key or not wav_path.exists():
        return False, ''
    try:
        with open(wav_path, 'rb') as f:
            audio64 = base64.b64encode(f.read()).decode()
        url = f"https://speech.googleapis.com/v1/speech:recognize?key={gem_key}"
        payload = {
            "config": {"encoding": "LINEAR16", "sampleRateHertz": 16000, "languageCode": "en-US"},
            "audio": {"content": audio64}
        }
        log.info("🎤 Transcribing with Gemini Speech-to-Text...")
        r = requests.post(url, json=payload, timeout=90)
        if r.status_code == 200:
            out = r.json()
            res = out.get("results", [])
            txt = " ".join([alt.get("transcript", "") for r in res for alt in r.get("alternatives", [])])
            log.info(f"✅ Gemini transcription successful: {txt[:100]}...")
            return True, txt
        log.error(f"❌ Gemini transcription failed: {r.status_code}")
        return False, ''
    except Exception as e:
        log.error(f"❌ Gemini transcription error: {e}")
        return False, ''

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    data = request.get_json() or {}
    filename = f"resp_{int(time.time())}.webm"
    audio_b64 = data.get('audio_base64')
    
    if not audio_b64:
        return jsonify({'status': 'error', 'error': 'no audio data'})
    
    try:
        # Extract base64 data (remove data:audio/webm;base64, prefix if present)
        if "," in audio_b64:
            audio_b64 = audio_b64.split(",")[1]
        
        audio_bytes = base64.b64decode(audio_b64)
        path = UPLOAD_DIR / filename
        path.write_bytes(audio_bytes)
        log.info(f"💾 Saved audio recording: {filename} ({len(audio_bytes)} bytes)")

        # Convert to WAV for better transcription
        wav_path = UPLOAD_DIR / (path.stem + ".wav")
        convert_to_wav(path, wav_path)

        keys = _load_keys()
        gem, hf = keys.get("gemini"), keys.get("huggingface")

        # Try Gemini first
        if gem:
            ok, tr = transcribe_with_gemini(wav_path, gem)
            if ok and tr and len(tr.strip()) > 10:  # Only use if meaningful transcript
                # Update session
                session['questions_answered'] = session.get('questions_answered', 0) + 1
                return jsonify({
                    'status': 'ok', 
                    'transcript': tr.strip(), 
                    'source': 'gemini',
                    'questions_answered': session.get('questions_answered', 0)
                })
        
        # Try Hugging Face
        if hf:
            ok, tr = transcribe_with_hf(wav_path.read_bytes(), hf)
            if ok and tr and len(tr.strip()) > 10:  # Only use if meaningful transcript
                session['questions_answered'] = session.get('questions_answered', 0) + 1
                return jsonify({
                    'status': 'ok', 
                    'transcript': tr.strip(), 
                    'source': 'huggingface',
                    'questions_answered': session.get('questions_answered', 0)
                })
        
        # No successful transcription
        session['questions_answered'] = session.get('questions_answered', 0) + 1
        return jsonify({
            'status': 'ok', 
            'transcript': '[Audio recorded but no transcription available]', 
            'source': 'none',
            'questions_answered': session.get('questions_answered', 0)
        })
        
    except Exception as e:
        log.error(f"❌ Upload audio error: {e}")
        return jsonify({'status': 'error', 'error': str(e)})

# -------------------- ANSWER GENERATION --------------------
def generate_with_hf(prompt, hf_key):
    if not hf_key:
        return False, ''
    try:
        # Using a more reliable model for conversation
        url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-large"
        headers = {"Authorization": f"Bearer {hf_key}"}
        payload = {
            "inputs": prompt, 
            "parameters": {
                "max_new_tokens": 300, 
                "temperature": 0.7,
                "do_sample": True
            }
        }
        log.info("🤖 Generating answer with Hugging Face...")
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        if r.status_code == 200:
            j = r.json()
            if isinstance(j, list) and len(j) and 'generated_text' in j[0]:
                answer = j[0]['generated_text']
                log.info(f"✅ HF answer generated: {answer[:100]}...")
                return True, answer
            return True, str(j)
        log.error(f"❌ HF answer generation failed: {r.status_code}")
        return False, ''
    except Exception as e:
        log.error(f"❌ HF answer generation error: {e}")
        return False, ''

def generate_with_gemini(prompt, gem_key):
    if not gem_key:
        return False, ''
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={gem_key}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500,
            }
        }
        log.info("🤖 Generating answer with Gemini...")
        r = requests.post(url, json=payload, timeout=90)
        if r.status_code == 200:
            j = r.json()
            candidates = j.get('candidates', [])
            if candidates:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts:
                    answer = parts[0].get('text', '').strip()
                    log.info(f"✅ Gemini answer generated: {answer[:100]}...")
                    return True, answer
        log.error(f"❌ Gemini answer generation failed: {r.status_code}")
        return False, ''
    except Exception as e:
        log.error(f"❌ Gemini answer generation error: {e}")
        return False, ''

@app.route('/generate_answer', methods=['POST'])
def generate_answer():
    data = request.get_json() or {}
    question = data.get('question', '')
    role = data.get('role', 'General')
    
    if not question:
        return jsonify({'ok': False, 'error': 'No question provided'})
    
    keys = _load_keys()
    gem, hf = keys.get("gemini"), keys.get("huggingface")
    
    prompt = f"""Provide a professional interview answer for a {role} position.

Question: {question}

Please provide a concise, well-structured answer that includes:
1. A clear introduction
2. Specific examples or experiences
3. Relevant skills or methodologies
4. A concluding statement

Answer:"""
    
    # Try Gemini first
    if gem:
        ok, ans = generate_with_gemini(prompt, gem)
        if ok and ans:
            return jsonify({'ok': True, 'answer': ans, 'source': 'gemini'})
    
    # Try Hugging Face
    if hf:
        ok, ans = generate_with_hf(prompt, hf)
        if ok and ans:
            return jsonify({'ok': True, 'answer': ans, 'source': 'huggingface'})
    
    # Fallback template
    templ = f"""For the {role} position question "{question}", here's a structured approach:

1. **Introduction**: Start with a clear, concise statement about your experience
2. **Example**: Share a specific relevant experience or project
3. **Skills**: Highlight key skills that match the role requirements
4. **Conclusion**: Connect back to how this makes you suitable for the position

Remember to be specific, use metrics when possible, and show enthusiasm for the role."""
    
    return jsonify({'ok': True, 'answer': templ, 'source': 'template'})

# -------------------- TTS --------------------
@app.route('/tts_synthesize', methods=['POST'])
def tts_synthesize():
    data = request.get_json() or {}
    text = data.get('text', '')
    
    if not text:
        return jsonify({'ok': False, 'error': 'No text provided'})
    
    keys = _load_keys()
    gem, hf = keys.get("gemini"), keys.get("huggingface")
    
    # Try Gemini TTS
    if gem:
        try:
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={gem}"
            payload = {
                "input": {"text": text},
                "voice": {"languageCode": "en-US", "name": "en-US-Neural2-F"},
                "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0}
            }
            log.info("🔊 Generating TTS with Gemini...")
            r = requests.post(url, json=payload, timeout=90)
            if r.status_code == 200:
                j = r.json()
                if 'audioContent' in j:
                    log.info("✅ Gemini TTS successful")
                    return jsonify({'ok': True, 'audio_base64': j['audioContent'], 'source': 'gemini'})
        except Exception as e:
            log.error(f"❌ Gemini TTS error: {e}")
    
    # Try Hugging Face TTS
    if hf:
        try:
            url = "https://api-inference.huggingface.co/models/facebook/mms-tts-eng"
            headers = {"Authorization": f"Bearer {hf}"}
            log.info("🔊 Generating TTS with Hugging Face...")
            r = requests.post(url, headers=headers, json={"inputs": text}, timeout=120)
            if r.status_code == 200:
                log.info("✅ Hugging Face TTS successful")
                return jsonify({'ok': True, 'audio_base64': base64.b64encode(r.content).decode(), 'source': 'huggingface'})
        except Exception as e:
            log.error(f"❌ Hugging Face TTS error: {e}")
    
    log.warning("❌ No TTS service available")
    return jsonify({'ok': False, 'error': 'no-tts-service'})

# -------------------- STATIC HELPER --------------------
def static_file_exists(path):
    full = Path(app.static_folder) / path
    return full.exists()

app.jinja_env.globals['static_file_exists'] = static_file_exists

# -------------------- MAIN --------------------
if __name__ == "__main__":

    # Test loading questions and keys
    questions = load_questions()
    keys = _load_keys()
    
    log.info("🚀 Starting Interview AI Server with Advanced Features...")
    log.info(f"📊 Loaded {len(questions)} questions from dataset")
    log.info(f"🔑 Hugging Face API: {'✅ Available' if keys['huggingface'] else '❌ Not configured'}")
    log.info(f"🔑 Gemini API: {'✅ Available' if keys['gemini'] else '❌ Not configured'}")
    log.info(f"🔑 DeepSeek API: {'✅ Available' if keys['deepseek'] else '❌ Not configured'}")
    log.info(f"🔑 Groq API: {'✅ Available' if keys['groq'] else '❌ Not configured'}")
    log.info("🎯 Advanced Features: Performance Analytics ✅ Gamification ✅ Learning Resources ✅")
    log.info("🤖 Counsellor: Robust chat system with guaranteed responses ✅")
    log.info("🌐 Server running at http://127.0.0.1:5000")
    
    app.run(debug=True, host="0.0.0.0", port=5000)
