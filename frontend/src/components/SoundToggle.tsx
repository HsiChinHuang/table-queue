/**
 * SoundToggle component - toggle sound on/off with Zustand store integration.
 * AC-9: staffStore/soundEnabled integration + aria-label
 * Reads from staffStore.soundEnabled and persists to localStorage.
 * 
 * @param className - Additional CSS classes
 */
import React, { useEffect } from 'react';
import { staffStore } from '@/api/staffStore';
import { Volume2, VolumeX } from 'lucide-react';

export const SoundToggle: React.FC<{ className?: string }> = ({ className = '' }) => {
  const { soundEnabled, toggleSound } = staffStore();

  // Play beep sound when enabling
  useEffect(() => {
    if (soundEnabled) {
      // Web Audio API beep - 880Hz for 0.3s per ui.md section 13
      const playBeep = () => {
        try {
          const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
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
      };

      // Play on mount if enabled (for initial state)
      // Note: Audio requires user interaction first per ui.md section 13
      const handleFirstInteraction = () => {
        playBeep();
        window.removeEventListener('click', handleFirstInteraction);
        window.removeEventListener('keydown', handleFirstInteraction);
      };

      window.addEventListener('click', handleFirstInteraction);
      window.addEventListener('keydown', handleFirstInteraction);

      return () => {
        window.removeEventListener('click', handleFirstInteraction);
        window.removeEventListener('keydown', handleFirstInteraction);
      };
    }
  }, [soundEnabled]);

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
