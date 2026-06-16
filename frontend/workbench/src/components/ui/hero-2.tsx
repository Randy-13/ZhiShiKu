import React from "react";

type AuroraHeroProps = {
  children: React.ReactNode;
  className?: string;
};

export const AuroraHero = ({ children, className = "" }: AuroraHeroProps) => {
  return (
    <div className={`aurora-hero ${className}`}>
      <div className="aurora-hero-glow" aria-hidden="true">
        <div className="aurora-blob aurora-blob-1" />
        <div className="aurora-blob aurora-blob-2" />
        <div className="aurora-blob aurora-blob-3" />
      </div>
      <div className="aurora-hero-content">{children}</div>
    </div>
  );
};

export default AuroraHero;
