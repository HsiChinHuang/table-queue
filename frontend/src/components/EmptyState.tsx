/**
 * EmptyState component - displays empty state with icon, title, description, and action.
 * AC-5: icon/title/description/action
 * 
 * @param icon - The icon component to display
 * @param title - The title text
 * @param description - The description text
 * @param action - Optional action button
 */
import React from 'react';

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center py-12 px-4 text-center ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="mb-4 text-text-secondary" aria-hidden="true">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-text-primary mb-2">{title}</h3>
      <p className="text-sm text-text-secondary mb-4 max-w-sm">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
};

export default EmptyState;
