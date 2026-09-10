/**
 * StatusBadge component - displays colored status badges.
 * AC-1: All 6 waitlist status names + ui.md s2 colors
 * WAITING #3B82F6, CALLED #EA580C, SEATED #16A34A, NO_SHOW #DC2626, CANCELLED #64748B, DONE
 * Table status: AVAILABLE, OCCUPIED, CLEANING
 * 
 * @param status - The status to display
 * @param size - Badge size variant
 */
import React from 'react';

type WaitlistStatus = 'WAITING' | 'CALLED' | 'SEATED' | 'NO_SHOW' | 'CANCELLED' | 'DONE';
type TableStatus = 'AVAILABLE' | 'OCCUPIED' | 'CLEANING';
type BadgeSize = 'sm' | 'md' | 'lg';

interface StatusBadgeProps {
  status: WaitlistStatus | TableStatus;
  size?: BadgeSize;
  className?: string;
}

const statusConfig: Record<WaitlistStatus | TableStatus, { label: string; colorClass: string }> = {
  WAITING: { label: 'Waiting', colorClass: 'bg-WAITING text-white' },
  CALLED: { label: 'Called', colorClass: 'bg-called text-white' },
  SEATED: { label: 'Seated', colorClass: 'bg-SEATED text-white' },
  NO_SHOW: { label: 'No-show', colorClass: 'bg-NO_SHOW text-white' },
  CANCELLED: { label: 'Cancelled', colorClass: 'bg-CANCELLED text-white' },
  DONE: { label: 'Done', colorClass: 'bg-DONE text-white' },
  AVAILABLE: { label: 'Available', colorClass: 'bg-AVAILABLE text-white' },
  OCCUPIED: { label: 'Occupied', colorClass: 'bg-OCCUPIED text-white' },
  CLEANING: { label: 'Cleaning', colorClass: 'bg-CLEANING text-white' },
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1 text-sm',
  lg: 'px-4 py-1.5 text-base',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
  className = '',
}) => {
  const config = statusConfig[status];
  const sizeClass = sizeClasses[size];

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${config.colorClass} ${sizeClass} ${className}`}
      aria-live="polite"
    >
      {config.label}
    </span>
  );
};

export default StatusBadge;
