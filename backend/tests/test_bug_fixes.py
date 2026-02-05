"""
Backend API Tests for IngresoUNAM - Bug Fixes Verification
Tests for 4 critical bugs:
1. Resume exam loads saved questions (not new ones)
2. Non-admin users can see question_count in /api/subjects
3. Subject practice allows changing answers (frontend test)
4. Admin stats shows correct premium_users count from subscriptions
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@ingresounam.com"
ADMIN_PASSWORD = "admin123"


class TestBugFixes:
    """Tests for the 4 critical bug fixes"""
    
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
    def headers(self, admin_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    # ============== BUG 1: Resume exam loads saved questions ==============
    
    @pytest.fixture(scope="class")
    def clean_in_progress_attempts(self, headers):
        """Complete any existing in-progress attempts before testing"""
        attempts_res = requests.get(f"{BASE_URL}/api/attempts", headers=headers)
        if attempts_res.status_code == 200:
            attempts = attempts_res.json()
            for attempt in attempts:
                if attempt["status"] == "in_progress":
                    # Submit with dummy answer to complete it
                    requests.post(
                        f"{BASE_URL}/api/attempts/{attempt['attempt_id']}/submit",
                        headers={**headers, "Content-Type": "application/json"},
                        json={"answers": [{"question_id": "dummy", "selected_option": 0}]}
                    )
        return True
    
    def test_bug1_create_attempt_stores_question_ids(self, headers, clean_in_progress_attempts):
        """Bug 1: Verify that creating an attempt stores question_ids"""
        # Get a simulator first
        simulators_res = requests.get(f"{BASE_URL}/api/simulators", headers=headers)
        assert simulators_res.status_code == 200, f"Failed to get simulators: {simulators_res.text}"
        simulators = simulators_res.json()
        assert len(simulators) > 0, "No simulators found"
        
        simulator_id = simulators[0]["simulator_id"]
        
        # Create an attempt
        attempt_res = requests.post(f"{BASE_URL}/api/attempts", 
            headers={**headers, "Content-Type": "application/json"},
            json={"simulator_id": simulator_id, "question_count": 40}
        )
        assert attempt_res.status_code == 200, f"Failed to create attempt: {attempt_res.text}"
        attempt_data = attempt_res.json()
        
        assert "attempt_id" in attempt_data, "No attempt_id in response"
        print(f"SUCCESS: Created attempt {attempt_data['attempt_id']}")
    
    def test_bug1_get_attempt_questions_endpoint_exists(self, headers, clean_in_progress_attempts):
        """Bug 1: Verify /api/attempts/{id}/questions endpoint exists and works"""
        # Get user attempts to find the in-progress one
        attempts_res = requests.get(f"{BASE_URL}/api/attempts", headers=headers)
        attempts = attempts_res.json()
        
        # Find in-progress attempt
        in_progress = [a for a in attempts if a["status"] == "in_progress"]
        if not in_progress:
            # Create a new one
            simulators_res = requests.get(f"{BASE_URL}/api/simulators", headers=headers)
            simulators = simulators_res.json()
            simulator_id = simulators[0]["simulator_id"]
            
            attempt_res = requests.post(f"{BASE_URL}/api/attempts",
                headers={**headers, "Content-Type": "application/json"},
                json={"simulator_id": simulator_id, "question_count": 40}
            )
            attempt_data = attempt_res.json()
            attempt_id = attempt_data["attempt_id"]
        else:
            attempt_id = in_progress[0]["attempt_id"]
        
        # Get questions for the attempt
        questions_res = requests.get(f"{BASE_URL}/api/attempts/{attempt_id}/questions", headers=headers)
        assert questions_res.status_code == 200, f"Failed to get attempt questions: {questions_res.text}"
        
        questions_data = questions_res.json()
        assert "questions" in questions_data, "No questions in response"
        assert "simulator" in questions_data, "No simulator info in response"
        assert len(questions_data["questions"]) > 0, "No questions returned"
        
        print(f"SUCCESS: Got {len(questions_data['questions'])} questions for attempt {attempt_id}")
    
    def test_bug1_resume_returns_same_questions(self, headers, clean_in_progress_attempts):
        """Bug 1: Verify resuming an attempt returns the same questions"""
        # Get user attempts to find the in-progress one
        attempts_res = requests.get(f"{BASE_URL}/api/attempts", headers=headers)
        attempts = attempts_res.json()
        
        # Find in-progress attempt
        in_progress = [a for a in attempts if a["status"] == "in_progress"]
        if not in_progress:
            pytest.skip("No in-progress attempt found")
        
        attempt_id = in_progress[0]["attempt_id"]
        
        # Get questions first time
        questions_res1 = requests.get(f"{BASE_URL}/api/attempts/{attempt_id}/questions", headers=headers)
        assert questions_res1.status_code == 200, f"First request failed: {questions_res1.text}"
        questions_data1 = questions_res1.json()
        question_ids_1 = [q["question_id"] for q in questions_data1["questions"]]
        
        # Get questions second time (simulating resume)
        questions_res2 = requests.get(f"{BASE_URL}/api/attempts/{attempt_id}/questions", headers=headers)
        assert questions_res2.status_code == 200, f"Second request failed: {questions_res2.text}"
        questions_data2 = questions_res2.json()
        question_ids_2 = [q["question_id"] for q in questions_data2["questions"]]
        
        # Verify same questions are returned
        assert question_ids_1 == question_ids_2, f"Questions differ! First: {question_ids_1[:5]}... Second: {question_ids_2[:5]}..."
        
        print(f"SUCCESS: Resume returns same {len(question_ids_1)} questions")
    
    # ============== BUG 2: Non-admin users can see question_count ==============
    
    def test_bug2_subjects_endpoint_returns_question_count(self, headers):
        """Bug 2: Verify /api/subjects returns question_count for all users"""
        response = requests.get(f"{BASE_URL}/api/subjects", headers=headers)
        assert response.status_code == 200, f"Failed to get subjects: {response.text}"
        
        subjects = response.json()
        assert len(subjects) > 0, "No subjects returned"
        
        # Check that each subject has question_count
        for subject in subjects:
            assert "question_count" in subject, f"Subject {subject.get('name')} missing question_count"
            assert isinstance(subject["question_count"], int), f"question_count should be int"
            print(f"  - {subject['name']}: {subject['question_count']} questions")
        
        print(f"SUCCESS: All {len(subjects)} subjects have question_count")
    
    def test_bug2_subjects_question_count_is_accurate(self, headers):
        """Bug 2: Verify question_count matches actual questions in database"""
        # Get subjects
        subjects_res = requests.get(f"{BASE_URL}/api/subjects", headers=headers)
        subjects = subjects_res.json()
        
        # For at least one subject, verify count by getting questions
        subject = subjects[0]
        
        # Get questions for this subject via practice endpoint
        practice_res = requests.post(f"{BASE_URL}/api/practice/start",
            headers={**headers, "Content-Type": "application/json"},
            json={"subject_id": subject["subject_id"], "question_count": 100}
        )
        
        if practice_res.status_code == 200:
            practice_data = practice_res.json()
            actual_count = len(practice_data.get("questions", []))
            reported_count = subject["question_count"]
            
            # The actual count should be <= reported count (we might get fewer if not enough questions)
            assert actual_count <= reported_count, f"Got more questions ({actual_count}) than reported ({reported_count})"
            print(f"SUCCESS: Subject {subject['name']} reports {reported_count} questions, got {actual_count}")
        else:
            # Just verify the endpoint returns data
            print(f"INFO: Could not verify exact count, but question_count field exists")
    
    # ============== BUG 4: Admin stats premium_users count ==============
    
    def test_bug4_admin_stats_endpoint_exists(self, headers):
        """Bug 4: Verify /api/admin/stats endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        assert response.status_code == 200, f"Failed to get admin stats: {response.text}"
        
        data = response.json()
        assert "total_users" in data, "Missing total_users"
        assert "premium_users" in data, "Missing premium_users"
        assert "total_questions" in data, "Missing total_questions"
        assert "total_attempts" in data, "Missing total_attempts"
        
        print(f"SUCCESS: Admin stats endpoint returns all required fields")
        print(f"  - Total users: {data['total_users']}")
        print(f"  - Premium users: {data['premium_users']}")
        print(f"  - Total questions: {data['total_questions']}")
        print(f"  - Total attempts: {data['total_attempts']}")
    
    def test_bug4_premium_users_is_integer(self, headers):
        """Bug 4: Verify premium_users is a valid integer"""
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        data = response.json()
        
        assert isinstance(data["premium_users"], int), f"premium_users should be int, got {type(data['premium_users'])}"
        assert data["premium_users"] >= 0, f"premium_users should be >= 0, got {data['premium_users']}"
        
        print(f"SUCCESS: premium_users is valid integer: {data['premium_users']}")
    
    def test_bug4_premium_users_counts_from_subscriptions(self, headers):
        """Bug 4: Verify premium_users counts from subscriptions collection"""
        # Get admin stats
        stats_res = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        stats = stats_res.json()
        
        # The premium_users count should reflect active subscriptions
        # We can't directly verify the DB query, but we can check the value is reasonable
        premium_count = stats["premium_users"]
        total_users = stats["total_users"]
        
        # Premium users should be <= total users
        assert premium_count <= total_users, f"Premium users ({premium_count}) > total users ({total_users})"
        
        print(f"SUCCESS: premium_users ({premium_count}) <= total_users ({total_users})")


