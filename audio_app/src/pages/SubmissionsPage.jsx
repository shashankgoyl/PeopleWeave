import React, { useEffect, useState } from "react";
import { listSubmissions } from "../lib/storage.js";

function NoiseBadge({ level }) {
  if (!level) return <span>—</span>;
  return <span className={`badge ${level}`}>{level.replace("_", " ")}</span>;
}

export default function SubmissionsPage() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    listSubmissions()
      .then(setRows)
      .catch((err) => setError(err.message || String(err)));
  }, []);

  return (
    <div className="page submissions-page">
      <div className="card">
        <h1>📋 All audio submissions</h1>

        {error && <div className="flash error">Couldn't load submissions: {error}</div>}
        {!rows && !error && <p>Loading…</p>}

        {rows && (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Phone</th>
              <th>Audio</th>
              <th>Duration</th>
              <th>Sample rate</th>
              <th>Bitrate</th>
              <th>Loudness</th>
              <th>Noise</th>
              <th>Submitted</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={9}>No submissions yet.</td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.submitted_name}</td>
                <td>{r.submitted_phone}</td>
                <td>
                  {r.playback_url ? (
                    <audio controls src={r.playback_url} className="row-audio" />
                  ) : (
                    <em>unavailable</em>
                  )}
                </td>
                <td>{r.duration_seconds != null ? `${r.duration_seconds.toFixed(1)}s` : "—"}</td>
                <td>{r.sample_rate_hz ? `${(r.sample_rate_hz / 1000).toFixed(1)} kHz` : "—"}</td>
                <td>{r.bitrate_kbps != null ? `${r.bitrate_kbps} kbps` : "—"}</td>
                <td>{r.loudness_db != null ? `${r.loudness_db} dB` : "—"}</td>
                <td>
                  <NoiseBadge level={r.noise_estimate} />
                </td>
                <td>{r.created_at ? new Date(r.created_at).toLocaleString() : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </div>
    </div>
  );
}
