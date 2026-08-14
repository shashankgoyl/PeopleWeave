// Quick sanity test for the pure math in audioAnalysis.js, runnable with plain
// node (no browser needed) - mirrors the exact test done for the old Python/
// pydub version (see docs/STUCK_LOG.md #3): a continuous tone has no dynamic
// range and reads as "noisy" no matter how clean it is, so the real test needs
// bursts of tone separated by actual silence, like speech.
import { computeRmsDbfs, snrEstimateDb, classifyNoise } from "./audioAnalysis.js";

function makeSpeechLike(sampleRate, seconds, bgAmplitude) {
  const n = sampleRate * seconds;
  const samples = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = i / sampleRate;
    const envelope = Math.sin(2 * Math.PI * 1.5 * t) > 0 ? 1 : 0;
    const voice = envelope * 0.3 * Math.sin(2 * Math.PI * 300 * t);
    const bg = bgAmplitude * (Math.random() * 2 - 1);
    samples[i] = voice + bg;
  }
  return samples;
}

function windows(samples, sampleRate, windowMs = 50) {
  const windowSize = Math.round((windowMs / 1000) * sampleRate);
  const levels = [];
  for (let start = 0; start < samples.length; start += windowSize) {
    const end = Math.min(samples.length, start + windowSize);
    const db = computeRmsDbfs(samples, start, end);
    if (Number.isFinite(db)) levels.push(db);
  }
  return levels;
}

const sr = 22050;
const clean = makeSpeechLike(sr, 4, 0.003);
const noisy = makeSpeechLike(sr, 4, 0.08);

const cleanOverall = computeRmsDbfs(clean, 0, clean.length);
const noisyOverall = computeRmsDbfs(noisy, 0, noisy.length);

const cleanSnr = snrEstimateDb(windows(clean, sr));
const noisySnr = snrEstimateDb(windows(noisy, sr));

console.log("clean speech-like: loudness_db=%s snr=%s -> %s",
  cleanOverall.toFixed(1), cleanSnr.toFixed(1), classifyNoise(cleanSnr));
console.log("noisy speech-like: loudness_db=%s snr=%s -> %s",
  noisyOverall.toFixed(1), noisySnr.toFixed(1), classifyNoise(noisySnr));

const cleanOk = classifyNoise(cleanSnr) === "clean";
const noisyOk = classifyNoise(noisySnr) === "noisy";
console.log(cleanOk && noisyOk ? "PASS" : "FAIL");
process.exit(cleanOk && noisyOk ? 0 : 1);