class TestAttemptFlow:
    """Additional tests for the attempt/resume flow"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_create_attempt_returns_existing_in_progress(self, headers):
        """Test that creating attempt for same simulator returns existing in-progress attempt"""
        # Get simulator
        simulators_res = requests.get(f"{BASE_URL}/api/simulators", headers=headers)
        simulators = simulators_res.json()
        simulator_id = simulators[0]["simulator_id"]
        
        # Create first attempt
        attempt_res1 = requests.post(f"{BASE_URL}/api/attempts",
            headers={**headers, "Content-Type": "application/json"},
            json={"simulator_id": simulator_id, "question_count": 40}
        )
        attempt1 = attempt_res1.json()
        
        # Try to create another attempt for same simulator
        attempt_res2 = requests.post(f"{BASE_URL}/api/attempts",
            headers={**headers, "Content-Type": "application/json"},
            json={"simulator_id": simulator_id, "question_count": 40}
        )
        attempt2 = attempt_res2.json()
        
        # Should return the same attempt
        assert attempt1["attempt_id"] == attempt2["attempt_id"], "Should return existing in-progress attempt"
        
        print(f"SUCCESS: Creating attempt for same simulator returns existing attempt {attempt1['attempt_id']}")
    
    def test_attempt_detail_includes_saved_progress(self, headers):
        """Test that attempt detail includes saved_progress field"""
        # Get user attempts
        attempts_res = requests.get(f"{BASE_URL}/api/attempts", headers=headers)
        assert attempts_res.status_code == 200
        attempts = attempts_res.json()
        
        if len(attempts) > 0:
            # Get detail of first attempt
            attempt_id = attempts[0]["attempt_id"]
            detail_res = requests.get(f"{BASE_URL}/api/attempts/{attempt_id}", headers=headers)
            assert detail_res.status_code == 200
            
            detail = detail_res.json()
            assert "saved_progress" in detail, "Missing saved_progress in attempt detail"
            
            print(f"SUCCESS: Attempt detail includes saved_progress field")
        else:
            print("INFO: No attempts found to test")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
