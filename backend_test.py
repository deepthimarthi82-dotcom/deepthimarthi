#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Spark Dating App
Tests all endpoints including auth, profile, discover, swipe, matches, messaging, AI features, and subscriptions
"""

import requests
import sys
import json
from datetime import datetime, timezone
import time

class SparkAPITester:
    def __init__(self, base_url="https://spark-dating-118.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.demo_users = [
            {"email": "demo1@spark.app", "password": "password123"},
            {"email": "demo2@spark.app", "password": "password123"},
            {"email": "demo3@spark.app", "password": "password123"}
        ]

    def log_test(self, name, success, response_data=None, error=None):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            self.failed_tests.append({"name": name, "error": error, "response": response_data})
            print(f"❌ {name} - {error}")

    def make_request(self, method, endpoint, data=None, headers=None):
        """Make HTTP request with error handling"""
        url = f"{self.api_url}{endpoint}"
        request_headers = {"Content-Type": "application/json"}
        
        if headers:
            request_headers.update(headers)
        
        if self.token:
            request_headers["Authorization"] = f"Bearer {self.token}"

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=request_headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, headers=request_headers, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data, headers=request_headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return response
        except requests.exceptions.RequestException as e:
            return None

    def test_health_check(self):
        """Test basic health endpoints"""
        print("\n🔍 Testing Health Endpoints...")
        
        # Test root endpoint
        response = self.make_request("GET", "/")
        if response and response.status_code == 200:
            self.log_test("Root endpoint (/api/)", True)
        else:
            self.log_test("Root endpoint (/api/)", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test health endpoint
        response = self.make_request("GET", "/health")
        if response and response.status_code == 200:
            self.log_test("Health endpoint (/api/health)", True)
        else:
            self.log_test("Health endpoint (/api/health)", False, error=f"Status: {response.status_code if response else 'No response'}")

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n🔍 Testing Authentication Endpoints...")
        
        # Test registration with new user
        test_email = f"test_{int(time.time())}@spark.app"
        register_data = {
            "email": test_email,
            "password": "testpass123",
            "name": "Test User"
        }
        
        response = self.make_request("POST", "/auth/register", register_data)
        if response and response.status_code == 200:
            data = response.json()
            if "token" in data and "user_id" in data:
                self.token = data["token"]
                self.user_id = data["user_id"]
                self.log_test("User Registration", True)
            else:
                self.log_test("User Registration", False, error="Missing token or user_id in response")
        else:
            self.log_test("User Registration", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test login with demo user
        login_data = self.demo_users[0]
        response = self.make_request("POST", "/auth/login", login_data)
        if response and response.status_code == 200:
            data = response.json()
            if "token" in data:
                self.token = data["token"]
                self.user_id = data["user_id"]
                self.log_test("Demo User Login", True)
            else:
                self.log_test("Demo User Login", False, error="Missing token in response")
        else:
            self.log_test("Demo User Login", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test /auth/me endpoint
        if self.token:
            response = self.make_request("GET", "/auth/me")
            if response and response.status_code == 200:
                data = response.json()
                if "id" in data and "email" in data:
                    self.log_test("Get Current User (/auth/me)", True)
                else:
                    self.log_test("Get Current User (/auth/me)", False, error="Missing user data")
            else:
                self.log_test("Get Current User (/auth/me)", False, error=f"Status: {response.status_code if response else 'No response'}")

    def test_profile_endpoints(self):
        """Test profile management endpoints"""
        print("\n🔍 Testing Profile Endpoints...")
        
        if not self.token:
            print("❌ Skipping profile tests - no auth token")
            return

        # Test profile update
        profile_data = {
            "name": "Test User Updated",
            "age": 28,
            "gender": "man",
            "looking_for": "women",
            "bio": "Test bio for dating app",
            "photos": ["https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=400"],
            "location": "New York",
            "job_title": "Software Engineer",
            "company": "Tech Corp",
            "education": "University",
            "height": "6'0\"",
            "intentions": "Long-term relationship",
            "dealbreakers": ["Smoking"],
            "interests": ["Travel", "Music", "Fitness"],
            "prompts": [{"question": "What makes you happy?", "answer": "Good coffee and great company"}]
        }
        
        response = self.make_request("PUT", "/profile", profile_data)
        if response and response.status_code == 200:
            self.log_test("Profile Update", True)
        else:
            self.log_test("Profile Update", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test compatibility quiz
        quiz_data = {
            "communication_style": "direct",
            "conflict_resolution": "talk it out",
            "love_language": "words",
            "life_goals": ["Career", "Family", "Travel"],
            "values": ["Honesty", "Kindness", "Humor"],
            "weekend_preference": "adventure",
            "social_battery": "ambivert"
        }
        
        response = self.make_request("PUT", "/profile/quiz", quiz_data)
        if response and response.status_code == 200:
            self.log_test("Compatibility Quiz", True)
        else:
            self.log_test("Compatibility Quiz", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test video verification
        response = self.make_request("POST", "/profile/verify-video")
        if response and response.status_code == 200:
            self.log_test("Video Verification", True)
        else:
            self.log_test("Video Verification", False, error=f"Status: {response.status_code if response else 'No response'}")

    def test_discover_endpoints(self):
        """Test discovery and swiping endpoints"""
        print("\n🔍 Testing Discovery Endpoints...")
        
        if not self.token:
            print("❌ Skipping discovery tests - no auth token")
            return

        # Test discover profiles
        response = self.make_request("GET", "/discover")
        if response and response.status_code == 200:
            data = response.json()
            if "profiles" in data:
                self.log_test("Discover Profiles", True)
                # Store first profile for swipe test
                if data["profiles"]:
                    self.target_user_id = data["profiles"][0]["id"]
            else:
                self.log_test("Discover Profiles", False, error="Missing profiles in response")
        else:
            self.log_test("Discover Profiles", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test daily picks
        response = self.make_request("GET", "/discover/daily-picks")
        if response and response.status_code == 200:
            data = response.json()
            if "daily_picks" in data:
                self.log_test("Daily Picks", True)
            else:
                self.log_test("Daily Picks", False, error="Missing daily_picks in response")
        else:
            self.log_test("Daily Picks", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test swipe action (if we have a target user)
        if hasattr(self, 'target_user_id'):
            swipe_data = {
                "target_user_id": self.target_user_id,
                "action": "like"
            }
            response = self.make_request("POST", "/swipe", swipe_data)
            if response and response.status_code == 200:
                data = response.json()
                if "success" in data:
                    self.log_test("Swipe Action", True)
                else:
                    self.log_test("Swipe Action", False, error="Missing success in response")
            else:
                self.log_test("Swipe Action", False, error=f"Status: {response.status_code if response else 'No response'}")

    def test_matches_endpoints(self):
        """Test matches and messaging endpoints"""
        print("\n🔍 Testing Matches Endpoints...")
        
        if not self.token:
            print("❌ Skipping matches tests - no auth token")
            return

        # Test get matches
        response = self.make_request("GET", "/matches")
        if response and response.status_code == 200:
            data = response.json()
            if "matches" in data:
                self.log_test("Get Matches", True)
                # Store first match for message test
                if data["matches"]:
                    self.match_id = data["matches"][0]["match_id"]
            else:
                self.log_test("Get Matches", False, error="Missing matches in response")
        else:
            self.log_test("Get Matches", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test likes-you endpoint
        response = self.make_request("GET", "/likes-you")
        if response and response.status_code == 200:
            data = response.json()
            if "count" in data and "likes" in data:
                self.log_test("Likes You", True)
            else:
                self.log_test("Likes You", False, error="Missing count or likes in response")
        else:
            self.log_test("Likes You", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test messages (if we have a match)
        if hasattr(self, 'match_id'):
            response = self.make_request("GET", f"/messages/{self.match_id}")
            if response and response.status_code == 200:
                data = response.json()
                if "messages" in data:
                    self.log_test("Get Messages", True)
                else:
                    self.log_test("Get Messages", False, error="Missing messages in response")
            else:
                self.log_test("Get Messages", False, error=f"Status: {response.status_code if response else 'No response'}")

            # Test send message
            message_data = {
                "match_id": self.match_id,
                "content": "Hello! This is a test message.",
                "message_type": "text"
            }
            response = self.make_request("POST", "/messages", message_data)
            if response and response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_test("Send Message", True)
                else:
                    self.log_test("Send Message", False, error="Missing message in response")
            else:
                self.log_test("Send Message", False, error=f"Status: {response.status_code if response else 'No response'}")

    def test_ai_endpoints(self):
        """Test AI-powered features"""
        print("\n🔍 Testing AI Endpoints...")
        
        if not self.token:
            print("❌ Skipping AI tests - no auth token")
            return

        # Test AI compatibility (if we have a target user)
        if hasattr(self, 'target_user_id'):
            response = self.make_request("POST", f"/ai/compatibility/{self.target_user_id}")
            if response and response.status_code == 200:
                data = response.json()
                if "score" in data and "insights" in data:
                    self.log_test("AI Compatibility", True)
                else:
                    self.log_test("AI Compatibility", False, error="Missing score or insights in response")
            else:
                self.log_test("AI Compatibility", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test AI icebreakers (if we have a match)
        if hasattr(self, 'match_id'):
            response = self.make_request("GET", f"/ai/icebreakers/{self.match_id}")
            if response and response.status_code == 200:
                data = response.json()
                if "icebreakers" in data:
                    self.log_test("AI Icebreakers", True)
                else:
                    self.log_test("AI Icebreakers", False, error="Missing icebreakers in response")
            else:
                self.log_test("AI Icebreakers", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test AI date ideas
        response = self.make_request("GET", "/ai/date-ideas?location=New York")
        if response and response.status_code == 200:
            data = response.json()
            if "date_ideas" in data:
                self.log_test("AI Date Ideas", True)
            else:
                self.log_test("AI Date Ideas", False, error="Missing date_ideas in response")
        else:
            self.log_test("AI Date Ideas", False, error=f"Status: {response.status_code if response else 'No response'}")

    def test_subscription_endpoints(self):
        """Test subscription and payment endpoints"""
        print("\n🔍 Testing Subscription Endpoints...")
        
        # Test get subscription plans (no auth required)
        response = self.make_request("GET", "/subscription/plans")
        if response and response.status_code == 200:
            data = response.json()
            if "plans" in data:
                self.log_test("Get Subscription Plans", True)
            else:
                self.log_test("Get Subscription Plans", False, error="Missing plans in response")
        else:
            self.log_test("Get Subscription Plans", False, error=f"Status: {response.status_code if response else 'No response'}")

        if not self.token:
            print("❌ Skipping checkout tests - no auth token")
            return

        # Test create checkout session
        checkout_data = {
            "plan_id": "premium_monthly",
            "origin_url": self.base_url
        }
        response = self.make_request("POST", "/subscription/checkout", checkout_data)
        if response and response.status_code == 200:
            data = response.json()
            if "checkout_url" in data and "session_id" in data:
                self.log_test("Create Checkout Session", True)
                self.session_id = data["session_id"]
            else:
                self.log_test("Create Checkout Session", False, error="Missing checkout_url or session_id")
        else:
            self.log_test("Create Checkout Session", False, error=f"Status: {response.status_code if response else 'No response'}")

    def test_settings_endpoints(self):
        """Test settings endpoints"""
        print("\n🔍 Testing Settings Endpoints...")
        
        if not self.token:
            print("❌ Skipping settings tests - no auth token")
            return

        # Test get settings
        response = self.make_request("GET", "/settings")
        if response and response.status_code == 200:
            data = response.json()
            if "slow_dating_mode" in data and "subscription" in data:
                self.log_test("Get Settings", True)
            else:
                self.log_test("Get Settings", False, error="Missing settings data")
        else:
            self.log_test("Get Settings", False, error=f"Status: {response.status_code if response else 'No response'}")

        # Test toggle slow dating mode
        response = self.make_request("PUT", "/settings/slow-dating?enabled=true")
        if response and response.status_code == 200:
            data = response.json()
            if "slow_dating_mode" in data:
                self.log_test("Toggle Slow Dating Mode", True)
            else:
                self.log_test("Toggle Slow Dating Mode", False, error="Missing slow_dating_mode in response")
        else:
            self.log_test("Toggle Slow Dating Mode", False, error=f"Status: {response.status_code if response else 'No response'}")

    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting Spark Dating App Backend API Tests")
        print(f"🌐 Testing against: {self.base_url}")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run test suites
        self.test_health_check()
        self.test_auth_endpoints()
        self.test_profile_endpoints()
        self.test_discover_endpoints()
        self.test_matches_endpoints()
        self.test_ai_endpoints()
        self.test_subscription_endpoints()
        self.test_settings_endpoints()
        
        end_time = time.time()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Tests Passed: {self.tests_passed}")
        print(f"❌ Tests Failed: {len(self.failed_tests)}")
        print(f"📈 Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        print(f"⏱️  Total Time: {end_time - start_time:.2f}s")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for test in self.failed_tests:
                print(f"  • {test['name']}: {test['error']}")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test execution"""
    tester = SparkAPITester()
    success = tester.run_all_tests()
    
    # Return appropriate exit code
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())