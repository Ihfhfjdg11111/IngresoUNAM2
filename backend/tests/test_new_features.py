"""
Backend API Tests for IngresoUNAM - New Features
Tests: Practice mode, Analytics, Bulk import, Exam submission prevention
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://unam-practice-1.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "admin@ingresounam.com"
ADMIN_PASSWORD = "admin123"
TEST_USER_EMAIL = f"test_practice_{os.urandom(4).hex()}@test.com"
TEST_USER_PASSWORD = "testpass123"
TEST_USER_NAME = "Test Practice User"


class TestAuthentication:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def test_user_token(self):
        """Create test user and get token"""
        # Register new user
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD,
            "name": TEST_USER_NAME
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        elif response.status_code == 400:
            # User exists, try login
            response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            })
            assert response.status_code == 200, f"Test user login failed: {response.text}"
            return response.json()["access_token"]
        else:
            pytest.fail(f"Failed to create test user: {response.text}")
    
    def test_admin_login(self, admin_token):
        """Test admin login works"""
        assert admin_token is not None
        print(f"SUCCESS: Admin login successful")


class TestPracticeMode:
    """Tests for enhanced practice mode with question count selection"""
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get user token for practice tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def subjects(self, user_token):
        """Get available subjects"""
        response = requests.get(f"{BASE_URL}/api/subjects", headers={
            "Authorization": f"Bearer {user_token}"
        })
        assert response.status_code == 200
        return response.json()
    
    def test_start_practice_with_5_questions(self, user_token, subjects):
        """Test starting practice with 5 questions (minimum)"""
        subject = subjects[0]
        response = requests.post(f"{BASE_URL}/api/practice/start", 
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "subject_id": subject["subject_id"],
                "question_count": 5
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "practice_id" in data
        assert "questions" in data
        assert len(data["questions"]) == 5
        print(f"SUCCESS: Practice started with 5 questions for {subject['name']}")
    
    def test_start_practice_with_10_questions(self, user_token, subjects):
        """Test starting practice with 10 questions (default)"""
        subject = subjects[1] if len(subjects) > 1 else subjects[0]
        response = requests.post(f"{BASE_URL}/api/practice/start", 
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "subject_id": subject["subject_id"],
                "question_count": 10
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert len(data["questions"]) == 10
        print(f"SUCCESS: Practice started with 10 questions")
    
    def test_start_practice_with_20_questions(self, user_token, subjects):
        """Test starting practice with 20 questions"""
        subject = subjects[0]
        response = requests.post(f"{BASE_URL}/api/practice/start", 
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "subject_id": subject["subject_id"],
                "question_count": 20
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert len(data["questions"]) == 20
        print(f"SUCCESS: Practice started with 20 questions")
    
    def test_start_practice_invalid_count_too_low(self, user_token, subjects):
        """Test that question count below 5 is rejected"""
        subject = subjects[0]
        response = requests.post(f"{BASE_URL}/api/practice/start", 
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "subject_id": subject["subject_id"],
                "question_count": 3
            }
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print(f"SUCCESS: Question count < 5 correctly rejected")
    
    def test_start_practice_invalid_count_too_high(self, user_token, subjects):
        """Test that question count above 30 is rejected"""
        subject = subjects[0]
        response = requests.post(f"{BASE_URL}/api/practice/start", 
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "subject_id": subject["subject_id"],
                "question_count": 50
            }
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print(f"SUCCESS: Question count > 30 correctly rejected")
    
    def test_submit_practice_and_get_results(self, user_token, subjects):
        """Test submitting practice and getting detailed results"""
        subject = subjects[0]
        
        # Start practice
        start_response = requests.post(f"{BASE_URL}/api/practice/start", 
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "subject_id": subject["subject_id"],
                "question_count": 5
            }
        )
        assert start_response.status_code == 200
        practice_data = start_response.json()
        practice_id = practice_data["practice_id"]
        questions = practice_data["questions"]
        
        # Submit answers (answer all with option 0)
        answers = [{"question_id": q["question_id"], "selected_option": 0} for q in questions]
        
        submit_response = requests.post(f"{BASE_URL}/api/practice/{practice_id}/submit",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"answers": answers}
        )
        assert submit_response.status_code == 200, f"Submit failed: {submit_response.text}"
        
        results = submit_response.json()
        assert "score" in results
        assert "total" in results
        assert "percentage" in results
        assert "results" in results
        assert len(results["results"]) == 5
        
        # Check result structure
        for result in results["results"]:
            assert "question_id" in result
            assert "is_correct" in result
            assert "correct_answer" in result
            assert "selected_option" in result
            assert "explanation" in result
        
        print(f"SUCCESS: Practice submitted with score {results['score']}/{results['total']} ({results['percentage']}%)")


class TestStudentAnalytics:
    """Tests for student analytics endpoint"""
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get user token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_get_student_performance(self, user_token):
        """Test getting student analytics"""
        response = requests.get(f"{BASE_URL}/api/analytics/student/performance",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # Check required fields
        assert "total_attempts" in data
        assert "total_questions_answered" in data
        assert "overall_accuracy" in data
        assert "subject_performance" in data
        assert "progress_trend" in data
        assert "recommendations" in data
        
        print(f"SUCCESS: Analytics returned - {data['total_attempts']} attempts, {data['overall_accuracy']}% accuracy")
    
    def test_analytics_has_weak_strong_subjects(self, user_token):
        """Test that analytics includes weak and strong subjects"""
        response = requests.get(f"{BASE_URL}/api/analytics/student/performance",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "weak_subjects" in data
        assert "strong_subjects" in data
        
        print(f"SUCCESS: Analytics includes weak/strong subjects analysis")


class TestBulkImport:
    """Tests for bulk question import"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_bulk_import_json(self, admin_token):
        """Test bulk import with JSON format"""
        questions = [
            {
                "subject_id": "subj_matematicas",
                "topic": "TEST_Álgebra",
                "text": "TEST_Pregunta de prueba para importación masiva 1",
                "options": ["Opción A", "Opción B", "Opción C", "Opción D"],
                "correct_answer": 0,
                "explanation": "Esta es una pregunta de prueba"
            },
            {
                "subject_id": "subj_fisica",
                "topic": "TEST_Mecánica",
                "text": "TEST_Pregunta de prueba para importación masiva 2",
                "options": ["Opción 1", "Opción 2", "Opción 3", "Opción 4"],
                "correct_answer": 1,
                "explanation": "Esta es otra pregunta de prueba"
            }
        ]
        
        response = requests.post(f"{BASE_URL}/api/admin/questions/bulk",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"questions": questions}
        )
        assert response.status_code == 200, f"Bulk import failed: {response.text}"
        
        data = response.json()
        assert "imported" in data
        assert data["imported"] >= 2
        print(f"SUCCESS: Bulk import - {data['imported']} questions imported")
    
    def test_bulk_import_with_invalid_subject(self, admin_token):
        """Test bulk import with invalid subject ID"""
        questions = [
            {
                "subject_id": "invalid_subject_id",
                "topic": "Test",
                "text": "Test question",
                "options": ["A", "B", "C", "D"],
                "correct_answer": 0,
                "explanation": "Test"
            }
        ]
        
        response = requests.post(f"{BASE_URL}/api/admin/questions/bulk",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"questions": questions}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["imported"] == 0
        assert len(data["errors"]) > 0
        print(f"SUCCESS: Invalid subject correctly reported as error")
    
    def test_bulk_import_requires_admin(self):
        """Test that bulk import requires admin role"""
        # Create regular user
        reg_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"regular_{os.urandom(4).hex()}@test.com",
            "password": "testpass123",
            "name": "Regular User"
        })
        
        if reg_response.status_code == 200:
            token = reg_response.json()["access_token"]
            
            response = requests.post(f"{BASE_URL}/api/admin/questions/bulk",
                headers={"Authorization": f"Bearer {token}"},
                json={"questions": []}
            )
            assert response.status_code == 403, f"Expected 403, got {response.status_code}"
            print(f"SUCCESS: Bulk import correctly requires admin role")
        else:
            pytest.skip("Could not create regular user for test")


