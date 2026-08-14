import React from "react";
import { Routes, Route, Link } from "react-router-dom";
import SubmitPage from "./pages/SubmitPage.jsx";
import SubmissionsPage from "./pages/SubmissionsPage.jsx";
import { USE_SUPABASE } from "./lib/supabaseClient.js";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="brand">
          🎙️ PeopleWeave
        </Link>
        <nav>
          <Link to="/">Submit</Link>
          <Link to="/submissions">Submissions</Link>
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
    </div>
  );
}
