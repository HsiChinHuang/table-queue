/**
 * ConnectionBanner component - shows connection status after 3 consecutive failures.
 * AC-8: failure/3 threshold + retry/disconnected state; also exports useConnection hook here
 * 
 * @param failureCount - Current failure count
 * @param onRetry - Callback to retry connection
 * @param className - Additional CSS classes
 */
import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { Wifi, WifiOff } from 'lucide-react';

interface ConnectionBannerProps {
  failureCount: number;
  onRetry?: () => void;
  className?: string;
}

// Threshold for showing connection banner
const FAILURE_THRESHOLD = 3;

interface ConnectionContextType {
  failureCount: number;
  incrementFailure: () => void;
  resetFailure: () => void;
  isDisconnected: boolean;
}

export const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

/**
 * useConnection hook - manages connection state with failure tracking.
 * Can be used independently or via ConnectionContext.
 * 
 * @param onRetry - Optional callback when connection is restored
 * @returns Connection state object
 */
export function useConnection(onRetry?: () => void): {
  failureCount: number;
  incrementFailure: () => void;
  resetFailure: () => void;
  isDisconnected: boolean;
  isRecovered: boolean;
} {
  const [failureCount, setFailureCount] = useState(0);
  const [isRecovered, setIsRecovered] = useState(false);

  const incrementFailure = useCallback(() => {
    setFailureCount((prev) => prev + 1);
    setIsRecovered(false);
  }, []);

  const resetFailure = useCallback(() => {
    if (failureCount > 0) {
      setIsRecovered(true);
      setTimeout(() => setIsRecovered(false), 3000);
      if (onRetry) onRetry();
    }
    setFailureCount(0);
  }, [failureCount, onRetry]);

  const isDisconnected = failureCount >= FAILURE_THRESHOLD;

  return {
    failureCount,
    incrementFailure,
    resetFailure,
    isDisconnected,
    isRecovered,
  };
}

// Provider component for connection state
interface ConnectionProviderProps {
  children: React.ReactNode;
  onRetry?: () => void;
}

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({ children, onRetry }) => {
  const connection = useConnection(onRetry);

  return (
    <ConnectionContext.Provider value={connection}>
      {children}
    </ConnectionContext.Provider>
  );
};

// Hook to use connection context
export function useConnectionContext(): ConnectionContextType {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnectionContext must be used within ConnectionProvider');
  }
  return context;
}

export const ConnectionBanner: React.FC<ConnectionBannerProps> = ({
  failureCount,
  onRetry,
  className = '',
}) => {
  const isDisconnected = failureCount >= FAILURE_THRESHOLD;
  const [showRecovered, setShowRecovered] = useState(false);

  // Show recovered message for 3 seconds after connection is restored
  useEffect(() => {
    if (failureCount === 0 && showRecovered) {
      const timer = setTimeout(() => setShowRecovered(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [failureCount, showRecovered]);

  // Auto-hide recovered message
  useEffect(() => {
    if (failureCount === 0) {
      setShowRecovered(true);
    }
  }, [failureCount]);

  if (!isDisconnected && !showRecovered) {
    return null;
  }

  return (
    <div
      className={`fixed top-0 left-0 right-0 z-50 ${className}`}
      role="alert"
      aria-live="assertive"
    >
      {isDisconnected ? (
        <div className="bg-NO_SHOW text-white px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <WifiOff className="w-5 h-5" aria-hidden="true" />
            <span className="font-medium">Connection lost. Retrying...</span>
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1 px-3 py-1.5 bg-white/20 rounded-lg hover:bg-white/30 transition-colors"
              aria-label="Retry connection"
            >
              <WifiOff className="w-4 h-4" aria-hidden="true" />
              <span className="text-sm">Retry</span>
            </button>
          )}
        </div>
      ) : (
        <div className="bg-SEATED text-white px-4 py-3 flex items-center justify-center">
          <div className="flex items-center gap-2">
            <Wifi className="w-5 h-5" aria-hidden="true" />
            <span className="font-medium">Updated just now</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConnectionBanner;
