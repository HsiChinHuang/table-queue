/**
 * SoundToggle component - toggle sound on/off with Zustand store integration.
 * AC-9: staffStore/soundEnabled integration + aria-label
 * T17 AC-5: ONE lazily-created shared AudioContext for the life of the app
 * (created on the first user interaction that triggers a beep, never at mount),
 * reused by every subsequent beep, .close()d on component teardown; the
 * first-interaction unlock listeners are registered ONCE and never
 * re-registered on later effect runs / toggles.
 * Reads from staffStore.soundEnabled and persists to localStorage.
 *
 * @param className - Additional CSS classes
 */
import React, { useEffect } from 'react';
import { staffStore } from '@/stores/staffStore';
import { Volume2, VolumeX } from 'lucide-react';

type AudioContextCtor = typeof AudioContext;

// T17 AC-5: the shared AudioContext. Lazily created by getAudioContext() on the
// first interaction that beeps; closed exactly once per page by closeSharedAudio().
let sharedAudioCtx: AudioContext | null = null;
// T17 AC-5: the first-interaction unlock listeners are registered at most once
// per page (module flag) - repeated mount/toggle cycles never stack duplicates.
let unlockListenersRegistered = false;

function getAudioContext(): AudioContext {
  if (!sharedAudioCtx) {
    const Ctor: AudioContextCtor =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: AudioContextCtor }).webkitAudioContext;
    sharedAudioCtx = new Ctor();
  }
  return sharedAudioCtx;
}

/** Close the shared AudioContext (idempotent); the next beep recreates it lazily. */
export function closeSharedAudio(): void {
  if (sharedAudioCtx && sharedAudioCtx.state !== 'closed') {
    void sharedAudioCtx.close();
  }
  sharedAudioCtx = null;
}

function playBeep(): void {
  try {
    // Web Audio API beep - 880Hz for 0.3s per ui.md section 13 (shape unchanged).
    const audioCtx = getAudioContext();
    if (audioCtx.state === 'closed') return;
    const oscillator = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioCtx.destination);

    oscillator.frequency.value = 880;
    oscillator.type = 'sine';

    gainNode.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);

    oscillator.start(audioCtx.currentTime);
    oscillator.stop(audioCtx.currentTime + 0.3);
  } catch {
    // Audio not supported or blocked
  }
}

// Single module-level unlock handler: the context is created HERE, on the first
// user interaction (never at mount), and only while sound is enabled.
function handleFirstInteraction(): void {
  if (!staffStore.getState().soundEnabled) return;
  playBeep();
}

export const SoundToggle: React.FC<{ className?: string }> = ({ className = '' }) => {
  const soundEnabled = staffStore((s) => s.soundEnabled);
  const toggleSound = () => staffStore.getState().setSoundEnabled(!soundEnabled);

  // T17 AC-5: register the first-interaction unlock listeners (click/keydown)
  // ONCE per page. The flag makes repeated effect runs (mounts, toggles) no-ops,
  // so after any number of sound on/off toggles a single user interaction still
  // arms the first beep. No removal: the listener lives for the page's lifetime.
  useEffect(() => {
    if (!soundEnabled) return;
    if (!unlockListenersRegistered) {
      unlockListenersRegistered = true;
      window.addEventListener('click', handleFirstInteraction);
      window.addEventListener('keydown', handleFirstInteraction);
    }
  }, [soundEnabled]);

  // T17 AC-5: close the lazily-created shared AudioContext on component
  // teardown, so a logged-out shared front-desk terminal leaves no live audio
  // context behind. Dedicated unmount-only effect (does not run on toggles).
  useEffect(() => {
    return () => {
      closeSharedAudio();
    };
  }, []);

  return (
    <button
      onClick={toggleSound}
      className={`p-2 rounded-lg hover:bg-gray-100 transition-colors ${className}`}
      aria-label={soundEnabled ? 'Disable sound' : 'Enable sound'}
      title={soundEnabled ? 'Sound enabled' : 'Sound disabled'}
    >
      {soundEnabled ? (
        <Volume2 className="w-5 h-5 text-text-primary" aria-hidden="true" />
      ) : (
        <VolumeX className="w-5 h-5 text-text-secondary" aria-hidden="true" />
      )}
    </button>
  );
};

export default SoundToggle;
