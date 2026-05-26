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

// Copyright footer rendered across the app
const CopyrightFooter = ({ className = "" }) => (
  <p
    className={`text-center text-xs text-gray-500 py-3 ${className}`}
    data-testid="copyright-footer"
  >
    © 2026 sparkmatch.dating | All rights reserved.
  </p>
);

// Spark brand logo (lightning bolt + wordmark)
const SparkLogo = ({ size = "md", className = "" }) => {
  const sizes = {
    sm: { gap: "gap-0.5", text: "text-2xl", iconW: 18, iconH: 22 },
    md: { gap: "gap-1", text: "text-3xl", iconW: 22, iconH: 26 },
    lg: { gap: "gap-1", text: "text-4xl", iconW: 28, iconH: 34 },
  };
  const s = sizes[size] || sizes.md;
  return (
    <span className={`inline-flex items-center ${s.gap} ${className}`} data-testid="spark-logo">
      <svg
        width={s.iconW}
        height={s.iconH}
        viewBox="0 0 24 28"
        fill="#FF2E63"
        aria-hidden="true"
      >
        <path d="M14 0 L2 16 L10 16 L8 28 L22 10 L14 10 Z" />
      </svg>
      <span
        className={`font-bold text-[#FF2E63] ${s.text}`}
        style={{ fontFamily: 'Syne' }}
      >
        Spark
      </span>
    </span>
  );
};

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
  try {
    const res = await axios(config);
    return res.data;
  } catch (err) {
    // Surface premium-required errors via global modal
    const d = err?.response?.data?.detail;
    if (err?.response?.status === 402 && d && typeof d === "object" && d.premium_required) {
      window.dispatchEvent(new CustomEvent("spark:upgrade", { detail: d }));
    }
    throw err;
  }
};

// ==================== UPGRADE MODAL ====================
const UpgradeModal = () => {
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState({});
  const navigate = useNavigate();
  useEffect(() => {
    const handler = (e) => { setInfo(e.detail || {}); setOpen(true); };
    window.addEventListener("spark:upgrade", handler);
    return () => window.removeEventListener("spark:upgrade", handler);
  }, []);
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[70] p-4" data-testid="upgrade-modal">
      <div className="card-brutal max-w-sm w-full p-6 text-center">
        <Crown className="w-12 h-12 text-[#FF2E63] mx-auto mb-3" />
        <h2 className="text-2xl font-bold mb-1" style={{ fontFamily: 'Syne' }}>Premium Feature</h2>
        <p className="text-gray-600 mb-4">
          <span className="font-bold text-[#FF2E63]">{info.feature || "This"}</span> is only for Premium members.
        </p>
        <p className="text-sm text-gray-700 mb-6">{info.message}</p>
        <div className="flex flex-col gap-2">
          <button
            onClick={() => { setOpen(false); navigate("/subscription"); }}
            className="btn-primary w-full"
            data-testid="upgrade-now-btn"
          >
            Upgrade to Premium
          </button>
          <button onClick={() => setOpen(false)} className="text-sm text-gray-500 hover:underline">
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
};

// ==================== HELP BUBBLE (Floating) ====================
const HelpBubble = () => {
  const navigate = useNavigate();
  const location = useLocation();
  // Hide on public pages (landing, login, signup, legal)
  const publicPaths = ["/", "/login", "/signup", "/privacy", "/terms"];
  if (publicPaths.includes(location.pathname)) return null;
  return (
    <button
      onClick={() => navigate("/help")}
      className="fixed bottom-24 right-4 z-40 bg-[#FF2E63] text-white border-2 border-black rounded-full shadow-[4px_4px_0_#000] px-4 py-3 flex items-center gap-2 hover:translate-y-0.5 hover:shadow-[2px_2px_0_#000] transition-all"
      data-testid="help-bubble"
      aria-label="Need help?"
    >
      <MessageCircle className="w-5 h-5" />
      <span className="font-bold text-sm hidden sm:inline">Need help?</span>
    </button>
  );
};

// ==================== LEGAL PAGES ====================
const LegalLayout = ({ title, effectiveDate, children, testid }) => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-[#FDFBF7]" data-testid={testid}>
      <header className="sticky top-0 z-50 bg-[#FDFBF7] border-b-2 border-black px-6 py-4">
        <div className="max-w-3xl mx-auto flex justify-between items-center">
          <button onClick={() => navigate("/")} className="inline-flex" aria-label="Home">
            <SparkLogo size="sm" />
          </button>
          <button
            onClick={() => navigate(-1)}
            className="btn-ghost inline-flex items-center gap-1"
            data-testid="legal-back-btn"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-6 py-10">
        <h1 className="text-4xl md:text-5xl font-bold mb-2" style={{ fontFamily: 'Syne' }}>
          {title}
        </h1>
        <p className="text-sm text-gray-500 mb-2">sparkmatch.dating</p>
        <p className="text-sm text-gray-500 mb-8">Effective Date: {effectiveDate}</p>
        <article className="card-brutal p-8 space-y-6 leading-relaxed text-gray-800">
          {children}
        </article>
        <CopyrightFooter className="mt-8" />
      </main>
    </div>
  );
};

const LegalSection = ({ heading, children }) => (
  <section>
    <h2 className="text-xl font-bold mb-2" style={{ fontFamily: 'Syne' }}>{heading}</h2>
    <div className="space-y-2">{children}</div>
  </section>
);

const PrivacyPage = () => (
  <LegalLayout title="Privacy Policy" effectiveDate="May 25, 2026" testid="privacy-page">
    <LegalSection heading="1. Introduction">
      <p>Welcome to Spark Match ("Spark," "we," "us," or "our"). We are committed to protecting your personal information. This Privacy Policy explains how we collect, use, and protect your data when you use sparkmatch.dating.</p>
    </LegalSection>
    <LegalSection heading="2. Information We Collect">
      <p>We may collect the following information when you use Spark Match:</p>
      <ul className="list-disc pl-6 space-y-1">
        <li>Name, email address, date of birth, and gender</li>
        <li>Profile photos and bio information</li>
        <li>Location data (city/region level only)</li>
        <li>Messages and communications between users</li>
        <li>Device information and usage data</li>
      </ul>
    </LegalSection>
    <LegalSection heading="3. How We Use Your Information">
      <p>We use your information to:</p>
      <ul className="list-disc pl-6 space-y-1">
        <li>Create and manage your account</li>
        <li>Match you with compatible users</li>
        <li>Send notifications and updates</li>
        <li>Improve our services</li>
        <li>Ensure safety and prevent fraud</li>
      </ul>
    </LegalSection>
    <LegalSection heading="4. California Privacy Rights (CCPA)">
      <p>As a California resident, you have the right to know what personal data we collect, request deletion of your data, and opt out of the sale of your personal information. We do not sell your personal data to third parties. To exercise your rights, contact us at <a href="mailto:privacy@sparkmatch.dating" className="text-[#FF2E63] font-bold hover:underline">privacy@sparkmatch.dating</a>.</p>
    </LegalSection>
    <LegalSection heading="5. Data Security">
      <p>We take reasonable measures to protect your personal information from unauthorized access, disclosure, or misuse. However, no method of transmission over the internet is 100% secure.</p>
    </LegalSection>
    <LegalSection heading="6. Data Retention">
      <p>We retain your data for as long as your account is active or as needed to provide services. You may request deletion of your account and associated data at any time.</p>
    </LegalSection>
    <LegalSection heading="7. Third-Party Services">
      <p>We may use third-party services to operate our platform. These services have their own privacy policies and we are not responsible for their practices.</p>
    </LegalSection>
    <LegalSection heading="8. Children's Privacy">
      <p>Spark Match is strictly for users aged 18 and older. We do not knowingly collect information from anyone under 18. If we discover a user is under 18, their account will be immediately terminated.</p>
    </LegalSection>
    <LegalSection heading="9. Changes to This Policy">
      <p>We may update this Privacy Policy from time to time. We will notify you of significant changes via email or in-app notification.</p>
    </LegalSection>
    <LegalSection heading="10. Contact Us">
      <p>For privacy-related questions, contact us at:<br />
        <a href="mailto:privacy@sparkmatch.dating" className="text-[#FF2E63] font-bold hover:underline">privacy@sparkmatch.dating</a>
      </p>
    </LegalSection>
  </LegalLayout>
);

