/**
 * TableCard component - displays a single table entry.
 * AC-4: OCCUPIED occupied + Release + capacity
 * 
 * @param table - The table data
 * @param onClick - Callback when table is clicked
 * @param onRelease - Callback for Release action
 */
import React from 'react';
import { StatusBadge } from './StatusBadge';
import { Countdown } from './Countdown';
import { Users, Clock } from 'lucide-react';

interface TableData {
  id: number;
  label: string;
  capacity: number;
  status: 'AVAILABLE' | 'OCCUPIED' | 'CLEANING';
  occupiedBy?: {
    queueNumber: string;
    partySize: number;
    targetTime: Date | number;
  };
}

interface TableCardProps {
  table: TableData;
  onClick?: () => void;
  onRelease?: () => void;
}

export const TableCard: React.FC<TableCardProps> = ({
  table,
  onClick,
  onRelease,
}) => {
  const isOccupied = table.status === 'OCCUPIED';
  const isCleaning = table.status === 'CLEANING';

  return (
    <div
      className={`bg-white rounded-xl shadow-sm border border-border-default p-4 ${
        !isOccupied ? 'cursor-pointer hover:bg-gray-50 transition-colors' : ''
      }`}
      onClick={isOccupied ? undefined : onClick}
      role={isOccupied ? 'article' : 'button'}
      tabIndex={isOccupied ? undefined : 0}
      aria-label={`Table ${table.label}, ${table.capacity} pax, ${table.status.toLowerCase()}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (!isOccupied && onClick) onClick();
        }
      }}
    >
      {/* Row 1: Label + status badge */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-lg font-bold text-text-primary">{table.label}</span>
        <StatusBadge status={table.status} size="sm" />
      </div>

      {/* Row 2: Capacity */}
      <div className="flex items-center gap-1 mb-2">
        <Users className="w-4 h-4 text-text-secondary" aria-hidden="true" />
        <span className="text-sm text-text-secondary">{table.capacity} pax</span>
      </div>

      {/* Row 3: Occupied info or status text */}
      {isOccupied && table.occupiedBy ? (
        <div className="mb-3">
          <div className="flex items-center gap-1 mb-1">
            <span className="text-sm font-medium text-called">
              {table.occupiedBy.queueNumber} · {table.occupiedBy.partySize} pax
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Clock className="w-4 h-4 text-called" aria-hidden="true" />
            <Countdown targetTime={table.occupiedBy.targetTime} />
          </div>
        </div>
      ) : (
        <p className="text-sm text-text-secondary mb-3">
          {isCleaning ? 'Currently cleaning' : 'Available'}
        </p>
      )}

      {/* Release button for occupied tables */}
      {isOccupied && onRelease && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRelease();
          }}
          className="w-full px-3 py-2 bg-SEATED text-white rounded-lg text-sm font-medium hover:bg-SEATED/90 transition-colors"
          aria-label={`Release table ${table.label}`}
        >
          Release Table
        </button>
      )}
    </div>
  );
};

export default TableCard;
