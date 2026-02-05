"""
Exam attempt service
"""
import random
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pymongo.errors import DuplicateKeyError
from utils.database import db
from utils.config import UNAM_EXAM_CONFIG, SUBJECT_ORDER, EXAM_DURATION_MINUTES, TOTAL_QUESTIONS
from services.auth_service import AuthService


class AttemptService:
    """Service for exam attempt operations"""
    
    @staticmethod
    async def generate_attempt_questions(area: str, question_count: int = 120) -> List[Dict]:
        """Generate questions for an attempt based on area configuration"""
        area_config = UNAM_EXAM_CONFIG.get(area)
        if not area_config:
            raise ValueError(f"Invalid area: {area}")
        
        subjects_config = area_config["subjects"]
        proportion = question_count / 120
        
        # Calculate target counts for each subject with proper rounding
        ordered_subjects = []
        total_target = 0
        
        for slug in SUBJECT_ORDER:
            if slug in subjects_config:
                # Use round() instead of int() for better distribution
                scaled_count = max(1, round(subjects_config[slug] * proportion))
                ordered_subjects.append((slug, scaled_count))
                total_target += scaled_count
        
        # Adjust to match exact question_count
        diff = question_count - total_target
        
        # Distribute difference among subjects (add/subtract 1 from each until balanced)
        if diff != 0:
            # Sort by which subjects can afford the adjustment
            # (subjects with higher original count get adjusted first)
            adjustment_indices = list(range(len(ordered_subjects)))
            if diff > 0:
                # Need to add questions - prioritize subjects with more questions originally
                adjustment_indices.sort(
                    key=lambda i: subjects_config[ordered_subjects[i][0]], 
                    reverse=True
                )
            else:
                # Need to remove questions - prioritize subjects with fewer questions
                adjustment_indices.sort(
                    key=lambda i: subjects_config[ordered_subjects[i][0]]
                )
            
            for i in range(abs(diff)):
                idx = adjustment_indices[i % len(adjustment_indices)]
                slug, current_count = ordered_subjects[idx]
                new_count = current_count + (1 if diff > 0 else -1)
                # Ensure minimum of 1 question per subject
                if new_count >= 1:
                    ordered_subjects[idx] = (slug, new_count)
        
        # Now select questions based on adjusted counts
        questions = []
        used_question_ids = set()
        
        for subject_slug, count in ordered_subjects:
            subject = await db.subjects.find_one({"slug": subject_slug}, {"_id": 0})
            if not subject:
                continue
            
            # Get all available questions for this subject
            all_subject_questions = await db.questions.find(
                {"subject_id": subject["subject_id"]},
                {"_id": 0}
            ).to_list(1000)
            
            # Filter out already used questions
            available = [q for q in all_subject_questions if q["question_id"] not in used_question_ids]
            
            # Randomly select (handle empty available list)
            if not available:
                continue
            
            # Don't select more than available
            select_count = min(count, len(available))
            selected = random.sample(available, select_count)
            
            for q in selected:
                used_question_ids.add(q["question_id"])
                questions.append({
                    "question_id": q["question_id"],
                    "subject_id": q["subject_id"],
                    "subject_name": subject["name"],
                    "topic": q["topic"],
                    "text": q["text"],
                    "options": q["options"],
                    "image_url": q.get("image_url"),
                    "option_images": q.get("option_images"),
                    "reading_text": None  # Will be populated if needed
                })
        
        # If we still don't have enough questions due to database limitations,
        # try to fill from other subjects in the same area
        current_count = len(questions)
        if current_count < question_count:
            for subject_slug, _ in ordered_subjects:
                if len(questions) >= question_count:
                    break
                    
                subject = await db.subjects.find_one({"slug": subject_slug}, {"_id": 0})
                if not subject:
                    continue
                
                all_subject_questions = await db.questions.find(
                    {"subject_id": subject["subject_id"]},
                    {"_id": 0}
                ).to_list(1000)
                
                available = [q for q in all_subject_questions if q["question_id"] not in used_question_ids]
                needed = question_count - len(questions)
                
                if available and needed > 0:
                    extra = random.sample(available, min(needed, len(available)))
                    for q in extra:
                        used_question_ids.add(q["question_id"])
                        questions.append({
                            "question_id": q["question_id"],
                            "subject_id": q["subject_id"],
                            "subject_name": subject["name"],
                            "topic": q["topic"],
                            "text": q["text"],
                            "options": q["options"],
                            "image_url": q.get("image_url"),
                            "option_images": q.get("option_images"),
                            "reading_text": None
                        })
        
        return questions
    
    @staticmethod
    async def get_reading_texts_for_questions(questions: List[Dict]) -> Dict[str, str]:
        """Fetch reading texts for questions that have them"""
        reading_texts_cache = {}
        
        # Get unique reading_text_ids
        reading_text_ids = set()
        for q in questions:
            if q.get("reading_text_id"):
                reading_text_ids.add(q["reading_text_id"])
        
        # Fetch all reading texts
        for rt_id in reading_text_ids:
            rt = await db.reading_texts.find_one({"reading_text_id": rt_id}, {"_id": 0})
            if rt:
                reading_texts_cache[rt_id] = rt["content"]
        
        return reading_texts_cache
    
    @staticmethod
    async def create_attempt(user_id: str, simulator_id: str, question_count: int = 120) -> Dict[str, Any]:
        """Create a new attempt for a user"""
        simulator = await db.simulators.find_one({"simulator_id": simulator_id}, {"_id": 0})
        if not simulator:
            raise ValueError("Simulator not found")
        
        # Check for existing in-progress attempt
        existing = await db.attempts.find_one({
            "user_id": user_id,
            "simulator_id": simulator_id,
            "status": "in_progress"
        }, {"_id": 0})
        
        if existing:
            return existing
        
        # Generate questions
        area_config = UNAM_EXAM_CONFIG.get(simulator["area"])
        if not area_config:
            raise ValueError("Invalid area")
        
        subjects_config = area_config["subjects"]
        proportion = question_count / 120
        
        # Calculate target counts with proper rounding (same logic as generate_attempt_questions)
        ordered_subjects = []
        total_target = 0
        
        for slug in SUBJECT_ORDER:
            if slug in subjects_config:
                scaled_count = max(1, round(subjects_config[slug] * proportion))
                ordered_subjects.append((slug, scaled_count))
                total_target += scaled_count
        
        # Adjust to match exact question_count
        diff = question_count - total_target
        
        if diff != 0:
            adjustment_indices = list(range(len(ordered_subjects)))
            if diff > 0:
                adjustment_indices.sort(
                    key=lambda i: subjects_config[ordered_subjects[i][0]], 
                    reverse=True
                )
            else:
                adjustment_indices.sort(
                    key=lambda i: subjects_config[ordered_subjects[i][0]]
                )
            
            for i in range(abs(diff)):
                idx = adjustment_indices[i % len(adjustment_indices)]
                slug, current_count = ordered_subjects[idx]
                new_count = current_count + (1 if diff > 0 else -1)
                if new_count >= 1:
                    ordered_subjects[idx] = (slug, new_count)
        
        # Select questions
        question_ids = []
        used_ids = set()
        
        for subject_slug, count in ordered_subjects:
            subject = await db.subjects.find_one({"slug": subject_slug}, {"_id": 0})
            if not subject:
                continue
            
            all_questions = await db.questions.find(
                {"subject_id": subject["subject_id"]},
                {"_id": 0, "question_id": 1}
            ).to_list(1000)
            
            available = [q for q in all_questions if q["question_id"] not in used_ids]
            if not available:
                continue
            
            select_count = min(count, len(available))
            selected = random.sample(available, select_count)
            
            for q in selected:
                used_ids.add(q["question_id"])
                question_ids.append(q["question_id"])
        
        # Fill if needed
        if len(question_ids) < question_count:
            for subject_slug, _ in ordered_subjects:
                if len(question_ids) >= question_count:
                    break
                    
                subject = await db.subjects.find_one({"slug": subject_slug}, {"_id": 0})
                if not subject:
                    continue
                
                all_questions = await db.questions.find(
                    {"subject_id": subject["subject_id"]},
                    {"_id": 0, "question_id": 1}
                ).to_list(1000)
                
                available = [q for q in all_questions if q["question_id"] not in used_ids]
                needed = question_count - len(question_ids)
                
                if available and needed > 0:
                    extra = random.sample(available, min(needed, len(available)))
                    for q in extra:
                        used_ids.add(q["question_id"])
                        question_ids.append(q["question_id"])
        
        duration_minutes = int(len(question_ids) * 1.5)
        attempt_id = AuthService.generate_id("attempt_")
        now = datetime.now(timezone.utc).isoformat()
        
        attempt_doc = {
            "attempt_id": attempt_id,
            "simulator_id": simulator_id,
            "user_id": user_id,
            "started_at": now,
            "finished_at": None,
            "score": None,
            "status": "in_progress",
            "answers": [],
            "total_questions": len(question_ids),
            "duration_minutes": duration_minutes,
            "question_ids": question_ids,
            "saved_progress": {
                "current_question": 0,
                "time_remaining": duration_minutes * 60,
                "answers": []
            }
        }
        
        try:
            await db.attempts.insert_one(attempt_doc)
            return attempt_doc
        except DuplicateKeyError:
            # Race condition: another request created the attempt
            # Return the existing attempt
            existing = await db.attempts.find_one({
                "user_id": user_id,
                "simulator_id": simulator_id,
                "status": "in_progress"
            }, {"_id": 0})
            if existing:
                return existing
            raise
    
    @staticmethod
    async def calculate_subject_scores(answers_data: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Calculate scores per subject from answers"""
        subject_scores = {}
        
        for answer in answers_data:
            subject_name = answer.get("subject_name", "Unknown")
            
            if subject_name not in subject_scores:
                subject_scores[subject_name] = {"correct": 0, "total": 0}
            
            subject_scores[subject_name]["total"] += 1
            if answer.get("is_correct"):
                subject_scores[subject_name]["correct"] += 1
        
        return subject_scores
