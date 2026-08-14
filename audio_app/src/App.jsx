import React from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
import SubmitPage from "./pages/SubmitPage.jsx";
import SubmissionsPage from "./pages/SubmissionsPage.jsx";
import { USE_SUPABASE } from "./lib/supabaseClient.js";

export default function App() {
  const { pathname } = useLocation();

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="brand">
          <span className="brand-icon" aria-hidden="true">🎙️</span>
          PeopleWeave
        </Link>
        <nav>
          <Link to="/" className={pathname === "/" ? "active" : ""}>
            Submit
          </Link>
          <Link to="/submissions" className={pathname === "/submissions" ? "active" : ""}>
            Submissions
          </Link>
        </nav>
        <span className={`backend-badge ${USE_SUPABASE ? "supabase" : "local"}`}>
          {USE_SUPABASE ? "Supabase" : "Local (browser only)"}
        </span>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<SubmitPage />} />
          <Route path="/submissions" element={<SubmissionsPage />} />
        </Routes>
      </main>
      <footer className="app-footer">
        <span className="copyright">© 2024 PeopleWeave. Built for high-fidelity audio capture.</span>
        <div className="footer-links">
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Service</a>
          <a href="#">Help Center</a>
        </div>
      </footer>
    </div>
  );
}
