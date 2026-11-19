interface Props {
  size?: number;
  className?: string;
}

export function Logo({ size = 28, className }: Props) {
  const id = "maes-grad";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="MAES logo"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FF7559" />
          <stop offset="100%" stopColor="#FFB726" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="7" fill={`url(#${id})`} />
      {/* Three horizontal bars — evokes context files / layers */}
      <rect x="7" y="10" width="18" height="2.5" rx="1.25" fill="white" fillOpacity="0.95" />
      <rect x="7" y="15" width="11" height="2.5" rx="1.25" fill="white" fillOpacity="0.95" />
      <rect x="7" y="20" width="14" height="2.5" rx="1.25" fill="white" fillOpacity="0.95" />
    </svg>
  );
}
