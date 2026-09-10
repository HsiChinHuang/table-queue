/**
 * WaitlistCard component - displays a single waitlist entry.
 * AC-3: Call Seat No-show Cancel + name + phone + Countdown
 * 
 * @param entry - The waitlist entry data
 * @param onCall - Callback for Call action
 * @param onSeat - Callback for Seat action
 * @param onNoShow - Callback for No-show action
 * @param onCancel - Callback for Cancel action
 * @param onRestore - Callback for Restore action
 * @param onRevert - Callback for Revert action
 * @param onEdit - Callback for Edit action
 */
import React from 'react';
import { StatusBadge } from './StatusBadge';
import { Countdown } from './Countdown';
import { Phone, User, Clock } from 'lucide-react';

interface WaitlistEntry {
  id: number;
  queueNumber: string;
  name: string;
  phone: string;
  partySize: number;
  status: 'WAITING' | 'CALLED' | 'SEATED' | 'NO_SHOW' | 'CANCELLED' | 'DONE';
  targetTime?: Date | number;
  note?: string;
  waitMinutes?: number;
  holdMinutes?: number;
}

interface WaitlistCardProps {
  entry: WaitlistEntry;
  onCall?: () => void;
  onSeat?: () => void;
  onNoShow?: () => void;
  onCancel?: () => void;
  onRestore?: () => void;
  onRevert?: () => void;
  onEdit?: () => void;
}

export const WaitlistCard: React.FC<WaitlistCardProps> = ({
  entry,
  onCall,
  onSeat,
  onNoShow,
  onCancel,
  onRestore,
  onRevert,
  onEdit,
}) => {
  const isCalled = entry.status === 'CALLED';
  const isWaiting = entry.status === 'WAITING';
  const isNoShow = entry.status === 'NO_SHOW';

  return (
    <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
      {/* Row 1: Queue number + StatusBadge */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-text-primary">{entry.queueNumber}</span>
          <StatusBadge status={entry.status} size="sm" />
        </div>
      </div>

      {/* Row 2: Name + party size */}
      <div className="flex items-center gap-2 mb-2">
        <User className="w-4 h-4 text-text-secondary" aria-hidden="true" />
        <span className="text-base font-medium text-text-primary">{entry.name}</span>
        <span className="text-sm text-text-secondary">· {entry.partySize} pax</span>
      </div>

      {/* Row 3: Phone + time info */}
      <div className="flex items-center gap-4 mb-3">
        <div className="flex items-center gap-1">
          <Phone className="w-4 h-4 text-text-secondary" aria-hidden="true" />
          <span className="text-sm text-text-secondary">{entry.phone}</span>
        </div>
        {isCalled && entry.targetTime && (
          <div className="flex items-center gap-1">
            <Clock className="w-4 h-4 text-called" aria-hidden="true" />
            <Countdown targetTime={entry.targetTime} />
          </div>
        )}
        {!isCalled && entry.waitMinutes !== undefined && (
          <span className="text-sm text-text-secondary">
            Waiting {entry.waitMinutes} min
          </span>
        )}
      </div>

      {/* Row 4: Note (if any) */}
      {entry.note && (
        <p className="text-sm text-text-secondary mb-3 italic">{entry.note}</p>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 flex-wrap">
        {isWaiting && onCall && (
          <button
            onClick={onCall}
            className="px-3 py-1.5 bg-called text-white rounded-lg text-sm font-medium hover:bg-called/90 transition-colors"
            aria-label={`Call ${entry.name}`}
          >
            Call
          </button>
        )}
        {(isWaiting || isCalled) && onSeat && (
          <button
            onClick={onSeat}
            className="px-3 py-1.5 bg-SEATED text-white rounded-lg text-sm font-medium hover:bg-SEATED/90 transition-colors"
            aria-label={`Seat ${entry.name}`}
          >
            Seat
          </button>
        )}
        {isCalled && onNoShow && (
          <button
            onClick={onNoShow}
            className="px-3 py-1.5 bg-NO_SHOW text-white rounded-lg text-sm font-medium hover:bg-NO_SHOW/90 transition-colors"
            aria-label={`Mark ${entry.name} as no-show`}
          >
            No-show
          </button>
        )}
        {isNoShow && onRestore && (
          <button
            onClick={onRestore}
            className="px-3 py-1.5 bg-WAITING text-white rounded-lg text-sm font-medium hover:bg-WAITING/90 transition-colors"
            aria-label={`Restore ${entry.name}`}
          >
            Restore
          </button>
        )}
        {isCalled && onRevert && (
          <button
            onClick={onRevert}
            className="px-3 py-1.5 bg-WAITING text-white rounded-lg text-sm font-medium hover:bg-WAITING/90 transition-colors"
            aria-label={`Revert call for ${entry.name}`}
          >
            Revert
          </button>
        )}
        {(isWaiting || isCalled) && onCancel && (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 bg-CANCELLED text-white rounded-lg text-sm font-medium hover:bg-CANCELLED/90 transition-colors"
            aria-label={`Cancel ${entry.name}`}
          >
            Cancel
          </button>
        )}
        {onEdit && (
          <button
            onClick={onEdit}
            className="px-3 py-1.5 border border-border-default rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
            aria-label={`Edit ${entry.name}`}
          >
            Edit
          </button>
        )}
      </div>
    </div>
  );
};

export default WaitlistCard;
