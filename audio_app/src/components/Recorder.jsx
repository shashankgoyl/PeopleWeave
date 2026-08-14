import React, { useRef, useState } from "react";

/**
 * Lets the user either record in-browser (MediaRecorder) or pick a file.
 * Calls onAudioReady(blob, filename) once a usable clip is available.
 */
export default function Recorder({ onAudioReady }) {
  const [recording, setRecording] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [fileName, setFileName] = useState(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const fileInputRef = useRef(null);

  async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunksRef.current = [];
    const recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      setPreviewUrl(URL.createObjectURL(blob));
      setFileName(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      onAudioReady(blob, "recording.webm");
      stream.getTracks().forEach((t) => t.stop());
    };
    recorder.start();
    mediaRecorderRef.current = recorder;
    setRecording(true);
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  function onFileChosen(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPreviewUrl(URL.createObjectURL(file));
    setFileName(file.name);
    onAudioReady(file, file.name);
  }

  return (
    <div className="recorder">
      <div className="rec-panel">
        <div className="field-label">Record audio in the browser</div>
        <div className="rec-controls">
          {!recording ? (
            <button type="button" className="pill-btn" onClick={startRecording}>
              <span className="dot" aria-hidden="true">●</span>
              Start recording
            </button>
          ) : (
            <button type="button" className="pill-btn recording-active" onClick={stopRecording}>
              <span className="dot" aria-hidden="true">■</span>
              Stop
            </button>
          )}
          {recording && <span className="rec-indicator">● REC</span>}
        </div>
      </div>

      <div className="divider">OR</div>

      <label className="upload-panel" htmlFor="fileUpload">
        <div className="field-label">Upload an audio file instead</div>
        <div className="upload-row">
          <span className="upload-icon" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M5 13.5V15a2 2 0 002 2h6a2 2 0 002-2v-1.5M10 3v9m0-9L7 6m3-3l3 3"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          {fileName ? fileName : "Choose File or drag & drop here"}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          id="fileUpload"
          accept="audio/*"
          onChange={onFileChosen}
        />
      </label>

      {previewUrl && <audio controls src={previewUrl} className="preview-audio" />}
    </div>
  );
}
