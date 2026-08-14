import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import Recorder from "../components/Recorder.jsx";
import { analyzeAudioBlob } from "../lib/audioAnalysis.js";
import { findOrCreatePerson, saveSubmission } from "../lib/storage.js";

export default function SubmitPage() {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [audio, setAudio] = useState(null); // { blob, filename }
  const [status, setStatus] = useState(null); // { type: 'error'|'info', text }
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  function handleAudioReady(blob, filename) {
    setAudio({ blob, filename });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setStatus(null);

    if (!name.trim() || !phone.trim()) {
      setStatus({ type: "error", text: "Name and phone number are both required." });
      return;
    }
    if (!audio) {
      setStatus({ type: "error", text: "Please record or upload an audio clip." });
      return;
    }

    setSubmitting(true);
    try {
      const props = await analyzeAudioBlob(audio.blob);
      const personId = await findOrCreatePerson(name.trim(), phone.trim());
      await saveSubmission({
        name: name.trim(),
        phone: phone.trim(),
        blob: audio.blob,
        filename: audio.filename,
        props,
        personId,
      });
      navigate("/submissions");
    } catch (err) {
      console.error(err);
      setStatus({
        type: "error",
        text: `Something went wrong analyzing or saving that clip: ${err.message || err}`,
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page submit-page">
      <div className="card">
        <h1>
          <span className="heading-icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="1" y="7" width="2" height="6" rx="1" fill="currentColor" />
              <rect x="5" y="3" width="2" height="14" rx="1" fill="currentColor" />
              <rect x="9" y="0" width="2" height="20" rx="1" fill="currentColor" />
              <rect x="13" y="4" width="2" height="12" rx="1" fill="currentColor" />
              <rect x="17" y="8" width="2" height="4" rx="1" fill="currentColor" />
            </svg>
          </span>
          Submit a voice recording
        </h1>

        {status && <div className={`flash ${status.type}`}>{status.text}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="name">Full name</label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
              />
            </div>

            <div className="field">
              <label htmlFor="phone">Phone number</label>
              <input
                id="phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="9876543210"
                required
              />
            </div>
          </div>

          <Recorder onAudioReady={handleAudioReady} />

          <button type="submit" className="submit-btn" disabled={submitting}>
            {submitting ? "Analyzing & submitting…" : (
              <>
                Submit recording
                <span aria-hidden="true">→</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
