/**
 * Switch component - minimal accessible toggle used by the settings pages.
 * ui.md section 5 lists Switch in the component kit; the kit ships Button,
 * Input and Label only, so this primitive is added here (additive, no API change).
 */

import React from 'react';
import { cn } from '@/lib/utils';

export interface SwitchProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'onChange'> {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}

const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(
  ({ className, checked, onCheckedChange, ...props }, ref) => {
    return (
      <input
        ref={ref}
        type="checkbox"
        role="switch"
        aria-checked={checked}
        checked={checked}
        className={cn(
          'h-5 w-9 cursor-pointer appearance-none rounded-full border border-border-default bg-muted',
          'relative transition-colors duration-200 checked:bg-primary',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
          className,
        )}
        onChange={(e) => onCheckedChange(e.target.checked)}
        {...props}
      />
    );
  },
);
Switch.displayName = 'Switch';

export { Switch };
export default Switch;
