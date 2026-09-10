/**
 * Countdown component - displays mm:ss countdown timer.
 * AC-2: mm:ss format / red when remainingSeconds===0 / uses useCountdown
 * 
 * @param targetTime - The target end time (Date or number in ms)
 * @param onComplete - Optional callback when countdown reaches zero
 * @param className - Additional CSS classes
 */
import React from 'react';
import { useCountdown } from '@/hooks/useCountdown';

interface CountdownProps {
  targetTime: Date | number;
  onComplete?: () => void;
  className?: string;
}

export const Countdown: React.FC<CountdownProps> = ({
  targetTime,
  onComplete,
  className = '',
}) => {
  const { remainingSeconds } = useCountdown(targetTime, onComplete);

  // Format as mm:ss
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Red styling when remainingSeconds === 0
  const isZero = remainingSeconds === 0;
  const timeClass = isZero
    ? 'text-error font-bold'
    : 'text-text-primary';

  return (
    <span
      className={`font-mono text-lg ${timeClass} ${className}`}
      aria-live="off"
      title={`Time remaining: ${formatTime(remainingSeconds)}`}
    >
      {formatTime(remainingSeconds)}
    </span>
  );
};

export default Countdown;
