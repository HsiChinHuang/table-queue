/**
 * ConfirmDialog component - confirmation dialog with variant support.
 * AC-7: variant danger default onConfirm - shadcn Dialog-based
 * Uses @radix-ui/react-dialog for the dialog implementation.
 * 
 * @param open - Whether the dialog is open
 * @param onClose - Callback when dialog is closed
 * @param title - Dialog title
 * @param description - Dialog description
 * @param variant - 'danger' or 'default' styling
 * @param confirmLabel - Confirm button label
 * @param cancelLabel - Cancel button label
 * @param onConfirm - Callback when confirm is clicked
 * @param onCancel - Callback when cancel is clicked
 */
import React, { useEffect } from 'react';
import * as Dialog from '@radix-ui/react-dialog';

type ConfirmDialogVariant = 'danger' | 'default';

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  variant?: ConfirmDialogVariant;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel?: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  onClose,
  title,
  description,
  variant = 'default',
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}) => {
  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      onClose();
    }
  };

  const handleConfirm = () => {
    onConfirm();
    onClose();
  };

  const handleCancel = () => {
    onCancel?.();
    onClose();
  };

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) {
        handleCancel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  const isDanger = variant === 'danger';

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-xl shadow-lg max-w-sm p-6 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0">
          <Dialog.Title className="text-lg font-semibold text-text-primary mb-2">
            {title}
          </Dialog.Title>
          {description && (
            <Dialog.Description className="text-sm text-text-secondary mb-4">
              {description}
            </Dialog.Description>
          )}
          <div className="flex gap-3 justify-end">
            <button
              onClick={handleCancel}
              className="px-4 py-2 border border-border-default rounded-lg text-sm font-medium text-text-primary hover:bg-gray-50 transition-colors"
              aria-label={cancelLabel}
            >
              {cancelLabel}
            </button>
            <button
              onClick={handleConfirm}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isDanger
                  ? 'bg-NO_SHOW text-white hover:bg-NO_SHOW/90'
                  : 'bg-primary text-white hover:bg-primary/90'
              }`}
              aria-label={confirmLabel}
            >
              {confirmLabel}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};

export default ConfirmDialog;