const TermsPage = () => (
  <LegalLayout title="Terms of Use" effectiveDate="May 25, 2026" testid="terms-page">
    <LegalSection heading="1. Acceptance of Terms">
      <p>By accessing or using Spark Match at sparkmatch.dating, you agree to be bound by these Terms of Use. If you do not agree, please do not use our service.</p>
    </LegalSection>
    <LegalSection heading="2. Eligibility">
      <p>You must be at least 18 years of age to use Spark Match. By creating an account, you confirm that you are 18 or older. We reserve the right to terminate accounts of users found to be under 18.</p>
    </LegalSection>
    <LegalSection heading="3. User Conduct">
      <p>You agree not to:</p>
      <ul className="list-disc pl-6 space-y-1">
        <li>Harass, threaten, or harm other users</li>
        <li>Post false, misleading, or fraudulent information</li>
        <li>Use the platform for commercial solicitation or spam</li>
        <li>Impersonate another person or entity</li>
        <li>Upload illegal, offensive, or inappropriate content</li>
        <li>Attempt to hack, scrape, or damage our platform</li>
      </ul>
    </LegalSection>
    <LegalSection heading="4. Intellectual Property">
      <p>All content, design, code, and branding on Spark Match is owned by Deepthi Marthi and protected under US copyright law (Case #1-15170846081). You may not copy, reproduce, or distribute any part of this platform without written permission.</p>
    </LegalSection>
    <LegalSection heading="5. User Content">
      <p>You retain ownership of content you post. By posting, you grant Spark Match a non-exclusive license to display your content within the platform. You are solely responsible for your content.</p>
    </LegalSection>
    <LegalSection heading="6. Safety">
      <p>Spark Match is not responsible for the conduct of users on or off the platform. Always meet in public places and take personal safety precautions. Report suspicious behavior immediately using our Safety feature.</p>
    </LegalSection>
    <LegalSection heading="7. Disclaimer of Warranties">
      <p>Spark Match is provided "as is" without warranties of any kind. We do not guarantee that you will find a match or that the service will be uninterrupted or error-free.</p>
    </LegalSection>
    <LegalSection heading="8. Limitation of Liability">
      <p>To the maximum extent permitted by law, Deepthi Marthi and Spark Match shall not be liable for any indirect, incidental, or consequential damages arising from your use of the platform.</p>
    </LegalSection>
    <LegalSection heading="9. Termination">
      <p>We reserve the right to suspend or terminate your account at any time for violation of these terms or for any other reason at our sole discretion.</p>
    </LegalSection>
    <LegalSection heading="10. Governing Law">
      <p>These Terms are governed by the laws of the State of California, United States.</p>
    </LegalSection>
    <LegalSection heading="11. Contact Us">
      <p>For questions about these Terms, contact us at:<br />
        <a href="mailto:legal@sparkmatch.dating" className="text-[#FF2E63] font-bold hover:underline">legal@sparkmatch.dating</a>
      </p>
    </LegalSection>
  </LegalLayout>
);

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
            <SparkLogo size="md" data-testid="brand-landing-nav" />
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
              <h2 className="text-5xl md:text-7xl font-extrabold leading-tight pr-2" style={{ fontFamily: 'Syne' }}>
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
          <SparkLogo size="sm" />
          <div className="flex gap-6 text-gray-600 items-center">
            <button onClick={() => navigate("/privacy")} className="hover:text-[#FF2E63] cursor-pointer" data-testid="footer-privacy-link">Privacy</button>
            <button onClick={() => navigate("/terms")} className="hover:text-[#FF2E63] cursor-pointer" data-testid="footer-terms-link">Terms</button>
            <span className="hover:text-[#FF2E63] cursor-pointer">Safety</span>
            <span className="flex items-center gap-1 text-xs text-[#00CC66]" data-testid="ssl-badge"><Lock className="w-3 h-3"/>256-bit SSL</span>
          </div>
          <p className="text-sm text-gray-500" data-testid="copyright-footer">© 2026 sparkmatch.dating | All rights reserved.</p>
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
  const [dob, setDob] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [twoFA, setTwoFA] = useState({ needed: false, userId: null });
  const [twoFACode, setTwoFACode] = useState("");
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isLogin && !ageConfirmed) {
      toast.error("You must confirm you are 18 or older to sign up");
      return;
    }
    setLoading(true);
    try {
      const endpoint = isLogin ? "/auth/login" : "/auth/register";
      const data = isLogin ? { email, password } : { email, password, name, date_of_birth: dob || undefined };
      const res = await apiCall("post", endpoint, data);

      if (res.two_factor_required) {
        setTwoFA({ needed: true, userId: res.user_id });
        toast.success(res.message || "Code sent to your email");
        setLoading(false);
        return;
      }
      
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

  const submit2FA = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await apiCall("post", "/auth/2fa/verify", { user_id: twoFA.userId, code: twoFACode });
      login(res.token, { id: res.user_id, profile_complete: res.profile_complete, quiz_complete: res.quiz_complete });
      toast.success("Verified!");
      if (!res.profile_complete) navigate("/onboarding");
      else if (!res.quiz_complete) navigate("/quiz");
      else navigate("/discover");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Invalid code");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] flex items-center justify-center p-6" data-testid={isLogin ? "login-page" : "signup-page"}>
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <button
            onClick={() => navigate("/")}
            className="mb-2 inline-flex"
            aria-label="Go home"
          >
            <SparkLogo size="lg" />
          </button>
          <p className="text-gray-600">
            {isLogin ? "Welcome back, hottie" : "Let's get you set up"}
          </p>
        </div>

        <div className="card-brutal p-8">
          {twoFA.needed ? (
            <form onSubmit={submit2FA} className="space-y-4" data-testid="twofa-form">
              <div className="text-center">
                <Shield className="w-10 h-10 text-[#FF2E63] mx-auto mb-2" />
                <h3 className="text-xl font-bold" style={{ fontFamily: 'Syne' }}>Two-Factor Verification</h3>
                <p className="text-sm text-gray-600">We sent a 6-digit code to your email. Valid for 10 minutes.</p>
              </div>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={twoFACode}
                onChange={(e) => setTwoFACode(e.target.value.replace(/\D/g, ""))}
                className="input-brutal text-center text-2xl tracking-[0.5em] font-bold"
                placeholder="------"
                required
                data-testid="twofa-code-input"
              />
              <button type="submit" disabled={loading || twoFACode.length !== 6} className="btn-primary w-full" data-testid="twofa-verify-btn">
                {loading ? "Verifying..." : "Verify"}
              </button>
              <button type="button" onClick={() => setTwoFA({needed:false, userId:null})} className="text-sm text-gray-500 w-full hover:underline">
                Back to login
              </button>
            </form>
          ) : (
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
                minLength={isLogin ? 6 : 8}
                data-testid="password-input"
              />
              {!isLogin && (
                <p className="text-xs text-gray-500 mt-1">At least 8 characters, 1 number, 1 special character</p>
              )}
            </div>

            {!isLogin && (
              <div>
                <label className="block text-sm font-bold mb-2">Date of Birth</label>
                <input
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  max={new Date(Date.now() - 18*365*24*60*60*1000).toISOString().slice(0,10)}
                  className="input-brutal"
                  required
                  data-testid="dob-input"
                />
                <p className="text-xs text-gray-500 mt-1">You must be 18 or older</p>
              </div>
            )}

            {!isLogin && (
              <label
                className="flex items-start gap-3 cursor-pointer select-none p-3 bg-[#FDFBF7] border-2 border-black rounded-lg hover:bg-white transition-colors"
                data-testid="age-confirm-label"
              >
                <input
                  type="checkbox"
                  checked={ageConfirmed}
                  onChange={(e) => setAgeConfirmed(e.target.checked)}
                  className="mt-1 w-5 h-5 accent-[#FF2E63] cursor-pointer flex-shrink-0"
                  required
                  data-testid="age-confirm-checkbox"
                />
                <span className="text-sm leading-tight">
                  I confirm that I am <span className="font-bold">18 or older</span> and agree to the{" "}
                  <button
                    type="button"
                    onClick={() => navigate("/terms")}
                    className="text-[#FF2E63] font-bold hover:underline"
                  >
                    Terms
                  </button>{" "}
                  &amp;{" "}
                  <button
                    type="button"
                    onClick={() => navigate("/privacy")}
                    className="text-[#FF2E63] font-bold hover:underline"
                  >
                    Privacy Policy
                  </button>
                  .
                </span>
              </label>
            )}

            <button 
              type="submit" 
              className="btn-primary w-full"
              disabled={loading || (!isLogin && !ageConfirmed)}
              data-testid="submit-btn"
            >
              {loading ? "Loading..." : (isLogin ? "Log In" : "Create Account")}
            </button>
          </form>
          )}

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
          <div className="mt-4 flex items-center justify-center gap-2 text-xs text-[#00CC66] border-t-2 border-gray-100 pt-4" data-testid="security-badge">
            <Lock className="w-3 h-3" />
            Your data is protected with 256-bit SSL encryption
          </div>
        </div>
        <CopyrightFooter className="mt-6" />
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
        <CopyrightFooter className="mt-6" />
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
        <CopyrightFooter className="mt-6" />
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
          <SparkLogo size="sm" />
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
        <CopyrightFooter className="mt-8" />
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
  const [lastSwipe, setLastSwipe] = useState(null);
  const [boost, setBoost] = useState({ is_active: false, active_until: null, boosts_remaining_this_week: 0 });
  const [boostSecondsLeft, setBoostSecondsLeft] = useState(0);
  const { token, user } = useAuth();
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

  const fetchBoostStatus = useCallback(async () => {
    try {
      const res = await apiCall("get", "/me/boost/status", null, token);
      setBoost(res);
    } catch (e) {}
  }, [token]);

  useEffect(() => {
    fetchProfiles();
    fetchBoostStatus();
  }, [fetchProfiles, fetchBoostStatus]);

  // Auto-record profile view when a card is displayed
  useEffect(() => {
    const p = profiles[currentIndex];
    if (p?.id && token) {
      apiCall("post", `/profile/view/${p.id}`, null, token).catch(() => {});
    }
  }, [profiles, currentIndex, token]);

  // Boost countdown timer
  useEffect(() => {
    if (!boost.is_active || !boost.active_until) { setBoostSecondsLeft(0); return; }
    const tick = () => {
      const left = Math.max(0, Math.floor((new Date(boost.active_until).getTime() - Date.now()) / 1000));
      setBoostSecondsLeft(left);
      if (left <= 0) fetchBoostStatus();
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [boost.is_active, boost.active_until, fetchBoostStatus]);

  const activateBoost = async () => {
    try {
      const res = await apiCall("post", "/me/boost", null, token);
      setBoost({ is_active: true, active_until: res.boost_active_until, boosts_remaining_this_week: res.boosts_remaining_this_week });
      toast.success("Boost active! You're top of stack for 30 minutes 🚀");
    } catch (e) {
      if (e.response?.status === 429) toast.error(e.response.data.detail);
      else if (e.response?.status !== 402) toast.error("Boost failed");
    }
  };

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

      setLastSwipe({ index: currentIndex, action, target: targetUser });

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

  const handleUndo = async () => {
    if (!lastSwipe) { toast.error("Nothing to undo"); return; }
    try {
      await apiCall("post", "/swipe/undo", null, token);
      setCurrentIndex(i => Math.max(0, i - 1));
      if (lastSwipe.action === "super_like") setSuperLikesRemaining(s => s + 1);
      else setSwipesRemaining(s => s + 1);
      setLastSwipe(null);
      toast.success("Undone!");
    } catch (e) {
      if (e.response?.status !== 402) toast.error("Couldn't undo");
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
          <div className="flex gap-2 flex-wrap">
            <span className="badge-outline flex items-center gap-1">
              <Heart className="w-3 h-3" /> {swipesRemaining} swipes
            </span>
            <span className="badge-accent flex items-center gap-1">
              <Star className="w-3 h-3" /> {superLikesRemaining} super
            </span>
            {boost.is_active && (
              <span className="px-2 py-1 bg-[#FF2E63] text-white text-xs font-bold rounded-full border-2 border-black flex items-center gap-1" data-testid="boost-countdown">
                <Zap className="w-3 h-3" /> Boost {Math.floor(boostSecondsLeft/60)}:{(boostSecondsLeft%60).toString().padStart(2,'0')}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={activateBoost}
              disabled={boost.is_active}
              className={`px-3 py-1.5 text-xs font-bold border-2 border-black rounded-full shadow-[2px_2px_0_#000] ${boost.is_active ? 'bg-gray-200 text-gray-400' : 'bg-[#CCFF00] hover:translate-y-0.5 hover:shadow-none'}`}
              data-testid="boost-btn"
              title={boost.is_active ? "Boost active" : `Boost (${boost.boosts_remaining_this_week} left this week)`}
            >
              <Zap className="w-3 h-3 inline mr-1" />
              {boost.is_active ? "Boosted!" : "Boost"}
            </button>
          </div>
        </div>

        {/* Swipe Card */}
        {currentProfile ? (
          <div className="relative">
            <div 
              className={`swipe-card ${swiping === 'like' || swiping === 'super_like' ? 'swiping-right' : ''} ${swiping === 'pass' ? 'swiping-left' : ''}`}
              data-testid="swipe-card"
            >
              <div className="relative protected-photo">
                <img 
                  src={currentProfile.photos?.[0] || "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=400"} 
                  alt={currentProfile.name}
                  className="w-full h-[400px] object-cover"
                />
                {/* Gradient Overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                
                {/* Profile Info */}
                <div className="absolute bottom-0 left-0 right-0 p-6 text-white">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <h2 className="text-3xl font-bold" style={{ fontFamily: 'Syne' }}>
                      {currentProfile.name}, {currentProfile.age}
                    </h2>
                    {currentProfile.video_verified && (
                      <div className="bg-[#00CC66] rounded-full p-1">
                        <Check className="w-4 h-4" />
                      </div>
                    )}
                    {(currentProfile.subscription === "premium" || currentProfile.subscription === "vip") && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#FF2E63] text-white text-xs font-bold rounded-full border-2 border-white" data-testid="premium-badge">
                        <Crown className="w-3 h-3" />
                        {currentProfile.subscription === "vip" ? "VIP" : "PREMIUM"}
                      </span>
                    )}
                  </div>
                  
                  {currentProfile.job_title && (
                    <p className="text-white/80 mb-2">
                      {currentProfile.job_title}
                      {currentProfile.location && ` • ${currentProfile.location}`}
                      {currentProfile.distance != null && ` • ${currentProfile.distance} ${currentProfile.distance_unit || 'mi'}`}
                    </p>
                  )}
                  
                  {currentProfile.intentions && (
                    <span className="badge bg-white/20 text-white">{currentProfile.intentions}</span>
                  )}

                  {currentProfile.compatibility_score && (
                    <div className="mt-3 flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-[#CCFF00]" />
                      <span className="text-[#CCFF00] font-bold">{currentProfile.compatibility_score}% Vibe Match</span>
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
          <div className="flex justify-center items-center gap-4 mt-6">
            <button
              onClick={handleUndo}
              className="w-12 h-12 rounded-full bg-white border-2 border-black shadow-[3px_3px_0_#000] hover:translate-y-0.5 hover:shadow-[1px_1px_0_#000] flex items-center justify-center disabled:opacity-30"
              disabled={!lastSwipe}
              data-testid="undo-btn"
              title="Undo last swipe (Premium)"
            >
              <ArrowLeft className="w-5 h-5 text-[#FFD400]" />
            </button>
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
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Who Likes You</h2>
          <button
            onClick={() => navigate("/viewers")}
            className="text-xs font-bold text-[#FF2E63] hover:underline inline-flex items-center gap-1"
            data-testid="who-viewed-link"
          >
            <Eye className="w-3 h-3" /> Who viewed me →
          </button>
        </div>

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
  const [peerTyping, setPeerTyping] = useState(false);
  const [peerOnline, setPeerOnline] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recap, setRecap] = useState(null);
  const [showRecap, setShowRecap] = useState(false);
  const [recapLoading, setRecapLoading] = useState(false);
  const wsRef = React.useRef(null);
  const mediaRecorderRef = React.useRef(null);
  const recordChunksRef = React.useRef([]);
  const recordStartRef = React.useRef(0);
  const recordIntervalRef = React.useRef(null);
  const typingTimeoutRef = React.useRef(null);
  const messagesEndRef = React.useRef(null);
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const matchIdFromUrl = location.pathname.split('/').pop();

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

  // WebSocket for real-time messages, typing, presence
  useEffect(() => {
    if (!token || !matchIdFromUrl) return;
    const wsBase = BACKEND_URL.replace(/^http/, "ws");
    const ws = new WebSocket(`${wsBase}/api/ws/chat/${matchIdFromUrl}?token=${encodeURIComponent(token)}`);
    wsRef.current = ws;
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "message") {
          setMessages(prev => prev.find(m => m.id === data.message.id) ? prev : [...prev, data.message]);
        } else if (data.type === "typing" && data.user_id !== user?.id) {
          setPeerTyping(!!data.is_typing);
        } else if (data.type === "presence" && data.user_id !== user?.id) {
          setPeerOnline(!!data.online);
        }
      } catch (e) {}
    };
    return () => { try { ws.close(); } catch(e){} };
  }, [token, matchIdFromUrl, user?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const emitTyping = (isTyping) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "typing", is_typing: isTyping }));
    }
  };

  const handleTyping = (value) => {
    setNewMessage(value);
    emitTyping(true);
    clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(() => emitTyping(false), 1500);
  };

  const sendMessage = async (content) => {
    if (!content.trim()) return;
    emitTyping(false);
    try {
      const res = await apiCall("post", "/messages", {
        match_id: matchIdFromUrl,
        content: content.trim(),
        message_type: "text"
      }, token);
      setMessages(m => m.find(x => x.id === res.message.id) ? m : [...m, res.message]);
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

  const openDateVault = async () => {
    setShowRecap(true);
    setRecapLoading(true);
    try {
      const res = await apiCall("get", `/ai/recap/${matchIdFromUrl}`, null, token);
      setRecap(res);
    } catch (e) {
      toast.error("Could not open Date Vault");
      setShowRecap(false);
    }
    setRecapLoading(false);
  };

  const refreshRecap = async () => {
    setRecapLoading(true);
    try {
      const res = await apiCall("get", `/ai/recap/${matchIdFromUrl}?force_refresh=true`, null, token);
      setRecap(res);
      toast.success("Recap refreshed!");
    } catch (e) {
      toast.error("Failed to refresh");
    }
    setRecapLoading(false);
  };

  const shareRecap = () => {
    if (!recap?.unlocked) return;
    const text = `${recap.headline} — Spark Date Vault with ${recap.other_user_name} | Vibe: ${recap.vibe} | Connection: ${recap.sentiment_score}/100`;
    if (navigator.share) {
      navigator.share({ title: "My Spark Date Vault", text }).catch(() => {});
    } else {
      navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard!");
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mr;
      recordChunksRef.current = [];
      recordStartRef.current = Date.now();
      setRecordingSeconds(0);
      recordIntervalRef.current = setInterval(() => {
        setRecordingSeconds(Math.floor((Date.now() - recordStartRef.current) / 1000));
      }, 500);
      mr.ondataavailable = (e) => e.data.size && recordChunksRef.current.push(e.data);
      mr.onstop = async () => {
        clearInterval(recordIntervalRef.current);
        stream.getTracks().forEach(t => t.stop());
        const duration = Math.max(1, Math.floor((Date.now() - recordStartRef.current) / 1000));
        const blob = new Blob(recordChunksRef.current, { type: "audio/webm" });
        const form = new FormData();
        form.append("audio", blob, "voice.webm");
        try {
          const res = await axios.post(
            `${API}/messages/voice?match_id=${matchIdFromUrl}&duration=${duration}`,
            form,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          setMessages(m => m.find(x => x.id === res.data.message.id) ? m : [...m, res.data.message]);
        } catch {
          toast.error("Failed to send voice note");
        }
        setRecording(false);
      };
      mr.start();
      setRecording(true);
    } catch (e) {
      toast.error("Microphone access denied");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
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
            <p className="text-xs text-gray-500 flex items-center gap-1" data-testid="presence-indicator">
              <span className={`w-2 h-2 rounded-full ${peerOnline ? 'bg-[#00CC66]' : 'bg-gray-300'}`} />
              {peerOnline ? 'Online now' : 'Offline'}
            </p>
          </div>
          <button 
            onClick={openDateVault}
            className="p-2 hover:bg-gray-100 rounded-full"
            data-testid="date-vault-btn"
            title="Open Date Vault"
          >
            <Sparkles className="w-5 h-5 text-[#FF2E63]" />
          </button>
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
            data-testid={`message-row`}
          >
            <div 
              className={`max-w-[80%] p-3 rounded-2xl ${
                msg.sender_id === user?.id 
                  ? 'bg-[#FF2E63] text-white rounded-br-none' 
                  : 'bg-white border-2 border-black rounded-bl-none'
              }`}
            >
              {msg.message_type === "voice" ? (
                <div className="flex items-center gap-2">
                  <audio controls src={msg.content} className="max-w-[200px]" data-testid="voice-audio" />
                  {msg.duration ? <span className="text-xs opacity-70">{msg.duration}s</span> : null}
                </div>
              ) : (
                <p>{msg.content}</p>
              )}
              <p className={`text-xs mt-1 ${msg.sender_id === user?.id ? 'text-white/70' : 'text-gray-400'}`}>
                {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          </div>
        ))}
        
        {peerTyping && (
          <div className="flex justify-start" data-testid="typing-indicator">
            <div className="bg-white border-2 border-black rounded-2xl rounded-bl-none px-4 py-3">
              <span className="inline-flex gap-1">
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
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
                className="flex-shrink-0 px-4 py-2 bg-[#CCFF00] border-2 border-black rounded-full text-sm font-medium hover:bg-[#b8e600] transition-colors max-w-[280px] truncate"
                data-testid={`icebreaker-${i}`}
              >
                {ice}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="sticky bottom-0 bg-white border-t-2 border-black p-4">
        {recording ? (
          <div className="flex items-center gap-3" data-testid="recording-bar">
            <div className="flex-1 flex items-center gap-2 px-4 py-3 bg-red-50 border-2 border-[#FF2E63] rounded-full">
              <span className="w-3 h-3 bg-[#FF2E63] rounded-full animate-pulse" />
              <span className="font-bold text-[#FF2E63]">Recording {recordingSeconds}s</span>
            </div>
            <button
              onClick={stopRecording}
              className="btn-primary !px-4 !py-3"
              data-testid="stop-record-btn"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={startRecording}
              className="p-3 hover:bg-gray-100 rounded-full"
              data-testid="voice-note-btn"
              title="Record voice note"
            >
              <Mic className="w-5 h-5" />
            </button>
            <input
              type="text"
              value={newMessage}
              onChange={(e) => handleTyping(e.target.value)}
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
        )}
        <CopyrightFooter className="!py-1 !text-[10px]" />
      </div>
      {/* Date Vault Modal */}
      {showRecap && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[60] p-4" data-testid="recap-modal">
          <div className="card-brutal max-w-md w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-6 h-6 text-[#FF2E63]" />
                  <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Date Vault</h2>
                </div>
                <button onClick={() => setShowRecap(false)} className="p-1 hover:bg-gray-100 rounded-full" data-testid="close-recap">
                  <X className="w-5 h-5" />
                </button>
              </div>

              {recapLoading ? (
                <div className="py-12 text-center">
                  <Heart className="w-10 h-10 text-[#FF2E63] mx-auto animate-bounce" />
                  <p className="mt-4 text-sm font-bold">Reading your story...</p>
                </div>
              ) : !recap?.unlocked ? (
                <div className="py-8 text-center" data-testid="recap-locked">
                  <div className="w-20 h-20 mx-auto mb-4 bg-gray-100 border-2 border-black rounded-full flex items-center justify-center">
                    <Lock className="w-8 h-8 text-gray-400" />
                  </div>
                  <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Syne' }}>Not Quite Yet</h3>
                  <p className="text-gray-600 mb-4">{recap?.message}</p>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-[#FF2E63] transition-all"
                      style={{ width: `${Math.min(100, (recap?.current_count / 10) * 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-2">{recap?.current_count}/10 messages</p>
                </div>
              ) : (
                <div className="space-y-5" data-testid="recap-unlocked">
                  {/* Vibe Badge */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="badge-accent uppercase tracking-wide">{recap.vibe}</span>
                    <span className="badge-outline">{recap.sentiment_score}/100 connection</span>
                  </div>

                  {/* Headline */}
                  <h3 className="text-2xl font-bold leading-tight" style={{ fontFamily: 'Syne' }}>
                    {recap.headline}
                  </h3>

                  {/* Common Interests */}
                  {recap.common_interests?.length > 0 && (
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Common Ground</p>
                      <div className="flex flex-wrap gap-2">
                        {recap.common_interests.map((i, idx) => (
                          <span key={idx} className="badge-outline">{i}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Memorable Moments */}
                  {recap.memorable_moments?.length > 0 && (
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Memorable Moments</p>
                      <ul className="space-y-2">
                        {recap.memorable_moments.map((m, idx) => (
                          <li key={idx} className="text-sm bg-[#FFF4E6] border-2 border-black rounded-lg p-3">
                            &ldquo;{m}&rdquo;
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Compatibility Signals */}
                  {recap.compatibility_signals?.length > 0 && (
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Why This Could Work</p>
                      <ul className="space-y-1">
                        {recap.compatibility_signals.map((s, idx) => (
                          <li key={idx} className="text-sm flex items-start gap-2">
                            <Check className="w-4 h-4 text-[#00CC66] flex-shrink-0 mt-0.5" />
                            <span>{s}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Next Step */}
                  {recap.next_step_suggestion && (
                    <div className="bg-[#CCFF00] border-2 border-black rounded-lg p-4">
                      <p className="text-xs font-bold uppercase tracking-wider mb-1">Try This Next</p>
                      <p className="font-bold">{recap.next_step_suggestion}</p>
                    </div>
                  )}

                  {/* Growth Area */}
                  {recap.growth_area && (
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">Go Deeper</p>
                      <p className="text-sm text-gray-700">{recap.growth_area}</p>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-2">
                    <button onClick={shareRecap} className="btn-primary flex-1" data-testid="share-recap-btn">
                      Share
                    </button>
                    <button onClick={refreshRecap} className="btn-secondary" data-testid="refresh-recap-btn">
                      Refresh
                    </button>
                  </div>
                  <p className="text-[10px] text-gray-400 text-center">Generated from {recap.message_count_at_generation} messages • AI by Spark</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
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
    "Unlimited likes/swipes per day",
    "See exactly who liked you (unblurred)",
    "AI Date Planner",
    "Vibe Check detailed compatibility report",
    "Profile Boost — top of stack 30 min/week",
    "Global Passport — match in any city",
    "Read receipts on messages",
    "Voice messages in chat",
    "Undo last swipe",
    "Advanced filters (height, education, language)",
    "See who viewed your profile"
  ];

  const vipFeatures = [
    "Everything in Premium",
    "3 Boosts per week",
    "Priority support",
    "VIP badge on your profile"
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
            onClick={() => navigate("/security")}
            className="w-full card-feature flex items-center justify-between"
            data-testid="settings-security-link"
          >
            <div className="flex items-center gap-3">
              <Lock className="w-5 h-5 text-[#FF2E63]" />
              <div>
                <h3 className="font-bold">Privacy &amp; Security</h3>
                <p className="text-sm text-gray-600">2FA, private mode, download data, delete account</p>
              </div>
            </div>
            <ChevronRight className="w-5 h-5" />
          </button>

          {["deepthimarthi82@gmail.com","vikaskesiraju@gmail.com"].includes(user?.email) && (
            <button
              onClick={() => navigate("/admin/security")}
              className="w-full card-feature flex items-center justify-between bg-[#FFF4E6]"
              data-testid="settings-admin-link"
            >
              <div className="flex items-center gap-3">
                <Shield className="w-5 h-5 text-[#FF0000]" />
                <div>
                  <h3 className="font-bold">Admin: Security Logs</h3>
                  <p className="text-sm text-gray-600">Flagged accounts, suspensions</p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5" />
            </button>
          )}

          <button 
            onClick={() => navigate("/safety")}
            className="w-full card-feature flex items-center justify-between"
            data-testid="settings-safety-link"
          >
            <div className="flex items-center gap-3">
              <Shield className="w-5 h-5 text-[#00CC66]" />
              <div>
                <h3 className="font-bold">Safety Center</h3>
                <p className="text-sm text-gray-600">Panic button, emergency contact, blocked users</p>
              </div>
            </div>
            <ChevronRight className="w-5 h-5" />
          </button>

          <button 
            onClick={() => navigate("/help")}
            className="w-full card-feature flex items-center justify-between"
            data-testid="settings-help-link"
          >
            <div className="flex items-center gap-3">
              <MessageCircle className="w-5 h-5 text-[#FF2E63]" />
              <div>
                <h3 className="font-bold">Help &amp; Support</h3>
                <p className="text-sm text-gray-600">FAQ, contact us, report a bug</p>
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

// ==================== SAFETY CENTER ====================
const SafetyPage = () => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [blocked, setBlocked] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        const [s, b] = await Promise.all([
          apiCall("get", "/safety/me", null, token),
          apiCall("get", "/safety/blocked", null, token),
        ]);
        setData(s);
        setBlocked(b.blocked || []);
      } catch (e) { toast.error("Failed to load safety center"); }
      setLoading(false);
    })();
  }, [token]);

  const save = async () => {
    setSaving(true);
    try {
      await apiCall("put", "/safety/settings", {
        emergency_contact_name: data.emergency_contact_name || null,
        emergency_contact_phone: data.emergency_contact_phone || null,
        emergency_contact_email: data.emergency_contact_email || null,
        distance_unit: data.distance_unit || "mi",
        language_filter_enabled: !!data.language_filter_enabled,
      }, token);
      toast.success("Safety settings saved");
    } catch (e) { toast.error("Failed to save"); }
    setSaving(false);
  };

  const triggerPanic = async () => {
    try {
      const res = await apiCall("post", "/safety/panic", null, token);
      if (!res.contact || !Object.values(res.contact).some(Boolean)) {
        toast.error(res.warning || "Add an emergency contact first");
        return;
      }
      const c = res.contact;
      const msg = `Spark Panic Alert: I need help. Please check on me.`;
      if (c.phone) window.location.href = `sms:${c.phone}?body=${encodeURIComponent(msg)}`;
      else if (c.email) window.location.href = `mailto:${c.email}?subject=Spark Panic Alert&body=${encodeURIComponent(msg)}`;
      toast.success(`Alert prepared for ${c.name || c.phone || c.email}`);
    } catch { toast.error("Couldn't trigger panic alert"); }
  };

  const unblock = async (id) => {
    try {
      await apiCall("post", `/safety/unblock/${id}`, null, token);
      setBlocked(blocked.filter(b => b.id !== id));
      toast.success("Unblocked");
    } catch { toast.error("Failed to unblock"); }
  };

  if (loading) return <AppLayout><div className="text-center py-10">Loading...</div></AppLayout>;

  return (
    <AppLayout>
      <div data-testid="safety-page" className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold mb-1" style={{ fontFamily: 'Syne' }}>Safety Center</h2>
          <p className="text-gray-600 text-sm">Tools to keep you safe on Spark.</p>
        </div>

        {/* Panic Button */}
        <div className="card-brutal p-5 bg-[#FFE5E5]">
          <h3 className="text-lg font-bold mb-1" style={{ fontFamily: 'Syne' }}>Panic Button</h3>
          <p className="text-sm text-gray-700 mb-3">Instantly text your emergency contact with a help message.</p>
          <button
            onClick={triggerPanic}
            className="w-full py-4 bg-[#FF0000] text-white font-extrabold text-lg border-2 border-black rounded-lg shadow-[4px_4px_0_#000] hover:translate-y-0.5 hover:shadow-[2px_2px_0_#000] transition-all"
            data-testid="panic-btn"
          >
            🚨 PANIC — ALERT MY CONTACT
          </button>
        </div>

        {/* Emergency Contact */}
        <div className="card-brutal p-5 space-y-3">
          <h3 className="text-lg font-bold" style={{ fontFamily: 'Syne' }}>Emergency Contact</h3>
          <input className="input-brutal" placeholder="Contact name" data-testid="ec-name"
            value={data.emergency_contact_name || ""} onChange={e => setData({...data, emergency_contact_name: e.target.value})} />
          <input className="input-brutal" placeholder="Phone (with country code, e.g. +1...)" data-testid="ec-phone"
            value={data.emergency_contact_phone || ""} onChange={e => setData({...data, emergency_contact_phone: e.target.value})} />
          <input className="input-brutal" placeholder="Email (optional)" data-testid="ec-email"
            value={data.emergency_contact_email || ""} onChange={e => setData({...data, emergency_contact_email: e.target.value})} />
        </div>

        {/* Preferences */}
        <div className="card-brutal p-5 space-y-3">
          <h3 className="text-lg font-bold" style={{ fontFamily: 'Syne' }}>Preferences</h3>
          <div>
            <label className="block text-sm font-bold mb-2">Distance unit</label>
            <div className="grid grid-cols-2 gap-2">
              {["mi", "km"].map(u => (
                <button key={u} onClick={() => setData({...data, distance_unit: u})}
                  className={`p-3 border-2 border-black rounded-lg font-bold ${data.distance_unit === u ? 'bg-[#FF2E63] text-white' : 'bg-white'}`}
                  data-testid={`unit-${u}`}>
                  {u === "mi" ? "Miles" : "Kilometers"}
                </button>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-3 p-3 border-2 border-black rounded-lg cursor-pointer">
            <input type="checkbox" className="w-5 h-5 accent-[#FF2E63]" checked={!!data.language_filter_enabled}
              onChange={e => setData({...data, language_filter_enabled: e.target.checked})} data-testid="lang-filter" />
            <span className="text-sm font-bold">Only show matches who share a language with me</span>
          </label>
        </div>

        <button onClick={save} disabled={saving} className="btn-primary w-full" data-testid="save-safety-btn">
          {saving ? "Saving..." : "Save Safety Settings"}
        </button>

        {/* Blocked Users */}
        <div className="card-brutal p-5">
          <h3 className="text-lg font-bold mb-3" style={{ fontFamily: 'Syne' }}>Blocked Users ({blocked.length})</h3>
          {blocked.length === 0 ? (
            <p className="text-sm text-gray-500">You haven't blocked anyone.</p>
          ) : (
            <div className="space-y-2">
              {blocked.map(b => (
                <div key={b.id} className="flex items-center justify-between p-2 border-2 border-black rounded-lg" data-testid={`blocked-${b.id}`}>
                  <div className="flex items-center gap-2">
                    <img src={b.photos?.[0] || "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=60"} alt="" className="w-10 h-10 rounded-full object-cover border-2 border-black" />
                    <span className="font-bold text-sm">{b.name}</span>
                  </div>
                  <button onClick={() => unblock(b.id)} className="text-xs font-bold text-[#FF2E63] hover:underline">Unblock</button>
                </div>
              ))}
            </div>
          )}
        </div>

        <button onClick={() => navigate("/help")} className="btn-secondary w-full" data-testid="report-link">
          Report Harassment or Abuse →
        </button>
      </div>
    </AppLayout>
  );
};

// ==================== SUPPORT / HELP ====================
const HelpPage = () => {
  const navigate = useNavigate();
  return (
    <AppLayout>
      <div data-testid="help-page" className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold mb-1" style={{ fontFamily: 'Syne' }}>Help &amp; Support</h2>
          <p className="text-gray-600 text-sm">We're here for you.</p>
        </div>
        {[
          { path: "/faq", title: "FAQ", desc: "Quick answers to common questions", icon: AlertCircle },
          { path: "/support/contact", title: "Contact Support", desc: "Talk to a real person", icon: MessageCircle },
          { path: "/support/bug", title: "Report a Bug", desc: "Spotted something broken?", icon: AlertCircle, testid: "bug-link" },
          { path: "/support/contact?type=Safety+Concern&urgent=1", title: "Report Harassment", desc: "Urgent safety issue", icon: Shield },
          { path: "/safety", title: "Safety Center", desc: "Panic button, blocked users, emergency contact", icon: Shield },
        ].map((it) => (
          <button key={it.path} onClick={() => navigate(it.path)} className="card-feature w-full flex items-center justify-between text-left" data-testid={it.testid || `help-${it.title.toLowerCase().replace(/\s+/g, '-')}`}>
            <div className="flex items-center gap-3">
              <it.icon className="w-5 h-5 text-[#FF2E63]" />
              <div>
                <h3 className="font-bold">{it.title}</h3>
                <p className="text-xs text-gray-600">{it.desc}</p>
              </div>
            </div>
            <ChevronRight className="w-5 h-5" />
          </button>
        ))}
        <p className="text-xs text-center text-gray-500 mt-6">Or email <a href="mailto:support@sparkmatch.dating" className="text-[#FF2E63] font-bold">support@sparkmatch.dating</a></p>
      </div>
    </AppLayout>
  );
};

const FaqPage = () => {
  const [faqs, setFaqs] = useState([]);
  const [open, setOpen] = useState(null);
  useEffect(() => {
    apiCall("get", "/support/faq").then(r => setFaqs(r.faqs || []));
  }, []);
  return (
    <AppLayout>
      <div data-testid="faq-page" className="space-y-3">
        <h2 className="text-2xl font-bold mb-4" style={{ fontFamily: 'Syne' }}>FAQ</h2>
        {faqs.map((f, i) => (
          <div key={i} className="card-brutal p-4" data-testid={`faq-${i}`}>
            <button onClick={() => setOpen(open === i ? null : i)} className="w-full flex items-start justify-between gap-3 text-left">
              <span className="font-bold">{f.q}</span>
              <ChevronRight className={`w-5 h-5 flex-shrink-0 transition-transform ${open === i ? 'rotate-90' : ''}`} />
            </button>
            {open === i && <p className="mt-3 text-sm text-gray-700 leading-relaxed">{f.a}</p>}
          </div>
        ))}
      </div>
    </AppLayout>
  );
};

const ContactSupportPage = () => {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const presetType = searchParams.get("type");
  const presetUrgent = searchParams.get("urgent") === "1";
  const [form, setForm] = useState({
    name: user?.name || "",
    email: user?.email || "",
    issue_type: presetType || "Bug Report",
    message: "",
    urgent: presetUrgent,
  });
  const [submitting, setSubmitting] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await apiCall("post", "/support/contact", form, token);
      toast.success(res.message);
      navigate("/help");
    } catch { toast.error("Failed to submit"); }
    setSubmitting(false);
  };
  const types = ["Bug Report", "Account Issue", "Safety Concern", "Billing", "Other"];
  return (
    <AppLayout>
      <form onSubmit={submit} data-testid="contact-page" className="space-y-4">
        <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Contact Support</h2>
        <p className="text-sm text-gray-600">We typically reply within 24 hours.</p>
        <input className="input-brutal" placeholder="Your name" required data-testid="contact-name"
          value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
        <input className="input-brutal" type="email" placeholder="Email" required data-testid="contact-email"
          value={form.email} onChange={e => setForm({...form, email: e.target.value})} />
        <select className="input-brutal" data-testid="contact-type"
          value={form.issue_type} onChange={e => setForm({...form, issue_type: e.target.value})}>
          {types.map(t => <option key={t}>{t}</option>)}
        </select>
        <textarea className="input-brutal min-h-[140px]" placeholder="Describe your issue..." required data-testid="contact-message"
          value={form.message} onChange={e => setForm({...form, message: e.target.value})} />
        <label className="flex items-center gap-3 p-3 border-2 border-black rounded-lg cursor-pointer bg-[#FFE5E5]">
          <input type="checkbox" className="w-5 h-5 accent-[#FF2E63]" checked={form.urgent}
            onChange={e => setForm({...form, urgent: e.target.checked})} data-testid="contact-urgent" />
          <span className="text-sm font-bold">Mark as urgent (safety concerns only)</span>
        </label>
        <button type="submit" disabled={submitting} className="btn-primary w-full" data-testid="contact-submit">
          {submitting ? "Sending..." : "Send"}
        </button>
        <p className="text-xs text-center text-gray-500">Sends to support@sparkmatch.dating</p>
      </form>
    </AppLayout>
  );
};

const BugReportPage = () => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [desc, setDesc] = useState("");
  const [screenshot, setScreenshot] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) { toast.error("Max 5MB"); return; }
    const reader = new FileReader();
    reader.onload = () => setScreenshot(reader.result);
    reader.readAsDataURL(f);
  };
  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await apiCall("post", "/support/bug-report", {
        description: desc,
        screenshot_data_url: screenshot,
        page_url: window.location.href,
        browser: navigator.userAgent,
      }, token);
      toast.success(res.message);
      navigate("/help");
    } catch { toast.error("Failed to submit"); }
    setSubmitting(false);
  };
  return (
    <AppLayout>
      <form onSubmit={submit} data-testid="bug-page" className="space-y-4">
        <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Report a Bug</h2>
        <textarea className="input-brutal min-h-[140px]" placeholder="What broke? Steps to reproduce..." required data-testid="bug-desc"
          value={desc} onChange={e => setDesc(e.target.value)} />
        <div>
          <label className="block text-sm font-bold mb-2">Screenshot (optional)</label>
          <input type="file" accept="image/*" onChange={onFile} className="text-sm" data-testid="bug-screenshot" />
          {screenshot && <img src={screenshot} alt="" className="mt-2 max-h-40 border-2 border-black rounded" />}
        </div>
        <button type="submit" disabled={submitting} className="btn-primary w-full" data-testid="bug-submit">
          {submitting ? "Submitting..." : "Submit Bug"}
        </button>
      </form>
    </AppLayout>
  );
};

// ==================== PRIVACY & SECURITY ====================
const SecurityPage = () => {
  const { token, user, logout } = useAuth();
  const navigate = useNavigate();
  const [twoFAEnabled, setTwoFAEnabled] = useState(!!user?.two_factor_enabled);
  const [privateMode, setPrivateMode] = useState(!!user?.private_mode);
  const [downloading, setDownloading] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [pendingDelete, setPendingDelete] = useState(user?.pending_deletion_at);

  const toggle2FA = async () => {
    try {
      const res = await apiCall("post", "/auth/2fa/toggle", { enabled: !twoFAEnabled }, token);
      setTwoFAEnabled(res.two_factor_enabled);
      toast.success(res.two_factor_enabled ? "2FA enabled" : "2FA disabled");
    } catch { toast.error("Failed"); }
  };

  const togglePrivate = async () => {
    try {
      const res = await apiCall("put", "/me/private-mode", { enabled: !privateMode }, token);
      setPrivateMode(res.private_mode);
      toast.success(res.private_mode ? "Private mode on 👻" : "Private mode off");
    } catch (e) {
      if (e.response?.status !== 402) toast.error("Failed");
    }
  };

  const downloadData = async () => {
    setDownloading(true);
    try {
      const res = await axios.get(`${API}/account/export`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: "blob"
      });
      const url = URL.createObjectURL(new Blob([res.data], { type: "application/zip" }));
      const a = document.createElement("a");
      a.href = url; a.download = "spark-my-data.zip"; a.click();
      URL.revokeObjectURL(url);
      toast.success("Your data has been downloaded");
    } catch { toast.error("Download failed"); }
    setDownloading(false);
  };

  const requestDeletion = async () => {
    try {
      const res = await apiCall("post", "/account/delete/request", null, token);
      setPendingDelete(res.pending_deletion_at);
      toast.success(res.message);
    } catch { toast.error("Failed to schedule deletion"); }
  };

  const cancelDeletion = async () => {
    try {
      await apiCall("post", "/account/delete/cancel", null, token);
      setPendingDelete(null);
      toast.success("Deletion cancelled");
    } catch { toast.error("Failed"); }
  };

  const confirmImmediate = async () => {
    if (deleteConfirm !== "DELETE FOREVER") { toast.error("Type DELETE FOREVER to confirm"); return; }
    try {
      await apiCall("post", "/account/delete/confirm", { confirm: deleteConfirm }, token);
      toast.success("Account permanently deleted");
      logout();
      navigate("/");
    } catch { toast.error("Failed to delete"); }
  };

  return (
    <AppLayout>
      <div data-testid="security-page" className="space-y-5">
        <div>
          <h2 className="text-2xl font-bold mb-1" style={{ fontFamily: 'Syne' }}>Privacy &amp; Security</h2>
          <p className="text-gray-600 text-sm">Control your data, identity, and visibility.</p>
        </div>

        {/* 2FA */}
        <div className="card-brutal p-5 flex items-center justify-between">
          <div className="flex-1">
            <h3 className="font-bold flex items-center gap-2"><Shield className="w-4 h-4 text-[#00CC66]"/>Two-Factor Auth</h3>
            <p className="text-sm text-gray-600">Email a 6-digit code on every login</p>
          </div>
          <button onClick={toggle2FA} className={`w-14 h-8 rounded-full border-2 border-black ${twoFAEnabled ? 'bg-[#CCFF00]' : 'bg-gray-200'} relative`} data-testid="2fa-toggle">
            <span className={`absolute top-0.5 ${twoFAEnabled ? 'right-0.5' : 'left-0.5'} w-6 h-6 bg-white border-2 border-black rounded-full transition-all`}></span>
          </button>
        </div>

        {/* Private Mode */}
        <div className="card-brutal p-5 flex items-center justify-between">
          <div className="flex-1">
            <h3 className="font-bold flex items-center gap-2">👻 Private Mode <span className="text-xs text-[#FF2E63] font-bold">PREMIUM</span></h3>
            <p className="text-sm text-gray-600">Browse without showing up in "Who Viewed Me"</p>
          </div>
          <button onClick={togglePrivate} className={`w-14 h-8 rounded-full border-2 border-black ${privateMode ? 'bg-[#CCFF00]' : 'bg-gray-200'} relative`} data-testid="private-toggle">
            <span className={`absolute top-0.5 ${privateMode ? 'right-0.5' : 'left-0.5'} w-6 h-6 bg-white border-2 border-black rounded-full transition-all`}></span>
          </button>
        </div>

        {/* Data Download */}
        <div className="card-brutal p-5 space-y-3">
          <h3 className="font-bold">Download My Data</h3>
          <p className="text-sm text-gray-600">CCPA-compliant export of everything we know about you, as a ZIP file.</p>
          <button onClick={downloadData} disabled={downloading} className="btn-secondary w-full" data-testid="download-data-btn">
            {downloading ? "Preparing..." : "Download ZIP"}
          </button>
        </div>

        {/* Account Deletion */}
        <div className="card-brutal p-5 space-y-3 bg-[#FFE5E5]">
          <h3 className="font-bold text-[#FF0000]">Delete My Account</h3>
          {pendingDelete ? (
            <>
              <p className="text-sm">Deletion scheduled for <b>{pendingDelete.slice(0,10)}</b>. Just log in any time to cancel.</p>
              <button onClick={cancelDeletion} className="btn-secondary w-full" data-testid="cancel-delete-btn">Cancel Deletion</button>
            </>
          ) : (
            <>
              <p className="text-sm">Permanently delete your account, photos, messages, matches and profile within 30 days. Complies with California CCPA law.</p>
              <button onClick={() => setShowDelete(true)} className="w-full p-3 bg-[#FF0000] text-white border-2 border-black font-bold rounded-lg shadow-[3px_3px_0_#000]" data-testid="open-delete-btn">
                Delete My Account
              </button>
            </>
          )}
        </div>

        {/* Security info */}
        <div className="text-center text-xs text-gray-500 py-3 border-t-2 border-gray-100">
          🔒 AES-256 encryption at rest · bcrypt (12 rounds) password hashing · 30-day session expiry
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDelete && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[60] p-4" data-testid="delete-modal">
          <div className="card-brutal max-w-sm w-full p-6">
            <h3 className="text-xl font-bold text-[#FF0000] mb-2" style={{ fontFamily: 'Syne' }}>This is permanent</h3>
            <p className="text-sm text-gray-700 mb-4">All your data — profile, photos, matches, messages — will be gone forever. You'll get a confirmation email.</p>
            <p className="text-sm font-bold mb-2">Type <code className="bg-gray-100 px-1">DELETE FOREVER</code> to confirm:</p>
            <input
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              className="input-brutal mb-3"
              placeholder="DELETE FOREVER"
              data-testid="delete-confirm-input"
            />
            <div className="flex flex-col gap-2">
              <button
                onClick={confirmImmediate}
                disabled={deleteConfirm !== "DELETE FOREVER"}
                className="w-full p-3 bg-[#FF0000] text-white border-2 border-black font-bold rounded-lg disabled:opacity-30"
                data-testid="confirm-delete-btn"
              >
                Delete Immediately
              </button>
              <button onClick={requestDeletion} className="btn-secondary w-full" data-testid="schedule-delete-btn">
                Schedule for 30 Days
              </button>
              <button onClick={() => setShowDelete(false)} className="text-sm text-gray-500 hover:underline">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

// ==================== ADMIN SECURITY ====================
const AdminSecurityPage = () => {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(true);
  const isAdmin = ["deepthimarthi82@gmail.com", "vikaskesiraju@gmail.com"].includes(user?.email);

  useEffect(() => {
    if (!isAdmin) { navigate("/discover"); return; }
    apiCall("get", "/admin/security/flags", null, token)
      .then(r => setFlags(r.flags || []))
      .catch(() => toast.error("Failed to load flags"))
      .finally(() => setLoading(false));
  }, [isAdmin, navigate, token]);

  const resolve = async (id, action) => {
    try {
      await apiCall("post", `/admin/security/resolve/${id}`, { action }, token);
      setFlags(flags.map(f => f.id === id ? { ...f, status: "resolved", resolved_action: action } : f));
      toast.success("Resolved");
    } catch { toast.error("Failed"); }
  };

  return (
    <AppLayout>
      <div data-testid="admin-security-page" className="space-y-4">
        <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>🚨 Security Flags</h2>
        <p className="text-gray-600 text-sm">{flags.length} flagged account{flags.length !== 1 && 's'}</p>
        {loading ? <div className="text-center py-6">Loading...</div> : flags.length === 0 ? (
          <div className="card-brutal p-8 text-center"><p className="font-bold">No flags. All clean. 🎉</p></div>
        ) : flags.map(f => (
          <div key={f.id} className="card-brutal p-4 space-y-2" data-testid={`flag-${f.id}`}>
            <div className="flex justify-between items-start">
              <div>
                <p className="font-bold">{f.user_name || "Unknown"} <span className="text-xs text-gray-500">{f.user_email}</span></p>
                <p className="text-sm text-[#FF0000] font-bold uppercase">{f.reason}</p>
                <p className="text-xs text-gray-500">{new Date(f.created_at).toLocaleString()} · severity: {f.severity}</p>
              </div>
              <div className="flex flex-col gap-1 text-right">
                {f.suspended && <span className="badge bg-red-100 text-[#FF0000]">SUSPENDED</span>}
                <span className={`badge ${f.status === 'resolved' ? 'bg-gray-100 text-gray-500' : 'bg-yellow-100'}`}>{f.status}</span>
              </div>
            </div>
            {f.status !== "resolved" && (
              <div className="flex gap-2 pt-2">
                <button onClick={() => resolve(f.id, "suspend")} className="flex-1 py-2 text-xs font-bold bg-[#FF0000] text-white border-2 border-black rounded">Suspend</button>
                <button onClick={() => resolve(f.id, "unsuspend")} className="flex-1 py-2 text-xs font-bold bg-[#00CC66] text-white border-2 border-black rounded">Unsuspend</button>
                <button onClick={() => resolve(f.id, "dismiss")} className="flex-1 py-2 text-xs font-bold bg-gray-200 border-2 border-black rounded">Dismiss</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </AppLayout>
  );
};

// ==================== PROFILE VIEWERS ====================
const ViewersPage = () => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [viewers, setViewers] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    apiCall("get", "/me/viewers", null, token)
      .then(r => setViewers(r.viewers || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);
  return (
    <AppLayout>
      <div data-testid="viewers-page" className="space-y-4">
        <h2 className="text-2xl font-bold" style={{ fontFamily: 'Syne' }}>Who Viewed You</h2>
        <p className="text-gray-600 text-sm">People who checked you out in the last 30 days.</p>
        {loading ? (
          <div className="text-center py-8">Loading...</div>
        ) : viewers.length === 0 ? (
          <div className="card-brutal p-8 text-center">
            <Eye className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="font-bold">No views yet</p>
            <p className="text-sm text-gray-500">Boost your profile to get more eyes on you.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {viewers.map(v => (
              <button key={v.id} onClick={() => navigate(`/profile/${v.id}`)}
                className="card-brutal overflow-hidden text-left" data-testid={`viewer-${v.id}`}>
                <img src={v.photos?.[0] || "https://images.unsplash.com/photo-1581977325979-80749e97b0c7?w=300"}
                  className="w-full h-40 object-cover" alt={v.name} />
                <div className="p-3">
                  <p className="font-bold">{v.name}, {v.age}</p>
                  <p className="text-xs text-gray-500">{v.view_count > 1 ? `Viewed ${v.view_count} times` : "Viewed once"}</p>
                </div>
              </button>
            ))}
          </div>
        )}
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
  // Disable right-click and drag globally on photos to discourage saving
  useEffect(() => {
    const preventOnImg = (e) => { if (e.target?.tagName === "IMG") e.preventDefault(); };
    document.addEventListener("contextmenu", preventOnImg);
    document.addEventListener("dragstart", preventOnImg);
    return () => {
      document.removeEventListener("contextmenu", preventOnImg);
      document.removeEventListener("dragstart", preventOnImg);
    };
  }, []);
  return (
    <AuthProvider>
      <div className="App">
        <Toaster position="top-center" richColors />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/terms" element={<TermsPage />} />
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
            <Route path="/viewers" element={<ProtectedRoute><ViewersPage /></ProtectedRoute>}/>
            <Route path="/security" element={<ProtectedRoute><SecurityPage /></ProtectedRoute>}/>
            <Route path="/admin/security" element={<ProtectedRoute><AdminSecurityPage /></ProtectedRoute>}/>
            <Route path="/safety" element={<ProtectedRoute><SafetyPage /></ProtectedRoute>} />
            <Route path="/help" element={<ProtectedRoute><HelpPage /></ProtectedRoute>} />
            <Route path="/faq" element={<ProtectedRoute><FaqPage /></ProtectedRoute>} />
            <Route path="/support/contact" element={<ProtectedRoute><ContactSupportPage /></ProtectedRoute>} />
            <Route path="/support/bug" element={<ProtectedRoute><BugReportPage /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <HelpBubble />
          <UpgradeModal />
        </BrowserRouter>
      </div>
    </AuthProvider>
  );
}

export default App;
