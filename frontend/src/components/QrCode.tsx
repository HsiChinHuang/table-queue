/**
 * QrCode component - QR code display using qrcode.react library.
 * AC-10: import { QRCodeSVG } from 'qrcode.react' + value + size
 * 
 * @param value - The URL/text to encode in the QR code
 * @param size - Size of the QR code in pixels (default: 200)
 * @param className - Additional CSS classes
 */
import React from 'react';
import { QRCodeSVG } from 'qrcode.react';

interface QrCodeProps {
  value: string;
  size?: number;
  className?: string;
}

export const QrCode: React.FC<QrCodeProps> = ({
  value,
  size = 200,
  className = '',
}) => {
  return (
    <div className={`flex justify-center ${className}`}>
      <QRCodeSVG
        value={value}
        size={size}
        level="M"
        bgColor="#FFFFFF"
        fgColor="#1E293B"
        includeMargin={true}
        aria-label="QR code to join waitlist"
      />
    </div>
  );
};

export default QrCode;
