import React, { useRef, useState } from "react";

/**
 * Lets the user either record in-browser (MediaRecorder) or pick a file.
 * Calls onAudioReady(blob, filename) once a usable clip is available.
 */
export default function Recorder({ onAudioReady }) {
  const [recording, setRecording] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
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
    onAudioReady(file, file.name);
  }

  return (
    <div className="recorder">
      <label>Record audio in the browser</label>
      <div className="rec-controls">
        {!recording ? (
          <button type="button" onClick={startRecording}>
            ● Start recording
          </button>
        ) : (
          <button type="button" onClick={stopRecording} className="recording-active">
            ■ Stop
          </button>
        )}
        {recording && <span className="rec-indicator">● REC</span>}
      </div>

      {previewUrl && <audio controls src={previewUrl} className="preview-audio" />}

      <div className="divider">— or —</div>

      <label htmlFor="fileUpload">Upload an audio file instead</label>
      <input ref={fileInputRef} type="file" id="fileUpload" accept="audio/*" onChange={onFileChosen} />
    </div>
  );
}
