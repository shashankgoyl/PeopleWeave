/**
 * Task 3 - audio property extraction, done entirely in the browser.
 *
 * The Flask/pydub version of this app shelled out to ffmpeg to decode audio
 * and read its properties. The browser can do the same decode step natively
 * via the Web Audio API (AudioContext.decodeAudioData) - same underlying
 * codecs the browser already uses to play the file - so no backend, no
 * ffmpeg, and no server round-trip are needed at all.
 *
 * Extracted, same as the Python version:
 *   - duration_seconds   -> AudioBuffer.duration
 *   - sample_rate_hz     -> AudioBuffer.sampleRate
 *   - bitrate_kbps       -> derived from actual file size / duration (meaningful
 *                           for compressed formats, not just a container header)
 *   - loudness_db        -> RMS-based dBFS across the whole decoded signal
 *   - noise_estimate     -> bonus, rough heuristic (see below)
 *
 * Noise/quality heuristic (bonus): identical idea to the Python version -
 * slice the decoded signal into 50ms windows, compare the loud windows
 * (90th percentile) to the quiet windows (10th percentile) as a crude SNR
 * proxy. Real speech has pauses between words (an actual noise floor to
 * measure against); a continuous tone does not - see docs/STUCK_LOG.md for
 * the story of why that matters for testing this function.
 */

const WINDOW_MS = 50;

function computeRmsDbfs(samples, start, end) {
  let sumSquares = 0;
  let count = 0;
  for (let i = start; i < end; i++) {
    sumSquares += samples[i] * samples[i];
    count++;
  }
  if (count === 0) return -Infinity;
  const rms = Math.sqrt(sumSquares / count);
  if (rms === 0) return -Infinity;
  return 20 * Math.log10(rms);
}

function windowedDbLevels(audioBuffer) {
  // mix down to mono by averaging channels, so multi-channel files behave the same as the Python version
  const { numberOfChannels, length, sampleRate } = audioBuffer;
  const mono = new Float32Array(length);
  for (let ch = 0; ch < numberOfChannels; ch++) {
    const data = audioBuffer.getChannelData(ch);
    for (let i = 0; i < length; i++) mono[i] += data[i] / numberOfChannels;
  }

  const windowSize = Math.max(1, Math.round((WINDOW_MS / 1000) * sampleRate));
  const levels = [];
  for (let start = 0; start < length; start += windowSize) {
    const end = Math.min(length, start + windowSize);
    const db = computeRmsDbfs(mono, start, end);
    if (Number.isFinite(db)) levels.push(db);
  }
  return { levels, mono };
}

function snrEstimateDb(levels) {
  if (levels.length < 4) return 40; // too short to judge, assume clean
  const sorted = [...levels].sort((a, b) => a - b);
  const n = sorted.length;
  const noiseFloor = sorted[Math.max(0, Math.floor(n * 0.1) - 1)];
  const signalLevel = sorted[Math.min(n - 1, Math.floor(n * 0.9))];
  return signalLevel - noiseFloor;
}

export function classifyNoise(snrDb) {
  if (snrDb >= 30) return "clean";
  if (snrDb >= 15) return "moderate_noise";
  return "noisy";
}

// exported for unit testing (see src/lib/audioAnalysis.test.mjs) - decodeAudioData
// itself needs a real browser, but the dB/SNR math underneath it is pure and testable
export { computeRmsDbfs, snrEstimateDb };

/**
 * @param {Blob} blob - the recorded/uploaded audio
 * @returns {Promise<{duration_seconds:number, sample_rate_hz:number, bitrate_kbps:number|null, loudness_db:number|null, noise_estimate:string, channels:number, file_size_bytes:number}>}
 */
export async function analyzeAudioBlob(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const fileSizeBytes = blob.size;

  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const ctx = new AudioCtx();
  let audioBuffer;
  try {
    // decodeAudioData mutates/detaches some engines' buffers - slice() keeps arrayBuffer reusable if needed
    audioBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
  } finally {
    ctx.close();
  }

  const durationSeconds = Math.round(audioBuffer.duration * 1000) / 1000;
  const sampleRateHz = audioBuffer.sampleRate;

  let bitrateKbps = null;
  if (durationSeconds > 0) {
    bitrateKbps = Math.round(((fileSizeBytes * 8) / durationSeconds / 1000) * 10) / 10;
  }

  const { levels, mono } = windowedDbLevels(audioBuffer);
  const overallDb = computeRmsDbfs(mono, 0, mono.length);
  const loudnessDb = Number.isFinite(overallDb) ? Math.round(overallDb * 10) / 10 : null;

  const snr = snrEstimateDb(levels);
  const noiseEstimate = classifyNoise(snr);

  return {
    duration_seconds: durationSeconds,
    sample_rate_hz: sampleRateHz,
    bitrate_kbps: bitrateKbps,
    loudness_db: loudnessDb,
    noise_estimate: noiseEstimate,
    channels: audioBuffer.numberOfChannels,
    file_size_bytes: fileSizeBytes,
  };
}