class TestExamSubmission:
    """Tests for exam submission prevention (incomplete exams)"""
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get user token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def simulator_id(self, user_token):
        """Get a simulator ID"""
        response = requests.get(f"{BASE_URL}/api/simulators",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200
        simulators = response.json()
        assert len(simulators) > 0
        return simulators[0]["simulator_id"]
    
    def test_create_attempt(self, user_token, simulator_id):
        """Test creating an exam attempt"""
        response = requests.post(f"{BASE_URL}/api/attempts",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"simulator_id": simulator_id}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "attempt_id" in data
        assert data["status"] == "in_progress"
        print(f"SUCCESS: Exam attempt created")
    
    def test_submit_incomplete_exam_rejected(self, user_token, simulator_id):
        """Test that submitting incomplete exam is rejected"""
        # Create new attempt
        create_response = requests.post(f"{BASE_URL}/api/attempts",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"simulator_id": simulator_id}
        )
        assert create_response.status_code == 200
        attempt_id = create_response.json()["attempt_id"]
        
        # Try to submit with only 5 answers (should need 120)
        answers = [{"question_id": f"q_test{i}", "selected_option": 0} for i in range(5)]
        
        submit_response = requests.post(f"{BASE_URL}/api/attempts/{attempt_id}/submit",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"answers": answers}
        )
        
        # Should be rejected because not all questions answered
        assert submit_response.status_code == 400, f"Expected 400, got {submit_response.status_code}"
        print(f"SUCCESS: Incomplete exam submission correctly rejected")


class TestSubjectsAndQuestions:
    """Tests for subjects and questions endpoints"""
    
    @pytest.fixture(scope="class")
    def user_token(self):
        """Get user token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_get_subjects(self, user_token):
        """Test getting all subjects"""
        response = requests.get(f"{BASE_URL}/api/subjects",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200
        
        subjects = response.json()
        assert len(subjects) == 10  # 10 subjects expected
        
        for subject in subjects:
            assert "subject_id" in subject
            assert "name" in subject
            assert "question_count" in subject
        
        print(f"SUCCESS: {len(subjects)} subjects returned")
    
    def test_get_subject_questions(self, user_token):
        """Test getting questions for a subject"""
        # Get subjects first
        subjects_response = requests.get(f"{BASE_URL}/api/subjects",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        subjects = subjects_response.json()
        subject_id = subjects[0]["subject_id"]
        
        response = requests.get(f"{BASE_URL}/api/subjects/{subject_id}/questions?limit=10",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200
        
        questions = response.json()
        assert len(questions) <= 10
        
        for q in questions:
            assert "question_id" in q
            assert "text" in q
            assert "options" in q
            assert len(q["options"]) == 4
        
        print(f"SUCCESS: {len(questions)} questions returned for subject")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
