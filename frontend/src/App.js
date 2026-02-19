import React, { useState, useEffect, createContext, useContext, useCallback } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Heart, X, Star, MessageCircle, User, Settings, Shield, Zap, Crown, ChevronRight, ChevronLeft, Check, Camera, Mic, Video, MapPin, Clock, AlertCircle, Sparkles, Calendar, Coffee, Send, ArrowLeft, Eye, Lock, Play, Pause } from "lucide-react";
import { Toaster, toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Auth Context
const AuthContext = createContext(null);

const useAuth = () => useContext(AuthContext);

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("spark_token"));
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUser(res.data);
    } catch (e) {
      localStorage.removeItem("spark_token");
      setToken(null);
    }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = (newToken, userData) => {
    localStorage.setItem("spark_token", newToken);
    setToken(newToken);
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem("spark_token");
    setToken(null);
    setUser(null);
  };

  const refreshUser = () => fetchUser();

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

// API Helper
const apiCall = async (method, endpoint, data = null, token = null) => {
  const config = {
    method,
    url: `${API}${endpoint}`,
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  };
  if (data) config.data = data;
  const res = await axios(config);
  return res.data;
};

// ==================== LANDING PAGE ====================
const LandingPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  useEffect(() => {
    if (user) {
      if (!user.profile_complete) navigate("/onboarding");
      else if (!user.quiz_complete) navigate("/quiz");
      else navigate("/discover");
    }
  }, [user, navigate]);

  const features = [
    { icon: Shield, title: "Video Verified", desc: "Real people, verified with live selfies" },
    { icon: Heart, title: "AI Matching", desc: "Smart compatibility scores that actually work" },
    { icon: Zap, title: "No Time Wasters", desc: "Matches expire - talk or move on" },
    { icon: Calendar, title: "Date Check-ins", desc: "Stay safe with safety alerts" },
  ];

  return (
    <div className="min-h-screen bg-[#FDFBF7] grain" data-testid="landing-page">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="max-w-7xl mx-auto px-6 py-8">
          {/* Nav */}
          <nav className="flex justify-between items-center mb-16">
            <h1 className="text-3xl font-bold" style={{ fontFamily: 'Syne' }}>
              <span className="text-[#FF2E63]">Spark</span>
            </h1>
            <button 
              onClick={() => navigate("/login")}
              className="btn-ghost"
              data-testid="login-btn"
            >
              Log In
            </button>
          </nav>

          {/* Hero Content */}
          <div className="grid md:grid-cols-2 gap-12 items-center min-h-[70vh]">
            <div className="space-y-8">
              <div className="inline-block">
                <span className="badge-accent">For Serious Connections Only</span>
              </div>
              <h2 className="text-5xl md:text-7xl font-extrabold leading-tight" style={{ fontFamily: 'Syne' }}>
                Dating Without The <span className="text-[#FF2E63]">BS</span>
              </h2>
              <p className="text-xl text-gray-600 max-w-lg">
                Swipe smarter, not harder. AI-powered matching for people who are done wasting time.
              </p>
              <div className="flex gap-4 flex-wrap">
                <button 
                  onClick={() => navigate("/signup")}
                  className="btn-primary"
                  data-testid="get-started-btn"
                >
                  Get Started
                </button>
                <button 
                  onClick={() => navigate("/login")}
                  className="btn-secondary"
                  data-testid="have-account-btn"
                >
                  I Have an Account
                </button>
              </div>
            </div>

            {/* Hero Image/Card */}
            <div className="relative">
              <div className="card-brutal p-2 max-w-sm mx-auto transform rotate-3 hover:rotate-0 transition-transform">
                <img 
                  src="https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=400&h=500&fit=crop" 
                  alt="Profile"
                  className="w-full h-80 object-cover rounded-lg"
                />
                <div className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Alex, 28</h3>
                    <div className="bg-[#00CC66] rounded-full p-1">
                      <Check className="w-3 h-3 text-white" />
                    </div>
                  </div>
                  <p className="text-gray-600 mb-3">Software Engineer • NYC</p>
                  <div className="flex gap-2 flex-wrap">
                    <span className="badge-outline">Coffee Addict</span>
                    <span className="badge-outline">Dog Parent</span>
                  </div>
                </div>
              </div>
              {/* Floating elements */}
              <div className="absolute -top-4 -right-4 bg-[#CCFF00] border-2 border-black rounded-full p-3 animate-bounce">
                <Star className="w-6 h-6" />
              </div>
              <div className="absolute bottom-20 -left-8 bg-[#FF2E63] border-2 border-black rounded-full p-3">
                <Heart className="w-6 h-6 text-white" fill="white" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="bg-black text-white py-20">
        <div className="max-w-7xl mx-auto px-6">
          <h3 className="text-4xl font-bold text-center mb-4" style={{ fontFamily: 'Syne' }}>
            What Makes Us <span className="text-[#CCFF00]">Different</span>
          </h3>
          <p className="text-center text-gray-400 mb-12 max-w-2xl mx-auto">
            We fixed everything that's broken about dating apps
          </p>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((f, i) => (
              <div 
                key={i} 
                className="bg-white/5 border border-white/20 rounded-xl p-6 hover:bg-white/10 transition-colors"
              >
                <div className="bg-[#FF2E63] rounded-lg p-3 w-fit mb-4">
                  <f.icon className="w-6 h-6 text-white" />
                </div>
                <h4 className="text-xl font-bold mb-2" style={{ fontFamily: 'Syne' }}>{f.title}</h4>
                <p className="text-gray-400">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h3 className="text-4xl md:text-5xl font-bold mb-6" style={{ fontFamily: 'Syne' }}>
            Ready to Find Your <span className="text-[#FF2E63]">Person</span>?
          </h3>
          <p className="text-xl text-gray-600 mb-8">
            Join thousands who are tired of the games
          </p>
          <button 
            onClick={() => navigate("/signup")}
            className="btn-primary text-lg"
            data-testid="cta-get-started"
          >
            Start Matching Now
          </button>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t-2 border-black py-8 px-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="font-bold" style={{ fontFamily: 'Syne' }}>
            <span className="text-[#FF2E63]">Spark</span> © 2025
          </p>
          <div className="flex gap-6 text-gray-600">
            <span className="hover:text-[#FF2E63] cursor-pointer">Privacy</span>
            <span className="hover:text-[#FF2E63] cursor-pointer">Terms</span>
            <span className="hover:text-[#FF2E63] cursor-pointer">Safety</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

// ==================== AUTH PAGES ====================
const AuthPage = ({ isLogin = true }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const endpoint = isLogin ? "/auth/login" : "/auth/register";
      const data = isLogin ? { email, password } : { email, password, name };
      const res = await apiCall("post", endpoint, data);
      
      login(res.token, { id: res.user_id, profile_complete: res.profile_complete, quiz_complete: res.quiz_complete });
      toast.success(isLogin ? "Welcome back!" : "Account created!");
      
      if (!res.profile_complete) navigate("/onboarding");
      else if (!res.quiz_complete) navigate("/quiz");
      else navigate("/discover");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Something went wrong");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] flex items-center justify-center p-6" data-testid={isLogin ? "login-page" : "signup-page"}>
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 
            className="text-4xl font-bold cursor-pointer mb-2" 
            style={{ fontFamily: 'Syne' }}
            onClick={() => navigate("/")}
          >
            <span className="text-[#FF2E63]">Spark</span>
          </h1>
          <p className="text-gray-600">
            {isLogin ? "Welcome back, hottie" : "Let's get you set up"}
          </p>
        </div>

        <div className="card-brutal p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div>
                <label className="block text-sm font-bold mb-2">Your Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input-brutal"
                  placeholder="What should we call you?"
                  required
                  data-testid="name-input"
                />
              </div>
            )}
            
            <div>
              <label className="block text-sm font-bold mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-brutal"
                placeholder="your@email.com"
                required
                data-testid="email-input"
              />
            </div>
            
            <div>
              <label className="block text-sm font-bold mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-brutal"
                placeholder="••••••••"
                required
                minLength={6}
                data-testid="password-input"
              />
            </div>

            <button 
              type="submit" 
              className="btn-primary w-full"
              disabled={loading}
              data-testid="submit-btn"
            >
              {loading ? "Loading..." : (isLogin ? "Log In" : "Create Account")}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-gray-600">
              {isLogin ? "Don't have an account?" : "Already have an account?"}{" "}
              <button 
                onClick={() => navigate(isLogin ? "/signup" : "/login")}
                className="text-[#FF2E63] font-bold hover:underline"
                data-testid="switch-auth-btn"
              >
                {isLogin ? "Sign Up" : "Log In"}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

// ==================== ONBOARDING ====================
const OnboardingPage = () => {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState({
    name: "",
    age: "",
    gender: "",
    looking_for: "",
    bio: "",
    photos: [],
    location: "",
    job_title: "",
    company: "",
    education: "",
    height: "",
    intentions: "",
    dealbreakers: [],
    interests: [],
    prompts: []
  });
  const navigate = useNavigate();
  const { token, refreshUser, user } = useAuth();

  useEffect(() => {
    if (user?.name) setProfile(p => ({ ...p, name: user.name }));
  }, [user]);

  const totalSteps = 5;

  const updateProfile = (key, value) => {
    setProfile(p => ({ ...p, [key]: value }));
  };

  const toggleArrayItem = (key, item) => {
    setProfile(p => ({
      ...p,
      [key]: p[key].includes(item) 
        ? p[key].filter(i => i !== item) 
        : [...p[key], item]
    }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await apiCall("put", "/profile", {
        ...profile,
        age: parseInt(profile.age),
        photos: profile.photos.length ? profile.photos : [
          "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=400&h=500&fit=crop"
        ]
      }, token);
      await refreshUser();
      toast.success("Profile saved!");
      navigate("/quiz");
    } catch (e) {
      toast.error("Failed to save profile");
    }
    setLoading(false);
  };

  const demoPhotos = [
    "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=400",
    "https://images.unsplash.com/photo-1679466061812-211a6b737175?w=400",
    "https://images.unsplash.com/photo-1740989475605-355ada18c3fb?w=400",
  ];

  const interests = [
    "Travel", "Music", "Fitness", "Cooking", "Art", "Reading", 
    "Gaming", "Hiking", "Photography", "Movies", "Dancing", "Yoga",
    "Coffee", "Wine", "Pets", "Fashion", "Tech", "Meditation"
  ];

  const dealbreakers = [
    "Smoking", "Heavy Drinking", "No Kids", "Wants Kids", 
    "Long Distance", "Non-Monogamy", "No Religion", "Different Politics"
  ];

  const intentions = [
    "Marriage within 2 years",
    "Long-term relationship",
    "Serious dating",
    "Let's see where it goes"
  ];

  return (
    <div className="min-h-screen bg-[#FDFBF7] p-6" data-testid="onboarding-page">
      <div className="max-w-lg mx-auto">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex justify-between items-center mb-4">
            <button 
              onClick={() => step > 1 && setStep(s => s - 1)}
              className={`btn-ghost ${step === 1 ? 'invisible' : ''}`}
              data-testid="back-btn"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="badge">Step {step} of {totalSteps}</span>
            <div className="w-16" />
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-[#FF2E63] transition-all duration-300"
              style={{ width: `${(step / totalSteps) * 100}%` }}
            />
          </div>
        </div>

        {/* Step Content */}
        <div className="card-brutal p-8">
          {step === 1 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>The Basics</h2>
              
              <div>
                <label className="block text-sm font-bold mb-2">Your Name</label>
                <input
                  type="text"
                  value={profile.name}
                  onChange={(e) => updateProfile("name", e.target.value)}
                  className="input-brutal"
                  placeholder="What's your name?"
                  data-testid="onboard-name"
                />
              </div>

              <div>
                <label className="block text-sm font-bold mb-2">Your Age</label>
                <input
                  type="number"
                  value={profile.age}
                  onChange={(e) => updateProfile("age", e.target.value)}
                  className="input-brutal"
                  placeholder="Age"
                  min={18}
                  max={100}
                  data-testid="onboard-age"
                />
              </div>

              <div>
                <label className="block text-sm font-bold mb-2">I am</label>
                <div className="grid grid-cols-3 gap-3">
                  {["Man", "Woman", "Non-binary"].map(g => (
                    <button
                      key={g}
                      type="button"
                      onClick={() => updateProfile("gender", g.toLowerCase())}
                      className={`p-3 border-2 border-black rounded-lg font-bold transition-all ${
                        profile.gender === g.toLowerCase() 
                          ? 'bg-[#FF2E63] text-white' 
                          : 'bg-white hover:bg-gray-100'
                      }`}
                      data-testid={`gender-${g.toLowerCase()}`}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-bold mb-2">Looking for</label>
                <div className="grid grid-cols-2 gap-3">
                  {["Men", "Women", "Everyone"].map(g => (
                    <button
                      key={g}
                      type="button"
                      onClick={() => updateProfile("looking_for", g.toLowerCase())}
                      className={`p-3 border-2 border-black rounded-lg font-bold transition-all ${
                        profile.looking_for === g.toLowerCase() 
                          ? 'bg-[#CCFF00]' 
                          : 'bg-white hover:bg-gray-100'
                      }`}
                      data-testid={`looking-${g.toLowerCase()}`}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Photos</h2>
              <p className="text-gray-600">Add your best pics (or use demo photos)</p>
              
              <div className="grid grid-cols-3 gap-3">
                {[0, 1, 2].map(i => (
                  <div 
                    key={i}
                    className="aspect-[3/4] border-2 border-dashed border-black rounded-lg overflow-hidden cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => updateProfile("photos", [...profile.photos, demoPhotos[i]])}
                    data-testid={`photo-slot-${i}`}
                  >
                    {profile.photos[i] ? (
                      <img src={profile.photos[i]} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Camera className="w-8 h-8 text-gray-400" />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <button 
                onClick={() => updateProfile("photos", demoPhotos)}
                className="btn-secondary w-full"
                data-testid="use-demo-photos"
              >
                Use Demo Photos
              </button>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>About You</h2>
              
              <div>
                <label className="block text-sm font-bold mb-2">Bio</label>
                <textarea
                  value={profile.bio}
                  onChange={(e) => updateProfile("bio", e.target.value)}
                  className="input-brutal min-h-[120px] resize-none"
                  placeholder="Tell people what makes you, you..."
                  maxLength={500}
                  data-testid="bio-input"
                />
                <p className="text-sm text-gray-400 mt-1">{profile.bio.length}/500</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-bold mb-2">Job Title</label>
                  <input
                    type="text"
                    value={profile.job_title}
                    onChange={(e) => updateProfile("job_title", e.target.value)}
                    className="input-brutal"
                    placeholder="What do you do?"
                    data-testid="job-input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-bold mb-2">Location</label>
                  <input
                    type="text"
                    value={profile.location}
                    onChange={(e) => updateProfile("location", e.target.value)}
                    className="input-brutal"
                    placeholder="City"
                    data-testid="location-input"
                  />
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Interests</h2>
              <p className="text-gray-600">Pick at least 3</p>
              
              <div className="flex flex-wrap gap-2">
                {interests.map(interest => (
                  <button
                    key={interest}
                    type="button"
                    onClick={() => toggleArrayItem("interests", interest)}
                    className={`px-4 py-2 border-2 border-black rounded-full font-medium transition-all ${
                      profile.interests.includes(interest)
                        ? 'bg-[#FF2E63] text-white'
                        : 'bg-white hover:bg-gray-100'
                    }`}
                    data-testid={`interest-${interest.toLowerCase()}`}
                  >
                    {interest}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>What Are You Looking For?</h2>
              
              <div>
                <label className="block text-sm font-bold mb-2">Relationship Goals</label>
                <div className="space-y-2">
                  {intentions.map(intent => (
                    <button
                      key={intent}
                      type="button"
                      onClick={() => updateProfile("intentions", intent)}
                      className={`w-full p-4 border-2 border-black rounded-lg font-medium text-left transition-all ${
                        profile.intentions === intent
                          ? 'bg-[#CCFF00]'
                          : 'bg-white hover:bg-gray-100'
                      }`}
                      data-testid={`intention-btn`}
                    >
                      {intent}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-bold mb-2">Dealbreakers (optional)</label>
                <div className="flex flex-wrap gap-2">
                  {dealbreakers.map(deal => (
                    <button
                      key={deal}
                      type="button"
                      onClick={() => toggleArrayItem("dealbreakers", deal)}
                      className={`px-3 py-1 border-2 border-black rounded-full text-sm font-medium transition-all ${
                        profile.dealbreakers.includes(deal)
                          ? 'bg-[#FF0000] text-white'
                          : 'bg-white hover:bg-gray-100'
                      }`}
                      data-testid={`dealbreaker-btn`}
                    >
                      {deal}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Navigation */}
          <div className="mt-8">
            {step < totalSteps ? (
              <button 
                onClick={() => setStep(s => s + 1)}
                className="btn-primary w-full"
                disabled={
                  (step === 1 && (!profile.name || !profile.age || !profile.gender || !profile.looking_for)) ||
                  (step === 4 && profile.interests.length < 3)
                }
                data-testid="next-btn"
              >
                Continue
              </button>
            ) : (
              <button 
                onClick={handleSubmit}
                className="btn-primary w-full"
                disabled={loading || !profile.intentions}
                data-testid="save-profile-btn"
              >
                {loading ? "Saving..." : "Complete Profile"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ==================== COMPATIBILITY QUIZ ====================
const QuizPage = () => {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [quiz, setQuiz] = useState({
    communication_style: "",
    conflict_resolution: "",
    love_language: "",
    life_goals: [],
    values: [],
    weekend_preference: "",
    social_battery: ""
  });
  const navigate = useNavigate();
  const { token, refreshUser } = useAuth();

  const totalSteps = 4;

  const updateQuiz = (key, value) => setQuiz(q => ({ ...q, [key]: value }));
  const toggleArrayItem = (key, item) => {
    setQuiz(q => ({
      ...q,
      [key]: q[key].includes(item) ? q[key].filter(i => i !== item) : [...q[key], item]
    }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await apiCall("put", "/profile/quiz", quiz, token);
      await refreshUser();
      toast.success("Quiz complete!");
      navigate("/discover");
    } catch (e) {
      toast.error("Failed to save quiz");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] p-6" data-testid="quiz-page">
      <div className="max-w-lg mx-auto">
        {/* Progress */}
        <div className="mb-8">
          <div className="flex justify-between items-center mb-4">
            <button 
              onClick={() => step > 1 && setStep(s => s - 1)}
              className={`btn-ghost ${step === 1 ? 'invisible' : ''}`}
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="badge-accent">Compatibility Quiz</span>
            <div className="w-16" />
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-[#CCFF00] transition-all duration-300"
              style={{ width: `${(step / totalSteps) * 100}%` }}
            />
          </div>
        </div>

        <div className="card-brutal p-8">
          {step === 1 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>How Do You Communicate?</h2>
              
              <div>
                <label className="block text-sm font-bold mb-3">Communication Style</label>
                <div className="space-y-2">
                  {[
                    { value: "direct", label: "Direct & Honest", desc: "Say it like it is" },
                    { value: "gentle", label: "Gentle & Thoughtful", desc: "Choose words carefully" },
                    { value: "playful", label: "Playful & Light", desc: "Humor is my language" }
                  ].map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => updateQuiz("communication_style", opt.value)}
                      className={`w-full p-4 border-2 border-black rounded-lg text-left transition-all ${
                        quiz.communication_style === opt.value ? 'bg-[#CCFF00]' : 'bg-white hover:bg-gray-100'
                      }`}
                      data-testid={`comm-${opt.value}`}
                    >
                      <div className="font-bold">{opt.label}</div>
                      <div className="text-sm text-gray-600">{opt.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-bold mb-3">When There's Conflict...</label>
                <div className="space-y-2">
                  {[
                    { value: "talk it out", label: "Talk It Out", desc: "Resolve it immediately" },
                    { value: "need space first", label: "Need Space First", desc: "Process, then discuss" },
                    { value: "write it down", label: "Write It Down", desc: "Better at texting feelings" }
                  ].map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => updateQuiz("conflict_resolution", opt.value)}
                      className={`w-full p-4 border-2 border-black rounded-lg text-left transition-all ${
                        quiz.conflict_resolution === opt.value ? 'bg-[#CCFF00]' : 'bg-white hover:bg-gray-100'
                      }`}
                      data-testid={`conflict-${opt.value.replace(/\s/g, '-')}`}
                    >
                      <div className="font-bold">{opt.label}</div>
                      <div className="text-sm text-gray-600">{opt.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Love Language</h2>
              
              <div className="space-y-2">
                {[
                  { value: "words", label: "Words of Affirmation", icon: "💬" },
                  { value: "touch", label: "Physical Touch", icon: "🤗" },
                  { value: "gifts", label: "Receiving Gifts", icon: "🎁" },
                  { value: "time", label: "Quality Time", icon: "⏰" },
                  { value: "acts", label: "Acts of Service", icon: "🛠️" }
                ].map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => updateQuiz("love_language", opt.value)}
                    className={`w-full p-4 border-2 border-black rounded-lg text-left transition-all flex items-center gap-4 ${
                      quiz.love_language === opt.value ? 'bg-[#FF2E63] text-white' : 'bg-white hover:bg-gray-100'
                    }`}
                    data-testid={`love-${opt.value}`}
                  >
                    <span className="text-2xl">{opt.icon}</span>
                    <span className="font-bold">{opt.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Life Goals & Values</h2>
              
              <div>
                <label className="block text-sm font-bold mb-3">What matters most? (Pick 3)</label>
                <div className="flex flex-wrap gap-2">
                  {["Career", "Family", "Travel", "Creativity", "Wealth", "Adventure", "Stability", "Growth"].map(goal => (
                    <button
                      key={goal}
                      onClick={() => toggleArrayItem("life_goals", goal)}
                      disabled={quiz.life_goals.length >= 3 && !quiz.life_goals.includes(goal)}
                      className={`px-4 py-2 border-2 border-black rounded-full font-medium transition-all ${
                        quiz.life_goals.includes(goal) ? 'bg-[#CCFF00]' : 'bg-white hover:bg-gray-100'
                      } ${quiz.life_goals.length >= 3 && !quiz.life_goals.includes(goal) ? 'opacity-50' : ''}`}
                      data-testid={`goal-${goal.toLowerCase()}`}
                    >
                      {goal}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-bold mb-3">Core Values (Pick 3)</label>
                <div className="flex flex-wrap gap-2">
                  {["Honesty", "Ambition", "Kindness", "Humor", "Loyalty", "Independence", "Faith", "Adventure"].map(value => (
                    <button
                      key={value}
                      onClick={() => toggleArrayItem("values", value)}
                      disabled={quiz.values.length >= 3 && !quiz.values.includes(value)}
                      className={`px-4 py-2 border-2 border-black rounded-full font-medium transition-all ${
                        quiz.values.includes(value) ? 'bg-[#FF2E63] text-white' : 'bg-white hover:bg-gray-100'
                      } ${quiz.values.length >= 3 && !quiz.values.includes(value) ? 'opacity-50' : ''}`}
                      data-testid={`value-${value.toLowerCase()}`}
                    >
                      {value}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Lifestyle</h2>
              
              <div>
                <label className="block text-sm font-bold mb-3">Ideal Weekend</label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { value: "adventure", label: "Adventure", icon: "🏔️" },
                    { value: "chill", label: "Netflix & Chill", icon: "🛋️" },
                    { value: "social", label: "Out with Friends", icon: "🎉" },
                    { value: "productive", label: "Get Stuff Done", icon: "📝" }
                  ].map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => updateQuiz("weekend_preference", opt.value)}
                      className={`p-4 border-2 border-black rounded-lg text-center transition-all ${
                        quiz.weekend_preference === opt.value ? 'bg-[#CCFF00]' : 'bg-white hover:bg-gray-100'
                      }`}
                      data-testid={`weekend-${opt.value}`}
                    >
                      <div className="text-2xl mb-1">{opt.icon}</div>
                      <div className="font-bold text-sm">{opt.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-bold mb-3">Social Battery</label>
                <div className="space-y-2">
                  {[
                    { value: "introvert", label: "Introvert", desc: "Recharge alone" },
                    { value: "ambivert", label: "Ambivert", desc: "Mix of both" },
                    { value: "extrovert", label: "Extrovert", desc: "Energy from others" }
                  ].map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => updateQuiz("social_battery", opt.value)}
                      className={`w-full p-4 border-2 border-black rounded-lg text-left transition-all ${
                        quiz.social_battery === opt.value ? 'bg-[#FF2E63] text-white' : 'bg-white hover:bg-gray-100'
                      }`}
                      data-testid={`social-${opt.value}`}
                    >
                      <div className="font-bold">{opt.label}</div>
                      <div className={`text-sm ${quiz.social_battery === opt.value ? 'text-white/80' : 'text-gray-600'}`}>{opt.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="mt-8">
            {step < totalSteps ? (
              <button 
                onClick={() => setStep(s => s + 1)}
                className="btn-primary w-full"
                disabled={
                  (step === 1 && (!quiz.communication_style || !quiz.conflict_resolution)) ||
                  (step === 2 && !quiz.love_language) ||
                  (step === 3 && (quiz.life_goals.length < 3 || quiz.values.length < 3))
                }
                data-testid="quiz-next-btn"
              >
                Continue
              </button>
            ) : (
              <button 
                onClick={handleSubmit}
                className="btn-primary w-full"
                disabled={loading || !quiz.weekend_preference || !quiz.social_battery}
                data-testid="quiz-complete-btn"
              >
                {loading ? "Saving..." : "Find My Matches"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ==================== MAIN APP LAYOUT ====================
const AppLayout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const navItems = [
    { path: "/discover", icon: Heart, label: "Discover" },
    { path: "/matches", icon: MessageCircle, label: "Matches" },
    { path: "/likes", icon: Star, label: "Likes" },
    { path: "/profile", icon: User, label: "Profile" },
  ];

  return (
    <div className="min-h-screen bg-[#FDFBF7] pb-20">
      {/* Top Header */}
      <header className="sticky top-0 z-50 bg-[#FDFBF7] border-b-2 border-black px-6 py-4">
        <div className="max-w-lg mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>
            <span className="text-[#FF2E63]">Spark</span>
          </h1>
          <div className="flex items-center gap-3">
            {user?.subscription !== "free" && (
              <span className="badge-primary flex items-center gap-1">
                <Crown className="w-3 h-3" /> {user?.subscription?.toUpperCase()}
              </span>
            )}
            <button 
              onClick={() => navigate("/settings")}
              className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              data-testid="settings-btn"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-lg mx-auto px-4 py-6">
        {children}
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t-2 border-black z-50">
        <div className="max-w-lg mx-auto flex justify-around">
          {navItems.map(item => {
            const isActive = location.pathname === item.path;
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`flex flex-col items-center py-3 px-6 transition-colors ${
                  isActive ? 'text-[#FF2E63]' : 'text-gray-500 hover:text-black'
                }`}
                data-testid={`nav-${item.label.toLowerCase()}`}
              >
                <item.icon className={`w-6 h-6 ${isActive ? 'fill-[#FF2E63]' : ''}`} fill={isActive ? "#FF2E63" : "none"} />
                <span className="text-xs font-bold mt-1">{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
};

// ==================== DISCOVER PAGE ====================
const DiscoverPage = () => {
  const [profiles, setProfiles] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [swiping, setSwiping] = useState(null);
  const [matchPopup, setMatchPopup] = useState(null);
  const [swipesRemaining, setSwipesRemaining] = useState(10);
  const [superLikesRemaining, setSuperLikesRemaining] = useState(1);
  const { token } = useAuth();
  const navigate = useNavigate();

  const fetchProfiles = useCallback(async () => {
    try {
      const res = await apiCall("get", "/discover", null, token);
      setProfiles(res.profiles || []);
      setSwipesRemaining(res.swipes_remaining);
      setSuperLikesRemaining(res.super_likes_remaining);
    } catch (e) {
      toast.error("Failed to load profiles");
    }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  const handleSwipe = async (action) => {
    if (currentIndex >= profiles.length) return;
    
    const targetUser = profiles[currentIndex];
    setSwiping(action);
    
    try {
      const res = await apiCall("post", "/swipe", {
        target_user_id: targetUser.id,
        action
      }, token);

      if (action === "like" || action === "pass") {
        setSwipesRemaining(s => s - 1);
      } else if (action === "super_like") {
        setSuperLikesRemaining(s => s - 1);
      }

      if (res.is_match) {
        setMatchPopup(res.match);
      }

      setTimeout(() => {
        setSwiping(null);
        setCurrentIndex(i => i + 1);
      }, 300);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Swipe failed");
      setSwiping(null);
    }
  };

  const currentProfile = profiles[currentIndex];

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-pulse text-center">
            <Heart className="w-12 h-12 text-[#FF2E63] mx-auto animate-bounce" />
            <p className="mt-4 font-bold">Finding your matches...</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div data-testid="discover-page">
        {/* Stats Bar */}
        <div className="flex justify-between items-center mb-4">
          <div className="flex gap-4">
            <span className="badge-outline flex items-center gap-1">
              <Heart className="w-3 h-3" /> {swipesRemaining} swipes
            </span>
            <span className="badge-accent flex items-center gap-1">
              <Star className="w-3 h-3" /> {superLikesRemaining} super
            </span>
          </div>
          <button 
            onClick={() => navigate("/daily-picks")}
            className="badge-primary flex items-center gap-1"
            data-testid="daily-picks-btn"
          >
            <Sparkles className="w-3 h-3" /> Daily Picks
          </button>
        </div>

        {/* Swipe Card */}
        {currentProfile ? (
          <div className="relative">
            <div 
              className={`swipe-card ${swiping === 'like' || swiping === 'super_like' ? 'swiping-right' : ''} ${swiping === 'pass' ? 'swiping-left' : ''}`}
              data-testid="swipe-card"
            >
              <div className="relative">
                <img 
                  src={currentProfile.photos?.[0] || "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=400"} 
                  alt={currentProfile.name}
                  className="w-full h-[400px] object-cover"
                />
                {/* Gradient Overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                
                {/* Profile Info */}
                <div className="absolute bottom-0 left-0 right-0 p-6 text-white">
                  <div className="flex items-center gap-2 mb-2">
                    <h2 className="text-3xl font-bold" style={{ fontFamily: 'Syne' }}>
                      {currentProfile.name}, {currentProfile.age}
                    </h2>
                    {currentProfile.video_verified && (
                      <div className="bg-[#00CC66] rounded-full p-1">
                        <Check className="w-4 h-4" />
                      </div>
                    )}
                  </div>
                  
                  {currentProfile.job_title && (
                    <p className="text-white/80 mb-2">{currentProfile.job_title} {currentProfile.location && `• ${currentProfile.location}`}</p>
                  )}
                  
                  {currentProfile.intentions && (
                    <span className="badge bg-white/20 text-white">{currentProfile.intentions}</span>
                  )}

                  {currentProfile.compatibility_score && (
                    <div className="mt-3 flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-[#CCFF00]" />
                      <span className="text-[#CCFF00] font-bold">{currentProfile.compatibility_score}% Match</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Bio Section */}
              <div className="p-6">
                {currentProfile.bio && (
                  <p className="text-gray-700 mb-4">{currentProfile.bio}</p>
                )}
                
                {currentProfile.interests?.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {currentProfile.interests.slice(0, 5).map(interest => (
                      <span key={interest} className="badge-outline">{interest}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Swipe Indicators */}
            {swiping === 'like' && (
              <div className="absolute top-20 left-10 rotate-[-20deg] border-4 border-[#00CC66] text-[#00CC66] px-6 py-2 text-3xl font-bold rounded-lg">
                LIKE
              </div>
            )}
            {swiping === 'pass' && (
              <div className="absolute top-20 right-10 rotate-[20deg] border-4 border-[#FF0000] text-[#FF0000] px-6 py-2 text-3xl font-bold rounded-lg">
                NOPE
              </div>
            )}
            {swiping === 'super_like' && (
              <div className="absolute top-20 left-1/2 -translate-x-1/2 border-4 border-[#CCFF00] text-[#CCFF00] px-6 py-2 text-3xl font-bold rounded-lg bg-black">
                SUPER LIKE
              </div>
            )}
          </div>
        ) : (
          <div className="card-brutal p-12 text-center">
            <Heart className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Syne' }}>No More Profiles</h3>
            <p className="text-gray-600 mb-4">Check back later or expand your preferences</p>
            <button onClick={fetchProfiles} className="btn-secondary" data-testid="refresh-btn">
              Refresh
            </button>
          </div>
        )}

        {/* Action Buttons */}
        {currentProfile && (
          <div className="flex justify-center items-center gap-6 mt-6">
            <button 
              onClick={() => handleSwipe("pass")}
              className="action-btn-pass"
              data-testid="pass-btn"
            >
              <X className="w-7 h-7" />
            </button>
            <button 
              onClick={() => handleSwipe("super_like")}
              className="action-btn-superlike"
              disabled={superLikesRemaining <= 0}
              data-testid="superlike-btn"
            >
              <Star className="w-6 h-6" />
            </button>
            <button 
              onClick={() => handleSwipe("like")}
              className="action-btn-like"
              data-testid="like-btn"
            >
              <Heart className="w-8 h-8" />
            </button>
          </div>
        )}

        {/* Match Popup */}
        {matchPopup && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-6" data-testid="match-popup">
            <div className="card-brutal p-8 text-center animate-match max-w-sm">
              <h2 className="text-4xl font-bold text-[#FF2E63] mb-4" style={{ fontFamily: 'Syne' }}>
                It's a Match!
              </h2>
              <div className="flex justify-center gap-[-20px] mb-6">
                <img 
                  src={matchPopup.user?.photos?.[0] || "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=100"} 
                  alt=""
                  className="w-24 h-24 rounded-full border-4 border-white object-cover"
                />
              </div>
              <p className="text-gray-600 mb-6">You and {matchPopup.user?.name} liked each other!</p>
              <div className="flex gap-3">
                <button 
                  onClick={() => navigate(`/chat/${matchPopup.match_id}`)}
                  className="btn-primary flex-1"
                  data-testid="send-message-btn"
                >
                  Send Message
                </button>
                <button 
                  onClick={() => setMatchPopup(null)}
                  className="btn-secondary flex-1"
                  data-testid="keep-swiping-btn"
                >
                  Keep Swiping
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

// ==================== MATCHES PAGE ====================
const MatchesPage = () => {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const { token } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchMatches = async () => {
      try {
        const res = await apiCall("get", "/matches", null, token);
        setMatches(res.matches || []);
      } catch (e) {
        toast.error("Failed to load matches");
      }
      setLoading(false);
    };
    fetchMatches();
  }, [token]);

  const getExpiryText = (expiresAt) => {
    if (!expiresAt) return null;
    const expires = new Date(expiresAt);
    const now = new Date();
    const hours = Math.floor((expires - now) / (1000 * 60 * 60));
    if (hours < 0) return "Expired";
    if (hours < 24) return `${hours}h left`;
    return `${Math.floor(hours / 24)}d left`;
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-pulse">Loading matches...</div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div data-testid="matches-page">
        <h2 className="text-2xl font-bold mb-6" style={{ fontFamily: 'Syne' }}>Your Matches</h2>

        {matches.length === 0 ? (
          <div className="card-brutal p-12 text-center">
            <MessageCircle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold mb-2">No Matches Yet</h3>
            <p className="text-gray-600 mb-4">Keep swiping to find your person!</p>
            <button onClick={() => navigate("/discover")} className="btn-primary" data-testid="start-swiping-btn">
              Start Swiping
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {matches.map(match => (
              <button
                key={match.match_id}
                onClick={() => navigate(`/chat/${match.match_id}`)}
                className="w-full card-feature flex items-center gap-4 text-left"
                data-testid={`match-${match.match_id}`}
              >
                <div className="relative">
                  <img 
                    src={match.user?.photos?.[0] || "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=100"} 
                    alt={match.user?.name}
                    className="w-16 h-16 rounded-full object-cover border-2 border-black"
                  />
                  {match.super_like && (
                    <div className="absolute -top-1 -right-1 bg-[#CCFF00] rounded-full p-1 border-2 border-black">
                      <Star className="w-3 h-3" />
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold">{match.user?.name}</h3>
                    {match.user?.video_verified && (
                      <div className="bg-[#00CC66] rounded-full p-0.5">
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    )}
                  </div>
                  {match.last_message ? (
                    <p className="text-gray-600 text-sm truncate">{match.last_message.content}</p>
                  ) : (
                    <p className="text-[#FF2E63] text-sm font-medium">Say hi! 👋</p>
                  )}
                </div>
                <div className="text-right">
                  {!match.has_messaged && match.expires_at && (
                    <span className="badge-outline text-xs flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {getExpiryText(match.expires_at)}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

// ==================== LIKES PAGE ====================
const LikesPage = () => {
  const [likesData, setLikesData] = useState({ count: 0, likes: [], is_premium_feature: true });
  const [loading, setLoading] = useState(true);
  const { token, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchLikes = async () => {
      try {
        const res = await apiCall("get", "/likes-you", null, token);
        setLikesData(res);
      } catch (e) {
        toast.error("Failed to load likes");
      }
      setLoading(false);
    };
    fetchLikes();
  }, [token]);

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-pulse">Loading...</div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div data-testid="likes-page">
        <h2 className="text-2xl font-bold mb-6" style={{ fontFamily: 'Syne' }}>Who Likes You</h2>

        {likesData.is_premium_feature ? (
          <div className="card-brutal p-8 text-center">
            <div className="relative inline-block mb-4">
              <div className="w-24 h-24 bg-gray-200 rounded-full flex items-center justify-center">
                <Lock className="w-10 h-10 text-gray-400" />
              </div>
              {likesData.count > 0 && (
                <div className="absolute -top-2 -right-2 bg-[#FF2E63] text-white rounded-full w-8 h-8 flex items-center justify-center font-bold border-2 border-black">
                  {likesData.count}
                </div>
              )}
            </div>
            <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Syne' }}>
              {likesData.count} {likesData.count === 1 ? 'person' : 'people'} liked you!
            </h3>
            <p className="text-gray-600 mb-6">Upgrade to see who they are</p>
            <button 
              onClick={() => navigate("/subscription")}
              className="btn-primary"
              data-testid="upgrade-btn"
            >
              <Crown className="w-5 h-5 mr-2 inline" />
              Upgrade to Premium
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {likesData.likes.length === 0 ? (
              <div className="card-brutal p-12 text-center">
                <Heart className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-xl font-bold mb-2">No Likes Yet</h3>
                <p className="text-gray-600">Complete your profile to get more likes!</p>
              </div>
            ) : (
              likesData.likes.map(like => (
                <div
                  key={like.user.id}
                  className="card-feature flex items-center gap-4"
                  data-testid={`like-${like.user.id}`}
                >
                  <img 
                    src={like.user?.photos?.[0] || "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=100"} 
                    alt={like.user?.name}
                    className="w-16 h-16 rounded-full object-cover border-2 border-black"
                  />
                  <div className="flex-1">
                    <h3 className="font-bold">{like.user?.name}, {like.user?.age}</h3>
                    <p className="text-gray-600 text-sm">{like.user?.location}</p>
                  </div>
                  {like.is_super_like && (
                    <span className="badge-accent">
                      <Star className="w-3 h-3 inline mr-1" /> Super Like
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

// ==================== CHAT PAGE ====================
const ChatPage = () => {
  const [match, setMatch] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [icebreakers, setIcebreakers] = useState([]);
  const [showIcebreakers, setShowIcebreakers] = useState(false);
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const { matchId } = useLocation().pathname.split('/').pop() ? { matchId: useLocation().pathname.split('/').pop() } : {};

  const matchIdFromUrl = window.location.pathname.split('/').pop();

  useEffect(() => {
    const fetchChat = async () => {
      try {
        const [matchesRes, messagesRes] = await Promise.all([
          apiCall("get", "/matches", null, token),
          apiCall("get", `/messages/${matchIdFromUrl}`, null, token)
        ]);
        
        const currentMatch = matchesRes.matches?.find(m => m.match_id === matchIdFromUrl);
        setMatch(currentMatch);
        setMessages(messagesRes.messages || []);
      } catch (e) {
        toast.error("Failed to load chat");
      }
      setLoading(false);
    };
    fetchChat();
  }, [token, matchIdFromUrl]);

  const sendMessage = async (content) => {
    if (!content.trim()) return;
    
    try {
      const res = await apiCall("post", "/messages", {
        match_id: matchIdFromUrl,
        content: content.trim(),
        message_type: "text"
      }, token);
      
      setMessages(m => [...m, res.message]);
      setNewMessage("");
    } catch (e) {
      toast.error("Failed to send message");
    }
  };

  const fetchIcebreakers = async () => {
    try {
      const res = await apiCall("get", `/ai/icebreakers/${matchIdFromUrl}`, null, token);
      setIcebreakers(res.icebreakers || []);
      setShowIcebreakers(true);
    } catch (e) {
      toast.error("Failed to get icebreakers");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FDFBF7] flex items-center justify-center">
        <div className="animate-pulse">Loading chat...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FDFBF7] flex flex-col" data-testid="chat-page">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white border-b-2 border-black px-4 py-3">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate("/matches")} className="p-2" data-testid="back-to-matches">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <img 
            src={match?.user?.photos?.[0] || "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=100"} 
            alt={match?.user?.name}
            className="w-10 h-10 rounded-full object-cover border-2 border-black"
          />
          <div className="flex-1">
            <h2 className="font-bold">{match?.user?.name}</h2>
            <p className="text-xs text-gray-500">Active recently</p>
          </div>
          <button 
            onClick={() => navigate("/safety/checkin/" + matchIdFromUrl)}
            className="p-2 hover:bg-gray-100 rounded-full"
            data-testid="safety-btn"
          >
            <Shield className="w-5 h-5 text-[#00CC66]" />
          </button>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <Sparkles className="w-12 h-12 text-[#CCFF00] mx-auto mb-4" />
            <p className="text-gray-600 mb-4">Start the conversation!</p>
            <button 
              onClick={fetchIcebreakers}
              className="btn-secondary text-sm"
              data-testid="get-icebreakers-btn"
            >
              Get AI Icebreakers
            </button>
          </div>
        )}
        
        {messages.map(msg => (
          <div 
            key={msg.id}
            className={`flex ${msg.sender_id === user?.id ? 'justify-end' : 'justify-start'}`}
          >
            <div 
              className={`max-w-[80%] p-3 rounded-2xl ${
                msg.sender_id === user?.id 
                  ? 'bg-[#FF2E63] text-white rounded-br-none' 
                  : 'bg-white border-2 border-black rounded-bl-none'
              }`}
            >
              <p>{msg.content}</p>
              <p className={`text-xs mt-1 ${msg.sender_id === user?.id ? 'text-white/70' : 'text-gray-400'}`}>
                {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Icebreakers */}
      {showIcebreakers && (
        <div className="border-t-2 border-black bg-white p-4">
          <div className="flex justify-between items-center mb-3">
            <span className="font-bold text-sm">AI Icebreakers</span>
            <button onClick={() => setShowIcebreakers(false)} className="text-gray-500">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex gap-2 overflow-x-auto hide-scrollbar pb-2">
            {icebreakers.map((ice, i) => (
              <button
                key={i}
                onClick={() => {
                  setNewMessage(ice);
                  setShowIcebreakers(false);
                }}
                className="flex-shrink-0 px-4 py-2 bg-[#CCFF00] border-2 border-black rounded-full text-sm font-medium hover:bg-[#b8e600] transition-colors"
              >
                {ice.substring(0, 40)}...
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="sticky bottom-0 bg-white border-t-2 border-black p-4">
        <div className="flex gap-2">
          <button className="p-3 hover:bg-gray-100 rounded-full" data-testid="voice-note-btn">
            <Mic className="w-5 h-5" />
          </button>
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage(newMessage)}
            placeholder="Type a message..."
            className="input-brutal flex-1"
            data-testid="message-input"
          />
          <button 
            onClick={() => sendMessage(newMessage)}
            className="btn-primary !px-4 !py-3"
            disabled={!newMessage.trim()}
            data-testid="send-btn"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

// ==================== PROFILE PAGE ====================
const ProfilePage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <AppLayout>
      <div data-testid="profile-page">
        <div className="card-brutal overflow-hidden mb-6">
          <img 
            src={user?.photos?.[0] || "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=400"} 
            alt={user?.name}
            className="w-full h-64 object-cover"
          />
          <div className="p-6">
            <div className="flex items-center gap-2 mb-2">
              <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>{user?.name}, {user?.age}</h2>
              {user?.video_verified && (
                <div className="bg-[#00CC66] rounded-full p-1">
                  <Check className="w-4 h-4 text-white" />
                </div>
              )}
            </div>
            {user?.job_title && <p className="text-gray-600">{user?.job_title}</p>}
            {user?.location && <p className="text-gray-500 text-sm">{user?.location}</p>}
          </div>
        </div>

        <div className="space-y-3">
          <button 
            onClick={() => navigate("/onboarding")}
            className="w-full card-feature flex items-center justify-between"
            data-testid="edit-profile-btn"
          >
            <div className="flex items-center gap-3">
              <User className="w-5 h-5" />
              <span className="font-bold">Edit Profile</span>
            </div>
            <ChevronRight className="w-5 h-5" />
          </button>

          {!user?.video_verified && (
            <button 
              onClick={() => navigate("/verify")}
              className="w-full card-feature flex items-center justify-between bg-[#00CC66]/10"
              data-testid="verify-btn"
            >
              <div className="flex items-center gap-3">
                <Camera className="w-5 h-5 text-[#00CC66]" />
                <span className="font-bold">Verify Your Profile</span>
              </div>
              <span className="badge-primary">Recommended</span>
            </button>
          )}

          <button 
            onClick={() => navigate("/subscription")}
            className="w-full card-feature flex items-center justify-between"
            data-testid="subscription-btn"
          >
            <div className="flex items-center gap-3">
              <Crown className="w-5 h-5 text-[#FF2E63]" />
              <span className="font-bold">
                {user?.subscription === "free" ? "Upgrade to Premium" : `${user?.subscription?.toUpperCase()} Plan`}
              </span>
            </div>
            <ChevronRight className="w-5 h-5" />
          </button>

          <button 
            onClick={() => navigate("/settings")}
            className="w-full card-feature flex items-center justify-between"
            data-testid="settings-link"
          >
            <div className="flex items-center gap-3">
              <Settings className="w-5 h-5" />
              <span className="font-bold">Settings</span>
            </div>
            <ChevronRight className="w-5 h-5" />
          </button>

          <button 
            onClick={logout}
            className="w-full p-4 text-[#FF0000] font-bold text-center hover:bg-red-50 rounded-lg transition-colors"
            data-testid="logout-btn"
          >
            Log Out
          </button>
        </div>
      </div>
    </AppLayout>
  );
};

// ==================== SUBSCRIPTION PAGE ====================
const SubscriptionPage = () => {
  const [plans, setPlans] = useState({});
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState(false);
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const res = await apiCall("get", "/subscription/plans", null, token);
        setPlans(res.plans || {});
      } catch (e) {
        toast.error("Failed to load plans");
      }
      setLoading(false);
    };
    fetchPlans();

    // Check for returning from Stripe
    const sessionId = searchParams.get('session_id');
    if (sessionId) {
      pollPaymentStatus(sessionId);
    }
  }, [token, searchParams]);

  const pollPaymentStatus = async (sessionId, attempts = 0) => {
    if (attempts >= 5) {
      toast.error("Payment verification timed out");
      return;
    }

    try {
      const res = await apiCall("get", `/subscription/status/${sessionId}`, null, token);
      if (res.payment_status === "paid") {
        toast.success("Payment successful! Welcome to Premium!");
        navigate("/discover");
      } else {
        setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2000);
      }
    } catch (e) {
      toast.error("Failed to verify payment");
    }
  };

  const handleCheckout = async (planId) => {
    setCheckingOut(true);
    try {
      const res = await apiCall("post", "/subscription/checkout", {
        plan_id: planId,
        origin_url: window.location.origin
      }, token);
      
      window.location.href = res.checkout_url;
    } catch (e) {
      toast.error("Failed to start checkout");
    }
    setCheckingOut(false);
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-pulse">Loading plans...</div>
        </div>
      </AppLayout>
    );
  }

  const premiumFeatures = [
    "Unlimited swipes",
    "See who likes you",
    "5 Super Likes daily",
    "1 Boost per week",
    "No ads"
  ];

  const vipFeatures = [
    ...premiumFeatures,
    "Unlimited Super Likes",
    "3 Boosts per week",
    "Read receipts",
    "Priority support"
  ];

  return (
    <AppLayout>
      <div data-testid="subscription-page">
        <div className="text-center mb-8">
          <Crown className="w-12 h-12 text-[#FF2E63] mx-auto mb-4" />
          <h2 className="text-3xl font-bold mb-2" style={{ fontFamily: 'Syne' }}>Go Premium</h2>
          <p className="text-gray-600">Unlock all features and find your match faster</p>
        </div>

        <div className="space-y-4">
          {/* Premium */}
          <div className="card-brutal p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-xl font-bold" style={{ fontFamily: 'Syne' }}>Premium</h3>
                <p className="text-gray-600">For serious daters</p>
              </div>
              <span className="badge-primary">Popular</span>
            </div>
            
            <ul className="space-y-2 mb-6">
              {premiumFeatures.map(f => (
                <li key={f} className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-[#00CC66]" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>

            <div className="grid grid-cols-2 gap-3">
              <button 
                onClick={() => handleCheckout("premium_monthly")}
                className="btn-secondary !p-4"
                disabled={checkingOut}
                data-testid="premium-monthly-btn"
              >
                <div className="text-lg font-bold">$19.99</div>
                <div className="text-sm text-gray-600">/month</div>
              </button>
              <button 
                onClick={() => handleCheckout("premium_yearly")}
                className="btn-primary !p-4"
                disabled={checkingOut}
                data-testid="premium-yearly-btn"
              >
                <div className="text-lg font-bold">$119.99</div>
                <div className="text-sm">Save 50%</div>
              </button>
            </div>
          </div>

          {/* VIP */}
          <div className="card-brutal p-6 border-[#CCFF00] border-4">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-xl font-bold" style={{ fontFamily: 'Syne' }}>VIP</h3>
                <p className="text-gray-600">The ultimate experience</p>
              </div>
              <span className="badge-accent">Best Value</span>
            </div>
            
            <ul className="space-y-2 mb-6">
              {vipFeatures.map(f => (
                <li key={f} className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-[#00CC66]" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>

            <div className="grid grid-cols-2 gap-3">
              <button 
                onClick={() => handleCheckout("vip_monthly")}
                className="btn-secondary !p-4"
                disabled={checkingOut}
                data-testid="vip-monthly-btn"
              >
                <div className="text-lg font-bold">$39.99</div>
                <div className="text-sm text-gray-600">/month</div>
              </button>
              <button 
                onClick={() => handleCheckout("vip_yearly")}
                className="btn-primary !p-4 bg-[#CCFF00] text-black"
                disabled={checkingOut}
                data-testid="vip-yearly-btn"
              >
                <div className="text-lg font-bold">$239.99</div>
                <div className="text-sm">Save 50%</div>
              </button>
            </div>
          </div>
        </div>

        <p className="text-center text-gray-500 text-sm mt-6">
          Cancel anytime. Secure payment via Stripe.
        </p>
      </div>
    </AppLayout>
  );
};

// ==================== SETTINGS PAGE ====================
const SettingsPage = () => {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const { token, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await apiCall("get", "/settings", null, token);
        setSettings(res);
      } catch (e) {
        toast.error("Failed to load settings");
      }
      setLoading(false);
    };
    fetchSettings();
  }, [token]);

  const toggleSlowDating = async () => {
    try {
      const res = await apiCall("put", `/settings/slow-dating?enabled=${!settings.slow_dating_mode}`, null, token);
      setSettings(s => ({ ...s, slow_dating_mode: res.slow_dating_mode }));
      toast.success(`Slow dating mode ${res.slow_dating_mode ? 'enabled' : 'disabled'}`);
    } catch (e) {
      toast.error("Failed to update settings");
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-pulse">Loading settings...</div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div data-testid="settings-page">
        <h2 className="text-2xl font-bold mb-6" style={{ fontFamily: 'Syne' }}>Settings</h2>

        <div className="space-y-3">
          <div className="card-feature flex items-center justify-between">
            <div>
              <h3 className="font-bold">Slow Dating Mode</h3>
              <p className="text-sm text-gray-600">Limit swipes to encourage quality connections</p>
            </div>
            <button
              onClick={toggleSlowDating}
              className={`w-14 h-8 rounded-full border-2 border-black transition-colors ${
                settings.slow_dating_mode ? 'bg-[#CCFF00]' : 'bg-gray-200'
              }`}
              data-testid="slow-dating-toggle"
            >
              <div className={`w-6 h-6 rounded-full bg-white border-2 border-black transition-transform ${
                settings.slow_dating_mode ? 'translate-x-6' : 'translate-x-0'
              }`} />
            </button>
          </div>

          <button 
            onClick={() => navigate("/subscription")}
            className="w-full card-feature flex items-center justify-between"
          >
            <div>
              <h3 className="font-bold">Subscription</h3>
              <p className="text-sm text-gray-600">
                {settings.subscription === "free" ? "Free Plan" : `${settings.subscription?.toUpperCase()} until ${new Date(settings.subscription_expires).toLocaleDateString()}`}
              </p>
            </div>
            <ChevronRight className="w-5 h-5" />
          </button>

          <button 
            onClick={() => navigate("/safety")}
            className="w-full card-feature flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <Shield className="w-5 h-5 text-[#00CC66]" />
              <div>
                <h3 className="font-bold">Safety Features</h3>
                <p className="text-sm text-gray-600">Date check-ins, emergency contacts</p>
              </div>
            </div>
            <ChevronRight className="w-5 h-5" />
          </button>

          <div className="border-t-2 border-gray-200 pt-4 mt-4">
            <button 
              onClick={logout}
              className="w-full p-4 text-[#FF0000] font-bold text-center hover:bg-red-50 rounded-lg transition-colors"
              data-testid="logout-settings-btn"
            >
              Log Out
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

// ==================== PROTECTED ROUTE ====================
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && !user) {
      navigate("/login");
    }
  }, [user, loading, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FDFBF7] flex items-center justify-center">
        <div className="animate-pulse">
          <Heart className="w-12 h-12 text-[#FF2E63] animate-bounce" />
        </div>
      </div>
    );
  }

  return user ? children : null;
};

// ==================== APP ====================
function App() {
  return (
    <AuthProvider>
      <div className="App">
        <Toaster position="top-center" richColors />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<AuthPage isLogin={true} />} />
            <Route path="/signup" element={<AuthPage isLogin={false} />} />
            <Route path="/onboarding" element={<ProtectedRoute><OnboardingPage /></ProtectedRoute>} />
            <Route path="/quiz" element={<ProtectedRoute><QuizPage /></ProtectedRoute>} />
            <Route path="/discover" element={<ProtectedRoute><DiscoverPage /></ProtectedRoute>} />
            <Route path="/matches" element={<ProtectedRoute><MatchesPage /></ProtectedRoute>} />
            <Route path="/likes" element={<ProtectedRoute><LikesPage /></ProtectedRoute>} />
            <Route path="/chat/:matchId" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
            <Route path="/subscription" element={<ProtectedRoute><SubscriptionPage /></ProtectedRoute>} />
            <Route path="/subscription/success" element={<ProtectedRoute><SubscriptionPage /></ProtectedRoute>} />
            <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </div>
    </AuthProvider>
  );
}

export default App;
