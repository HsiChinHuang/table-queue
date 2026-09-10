/**
 * LoadingSkeleton component - displays loading skeleton with variant support.
 * AC-6: variant card row skeleton
 * 
 * @param variant - The skeleton variant: card, list, form, board, row
 * @param count - Number of items to skeleton (for list variant)
 * @param className - Additional CSS classes
 */
import React from 'react';

type SkeletonVariant = 'card' | 'list' | 'form' | 'board' | 'row';

interface LoadingSkeletonProps {
  variant: SkeletonVariant;
  count?: number;
  className?: string;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  variant,
  count = 1,
  className = '',
}): React.ReactElement => {
  // Base skeleton styles
  const skeletonBase = 'bg-gray-200 animate-pulse rounded-lg';

  const renderCard = (): React.ReactElement => (
    <div className={`bg-white rounded-xl shadow-sm border border-border-default p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div className={`${skeletonBase} h-6 w-20`} />
        <div className={`${skeletonBase} h-5 w-16 rounded-full`} />
      </div>
      <div className={`${skeletonBase} h-4 w-32 mb-2`} />
      <div className={`${skeletonBase} h-3 w-24 mb-3`} />
      <div className="flex gap-2">
        <div className={`${skeletonBase} h-8 w-20 rounded-lg`} />
        <div className={`${skeletonBase} h-8 w-20 rounded-lg`} />
      </div>
    </div>
  );

  const renderRow = (): React.ReactElement => (
    <div className={`bg-white rounded-lg shadow-sm border border-border-default p-3 ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`${skeletonBase} h-5 w-16 rounded`} />
          <div className={`${skeletonBase} h-4 w-24 rounded`} />
        </div>
        <div className={`${skeletonBase} h-4 w-20 rounded`} />
      </div>
    </div>
  );

  const renderList = (): React.ReactElement => (
    <div className={`space-y-3 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={`${skeletonBase} h-16 rounded-lg`} />
      ))}
    </div>
  );

  const renderForm = (): React.ReactElement => (
    <div className={`space-y-4 ${className}`}>
      <div>
        <div className={`${skeletonBase} h-4 w-24 mb-2 rounded`} />
        <div className={`${skeletonBase} h-10 w-full rounded-lg`} />
      </div>
      <div>
        <div className={`${skeletonBase} h-4 w-24 mb-2 rounded`} />
        <div className={`${skeletonBase} h-10 w-full rounded-lg`} />
      </div>
      <div>
        <div className={`${skeletonBase} h-4 w-24 mb-2 rounded`} />
        <div className={`${skeletonBase} h-10 w-full rounded-lg`} />
      </div>
      <div className={`${skeletonBase} h-10 w-32 rounded-lg`} />
    </div>
  );

  const renderBoard = (): React.ReactElement => (
    <div className={`grid grid-cols-1 md:grid-cols-2 gap-6 ${className}`}>
      <div className="bg-white rounded-xl shadow-sm border border-border-default p-6">
        <div className={`${skeletonBase} h-6 w-32 mb-4 rounded`} />
        <div className={`${skeletonBase} h-12 w-48 mb-2 rounded`} />
        <div className={`${skeletonBase} h-6 w-24 rounded`} />
      </div>
      <div className="bg-white rounded-xl shadow-sm border border-border-default p-6">
        <div className={`${skeletonBase} h-6 w-24 mb-4 rounded`} />
        <div className={`${skeletonBase} h-48 w-48 mx-auto rounded-lg`} />
      </div>
    </div>
  );

  const renderers: Record<SkeletonVariant, () => React.ReactElement> = {
    card: renderCard,
    row: renderRow,
    list: renderList,
    form: renderForm,
    board: renderBoard,
  };

  return renderers[variant]();
};

export default LoadingSkeleton;
